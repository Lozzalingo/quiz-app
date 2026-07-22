"""
Background upload worker for media file processing.

Handles the upload queue: receives files, compresses them via FFmpeg,
uploads to DO Spaces, and updates the MediaUpload record status.

Uses an eventlet-compatible background thread so it does not block
the main Flask/SocketIO worker.
"""
import os
import subprocess
import tempfile
import shutil
from collections import deque
from threading import Lock

import eventlet

# Queue and lock for thread-safe access
_upload_queue = deque()
_queue_lock = Lock()
_worker_running = False


def enqueue_upload(upload_id, file_path, app):
    """
    Add an upload job to the processing queue.

    Args:
        upload_id: ID of the MediaUpload record
        file_path: Path to the temporary uploaded file
        app: Flask app instance (for app context)
    """
    global _worker_running

    with _queue_lock:
        _upload_queue.append({
            'upload_id': upload_id,
            'file_path': file_path,
            'app': app,
        })

    # Start worker if not running
    if not _worker_running:
        _worker_running = True
        eventlet.spawn(_process_queue)


def _process_queue():
    """Background worker that processes upload jobs one at a time."""
    global _worker_running

    while True:
        with _queue_lock:
            if not _upload_queue:
                _worker_running = False
                return
            job = _upload_queue.popleft()

        try:
            _process_upload(job)
        except Exception as e:
            print(f'[UploadWorker] Error processing upload {job["upload_id"]}: {e}')
            _mark_failed(job, str(e))

        # Yield to eventlet
        eventlet.sleep(0)


def _process_upload(job):
    """
    Process a single upload job:
    1. Update status to 'processing'
    2. Determine file type and compress
    3. Upload to DO Spaces
    4. Update status to 'complete'
    """
    upload_id = job['upload_id']
    file_path = job['file_path']
    app = job['app']

    with app.app_context():
        from models import db, MediaUpload
        from storage import upload_file_to_spaces, build_storage_key, build_storage_filename

        upload = MediaUpload.query.get(upload_id)
        if not upload:
            print(f'[UploadWorker] Upload {upload_id} not found, skipping')
            return

        # Update status to uploading
        upload.upload_status = 'uploading'
        upload.upload_progress = 10
        db.session.commit()

        try:
            # Determine processing needed
            if upload.file_type == 'video':
                processed_path = _compress_video(file_path, upload)
            elif upload.file_type == 'image':
                processed_path = _compress_image(file_path, upload)
            else:
                processed_path = file_path

            # Update progress
            upload.upload_progress = 50
            db.session.commit()

            # Build filename and storage key
            team = upload.team
            game = upload.game
            round_obj = upload.round
            questions = round_obj.get_questions()
            task_name = upload.question_id
            for q in questions:
                if q.get('id') == upload.question_id:
                    task_name = q.get('text', upload.question_id)[:80]
                    break

            ext = _get_extension(upload.original_filename, upload.mime_type)
            filename = build_storage_filename(team.name, task_name, game.name, ext)
            storage_key = build_storage_key(game.id, filename)

            # Upload to DO Spaces
            upload.upload_progress = 70
            db.session.commit()

            url = upload_file_to_spaces(
                processed_path,
                storage_key,
                content_type=upload.mime_type,
            )

            # Get file size
            file_size = os.path.getsize(processed_path)

            # Update record
            upload.storage_key = storage_key
            upload.storage_url = url
            upload.file_size_bytes = file_size
            upload.upload_status = 'complete'
            upload.upload_progress = 100
            db.session.commit()

            print(f'[UploadWorker] Upload {upload_id} complete: {url}')

            # Emit socket event for real-time update
            try:
                from app import socketio
                socketio.emit('upload_status_changed', {
                    'upload_id': upload_id,
                    'status': 'complete',
                    'progress': 100,
                    'url': url,
                }, room=f'game_{game.id}')
            except Exception:
                pass

        finally:
            # Clean up temp files
            if os.path.exists(file_path):
                os.remove(file_path)
            if 'processed_path' in locals() and processed_path != file_path and os.path.exists(processed_path):
                os.remove(processed_path)


def _compress_video(file_path, upload):
    """
    Compress a video file using FFmpeg.

    - Re-encodes to H.264 (libx264) with CRF 23 for good quality/size balance
    - Caps duration at 60 seconds
    - Preserves audio (AAC)
    - Outputs MP4 container

    Returns path to the compressed file.
    """
    from flask import current_app

    max_duration = current_app.config.get('MAX_VIDEO_DURATION_SECONDS', 60)
    output_path = file_path + '_compressed.mp4'

    cmd = [
        'ffmpeg', '-y',
        '-i', file_path,
        '-t', str(max_duration),
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-movflags', '+faststart',
        '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',  # Ensure even dimensions
        output_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )
        if result.returncode != 0:
            print(f'[UploadWorker] FFmpeg error: {result.stderr[:500]}')
            # Fall back to original file if compression fails
            return file_path

        # Get video duration
        duration = _get_video_duration(output_path)
        if duration:
            upload.duration_seconds = duration

        # Update mime type since we force MP4 output
        upload.mime_type = 'video/mp4'
        return output_path

    except subprocess.TimeoutExpired:
        print(f'[UploadWorker] FFmpeg timeout for upload {upload.id}')
        return file_path
    except FileNotFoundError:
        print('[UploadWorker] FFmpeg not found - skipping compression')
        return file_path


def _compress_image(file_path, upload):
    """
    Compress an image file using Pillow.

    - Resize if over 4MB
    - Convert to JPEG/WebP with quality 85
    - Strip EXIF data for privacy

    Returns path to the compressed file.
    """
    try:
        from PIL import Image

        img = Image.open(file_path)

        # Convert RGBA to RGB for JPEG output
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        # Resize if image is very large (over 4000px on longest side)
        max_dimension = 4000
        if max(img.size) > max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

        output_path = file_path + '_compressed.jpg'
        img.save(output_path, 'JPEG', quality=85, optimize=True)

        # Update mime type
        upload.mime_type = 'image/jpeg'
        return output_path

    except ImportError:
        print('[UploadWorker] Pillow not found - skipping image compression')
        return file_path
    except Exception as e:
        print(f'[UploadWorker] Image compression error: {e}')
        return file_path


def _get_video_duration(file_path):
    """Get video duration in seconds using ffprobe."""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except Exception:
        pass
    return None


def _get_extension(filename, mime_type):
    """Determine file extension from filename or MIME type."""
    if filename and '.' in filename:
        return filename.rsplit('.', 1)[-1].lower()

    # Fallback based on MIME type
    mime_map = {
        'image/jpeg': 'jpg',
        'image/png': 'png',
        'image/webp': 'webp',
        'image/gif': 'gif',
        'image/heic': 'heic',
        'video/mp4': 'mp4',
        'video/quicktime': 'mov',
        'video/webm': 'webm',
        'video/x-msvideo': 'avi',
        'video/3gpp': '3gp',
    }
    return mime_map.get(mime_type, 'bin')


def _mark_failed(job, error_message):
    """Mark an upload as failed in the database."""
    app = job['app']
    with app.app_context():
        from models import db, MediaUpload
        upload = MediaUpload.query.get(job['upload_id'])
        if upload:
            upload.upload_status = 'failed'
            upload.error_message = error_message[:500]
            db.session.commit()

            # Emit socket event
            try:
                from app import socketio
                socketio.emit('upload_status_changed', {
                    'upload_id': job['upload_id'],
                    'status': 'failed',
                    'error': error_message[:200],
                }, room=f'game_{upload.game_id}')
            except Exception:
                pass

    # Clean up temp file
    if os.path.exists(job['file_path']):
        os.remove(job['file_path'])
