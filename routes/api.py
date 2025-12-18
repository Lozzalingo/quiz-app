"""
API routes for Quiz App.

JSON endpoints for AJAX requests and real-time updates.
"""
import os
import uuid
from datetime import datetime
from functools import wraps
from flask import Blueprint, jsonify, request, current_app
from flask_login import current_user
from werkzeug.utils import secure_filename

from models import db, Game, Round, Team, Answer, ResubmitPermission

bp = Blueprint('api', __name__, url_prefix='/api')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def admin_required_api(f):
    """Decorator to require admin authentication for API endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        if not current_user.get_id().startswith('admin_'):
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/round/<int:round_id>/questions', methods=['GET'])
@admin_required_api
def get_questions(round_id):
    """Get questions for a round."""
    round_obj = Round.query.get_or_404(round_id)
    return jsonify({
        'success': True,
        'questions': round_obj.get_questions()
    })


@bp.route('/round/<int:round_id>/questions', methods=['POST'])
@admin_required_api
def update_questions(round_id):
    """Update questions for a round."""
    round_obj = Round.query.get_or_404(round_id)

    data = request.get_json()
    if not data or 'questions' not in data:
        return jsonify({'success': False, 'error': 'No questions provided'}), 400

    round_obj.set_questions(data['questions'])
    db.session.commit()

    return jsonify({'success': True})


@bp.route('/round/<int:round_id>/toggle', methods=['POST'])
@admin_required_api
def toggle_round(round_id):
    """Toggle round open/closed status."""
    round_obj = Round.query.get_or_404(round_id)

    round_obj.is_open = not round_obj.is_open
    db.session.commit()

    # Emit socket event to notify players
    try:
        from app import socketio
        game_id = round_obj.game_id
        print(f'[API] toggle_round: Emitting round_status_changed to game_{game_id}, round_id={round_id}, is_open={round_obj.is_open}')
        socketio.emit('round_status_changed', {
            'round_id': round_id,
            'is_open': round_obj.is_open
        }, room=f'game_{game_id}')
        print(f'[API] toggle_round: Socket emit completed')
    except Exception as e:
        print(f'[API] Error emitting round_status_changed: {e}')

    return jsonify({
        'success': True,
        'is_open': round_obj.is_open
    })


@bp.route('/round/<int:round_id>/name', methods=['PUT'])
@admin_required_api
def update_round_name(round_id):
    """Update round name."""
    round_obj = Round.query.get_or_404(round_id)

    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'success': False, 'error': 'No name provided'}), 400

    new_name = data['name'].strip()
    if not new_name:
        return jsonify({'success': False, 'error': 'Name cannot be empty'}), 400

    round_obj.name = new_name
    db.session.commit()

    return jsonify({
        'success': True,
        'name': round_obj.name
    })


@bp.route('/game/<int:game_id>/rounds/reorder', methods=['POST'])
@admin_required_api
def reorder_rounds(game_id):
    """Reorder rounds within a game."""
    game = Game.query.get_or_404(game_id)

    data = request.get_json()
    if not data or 'order' not in data:
        return jsonify({'success': False, 'error': 'No order provided'}), 400

    # order is a list of {id, order, parent_id} objects
    order_data = data['order']

    for item in order_data:
        round_obj = Round.query.get(item['id'])
        if round_obj and round_obj.game_id == game.id:
            round_obj.order = item['order']
            # Update parent_id if provided (for moving between levels)
            if 'parent_id' in item:
                round_obj.parent_id = item['parent_id']

    db.session.commit()

    # Emit socket event for spreadsheet to update
    try:
        from app import socketio
        socketio.emit('rounds_reordered', {
            'game_id': game_id
        }, room=f'spreadsheet_{game_id}')
    except Exception:
        pass

    return jsonify({'success': True})


@bp.route('/round/<int:round_id>/question/<question_id>', methods=['PATCH'])
@admin_required_api
def update_question(round_id, question_id):
    """Update a question's text, validation, or correct_answer (syncs to form)."""
    from utils import calculate_points_for_answer

    round_obj = Round.query.get_or_404(round_id)

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    questions = round_obj.get_questions()
    updated_question = None
    for q in questions:
        if q.get('id') == question_id:
            if 'text' in data:
                q['text'] = data['text']
            if 'validation' in data:
                q['validation'] = data['validation']
            if 'correct_answer' in data:
                q['correct_answer'] = data['correct_answer']
            updated_question = q
            break

    round_obj.set_questions(questions)

    # Re-score all existing answers for this question if validation changed
    if updated_question and ('validation' in data or 'correct_answer' in data):
        answers = Answer.query.filter_by(round_id=round_id, question_id=question_id).all()
        for answer in answers:
            new_points = calculate_points_for_answer(updated_question, answer.answer_text)
            answer.points = new_points

    db.session.commit()

    return jsonify({'success': True})


@bp.route('/game/<int:game_id>/answers', methods=['GET'])
@admin_required_api
def get_game_answers(game_id):
    """Get all answers for a game (for spreadsheet view).

    Returns one row per team with all answers as columns.
    Format: team_name, total_score, bonus_total, [round1_q1, round1_q2, ..., round1_points], [round2_q1, ...], etc.
    """
    game = Game.query.get_or_404(game_id)

    # Get rounds in proper hierarchical order (parent followed by children)
    top_level_rounds = Round.query.filter_by(game_id=game.id, parent_id=None).order_by(Round.order).all()
    rounds = []
    for parent in top_level_rounds:
        rounds.append(parent)
        # Add children right after their parent
        children = Round.query.filter_by(parent_id=parent.id).order_by(Round.order).all()
        rounds.extend(children)

    teams = Team.query.filter_by(game_id=game.id).order_by(Team.name).all()

    # Build column definitions for the frontend
    columns = []
    for round_obj in rounds:
        questions = round_obj.get_questions()
        round_cols = {
            'round_id': round_obj.id,
            'round_name': round_obj.name,
            'parent_id': round_obj.parent_id,
            'questions': []
        }
        for q in questions:
            round_cols['questions'].append({
                'id': q.get('id', ''),
                'text': q.get('text', ''),
                'type': q.get('type', 'text'),
                'validation': q.get('validation', ''),
                'correct_answer': q.get('correct_answer', '')
            })
        columns.append(round_cols)

    # Get custom columns for this game
    custom_columns = game.get_custom_columns()

    # Build team rows
    team_rows = []
    for idx, team in enumerate(teams, 1):
        custom_scores = team.get_custom_scores()
        custom_total = sum(custom_scores.values()) if custom_scores else 0

        row = {
            'position': idx,
            'team_id': team.id,
            'team_name': team.name,
            'created_at': team.created_at.isoformat(),
            'total_score': 0,
            'total_bonus': 0,
            'total_penalty': 0,
            'custom_scores': custom_scores,
            'tab_away_seconds': team.tab_away_seconds or 0,
            'tab_penalty_points': team.tab_penalty_points,
            'tab_switch_count': team.tab_switch_count or 0,
            'login_count': team.login_count or 0,
            'logout_count': team.logout_count or 0,
            'rounds': {}
        }

        grand_total = 0
        total_bonus = 0
        total_penalty = 0

        for round_obj in rounds:
            questions = round_obj.get_questions()
            round_data = {
                'answers': {},
                'round_points': 0
            }

            for q in questions:
                q_id = q.get('id', '')
                answer = Answer.query.filter_by(
                    team_id=team.id,
                    round_id=round_obj.id,
                    question_id=q_id
                ).first()

                if answer:
                    round_data['answers'][q_id] = {
                        'answer_id': answer.id,
                        'text': answer.answer_text or '',
                        'points': answer.points or 0,
                        'bonus': answer.bonus_points or 0,
                        'penalty': answer.penalty_points or 0,
                        'notes': answer.notes or ''
                    }
                    round_data['round_points'] += (answer.points or 0)
                    total_bonus += (answer.bonus_points or 0)
                    total_penalty += (answer.penalty_points or 0)
                else:
                    round_data['answers'][q_id] = {
                        'answer_id': None,
                        'text': '',
                        'points': 0,
                        'bonus': 0,
                        'penalty': 0,
                        'notes': ''
                    }

            row['rounds'][round_obj.id] = round_data
            grand_total += round_data['round_points']

        row['total_score'] = grand_total + total_bonus - total_penalty + custom_total - team.tab_penalty_points
        row['total_bonus'] = total_bonus
        row['total_penalty'] = total_penalty

        team_rows.append(row)

    # Sort by total score descending and update positions
    team_rows.sort(key=lambda x: x['total_score'], reverse=True)
    for idx, row in enumerate(team_rows, 1):
        row['position'] = idx

    return jsonify({
        'success': True,
        'columns': columns,
        'custom_columns': custom_columns,
        'teams': team_rows
    })


@bp.route('/answer/<int:answer_id>/text', methods=['POST'])
@admin_required_api
def update_answer_text(answer_id):
    """Update answer text and re-score."""
    from utils import calculate_points_for_answer

    answer = Answer.query.get_or_404(answer_id)
    round_obj = answer.round
    game_id = round_obj.game_id

    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'success': False, 'error': 'Text required'}), 400

    answer.answer_text = data['text']

    # Re-score based on question config
    questions = round_obj.get_questions()
    for q in questions:
        if q.get('id') == answer.question_id:
            answer.points = calculate_points_for_answer(q, answer.answer_text)
            break

    db.session.commit()

    # Emit Socket.IO event
    try:
        from app import socketio
        socketio.emit('score_updated', {
            'answer_id': answer.id
        }, room=f'spreadsheet_{game_id}')
        # Also emit to game room for players viewing their answers
        socketio.emit('answer_score_updated', {
            'round_id': answer.round_id,
            'question_id': answer.question_id,
            'team_id': answer.team_id,
            'points': answer.points
        }, room=f'game_{game_id}')
    except Exception:
        pass

    return jsonify({
        'success': True,
        'points': answer.points
    })


@bp.route('/answer/create', methods=['POST'])
@admin_required_api
def create_answer():
    """Create a new answer for a team/question."""
    from utils import calculate_points_for_answer

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    team_id = data.get('team_id')
    round_id = data.get('round_id')
    question_id = data.get('question_id')
    text = data.get('text', '')

    if not all([team_id, round_id, question_id]):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    # Check if answer already exists
    existing = Answer.query.filter_by(
        team_id=team_id,
        round_id=round_id,
        question_id=question_id
    ).first()

    if existing:
        # Update existing
        existing.answer_text = text
        answer = existing
    else:
        # Create new
        answer = Answer(
            team_id=team_id,
            round_id=round_id,
            question_id=question_id,
            answer_text=text
        )
        db.session.add(answer)

    # Score the answer
    round_obj = Round.query.get(round_id)
    if round_obj:
        questions = round_obj.get_questions()
        for q in questions:
            if q.get('id') == question_id:
                answer.points = calculate_points_for_answer(q, text)
                break

    db.session.commit()

    # Emit Socket.IO event
    try:
        from app import socketio
        socketio.emit('score_updated', {
            'answer_id': answer.id
        }, room=f'spreadsheet_{round_obj.game_id}')
    except Exception:
        pass

    return jsonify({
        'success': True,
        'answer_id': answer.id,
        'points': answer.points
    })


@bp.route('/answer/<int:answer_id>/score', methods=['POST'])
@admin_required_api
def update_answer_score(answer_id):
    """Update score for an answer."""
    answer = Answer.query.get_or_404(answer_id)
    game_id = answer.round.game_id

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    if 'points' in data:
        answer.points = float(data['points'])
    if 'bonus_points' in data:
        answer.bonus_points = float(data['bonus_points'])
    if 'penalty_points' in data:
        answer.penalty_points = float(data['penalty_points'])
    if 'notes' in data:
        answer.notes = data['notes']

    db.session.commit()

    # Emit Socket.IO event for real-time spreadsheet sync
    try:
        from app import socketio
        socketio.emit('score_updated', {
            'answer_id': answer.id,
            'points': answer.points,
            'bonus_points': answer.bonus_points,
            'penalty_points': answer.penalty_points,
            'notes': answer.notes,
            'total': answer.total_points
        }, room=f'spreadsheet_{game_id}')
        # Also emit to game room for players viewing their answers
        socketio.emit('answer_score_updated', {
            'round_id': answer.round_id,
            'question_id': answer.question_id,
            'team_id': answer.team_id,
            'points': answer.points
        }, room=f'game_{game_id}')
    except Exception:
        pass  # Socket.IO not available

    return jsonify({
        'success': True,
        'total': answer.total_points
    })


@bp.route('/game/<int:game_id>/teams', methods=['GET'])
@admin_required_api
def get_game_teams(game_id):
    """Get all teams for a game."""
    game = Game.query.get_or_404(game_id)
    teams = Team.query.filter_by(game_id=game.id).order_by(Team.name).all()

    return jsonify({
        'success': True,
        'teams': [{
            'id': team.id,
            'name': team.name,
            'created_at': team.created_at.isoformat()
        } for team in teams]
    })


@bp.route('/game/<int:game_id>/leaderboard', methods=['GET'])
def get_leaderboard(game_id):
    """Get leaderboard for a game (public endpoint).

    Scores are hidden per-team when they have submitted answers to a closed round.
    Once game.is_finished is True, scores are revealed for everyone.
    """
    game = Game.query.get_or_404(game_id)
    teams = Team.query.filter_by(game_id=game.id).all()

    # Check if scores should be hidden for the requesting team
    # Get team_id from query param (for team-specific hiding)
    requesting_team_id = request.args.get('team_id', type=int)

    # If game is finished, always show scores
    if game.is_finished:
        scores_hidden = False
    elif requesting_team_id:
        # Check if this team has submitted answers to the FINAL round
        # Scores are hidden only when team has submitted to the last round (by order)

        # Get the final round (last by order, excluding parent rounds with children)
        all_rounds = Round.query.filter_by(game_id=game.id).order_by(Round.order.desc()).all()

        # Find the final "leaf" round (one that has no children)
        final_round = None
        for r in all_rounds:
            # Check if this round has children (is a parent)
            has_children = Round.query.filter_by(parent_id=r.id).first() is not None
            if not has_children:
                final_round = r
                break

        if final_round:
            # Check if team submitted to the final round
            submitted_to_final = Answer.query.filter_by(
                team_id=requesting_team_id,
                round_id=final_round.id
            ).first()
            scores_hidden = submitted_to_final is not None
        else:
            # No final round - show scores
            scores_hidden = False
    else:
        # No team_id provided (admin view) - show scores
        scores_hidden = False

    if scores_hidden:
        return jsonify({
            'success': True,
            'leaderboard': [],
            'is_finished': False,
            'scores_hidden': True,
            'message': 'Scores are hidden until the quiz master reveals them!'
        })

    leaderboard = []
    for team in teams:
        # Sum scores from all rounds (real-time)
        total_points = db.session.query(
            db.func.coalesce(db.func.sum(Answer.points), 0) +
            db.func.coalesce(db.func.sum(Answer.bonus_points), 0) -
            db.func.coalesce(db.func.sum(Answer.penalty_points), 0)
        ).filter(
            Answer.team_id == team.id
        ).scalar() or 0

        # Add custom scores
        custom_scores = team.get_custom_scores()
        custom_total = sum(custom_scores.values()) if custom_scores else 0

        # Subtract tab penalty
        tab_penalty = team.tab_penalty_points

        leaderboard.append({
            'team_name': team.name,
            'total_points': float(total_points) + custom_total - tab_penalty
        })

    leaderboard.sort(key=lambda x: x['total_points'], reverse=True)

    return jsonify({
        'success': True,
        'leaderboard': leaderboard,
        'is_finished': game.is_finished,
        'scores_hidden': False
    })


@bp.route('/game/<int:game_id>/custom_columns', methods=['GET'])
@admin_required_api
def get_custom_columns(game_id):
    """Get custom columns for a game."""
    game = Game.query.get_or_404(game_id)
    return jsonify({
        'success': True,
        'columns': game.get_custom_columns()
    })


@bp.route('/game/<int:game_id>/custom_columns', methods=['POST'])
@admin_required_api
def add_custom_column(game_id):
    """Add a custom column to a game."""
    game = Game.query.get_or_404(game_id)

    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'success': False, 'error': 'Column name required'}), 400

    columns = game.get_custom_columns()
    # Generate unique ID
    col_id = f"custom_{len(columns) + 1}_{int(datetime.now().timestamp())}"

    columns.append({
        'id': col_id,
        'name': data['name']
    })

    game.set_custom_columns(columns)
    db.session.commit()

    # Emit Socket.IO event
    try:
        from app import socketio
        socketio.emit('columns_updated', {
            'game_id': game_id
        }, room=f'spreadsheet_{game_id}')
    except Exception:
        pass

    return jsonify({
        'success': True,
        'column': {'id': col_id, 'name': data['name']}
    })


@bp.route('/game/<int:game_id>/custom_columns/<col_id>', methods=['DELETE'])
@admin_required_api
def delete_custom_column(game_id, col_id):
    """Delete a custom column from a game."""
    game = Game.query.get_or_404(game_id)

    columns = game.get_custom_columns()
    columns = [c for c in columns if c['id'] != col_id]
    game.set_custom_columns(columns)

    # Remove this column from all team scores
    teams = Team.query.filter_by(game_id=game_id).all()
    for team in teams:
        scores = team.get_custom_scores()
        if col_id in scores:
            del scores[col_id]
            team.set_custom_scores(scores)

    db.session.commit()

    # Emit Socket.IO event
    try:
        from app import socketio
        socketio.emit('columns_updated', {
            'game_id': game_id
        }, room=f'spreadsheet_{game_id}')
    except Exception:
        pass

    return jsonify({'success': True})


@bp.route('/game/<int:game_id>/custom_columns/<col_id>', methods=['PATCH'])
@admin_required_api
def rename_custom_column(game_id, col_id):
    """Rename a custom column."""
    game = Game.query.get_or_404(game_id)

    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'success': False, 'error': 'Name required'}), 400

    columns = game.get_custom_columns()
    for col in columns:
        if col['id'] == col_id:
            col['name'] = data['name']
            break

    game.set_custom_columns(columns)
    db.session.commit()

    # Emit Socket.IO event
    try:
        from app import socketio
        socketio.emit('columns_updated', {
            'game_id': game_id
        }, room=f'spreadsheet_{game_id}')
    except Exception:
        pass

    return jsonify({'success': True})


@bp.route('/team/<int:team_id>/custom_score', methods=['POST'])
@admin_required_api
def update_custom_score(team_id):
    """Update a custom score for a team."""
    team = Team.query.get_or_404(team_id)
    game_id = team.game_id

    data = request.get_json()
    if not data or 'column_id' not in data:
        return jsonify({'success': False, 'error': 'Column ID required'}), 400

    scores = team.get_custom_scores()
    scores[data['column_id']] = float(data.get('value', 0))
    team.set_custom_scores(scores)
    db.session.commit()

    # Emit Socket.IO event
    try:
        from app import socketio
        socketio.emit('score_updated', {
            'team_id': team_id,
            'column_id': data['column_id'],
            'value': scores[data['column_id']]
        }, room=f'spreadsheet_{game_id}')
    except Exception:
        pass

    return jsonify({
        'success': True,
        'value': scores[data['column_id']]
    })


@bp.route('/upload/image', methods=['POST'])
@admin_required_api
def upload_image():
    """Upload an image for a question."""
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image provided'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Invalid file type'}), 400

    # Generate unique filename
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"

    # Ensure upload directory exists
    upload_dir = os.path.join('static', 'uploads', 'questions')
    os.makedirs(upload_dir, exist_ok=True)

    # Save file
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)

    # Return the URL path
    return jsonify({
        'success': True,
        'url': f'/static/uploads/questions/{filename}'
    })


@bp.route('/round/<int:round_id>/submissions', methods=['GET'])
@admin_required_api
def get_round_submissions(round_id):
    """Get submission status for all teams in a round."""
    round_obj = Round.query.get_or_404(round_id)
    game = round_obj.game
    teams = Team.query.filter_by(game_id=game.id).order_by(Team.name).all()

    # Get all resubmit permissions for this round
    resubmit_perms = {p.team_id for p in ResubmitPermission.query.filter_by(round_id=round_id).all()}

    submissions = []
    for team in teams:
        has_submitted = Answer.query.filter_by(
            team_id=team.id,
            round_id=round_id
        ).first() is not None

        can_resubmit = team.id in resubmit_perms

        submissions.append({
            'team_id': team.id,
            'team_name': team.name,
            'submitted': has_submitted,
            'can_resubmit': can_resubmit
        })

    return jsonify({
        'success': True,
        'submissions': submissions
    })


@bp.route('/round/<int:round_id>/team/<int:team_id>/clear', methods=['POST'])
@admin_required_api
def clear_team_submission(round_id, team_id):
    """Allow a team to resubmit their answers for a round."""
    round_obj = Round.query.get_or_404(round_id)
    team = Team.query.get_or_404(team_id)
    game = round_obj.game

    # Verify team belongs to this game
    if team.game_id != game.id:
        return jsonify({'success': False, 'error': 'Team not in this game'}), 400

    # Create or update resubmit permission (don't delete answers)
    existing = ResubmitPermission.query.filter_by(
        team_id=team_id,
        round_id=round_id
    ).first()

    if not existing:
        permission = ResubmitPermission(
            team_id=team_id,
            round_id=round_id
        )
        db.session.add(permission)
        db.session.commit()

    # Emit Socket.IO event
    try:
        from app import socketio
        # Notify the team they can resubmit
        socketio.emit('submission_cleared', {
            'round_id': round_id,
            'team_id': team_id
        }, room=f'game_{game.id}')
    except Exception:
        pass

    return jsonify({
        'success': True,
        'message': f'Allowed {team.name} to resubmit'
    })


def team_required_api(f):
    """Decorator to require team authentication for API endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Not authenticated'}), 401
        if not current_user.get_id().startswith('team_'):
            return jsonify({'success': False, 'error': 'Team access required'}), 403
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/team/update-name', methods=['POST'])
@team_required_api
def update_team_name():
    """Update the current team's name."""
    team = Team.query.get(int(current_user.get_id().split('_')[1]))
    if not team:
        return jsonify({'success': False, 'error': 'Team not found'}), 404

    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'success': False, 'error': 'Name required'}), 400

    new_name = data['name'].strip()
    if not new_name:
        return jsonify({'success': False, 'error': 'Name cannot be empty'}), 400

    # Check if name is already taken by another team in this game
    existing = Team.query.filter_by(game_id=team.game_id, name=new_name).first()
    if existing and existing.id != team.id:
        return jsonify({'success': False, 'error': 'Team name already taken'}), 400

    team.name = new_name
    db.session.commit()

    return jsonify({'success': True})


@bp.route('/team/update-password', methods=['POST'])
@team_required_api
def update_team_password():
    """Update the current team's password."""
    team = Team.query.get(int(current_user.get_id().split('_')[1]))
    if not team:
        return jsonify({'success': False, 'error': 'Team not found'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')

    if not current_password or not new_password:
        return jsonify({'success': False, 'error': 'Both current and new password required'}), 400

    # Verify current password
    if not team.check_password(current_password):
        return jsonify({'success': False, 'error': 'Current password is incorrect'}), 400

    # Set new password
    team.set_password(new_password)
    db.session.commit()

    return jsonify({'success': True})


@bp.route('/team/round/<int:round_id>/scores', methods=['GET'])
@team_required_api
def get_team_round_scores(round_id):
    """Get scores for a team's answers in a round (for showing correct/incorrect)."""
    team = Team.query.get(int(current_user.get_id().split('_')[1]))
    if not team:
        return jsonify({'success': False, 'error': 'Team not found'}), 404

    round_obj = Round.query.get_or_404(round_id)

    # Verify team belongs to this game
    if team.game_id != round_obj.game_id:
        return jsonify({'success': False, 'error': 'Access denied'}), 403

    # Get all answers for this team in this round
    answers = Answer.query.filter_by(team_id=team.id, round_id=round_id).all()

    scores = {}
    for answer in answers:
        scores[answer.question_id] = answer.points or 0

    return jsonify({
        'success': True,
        'scores': scores
    })


@bp.route('/team/round/<int:round_id>/ordering-results/<question_id>', methods=['GET'])
@team_required_api
def get_ordering_results(round_id, question_id):
    """Get per-slot ordering results for a question."""
    import json
    team = Team.query.get(int(current_user.get_id().split('_')[1]))
    if not team:
        return jsonify({'success': False, 'error': 'Team not found'}), 404

    round_obj = Round.query.get_or_404(round_id)

    # Verify team belongs to this game
    if team.game_id != round_obj.game_id:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    # Get the question config
    questions = round_obj.get_questions()
    question = None
    for q in questions:
        if q.get('id') == question_id:
            question = q
            break

    if not question or question.get('type') != 'ordering':
        return jsonify({'success': False, 'error': 'Ordering question not found'}), 404

    # Get the answer
    answer = Answer.query.filter_by(
        team_id=team.id,
        round_id=round_id,
        question_id=question_id
    ).first()

    if not answer:
        return jsonify({'success': True, 'results': [], 'points': 0})

    ordering_config = question.get('ordering', {})
    correct_items = ordering_config.get('items', [])

    try:
        player_order = json.loads(answer.answer_text) if answer.answer_text else []
    except (json.JSONDecodeError, TypeError):
        player_order = []

    slot_results = []
    for player_pos, player_item in enumerate(player_order):
        if player_item and player_item in correct_items:
            correct_pos = correct_items.index(player_item)
            distance = abs(player_pos - correct_pos)
            if distance == 0:
                slot_results.append({'item': player_item, 'status': 'correct'})
            elif distance == 1:
                slot_results.append({'item': player_item, 'status': 'adjacent'})
            else:
                slot_results.append({'item': player_item, 'status': 'wrong'})
        else:
            slot_results.append({'item': player_item or '', 'status': 'wrong'})

    return jsonify({
        'success': True,
        'results': slot_results,
        'points': answer.points or 0
    })


@bp.route('/team/get-away-time', methods=['GET'])
@team_required_api
def get_away_time():
    """Get current away time for the team."""
    team = Team.query.get(int(current_user.get_id().split('_')[1]))
    if not team:
        return jsonify({'success': False, 'error': 'Team not found'}), 404

    game = team.game

    return jsonify({
        'success': True,
        'total_away_seconds': team.tab_away_seconds or 0,
        'penalty_points': team.tab_penalty_points,
        'tracking_enabled': game.tab_penalty_enabled if game else True
    })


@bp.route('/team/tick-away-time', methods=['POST'])
@team_required_api
def tick_away_time():
    """Add 1 second to away time. Called every second while player is away.

    Checks if tracking is enabled before adding time.
    Broadcasts update to all connected clients.
    """
    team = Team.query.get(int(current_user.get_id().split('_')[1]))
    if not team:
        return jsonify({'success': False, 'error': 'Team not found'}), 404

    game = team.game

    # Check if tracking is enabled or game is paused
    if not game.tab_penalty_enabled or game.pause_mode:
        return jsonify({
            'success': False,
            'tracking_disabled': True,
            'total_away_seconds': team.tab_away_seconds or 0
        })

    # Check if game has any open rounds
    open_rounds = Round.query.filter_by(game_id=game.id, is_open=True).first()
    if not open_rounds:
        return jsonify({
            'success': False,
            'game_finished': True,
            'total_away_seconds': team.tab_away_seconds or 0
        })

    # Add 1 second
    team.tab_away_seconds = (team.tab_away_seconds or 0) + 1
    db.session.commit()

    # Broadcast to all clients (player + admin)
    try:
        from app import socketio
        socketio.emit('tab_time_updated', {
            'team_id': team.id,
            'total_away_seconds': team.tab_away_seconds,
            'penalty_points': team.tab_penalty_points
        }, room=f'game_{game.id}')
        socketio.emit('tab_time_updated', {
            'team_id': team.id,
            'total_away_seconds': team.tab_away_seconds,
            'penalty_points': team.tab_penalty_points
        }, room=f'spreadsheet_{game.id}')
    except Exception as e:
        print(f'[API] Error broadcasting tab_time_updated: {e}')

    return jsonify({
        'success': True,
        'total_away_seconds': team.tab_away_seconds,
        'penalty_points': team.tab_penalty_points
    })


@bp.route('/team/report-tab-switch', methods=['POST'])
@team_required_api
def report_tab_switch():
    """Report a tab switch (called when player leaves the tab)."""
    team = Team.query.get(int(current_user.get_id().split('_')[1]))
    if not team:
        return jsonify({'success': False, 'error': 'Team not found'}), 404

    game = team.game

    # Check if tracking is enabled or game is paused
    if not game.tab_penalty_enabled or game.pause_mode:
        return jsonify({
            'success': False,
            'tracking_disabled': True,
            'tab_switch_count': team.tab_switch_count or 0
        })

    # Check if game has any open rounds
    open_rounds = Round.query.filter_by(game_id=game.id, is_open=True).first()
    if not open_rounds:
        return jsonify({
            'success': False,
            'game_finished': True,
            'tab_switch_count': team.tab_switch_count or 0
        })

    # Increment tab switch count
    team.tab_switch_count = (team.tab_switch_count or 0) + 1
    db.session.commit()

    # Broadcast to admin views
    try:
        from app import socketio
        socketio.emit('tab_switch_updated', {
            'team_id': team.id,
            'tab_switch_count': team.tab_switch_count
        }, room=f'game_{game.id}')
        socketio.emit('tab_switch_updated', {
            'team_id': team.id,
            'tab_switch_count': team.tab_switch_count
        }, room=f'spreadsheet_{game.id}')
    except Exception as e:
        print(f'[API] Error broadcasting tab_switch_updated: {e}')

    return jsonify({
        'success': True,
        'tab_switch_count': team.tab_switch_count
    })


@bp.route('/team/report-away-time', methods=['POST'])
@team_required_api
def report_away_time():
    """Report time spent away from the tab (for anti-cheat tracking)."""
    team = Team.query.get(int(current_user.get_id().split('_')[1]))
    if not team:
        return jsonify({'success': False, 'error': 'Team not found'}), 404

    game = team.game

    # Check if tab penalty tracking is enabled for this game
    if not game.tab_penalty_enabled:
        return jsonify({
            'success': True,
            'tracking_disabled': True,
            'total_away_seconds': team.tab_away_seconds or 0,
            'penalty_points': team.tab_penalty_points
        })

    # Check if game has any open rounds (don't track if all rounds closed)
    open_rounds = Round.query.filter_by(game_id=game.id, is_open=True).first()
    if not open_rounds:
        return jsonify({
            'success': True,
            'game_finished': True,
            'total_away_seconds': team.tab_away_seconds or 0,
            'penalty_points': team.tab_penalty_points
        })

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    seconds = data.get('seconds', 0)
    if seconds > 0:
        team.tab_away_seconds = (team.tab_away_seconds or 0) + int(seconds)
        db.session.commit()

        # Emit Socket.IO event to update spreadsheet in real-time
        try:
            from app import socketio
            socketio.emit('tab_penalty_updated', {
                'team_id': team.id,
                'tab_away_seconds': team.tab_away_seconds,
                'penalty_points': team.tab_penalty_points
            }, room=f'spreadsheet_{team.game_id}')
        except Exception:
            pass

    return jsonify({
        'success': True,
        'total_away_seconds': team.tab_away_seconds,
        'penalty_points': team.tab_penalty_points
    })


@bp.route('/team/<int:team_id>/reset-tab-penalty', methods=['POST'])
@admin_required_api
def reset_tab_penalty(team_id):
    """Reset a team's tab away penalty (admin only)."""
    team = Team.query.get_or_404(team_id)

    team.tab_away_seconds = 0
    team.tab_switch_count = 0
    db.session.commit()

    # Emit Socket.IO events
    try:
        from app import socketio
        socketio.emit('tab_penalty_updated', {
            'team_id': team.id,
            'tab_away_seconds': 0,
            'penalty_points': 0
        }, room=f'spreadsheet_{team.game_id}')
        socketio.emit('tab_switch_updated', {
            'team_id': team.id,
            'tab_switch_count': 0
        }, room=f'game_{team.game_id}')
    except Exception:
        pass

    return jsonify({'success': True})


@bp.route('/team/<int:team_id>/tab-away-seconds', methods=['PUT'])
@admin_required_api
def set_tab_away_seconds(team_id):
    """Set a team's tab away seconds directly (admin only)."""
    team = Team.query.get_or_404(team_id)
    data = request.get_json()

    if not data or 'seconds' not in data:
        return jsonify({'success': False, 'error': 'Seconds value required'}), 400

    try:
        seconds = int(data['seconds'])
        if seconds < 0:
            seconds = 0
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': 'Invalid seconds value'}), 400

    team.tab_away_seconds = seconds
    db.session.commit()

    # Emit Socket.IO events
    try:
        from app import socketio
        print(f'[API] set_tab_away_seconds: Emitting to spreadsheet_{team.game_id} and game_{team.game_id}')
        # Notify spreadsheet
        socketio.emit('tab_penalty_updated', {
            'team_id': team.id,
            'tab_away_seconds': team.tab_away_seconds,
            'penalty_points': team.tab_penalty_points
        }, room=f'spreadsheet_{team.game_id}')

        # Notify players so they fetch fresh time (same pattern as reset button)
        game = Game.query.get(team.game_id)
        print(f'[API] set_tab_away_seconds: Emitting tab_penalty_tracking_changed to game_{team.game_id}')
        socketio.emit('tab_penalty_tracking_changed', {
            'enabled': game.tab_penalty_enabled if game else True
        }, room=f'game_{team.game_id}')
    except Exception as e:
        print(f'[API] set_tab_away_seconds: Error emitting socket events: {e}')

    return jsonify({
        'success': True,
        'tab_away_seconds': team.tab_away_seconds,
        'penalty_points': team.tab_penalty_points
    })


@bp.route('/game/<int:game_id>/tab-penalty-enabled', methods=['PUT'])
@admin_required_api
def toggle_tab_penalty(game_id):
    """Toggle tab penalty tracking for a game (admin only)."""
    print(f'[API] toggle_tab_penalty called for game {game_id}')
    game = Game.query.get_or_404(game_id)
    data = request.get_json()
    print(f'[API] Request data: {data}')

    if data and 'enabled' in data:
        game.tab_penalty_enabled = bool(data['enabled'])
    else:
        # Toggle if no value provided
        game.tab_penalty_enabled = not game.tab_penalty_enabled

    db.session.commit()
    print(f'[API] tab_penalty_enabled set to: {game.tab_penalty_enabled}')

    # Emit Socket.IO event to notify players and other admin tabs
    try:
        from app import socketio
        print(f'[API] Emitting tab_penalty_tracking_changed to game_{game_id} and spreadsheet_{game_id}')
        # Notify players
        socketio.emit('tab_penalty_tracking_changed', {
            'enabled': game.tab_penalty_enabled
        }, room=f'game_{game_id}')
        # Notify admin spreadsheet views
        socketio.emit('tab_penalty_tracking_changed', {
            'enabled': game.tab_penalty_enabled
        }, room=f'spreadsheet_{game_id}')
    except Exception as e:
        print(f'[API] Error emitting socket event: {e}')

    return jsonify({
        'success': True,
        'tab_penalty_enabled': game.tab_penalty_enabled
    })


@bp.route('/game/<int:game_id>/reset-all-tab-penalties', methods=['POST'])
@admin_required_api
def reset_all_tab_penalties(game_id):
    """Reset all teams' tab penalties for a game (admin only)."""
    print(f'[API] reset_all_tab_penalties called for game {game_id}')
    game = Game.query.get_or_404(game_id)

    # Reset all teams' tab away seconds and switch counts
    teams = Team.query.filter_by(game_id=game_id).all()
    for team in teams:
        team.tab_away_seconds = 0
        team.tab_switch_count = 0

    db.session.commit()
    print(f'[API] Reset {len(teams)} teams to 0 seconds and 0 switches')

    # Emit Socket.IO events to ALL clients
    try:
        from app import socketio
        print(f'[API] Broadcasting reset to game_{game_id} and spreadsheet_{game_id}')

        # Notify players - use same event as Start/Pause so they fetch fresh time from DB
        socketio.emit('tab_penalty_tracking_changed', {
            'enabled': game.tab_penalty_enabled
        }, room=f'game_{game_id}')

        # Notify admin views - send update for each team
        for team in teams:
            socketio.emit('tab_penalty_updated', {
                'team_id': team.id,
                'tab_away_seconds': 0,
                'penalty_points': 0
            }, room=f'spreadsheet_{game_id}')
    except Exception as e:
        print(f'[API] Error broadcasting reset: {e}')

    return jsonify({
        'success': True,
        'teams_reset': len(teams)
    })


@bp.route('/game/<int:game_id>/name', methods=['PUT'])
@admin_required_api
def update_game_name(game_id):
    """Update game name (admin only)."""
    game = Game.query.get_or_404(game_id)
    data = request.get_json()

    if not data or 'name' not in data:
        return jsonify({'success': False, 'error': 'Name is required'}), 400

    new_name = data['name'].strip()
    if not new_name:
        return jsonify({'success': False, 'error': 'Name cannot be empty'}), 400

    game.name = new_name
    db.session.commit()

    return jsonify({
        'success': True,
        'name': game.name
    })


@bp.route('/game/<int:game_id>/pause', methods=['PUT'])
@admin_required_api
def set_game_pause(game_id):
    """Set game pause mode (admin only).

    pause_mode can be:
    - null/None: Game is playing normally
    - 'starting': Game starting soon (pre-game pause)
    - 'halftime': Half time break
    """
    game = Game.query.get_or_404(game_id)
    data = request.get_json()

    pause_mode = data.get('pause_mode') if data else None

    # Validate pause_mode
    if pause_mode is not None and pause_mode not in ['starting', 'halftime']:
        return jsonify({'success': False, 'error': 'Invalid pause mode'}), 400

    # When pausing, also pause tab penalty tracking
    # When resuming, restore tab penalty tracking
    was_paused = game.pause_mode is not None
    will_be_paused = pause_mode is not None

    game.pause_mode = pause_mode

    # Auto-pause tab penalty when game is paused, re-enable when resumed
    if will_be_paused and not was_paused:
        # Pause - disable tab penalty tracking
        game.tab_penalty_enabled = False
    elif not will_be_paused and was_paused:
        # Resume - re-enable tab penalty tracking
        game.tab_penalty_enabled = True

    db.session.commit()

    # Emit Socket.IO event to notify players
    try:
        from app import socketio
        socketio.emit('game_pause_changed', {
            'pause_mode': game.pause_mode,
            'tab_penalty_enabled': game.tab_penalty_enabled
        }, room=f'game_{game_id}')
        # Also notify admin views
        socketio.emit('game_pause_changed', {
            'pause_mode': game.pause_mode,
            'tab_penalty_enabled': game.tab_penalty_enabled
        }, room=f'spreadsheet_{game_id}')
    except Exception as e:
        print(f'[API] Error emitting game_pause_changed: {e}')

    return jsonify({
        'success': True,
        'pause_mode': game.pause_mode
    })


@bp.route('/game/<int:game_id>/regenerate-qr', methods=['POST'])
@admin_required_api
def regenerate_qr_code(game_id):
    """Regenerate QR code for a game with correct BASE_URL (admin only)."""
    from flask import current_app
    from utils import generate_qr_code

    game = Game.query.get_or_404(game_id)
    base_url = current_app.config.get('BASE_URL', 'http://localhost:5777')
    qr_path = generate_qr_code(game.code, game.id, base_url)
    game.qr_code_path = qr_path
    db.session.commit()

    return jsonify({
        'success': True,
        'qr_path': qr_path,
        'base_url': base_url
    })


@bp.route('/game/<int:game_id>/finish', methods=['POST'])
@admin_required_api
def finish_game(game_id):
    """Mark a game as finished, revealing final scores (admin only)."""
    game = Game.query.get_or_404(game_id)
    game.is_finished = True
    db.session.commit()

    # Emit Socket.IO event to notify all clients
    try:
        from app import socketio
        socketio.emit('game_finished', {
            'game_id': game_id
        }, room=f'game_{game_id}')
    except Exception:
        pass

    return jsonify({
        'success': True,
        'is_finished': game.is_finished
    })


@bp.route('/game/<int:game_id>/unfinish', methods=['POST'])
@admin_required_api
def unfinish_game(game_id):
    """Mark a game as not finished (admin only)."""
    game = Game.query.get_or_404(game_id)
    game.is_finished = False
    db.session.commit()

    # Emit Socket.IO event to notify all clients
    try:
        from app import socketio
        socketio.emit('game_unfinished', {
            'game_id': game_id
        }, room=f'game_{game_id}')
    except Exception:
        pass

    return jsonify({
        'success': True,
        'is_finished': game.is_finished
    })


@bp.route('/team/<int:team_id>/name', methods=['PUT'])
@admin_required_api
def admin_update_team_name(team_id):
    """Update a team's name (admin only)."""
    team = Team.query.get_or_404(team_id)
    data = request.get_json()

    if not data or 'name' not in data:
        return jsonify({'success': False, 'error': 'Name is required'}), 400

    new_name = data['name'].strip()
    if not new_name:
        return jsonify({'success': False, 'error': 'Name cannot be empty'}), 400

    # Check for duplicate within game
    existing = Team.query.filter_by(game_id=team.game_id, name=new_name).first()
    if existing and existing.id != team.id:
        return jsonify({'success': False, 'error': 'Team name already taken'}), 400

    team.name = new_name
    db.session.commit()

    # Emit Socket.IO event to both admin spreadsheet and player game rooms
    try:
        from app import socketio
        event_data = {
            'team_id': team.id,
            'name': team.name
        }
        socketio.emit('team_updated', event_data, room=f'spreadsheet_{team.game_id}')
        socketio.emit('team_updated', event_data, room=f'game_{team.game_id}')
    except Exception:
        pass

    return jsonify({'success': True, 'name': team.name})


@bp.route('/team/<int:team_id>', methods=['DELETE'])
@admin_required_api
def delete_team(team_id):
    """Delete a team and all its answers (admin only)."""
    team = Team.query.get_or_404(team_id)
    game_id = team.game_id
    team_name = team.name

    db.session.delete(team)
    db.session.commit()

    # Emit Socket.IO event
    try:
        from app import socketio
        socketio.emit('team_deleted', {
            'team_id': team_id
        }, room=f'spreadsheet_{game_id}')
    except Exception:
        pass

    return jsonify({'success': True, 'message': f'Team "{team_name}" deleted'})


@bp.route('/round/<int:round_id>/question/<question_id>/betting-results', methods=['POST'])
@admin_required_api
def set_betting_results(round_id, question_id):
    """Set betting results for a question and calculate scores.

    Expected JSON body:
    {
        "results": ["Horse 1", "Horse 3", "Horse 2"]  // Winners in order (1st, 2nd, 3rd)
    }
    """
    import json

    round_obj = Round.query.get_or_404(round_id)
    game = round_obj.game

    data = request.get_json()
    if not data or 'results' not in data:
        return jsonify({'success': False, 'error': 'Results required'}), 400

    results = data['results']  # List of winning choices in order

    # Get the question config
    questions = round_obj.get_questions()
    question = None
    for q in questions:
        if q.get('id') == question_id:
            question = q
            break

    if not question or question.get('type') != 'betting':
        return jsonify({'success': False, 'error': 'Question not found or not a betting question'}), 400

    betting_config = question.get('betting', {})
    multipliers = betting_config.get('multipliers', [1])

    # Store the results in the question config
    question['betting_results'] = results
    round_obj.set_questions(questions)

    # Now update all answers for this question
    answers = Answer.query.filter_by(round_id=round_id, question_id=question_id).all()
    updated_count = 0

    for answer in answers:
        try:
            bet_data = json.loads(answer.answer_text)
            bet_amount = bet_data.get('bet_amount', 0)
            choice = bet_data.get('choice', '')

            # Calculate points based on where their choice placed
            # Points are NOT deducted upfront, so:
            # - If won: net gain = bet_amount * multiplier - bet_amount (profit)
            # - If lost: net loss = -bet_amount
            if choice in results:
                place = results.index(choice)  # 0 = 1st, 1 = 2nd, etc.
                if place < len(multipliers):
                    multiplier = multipliers[place]
                    # Win: profit = (multiplier * bet) - bet = bet * (multiplier - 1)
                    # But if multiplier >= 1, they at least get their bet back as profit
                    points = bet_amount * multiplier - bet_amount
                    if points < 0:
                        points = 0  # At worst, break even if multiplier < 1
                else:
                    # Placed but no multiplier for this place - lose bet
                    points = -bet_amount
            else:
                # Didn't place at all - lose bet
                points = -bet_amount

            answer.points = points
            updated_count += 1
        except (json.JSONDecodeError, KeyError, TypeError):
            # Invalid betting data, leave as-is
            pass

    db.session.commit()

    # Emit Socket.IO event
    try:
        from app import socketio
        socketio.emit('betting_results_set', {
            'round_id': round_id,
            'question_id': question_id,
            'results': results
        }, room=f'spreadsheet_{game.id}')
        socketio.emit('score_updated', {
            'round_id': round_id
        }, room=f'spreadsheet_{game.id}')

        # Also emit to game room for players viewing their answers
        # Re-fetch answers to get updated points
        updated_answers = Answer.query.filter_by(round_id=round_id, question_id=question_id).all()
        for answer in updated_answers:
            socketio.emit('answer_score_updated', {
                'round_id': round_id,
                'question_id': question_id,
                'team_id': answer.team_id,
                'points': answer.points
            }, room=f'game_{game.id}')
    except Exception:
        pass

    return jsonify({
        'success': True,
        'updated_count': updated_count,
        'results': results
    })


@bp.route('/round/<int:round_id>/question/<question_id>/betting-results', methods=['GET'])
@admin_required_api
def get_betting_results(round_id, question_id):
    """Get betting results for a question."""
    round_obj = Round.query.get_or_404(round_id)

    questions = round_obj.get_questions()
    for q in questions:
        if q.get('id') == question_id:
            if q.get('type') != 'betting':
                return jsonify({'success': False, 'error': 'Not a betting question'}), 400

            return jsonify({
                'success': True,
                'results': q.get('betting_results', []),
                'choices': q.get('betting', {}).get('choices', []),
                'multipliers': q.get('betting', {}).get('multipliers', [1]),
                'num_places': q.get('betting', {}).get('num_places', 1)
            })

    return jsonify({'success': False, 'error': 'Question not found'}), 404


@bp.route('/round/<int:round_id>/betting-questions', methods=['GET'])
@admin_required_api
def get_betting_questions(round_id):
    """Get all betting questions in a round with their configs and results."""
    round_obj = Round.query.get_or_404(round_id)
    questions = round_obj.get_questions()

    betting_questions = []
    for q in questions:
        if q.get('type') == 'betting':
            betting_config = q.get('betting', {})
            betting_questions.append({
                'id': q.get('id'),
                'text': q.get('text', ''),
                'choices': betting_config.get('choices', []),
                'num_places': betting_config.get('num_places', 1),
                'multipliers': betting_config.get('multipliers', [1]),
                'max_bet': betting_config.get('max_bet', 3),
                'results': q.get('betting_results', [])
            })

    return jsonify({
        'success': True,
        'betting_questions': betting_questions
    })


@bp.route('/game/<int:game_id>/active-timers', methods=['GET'])
def get_active_timers(game_id):
    """Get active timers for a game (public endpoint for players)."""
    import time

    timers = []
    current_time = time.time()

    # Get all rounds for this game with active timers
    rounds_with_timers = Round.query.filter(
        Round.game_id == game_id,
        Round.timer_end_time.isnot(None)
    ).all()

    for round_obj in rounds_with_timers:
        remaining = int(round_obj.timer_end_time - current_time)
        if remaining > 0:
            timers.append({
                'round_id': round_obj.id,
                'seconds_remaining': remaining
            })
        else:
            # Timer expired, clean it up
            round_obj.timer_end_time = None

    # Commit any cleared timers
    if rounds_with_timers:
        db.session.commit()

    print(f'[API] get_active_timers for game_id={game_id}: {timers}')
    return jsonify({
        'success': True,
        'timers': timers
    })
