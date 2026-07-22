"""
Storage module for DigitalOcean Spaces (S3-compatible).

Handles file upload, retrieval, and URL generation for media files.
"""
import os
import re
import boto3
from botocore.config import Config as BotoConfig
from flask import current_app


def get_s3_client():
    """Create and return a boto3 S3 client configured for DO Spaces."""
    return boto3.client(
        's3',
        endpoint_url=current_app.config['DO_SPACES_ENDPOINT'],
        region_name=current_app.config['DO_SPACES_REGION'],
        aws_access_key_id=current_app.config['DO_SPACES_KEY'],
        aws_secret_access_key=current_app.config['DO_SPACES_SECRET'],
        config=BotoConfig(signature_version='s3v4'),
    )


def sanitise_filename(text):
    """
    Sanitise a string for use in filenames.

    Keeps alphanumeric, spaces, hyphens, dots, and hash.
    Replaces everything else with underscores.
    """
    # Replace pipe separators with double pipe for our naming convention
    sanitised = re.sub(r'[^\w\s\-\.#|]', '_', text)
    # Collapse multiple spaces/underscores
    sanitised = re.sub(r'[\s_]+', ' ', sanitised).strip()
    return sanitised


def build_storage_filename(team_name, task_name, game_name, extension):
    """
    Build the storage filename following the naming convention:
    {Team Name} || {Task Name} || {Game Name}.ext

    Args:
        team_name: Name of the team
        task_name: Name/number of the task/question
        game_name: Name of the game
        extension: File extension (e.g. 'jpg', 'mp4')

    Returns:
        Sanitised filename string
    """
    safe_team = sanitise_filename(team_name)
    safe_task = sanitise_filename(task_name)
    safe_game = sanitise_filename(game_name)

    filename = f'{safe_team} || {safe_task} || {safe_game}.{extension}'
    return filename


def build_storage_key(game_id, filename):
    """
    Build the full storage key (path) for a file in DO Spaces.

    Structure: {folder}/games/{game_id}/{filename}
    Uses DO_SPACES_FOLDER config to namespace within the shared bucket.
    """
    folder = current_app.config.get('DO_SPACES_FOLDER', 'fat-big-quiz')
    return f'{folder}/games/{game_id}/{filename}'


def upload_file_to_spaces(file_path, storage_key, content_type=None):
    """
    Upload a local file to DO Spaces.

    Args:
        file_path: Path to the local file
        storage_key: The S3 key (path in bucket)
        content_type: MIME type of the file

    Returns:
        Public URL of the uploaded file
    """
    client = get_s3_client()
    bucket = current_app.config['DO_SPACES_BUCKET']

    extra_args = {'ACL': 'public-read'}
    if content_type:
        extra_args['ContentType'] = content_type

    client.upload_file(
        file_path,
        bucket,
        storage_key,
        ExtraArgs=extra_args,
    )

    # Build public URL (prefer CDN endpoint)
    cdn_endpoint = current_app.config.get('DO_SPACES_CDN_ENDPOINT', '')
    if cdn_endpoint:
        url = f'{cdn_endpoint}/{storage_key}'
    else:
        endpoint = current_app.config['DO_SPACES_ENDPOINT']
        url = f'{endpoint}/{bucket}/{storage_key}'
    return url


def upload_fileobj_to_spaces(file_obj, storage_key, content_type=None):
    """
    Upload a file-like object to DO Spaces.

    Args:
        file_obj: File-like object (e.g. from request.files)
        storage_key: The S3 key (path in bucket)
        content_type: MIME type of the file

    Returns:
        Public URL of the uploaded file
    """
    client = get_s3_client()
    bucket = current_app.config['DO_SPACES_BUCKET']

    extra_args = {'ACL': 'public-read'}
    if content_type:
        extra_args['ContentType'] = content_type

    client.upload_fileobj(
        file_obj,
        bucket,
        storage_key,
        ExtraArgs=extra_args,
    )

    cdn_endpoint = current_app.config.get('DO_SPACES_CDN_ENDPOINT', '')
    if cdn_endpoint:
        url = f'{cdn_endpoint}/{storage_key}'
    else:
        endpoint = current_app.config['DO_SPACES_ENDPOINT']
        url = f'{endpoint}/{bucket}/{storage_key}'
    return url


def delete_from_spaces(storage_key):
    """
    Delete a file from DO Spaces.

    Args:
        storage_key: The S3 key to delete
    """
    client = get_s3_client()
    bucket = current_app.config['DO_SPACES_BUCKET']
    client.delete_object(Bucket=bucket, Key=storage_key)


def get_public_url(storage_key):
    """
    Get the public URL for a stored file.

    Args:
        storage_key: The S3 key

    Returns:
        Public URL string (CDN if configured)
    """
    cdn_endpoint = current_app.config.get('DO_SPACES_CDN_ENDPOINT', '')
    if cdn_endpoint:
        return f'{cdn_endpoint}/{storage_key}'
    endpoint = current_app.config['DO_SPACES_ENDPOINT']
    bucket = current_app.config['DO_SPACES_BUCKET']
    return f'{endpoint}/{bucket}/{storage_key}'
