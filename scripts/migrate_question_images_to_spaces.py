"""
One-off migration: move question images from local static/uploads/questions/
to DO Spaces, and update the image URLs stored in Round.questions_json.

Run inside the quiz_app_web container:
    python scripts/migrate_question_images_to_spaces.py

Safe to re-run: already-migrated URLs (not starting with /static/uploads/questions/)
are skipped. Missing local files are reported but left unchanged.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, Round, Game
from storage import upload_file_to_spaces

CONTENT_TYPES = {
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'gif': 'image/gif',
    'webp': 'image/webp',
}

LOCAL_PREFIX = '/static/uploads/questions/'


def main():
    with app.app_context():
        folder = app.config.get('DO_SPACES_FOLDER', 'fat-big-quiz')
        migrated = {}
        missing = []
        rounds_updated = 0

        for rnd in Round.query.all():
            questions = json.loads(rnd.questions_json or '[]')
            changed = False

            for q in questions:
                image = q.get('image')
                if not image or not image.startswith(LOCAL_PREFIX):
                    continue

                filename = image[len(LOCAL_PREFIX):]
                if filename in migrated:
                    q['image'] = migrated[filename]
                    changed = True
                    continue

                local_path = os.path.join('static', 'uploads', 'questions', filename)
                if not os.path.exists(local_path):
                    missing.append((rnd.game_id, rnd.id, rnd.name, image))
                    continue

                ext = filename.rsplit('.', 1)[-1].lower()
                content_type = CONTENT_TYPES.get(ext, 'application/octet-stream')
                storage_key = f'{folder}/question-images/{filename}'
                url = upload_file_to_spaces(local_path, storage_key, content_type=content_type)
                migrated[filename] = url
                q['image'] = url
                changed = True
                print(f'Migrated {filename} -> {url}')

            if changed:
                rnd.questions_json = json.dumps(questions)
                rounds_updated += 1

        if rounds_updated:
            db.session.commit()

        print(f'\nDone. {len(migrated)} images migrated, {rounds_updated} rounds updated.')
        if missing:
            print(f'\n{len(missing)} image references could not be recovered (file lost):')
            for game_id, round_id, round_name, image in missing:
                game = db.session.get(Game, game_id)
                game_name = game.name if game else '?'
                print(f'  Game {game_id} ({game_name}), round {round_id} ({round_name}): {image}')


if __name__ == '__main__':
    main()
