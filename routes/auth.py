"""
Authentication routes for Quiz App.

Handles login/logout for admin users (via centralised SSO) and player teams
(via Flask-Login).
"""
import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user

from models import db, Admin, Team, Game, Subscription
from forms import TeamLoginForm, TeamReloginForm

try:
    from lozzalingo.core import db_log
except ImportError:
    def db_log(*args, **kwargs):
        pass  # Graceful fallback if framework not available

bp = Blueprint('auth', __name__, url_prefix='/auth')


def _sso_login_redirect(next_url=None):
    """Build a redirect to the centralised SSO login page."""
    auth_url = os.getenv('AUTH_SERVICE_URL', 'https://auth.laurence.computer')
    base_url = current_app.config.get('BASE_URL', request.host_url.rstrip('/'))
    redirect_url = next_url or f'{base_url}/admin/dashboard'
    return redirect(f'{auth_url}/login?redirect={redirect_url}')


@bp.route('/login')
def login():
    """Redirect alias for Lozzalingo framework compatibility.

    Framework modules (analytics, ops) redirect to url_for('auth.login')
    when admin is not logged in. This redirects to centralised SSO.
    """
    next_url = request.args.get('next')
    return _sso_login_redirect(next_url)


@bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login - redirects to centralised SSO at auth.laurence.computer."""
    next_url = request.args.get('next')
    return _sso_login_redirect(next_url)


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
                # Track login
                existing_team.login_count = (existing_team.login_count or 0) + 1
                db.session.commit()

                # Emit socket event for admin to see login
                try:
                    from app import socketio
                    socketio.emit('team_login', {
                        'team_id': existing_team.id,
                        'login_count': existing_team.login_count
                    }, room=f'game_{game.id}')
                except Exception as e:
                    print(f'[Auth] Error emitting team_login: {e}')

                login_user(existing_team, remember=True)
                flash(f'Welcome back, {team_name}!', 'success')
                return redirect(url_for('player.quiz', game_code=game_code))
            else:
                flash('team_exists', 'team_error')  # Special marker for template
        else:
            # Check team limit based on game owner's subscription
            if game.admin_id:
                admin = Admin.query.get(game.admin_id)
                # Platform admin bypasses team limits
                if not (admin and admin.email == 'laurencedotcomputer@gmail.com'):
                    sub = Subscription.query.filter_by(admin_id=game.admin_id).first()
                    max_teams = sub.max_teams if sub else 5
                    current_team_count = Team.query.filter_by(game_id=game.id).count()
                    if current_team_count >= max_teams:
                        flash(f'This game is full ({max_teams} teams maximum).', 'danger')
                        return render_template('player/login.html', form=form)

            # Create new team
            new_team = Team(
                game_id=game.id,
                name=team_name,
                login_count=1
            )
            new_team.set_password(password)

            try:
                db.session.add(new_team)
                db.session.commit()

                # Emit socket event to notify admin of new team
                try:
                    from app import socketio
                    socketio.emit('team_joined', {
                        'team_id': new_team.id,
                        'team_name': new_team.name,
                        'game_id': game.id
                    }, room=f'game_{game.id}')
                except Exception as e:
                    print(f'[Auth] Error emitting team_joined: {e}')

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
            # Track login
            team.login_count = (team.login_count or 0) + 1
            db.session.commit()

            # Emit socket event for admin to see login
            try:
                from app import socketio
                socketio.emit('team_login', {
                    'team_id': team.id,
                    'login_count': team.login_count
                }, room=f'game_{game.id}')
            except Exception as e:
                print(f'[Auth] Error emitting team_login: {e}')

            login_user(team, remember=True)
            flash(f'Welcome back, {team_name}!', 'success')
            return redirect(url_for('player.quiz', game_code=game_code))

        flash('Invalid team name or password.', 'danger')

    return render_template('player/relogin.html', form=form, game=game)


@bp.route('/logout')
def logout():
    """Log out current user (admin or team).

    For teams: tracks logout via Flask-Login.
    For SSO admins: clears session bridge vars. The auth_token cookie is
    domain-scoped to .laurence.computer so it cannot be cleared from here,
    but clearing the session is sufficient for the quiz app.
    """
    # Track logout for teams
    if current_user.is_authenticated and current_user.get_id().startswith('team_'):
        team = Team.query.get(int(current_user.get_id().split('_')[1]))
        if team:
            team.logout_count = (team.logout_count or 0) + 1
            game_id = team.game_id
            db.session.commit()

            # Emit socket event for admin to see logout
            try:
                from app import socketio
                socketio.emit('team_logout', {
                    'team_id': team.id,
                    'logout_count': team.logout_count
                }, room=f'game_{game_id}')
            except Exception as e:
                print(f'[Auth] Error emitting team_logout: {e}')

    if current_user.is_authenticated:
        logout_user()

    # Clear Lozzalingo session bridge
    session.pop('admin_id', None)
    session.pop('admin_email', None)
    # Clear any pending flash messages before showing logout message
    session.pop('_flashes', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))
