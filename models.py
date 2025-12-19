"""
Database models for Quiz App.

Defines all SQLAlchemy models for the application:
- Admin: Administrator users who manage games
- Game: Quiz games with unique codes
- Round: Rounds within a game (e.g., History, Music)
- Team: Player teams (per game)
- Answer: Individual question answers with scoring
"""
from datetime import datetime
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# Create database instance here to avoid circular imports
db = SQLAlchemy()


class Admin(UserMixin, db.Model):
    """
    Admin user model for game management.

    Admins can create games, manage rounds, and grade answers.
    Uses Flask-Login's UserMixin for authentication support.
    """
    __tablename__ = 'admin'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        """Hash and store password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify password against stored hash."""
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        """Return prefixed ID for Flask-Login."""
        return f'admin_{self.id}'

    def __repr__(self):
        return f'<Admin {self.username}>'


class Game(db.Model):
    """
    Quiz game model.

    Each game has a unique code for players to join and can
    contain multiple rounds.
    """
    __tablename__ = 'game'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(6), unique=True, nullable=False)
    qr_code_path = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    is_finished = db.Column(db.Boolean, default=False)  # Game completed, show final scores
    custom_columns_json = db.Column(db.Text, nullable=False, default='[]')
    tab_penalty_enabled = db.Column(db.Boolean, default=True)  # Toggle tab penalty tracking
    pause_mode = db.Column(db.String(20), nullable=True)  # null=playing, 'starting'=game starting soon, 'halftime'=half time break

    # Relationships
    rounds = db.relationship('Round', backref='game', lazy='dynamic',
                            cascade='all, delete-orphan')
    teams = db.relationship('Team', backref='game', lazy='dynamic',
                           cascade='all, delete-orphan')

    def get_custom_columns(self):
        """Parse custom columns JSON to Python list."""
        import json
        return json.loads(self.custom_columns_json or '[]')

    def set_custom_columns(self, columns):
        """Serialize custom columns to JSON string."""
        import json
        self.custom_columns_json = json.dumps(columns)

    def __repr__(self):
        return f'<Game {self.name} ({self.code})>'


class Round(db.Model):
    """
    Round model within a game.

    Each round contains questions stored as JSON and can be
    opened/closed by the admin. Rounds can be nested under a parent round.
    """
    __tablename__ = 'round'

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('round.id'), nullable=True)
    name = db.Column(db.String(200), nullable=False)
    order = db.Column(db.Integer, default=0)
    is_open = db.Column(db.Boolean, default=True)
    questions_json = db.Column(db.Text, nullable=False, default='[]')
    timer_end_time = db.Column(db.Float, nullable=True)  # Unix timestamp when timer ends

    # Relationships
    answers = db.relationship('Answer', backref='round', lazy='dynamic',
                             cascade='all, delete-orphan')
    children = db.relationship('Round', backref=db.backref('parent', remote_side=[id]),
                              lazy='dynamic', cascade='all, delete-orphan')

    @property
    def is_nested(self):
        """Return True if this round has a parent."""
        return self.parent_id is not None

    def get_children(self):
        """Get child rounds ordered by their order field."""
        return Round.query.filter_by(parent_id=self.id).order_by(Round.order).all()

    def get_questions(self):
        """Parse JSON string to Python list."""
        import json
        return json.loads(self.questions_json or '[]')

    def set_questions(self, questions):
        """Serialize Python list to JSON string."""
        import json
        self.questions_json = json.dumps(questions)

    def __repr__(self):
        return f'<Round {self.name}>'


class Team(UserMixin, db.Model):
    """
    Player team model.

    Teams belong to a specific game and can submit answers to rounds.
    Uses Flask-Login's UserMixin for authentication support.
    """
    __tablename__ = 'team'

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    custom_scores_json = db.Column(db.Text, nullable=False, default='{}')
    tab_away_seconds = db.Column(db.Integer, default=0)  # Track time spent away from tab
    tab_switch_count = db.Column(db.Integer, default=0)  # Track number of tab switches
    login_count = db.Column(db.Integer, default=0)  # Track number of sign-ins
    logout_count = db.Column(db.Integer, default=0)  # Track number of sign-outs
    manual_penalty_points = db.Column(db.Float, default=0)  # Manual penalty points (subtracted from score)

    # Relationships
    answers = db.relationship('Answer', backref='team', lazy='dynamic',
                             cascade='all, delete-orphan')

    # Unique constraint: team name must be unique within a game
    __table_args__ = (
        db.UniqueConstraint('game_id', 'name', name='unique_team_per_game'),
    )

    def set_password(self, password):
        """Hash and store password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify password against stored hash."""
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        """Return prefixed ID for Flask-Login."""
        return f'team_{self.id}'

    def get_custom_scores(self):
        """Parse custom scores JSON to Python dict."""
        import json
        return json.loads(self.custom_scores_json or '{}')

    def set_custom_scores(self, scores):
        """Serialize custom scores to JSON string."""
        import json
        self.custom_scores_json = json.dumps(scores)

    @property
    def tab_penalty_points(self):
        """Calculate penalty points from tab away time (1 point per 10 seconds)."""
        return (self.tab_away_seconds or 0) // 10

    def __repr__(self):
        return f'<Team {self.name}>'


class Answer(db.Model):
    """
    Individual answer model.

    Stores each team's answer to a specific question within a round,
    along with scoring information.
    """
    __tablename__ = 'answer'

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    round_id = db.Column(db.Integer, db.ForeignKey('round.id'), nullable=False)
    question_id = db.Column(db.String(50), nullable=False)
    answer_text = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Scoring fields
    points = db.Column(db.Float, default=0.0)
    bonus_points = db.Column(db.Float, default=0.0)
    penalty_points = db.Column(db.Float, default=0.0)
    notes = db.Column(db.Text)

    @property
    def total_points(self):
        """Calculate total points (points + bonus - penalty)."""
        return (self.points or 0) + (self.bonus_points or 0) - (self.penalty_points or 0)

    def __repr__(self):
        return f'<Answer {self.question_id} by Team {self.team_id}>'


class ResubmitPermission(db.Model):
    """
    Tracks which teams are allowed to resubmit answers for a round.

    Created by admin, consumed when team resubmits.
    """
    __tablename__ = 'resubmit_permission'

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    round_id = db.Column(db.Integer, db.ForeignKey('round.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Unique constraint: one permission per team/round combo
    __table_args__ = (
        db.UniqueConstraint('team_id', 'round_id', name='unique_resubmit_permission'),
    )

    def __repr__(self):
        return f'<ResubmitPermission Team {self.team_id} Round {self.round_id}>'
