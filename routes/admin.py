"""
Admin routes for Quiz App.

Handles game management, round creation, and administrative functions.
"""
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user

from models import db, Admin, Game, Round, Team, Answer
from sqlalchemy import func
from forms import CreateGameForm, CreateRoundForm, AdminSettingsForm
from utils import generate_unique_code, generate_qr_code

bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    """
    Decorator to require admin authentication.

    Wraps login_required and additionally checks that
    the current user is an Admin (not a Team).
    """
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.get_id().startswith('admin_'):
            flash('Admin access required.', 'danger')
            return redirect(url_for('auth.admin_login'))
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/dashboard')
@admin_required
def dashboard():
    """
    Admin dashboard showing all games.

    Displays list of games with links to manage each.
    """
    games = Game.query.order_by(Game.created_at.desc()).all()
    return render_template('admin/dashboard.html', games=games)


@bp.route('/create_game', methods=['GET', 'POST'])
@admin_required
def create_game():
    """
    Create a new quiz game.

    Generates unique code and QR code for the game.
    """
    form = CreateGameForm()

    if form.validate_on_submit():
        # Generate unique code
        code = generate_unique_code()
        while Game.query.filter_by(code=code).first():
            code = generate_unique_code()

        # Create game
        game = Game(
            name=form.name.data.strip(),
            code=code
        )

        db.session.add(game)
        db.session.flush()  # Get the game ID

        # Generate QR code
        base_url = current_app.config.get('BASE_URL', 'http://localhost:5777')
        qr_path = generate_qr_code(code, game.id, base_url)
        game.qr_code_path = qr_path

        db.session.commit()

        flash(f'Game "{game.name}" created with code {game.code}', 'success')
        return redirect(url_for('admin.edit_game', game_id=game.id))

    return render_template('admin/create_game.html', form=form)


@bp.route('/game/<int:game_id>/edit')
@admin_required
def edit_game(game_id):
    """
    Edit game page showing rounds and settings.

    Args:
        game_id: Database ID of the game
    """
    game = Game.query.get_or_404(game_id)
    # Get only top-level rounds (no parent)
    top_rounds = Round.query.filter_by(game_id=game.id, parent_id=None).order_by(Round.order).all()
    teams = Team.query.filter_by(game_id=game.id).all()

    # Calculate team scores (full calculation: points + bonus - penalty + custom - tab_penalty)
    team_scores = {}
    for team in teams:
        # Sum base points, bonus, and penalties from answers
        score_result = db.session.query(
            func.coalesce(func.sum(Answer.points), 0) +
            func.coalesce(func.sum(Answer.bonus_points), 0) -
            func.coalesce(func.sum(Answer.penalty_points), 0)
        ).filter(Answer.team_id == team.id).scalar() or 0

        # Add custom scores
        custom_scores = team.get_custom_scores()
        custom_total = sum(custom_scores.values()) if custom_scores else 0

        # Subtract tab penalty
        tab_penalty = team.tab_penalty_points

        team_scores[team.id] = int(score_result + custom_total - tab_penalty)

    return render_template('admin/edit_game.html', game=game, rounds=top_rounds, teams=teams, team_scores=team_scores)


@bp.route('/game/<int:game_id>/scores')
@admin_required
def admin_scores(game_id):
    """
    Admin-only scoreboard that always shows real-time scores.
    """
    game = Game.query.get_or_404(game_id)
    return render_template('admin/scores.html', game=game)


@bp.route('/game/<int:game_id>/create_round', methods=['GET', 'POST'])
@admin_required
def create_round(game_id):
    """
    Create a new round for a game.

    Args:
        game_id: Database ID of the game
    """
    from flask import request
    game = Game.query.get_or_404(game_id)
    form = CreateRoundForm()

    # Check if creating a sub-round
    parent_id = request.args.get('parent_id', type=int)
    parent_round = None
    if parent_id:
        parent_round = Round.query.get_or_404(parent_id)
        # Verify parent belongs to this game
        if parent_round.game_id != game.id:
            parent_round = None
            parent_id = None

    if form.validate_on_submit():
        if parent_id:
            # Get max order for sibling rounds (same parent)
            max_order = db.session.query(db.func.max(Round.order))\
                .filter(Round.parent_id == parent_id).scalar() or 0
        else:
            # Get max order for top-level rounds
            max_order = db.session.query(db.func.max(Round.order))\
                .filter(Round.game_id == game.id, Round.parent_id == None).scalar() or 0

        round_obj = Round(
            game_id=game.id,
            parent_id=parent_id,
            name=form.name.data.strip(),
            order=max_order + 1,
            questions_json='[]'
        )

        db.session.add(round_obj)
        db.session.commit()

        flash(f'Round "{round_obj.name}" created.', 'success')
        return redirect(url_for('admin.edit_questions', round_id=round_obj.id))

    return render_template('admin/create_round.html', form=form, game=game, parent_round=parent_round)


@bp.route('/round/<int:round_id>/edit_questions')
@admin_required
def edit_questions(round_id):
    """
    Edit questions for a round using form builder.

    Args:
        round_id: Database ID of the round
    """
    round_obj = Round.query.get_or_404(round_id)
    game = round_obj.game

    return render_template('admin/edit_questions.html', round=round_obj, game=game)


@bp.route('/game/<int:game_id>/spreadsheet')
@admin_required
def spreadsheet(game_id):
    """
    Spreadsheet view of all answers for grading.

    Args:
        game_id: Database ID of the game
    """
    game = Game.query.get_or_404(game_id)
    rounds = Round.query.filter_by(game_id=game.id).order_by(Round.order).all()
    teams = Team.query.filter_by(game_id=game.id).order_by(Team.name).all()

    return render_template('admin/spreadsheet.html', game=game, rounds=rounds, teams=teams)


@bp.route('/game/<int:game_id>/live_control')
@admin_required
def live_control(game_id):
    """
    Live control panel for managing rounds in real-time.

    Args:
        game_id: Database ID of the game
    """
    game = Game.query.get_or_404(game_id)
    # Get only top-level rounds (no parent)
    top_rounds = Round.query.filter_by(game_id=game.id, parent_id=None).order_by(Round.order).all()
    teams = Team.query.filter_by(game_id=game.id).all()

    return render_template('admin/live_control.html', game=game, rounds=top_rounds, teams=teams)


@bp.route('/game/<int:game_id>/toggle_active', methods=['POST'])
@admin_required
def toggle_game_active(game_id):
    """Toggle game active status."""
    game = Game.query.get_or_404(game_id)
    game.is_active = not game.is_active
    db.session.commit()

    status = 'activated' if game.is_active else 'deactivated'
    flash(f'Game {status}.', 'success')
    return redirect(url_for('admin.edit_game', game_id=game.id))


@bp.route('/game/<int:game_id>/delete', methods=['POST'])
@admin_required
def delete_game(game_id):
    """Delete a game and all associated data."""
    game = Game.query.get_or_404(game_id)
    game_name = game.name

    db.session.delete(game)
    db.session.commit()

    flash(f'Game "{game_name}" deleted.', 'success')
    return redirect(url_for('admin.dashboard'))


@bp.route('/round/<int:round_id>/delete', methods=['POST'])
@admin_required
def delete_round(round_id):
    """Delete a round and all associated answers."""
    round_obj = Round.query.get_or_404(round_id)
    game_id = round_obj.game_id
    round_name = round_obj.name

    db.session.delete(round_obj)
    db.session.commit()

    flash(f'Round "{round_name}" deleted.', 'success')
    return redirect(url_for('admin.edit_game', game_id=game_id))


@bp.route('/game/<int:game_id>/scoreboard')
@admin_required
def scoreboard(game_id):
    """
    Animated scoreboard view for displaying scores.

    Args:
        game_id: Database ID of the game
    """
    game = Game.query.get_or_404(game_id)
    return render_template('scoreboard.html', game=game, is_admin=True)


@bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    """Admin settings page to update username and password."""
    admin_id = int(current_user.get_id().replace('admin_', ''))
    admin = Admin.query.get_or_404(admin_id)
    form = AdminSettingsForm(obj=admin)

    if form.validate_on_submit():
        # Verify current password
        if not admin.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
            return render_template('admin/settings.html', form=form)

        # Update username
        admin.username = form.username.data

        # Update password if provided
        if form.new_password.data:
            admin.set_password(form.new_password.data)

        db.session.commit()
        flash('Settings updated successfully.', 'success')
        return redirect(url_for('admin.settings'))

    return render_template('admin/settings.html', form=form)
