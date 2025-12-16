"""
Authentication routes for Quiz App.

Handles login/logout for both admin users and player teams.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user

from models import db, Admin, Team, Game
from forms import AdminLoginForm, TeamLoginForm, TeamReloginForm

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """
    Admin login page.

    GET: Display login form
    POST: Verify credentials and log in
    """
    # Redirect if already logged in as admin
    if current_user.is_authenticated and current_user.get_id().startswith('admin_'):
        return redirect(url_for('admin.dashboard'))

    form = AdminLoginForm()

    if form.validate_on_submit():
        admin = Admin.query.filter_by(username=form.username.data).first()

        if admin and admin.check_password(form.password.data):
            login_user(admin, remember=True)
            flash('Logged in successfully.', 'success')

            # Redirect to requested page or dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('admin.dashboard'))

        flash('Invalid username or password.', 'danger')

    return render_template('admin/login.html', form=form)


@bp.route('/player/login', methods=['GET', 'POST'])
@bp.route('/player/login/<game_code>', methods=['GET', 'POST'])
def player_login(game_code=None):
    """
    Player/Team login or signup page.

    If team doesn't exist for the game, creates a new team.
    If team exists, verifies password.

    Args:
        game_code: Optional game code from URL
    """
    # Redirect if already logged in as team
    if current_user.is_authenticated and current_user.get_id().startswith('team_'):
        team = Team.query.get(int(current_user.get_id().split('_')[1]))
        if team:
            return redirect(url_for('player.quiz', game_code=team.game.code))

    form = TeamLoginForm()

    # Pre-fill game code if provided in URL
    if game_code and request.method == 'GET':
        form.game_code.data = game_code.upper()

    if form.validate_on_submit():
        game_code = form.game_code.data.upper()
        team_name = form.team_name.data.strip()
        password = form.password.data

        # Get the game
        game = Game.query.filter_by(code=game_code).first()
        if not game:
            flash('Invalid game code.', 'danger')
            return render_template('player/login.html', form=form)

        # Check if team already exists for this game
        existing_team = Team.query.filter_by(game_id=game.id, name=team_name).first()

        if existing_team:
            # Team exists - verify password
            if existing_team.check_password(password):
                login_user(existing_team, remember=True)
                flash(f'Welcome back, {team_name}!', 'success')
                return redirect(url_for('player.quiz', game_code=game_code))
            else:
                flash('team_exists', 'team_error')  # Special marker for template
        else:
            # Create new team
            new_team = Team(
                game_id=game.id,
                name=team_name
            )
            new_team.set_password(password)

            try:
                db.session.add(new_team)
                db.session.commit()
                login_user(new_team, remember=True)
                flash(f'Team "{team_name}" created! Welcome to the quiz.', 'success')
                # Redirect new teams to instructions first
                return redirect(url_for('player.instructions', game_code=game_code, new=1))
            except Exception as e:
                db.session.rollback()
                flash('Error creating team. Please try again.', 'danger')

    return render_template('player/login.html', form=form, game_code=game_code)


@bp.route('/player/relogin/<game_code>', methods=['GET', 'POST'])
def player_relogin(game_code):
    """
    Simplified login for returning teams.

    Used when team is already registered and needs to log back in.
    """
    game = Game.query.filter_by(code=game_code.upper()).first()
    if not game:
        flash('Invalid game code.', 'danger')
        return redirect(url_for('index'))

    form = TeamReloginForm()

    if form.validate_on_submit():
        team_name = form.team_name.data.strip()
        password = form.password.data

        team = Team.query.filter_by(game_id=game.id, name=team_name).first()

        if team and team.check_password(password):
            login_user(team, remember=True)
            flash(f'Welcome back, {team_name}!', 'success')
            return redirect(url_for('player.quiz', game_code=game_code))

        flash('Invalid team name or password.', 'danger')

    return render_template('player/relogin.html', form=form, game=game)


@bp.route('/logout')
@login_required
def logout():
    """Log out current user (admin or team)."""
    logout_user()
    # Clear any pending flash messages before showing logout message
    session.pop('_flashes', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))
