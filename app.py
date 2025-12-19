"""
Quiz App - Flask Application Entry Point

A Flask-based quiz platform combining the simplicity of Google Forms
with advanced features like timed rounds, team management, and
spreadsheet-style answer grading.
"""
import os
import time
from flask import Flask, render_template
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

from config import Config, config
from models import db

# Initialize extensions (db is imported from models)
login_manager = LoginManager()
socketio = SocketIO()
migrate = Migrate()
csrf = CSRFProtect()

# Active timers storage: {round_id: {'end_time': timestamp, 'game_id': int}}
active_timers = {}

# Optional rate limiter (only if Flask-Limiter is installed)
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    limiter = Limiter(key_func=get_remote_address)
except ImportError:
    limiter = None


def create_app(config_name=None):
    """
    Application factory function.

    Creates and configures the Flask application with all necessary
    extensions and blueprints.

    Args:
        config_name: Configuration name ('development', 'production', 'testing')
                    or Config class. Defaults to FLASK_ENV environment variable.

    Returns:
        Configured Flask application instance
    """
    app = Flask(__name__)

    # Determine configuration
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    if isinstance(config_name, str):
        config_class = config.get(config_name, config['default'])
    else:
        config_class = config_name

    app.config.from_object(config_class)

    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")

    # Initialize rate limiter if available and enabled
    if limiter and app.config.get('RATELIMIT_ENABLED', True):
        limiter.init_app(app)

    # Configure login manager
    login_manager.login_view = 'auth.player_login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    # Import models (after db is initialized)
    from models import Admin, Team

    @login_manager.user_loader
    def load_user(user_id):
        """
        Load user from session.

        User IDs are prefixed to distinguish between admin and team users:
        - 'admin_X' for Admin users
        - 'team_X' for Team users

        Args:
            user_id: Prefixed user identifier string

        Returns:
            Admin or Team instance, or None if not found
        """
        if not user_id:
            return None

        try:
            if user_id.startswith('admin_'):
                admin_id = int(user_id.split('_')[1])
                return Admin.query.get(admin_id)
            elif user_id.startswith('team_'):
                team_id = int(user_id.split('_')[1])
                return Team.query.get(team_id)
        except (ValueError, IndexError):
            return None

        return None

    # Register template filters
    import json

    @app.template_filter('fromjson')
    def fromjson_filter(value):
        """Parse a JSON string into a Python object."""
        try:
            return json.loads(value) if value else None
        except (json.JSONDecodeError, TypeError):
            return None

    # Register blueprints
    from routes import auth, player, admin, api
    app.register_blueprint(auth.bp)
    app.register_blueprint(player.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(api.bp)

    # Exempt API routes from CSRF for AJAX calls
    csrf.exempt(api.bp)

    # Basic routes
    @app.route('/')
    def index():
        """Landing page for the quiz application."""
        return render_template('index.html')

    # Create database tables and default admin user
    with app.app_context():
        db.create_all()
        create_default_admin(app)

    # Register Socket.IO event handlers
    register_socketio_handlers(socketio)

    return app


def register_socketio_handlers(sio):
    """Register Socket.IO event handlers."""
    from flask_socketio import emit, join_room, leave_room
    from flask import request

    @sio.on('connect')
    def handle_connect():
        """Handle client connection."""
        print(f'Client connected: {request.sid}')

    @sio.on('disconnect')
    def handle_disconnect():
        """Handle client disconnection."""
        print(f'Client disconnected: {request.sid}')

    @sio.on('join_game')
    def handle_join_game(data):
        """Player joins a game room."""
        game_id = data.get('game_id')
        if game_id:
            room = f'game_{game_id}'
            join_room(room)
            print(f'Client {request.sid} joined room {room}')
            emit('joined_game', {'game_id': game_id})

    @sio.on('join_admin')
    def handle_join_admin(data):
        """Admin joins a game room for control."""
        game_id = data.get('game_id')
        if game_id:
            join_room(f'game_{game_id}')
            join_room(f'admin_{game_id}')
            print(f'Admin {request.sid} joined rooms game_{game_id} and admin_{game_id}')
            emit('joined_admin', {'game_id': game_id})

    @sio.on('timer_started')
    def handle_timer_started(data):
        """Broadcast timer start to all players in game."""
        game_id = data.get('game_id')
        round_id = data.get('round_id')
        seconds = data.get('seconds', 60)
        if game_id and round_id:
            # Store timer end time in database for persistence
            from models import Round
            round_obj = Round.query.get(round_id)
            if round_obj:
                round_obj.timer_end_time = time.time() + seconds
                db.session.commit()
                print(f'[Socket] Stored timer in DB: round_id={round_id}, timer_end_time={round_obj.timer_end_time}')

            room = f'game_{game_id}'
            print(f'Broadcasting timer_started ({seconds}s) for round {round_id} to room {room}')
            sio.emit('timer_started', {'seconds': seconds, 'round_id': round_id}, room=room)

    @sio.on('timer_stopped')
    def handle_timer_stopped(data):
        """Broadcast timer stop to all players in game."""
        game_id = data.get('game_id')
        round_id = data.get('round_id')
        if game_id:
            # Clear timer from database
            if round_id:
                from models import Round
                round_obj = Round.query.get(round_id)
                if round_obj:
                    round_obj.timer_end_time = None
                    db.session.commit()
                    print(f'[Socket] Cleared timer from DB: round_id={round_id}')

            room = f'game_{game_id}'
            print(f'Broadcasting timer_stopped for round {round_id} to room {room}')
            sio.emit('timer_stopped', {'round_id': round_id}, room=room)

    @sio.on('round_status_changed')
    def handle_round_status_changed(data):
        """Broadcast round status change to all players in game."""
        game_id = data.get('game_id')
        round_id = data.get('round_id')
        is_open = data.get('is_open')
        if game_id:
            room = f'game_{game_id}'
            print(f'Broadcasting round_status_changed for round {round_id} (open={is_open}) to room {room}')
            sio.emit('round_status_changed', {'round_id': round_id, 'is_open': is_open}, room=room)

    @sio.on('round_ending')
    def handle_round_ending(data):
        """Broadcast round ending to all players - triggers auto-submit."""
        game_id = data.get('game_id')
        round_id = data.get('round_id')
        if game_id:
            room = f'game_{game_id}'
            print(f'Broadcasting round_ending for round {round_id} to room {room}')
            sio.emit('round_ending', {'round_id': round_id}, room=room)

    @sio.on('round_closed')
    def handle_round_closed(data):
        """Broadcast round closed to all players in game."""
        game_id = data.get('game_id')
        round_id = data.get('round_id')
        if game_id:
            room = f'game_{game_id}'
            print(f'Broadcasting round_closed for round {round_id} to room {room}')
            sio.emit('round_closed', {'round_id': round_id}, room=room)

            # Check if all rounds are now closed (game finalising)
            from models import Round
            all_rounds = Round.query.filter_by(game_id=game_id).all()
            all_closed = all(not r.is_open for r in all_rounds)
            if all_closed and len(all_rounds) > 0:
                print(f'All rounds closed - broadcasting game_finalising to room {room}')
                sio.emit('game_finalising', {'game_id': game_id}, room=room)

    @sio.on('submission_cleared')
    def handle_submission_cleared(data):
        """Broadcast submission cleared to all players in game."""
        game_id = data.get('game_id')
        round_id = data.get('round_id')
        team_id = data.get('team_id')
        if game_id:
            room = f'game_{game_id}'
            print(f'Broadcasting submission_cleared for round {round_id}, team {team_id} to room {room}')
            sio.emit('submission_cleared', {'round_id': round_id, 'team_id': team_id}, room=room)

    @sio.on('join_spreadsheet')
    def handle_join_spreadsheet(data):
        """Admin joins spreadsheet room for real-time sync."""
        game_id = data.get('game_id')
        if game_id:
            spreadsheet_room = f'spreadsheet_{game_id}'
            game_room = f'game_{game_id}'
            join_room(spreadsheet_room)
            join_room(game_room)  # Also join game room to receive score_updated events
            print(f'Admin {request.sid} joined rooms: {spreadsheet_room}, {game_room}')
            emit('joined_spreadsheet', {'game_id': game_id})

    @sio.on('team_away_status_changed')
    def handle_team_away_status(data):
        """Broadcast team away/back status for live stopwatch in admin view."""
        game_id = data.get('game_id')
        team_id = data.get('team_id')
        is_away = data.get('is_away')
        current_seconds = data.get('current_seconds', 0)
        print(f'[Socket] team_away_status_changed received: game={game_id}, team={team_id}, away={is_away}')
        if game_id and team_id is not None:
            room = f'spreadsheet_{game_id}'
            print(f'[Socket] Broadcasting to room {room}')
            sio.emit('team_away_status_changed', {
                'team_id': team_id,
                'is_away': is_away,
                'current_seconds': current_seconds
            }, room=room)

    @sio.on('tab_penalty_tracking_changed')
    def handle_tab_penalty_tracking_changed(data):
        """Broadcast tab penalty tracking change to all players in game."""
        game_id = data.get('game_id')
        enabled = data.get('enabled')
        print(f'[Socket] tab_penalty_tracking_changed received: game={game_id}, enabled={enabled}')
        if game_id is not None:
            room = f'game_{game_id}'
            print(f'[Socket] Broadcasting to room {room}')
            sio.emit('tab_penalty_tracking_changed', {
                'enabled': enabled
            }, room=room)


def create_default_admin(app):
    """
    Create default admin user if none exists.

    Uses ADMIN_PASSWORD from environment/config.

    Args:
        app: Flask application instance
    """
    from models import Admin

    if Admin.query.filter_by(username='admin').first() is None:
        admin = Admin(username='admin')
        admin.set_password(app.config['ADMIN_PASSWORD'])
        db.session.add(admin)
        db.session.commit()
        print("Default admin user created (username: admin)")


# Create application instance
app = create_app()


if __name__ == '__main__':
    # Ensure qrcodes directory exists
    os.makedirs('static/qrcodes', exist_ok=True)

    # Run with SocketIO support
    socketio.run(app, debug=True, host='0.0.0.0', port=5777)
