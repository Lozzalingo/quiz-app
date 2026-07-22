"""
Database models for Quiz App.

Defines all SQLAlchemy models for the application:
- Admin: Administrator users who manage games
- Game: Quiz games with unique codes
- Round: Rounds within a game (e.g., History, Music)
- Team: Player teams (per game)
- Answer: Individual question answers with scoring
- MediaUpload: Photo/video file uploads with audit tracking
- ChatMessage: In-app messaging between teams and admin
- RoundBonus: Bonus points awarded per round based on correct answer thresholds
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
    email = db.Column(db.String(320), nullable=True)
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
    admin_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=True)  # nullable for legacy games
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(6), unique=True, nullable=False)
    qr_code_path = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    is_finished = db.Column(db.Boolean, default=False)  # Game completed, show final scores
    custom_columns_json = db.Column(db.Text, nullable=False, default='[]')
    tab_penalty_enabled = db.Column(db.Boolean, default=True)  # Toggle tab penalty tracking
    pause_mode = db.Column(db.String(20), nullable=True)  # null=playing, 'starting'=game starting soon, 'halftime'=half time break

    # Game type and timer
    game_type = db.Column(db.String(30), nullable=False, default='quiz')  # quiz, treasure_hunt, adventure
    timer_end_time = db.Column(db.Float, nullable=True)  # Game-level timer (Unix timestamp)
    round_label = db.Column(db.String(50), nullable=False, default='Round')  # Customisable label for rounds
    is_gallery_public = db.Column(db.Boolean, default=False)  # Gallery visible to teams after game ends

    # Relationships
    rounds = db.relationship('Round', backref='game', lazy='dynamic',
                            cascade='all, delete-orphan')
    teams = db.relationship('Team', backref='game', lazy='dynamic',
                           cascade='all, delete-orphan')
    media_uploads = db.relationship('MediaUpload', backref='game', lazy='dynamic',
                                   cascade='all, delete-orphan')
    chat_messages = db.relationship('ChatMessage', backref='game', lazy='dynamic',
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

    # Submission mode and bonus config
    submission_mode = db.Column(db.String(20), nullable=False, default='all_at_once')  # all_at_once, one_by_one
    bonus_thresholds_json = db.Column(db.Text, nullable=False, default='[]')  # [{correct_count: 5, bonus_points: 50}]
    branching_rules_json = db.Column(db.Text, nullable=True)  # [{question_id, answer_match, target_round_id}]

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

    def get_bonus_thresholds(self):
        """Parse bonus thresholds JSON to Python list."""
        import json
        return json.loads(self.bonus_thresholds_json or '[]')

    def set_bonus_thresholds(self, thresholds):
        """Serialize bonus thresholds to JSON string."""
        import json
        self.bonus_thresholds_json = json.dumps(thresholds)

    def get_branching_rules(self):
        """Parse branching rules JSON to Python list."""
        import json
        return json.loads(self.branching_rules_json or '[]')

    def set_branching_rules(self, rules):
        """Serialize branching rules to JSON string."""
        import json
        self.branching_rules_json = json.dumps(rules)

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


class Subscription(db.Model):
    """
    Tracks admin subscriptions and event purchases.

    plan_type: 'free', 'event', 'pro_monthly', 'pro_yearly'
    For event purchases, games_remaining tracks unused credits.
    For pro subscriptions, games_per_month and max_teams define limits.
    """
    __tablename__ = 'subscription'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=False)

    # Plan details
    plan_type = db.Column(db.String(20), nullable=False, default='free')  # free, event, pro_monthly, pro_yearly
    games_per_month = db.Column(db.Integer, default=0)  # 0 for free/event, 1/4/8/16/32 for pro
    max_teams = db.Column(db.Integer, default=5)  # 5/10/20/50/100

    # Event purchases: how many game credits remain
    event_games_remaining = db.Column(db.Integer, default=0)

    # Stripe references
    stripe_customer_id = db.Column(db.String(255), nullable=True)
    stripe_subscription_id = db.Column(db.String(255), nullable=True)
    stripe_price_id = db.Column(db.String(255), nullable=True)

    # Status
    is_active = db.Column(db.Boolean, default=True)
    current_period_start = db.Column(db.DateTime, nullable=True)
    current_period_end = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Tracking
    total_games_created = db.Column(db.Integer, default=0)  # lifetime count (never resets)
    games_created_this_period = db.Column(db.Integer, default=0)  # resets each billing cycle

    # Relationship
    admin = db.relationship('Admin', backref=db.backref('subscription', uselist=False))

    @property
    def can_create_game(self):
        """Check if the admin can create another game."""
        if self.plan_type == 'free':
            return self.total_games_created < 1
        elif self.plan_type == 'event':
            return self.event_games_remaining > 0
        elif self.plan_type in ('pro_monthly', 'pro_yearly'):
            if not self.is_active:
                return False
            return self.games_created_this_period < self.games_per_month
        return False

    @property
    def games_remaining(self):
        """How many games the admin can still create this period."""
        if self.plan_type == 'free':
            return max(0, 1 - self.total_games_created)
        elif self.plan_type == 'event':
            return self.event_games_remaining
        elif self.plan_type in ('pro_monthly', 'pro_yearly'):
            if not self.is_active:
                return 0
            return max(0, self.games_per_month - self.games_created_this_period)
        return 0

    @property
    def plan_display(self):
        """Human-readable plan name."""
        if self.plan_type == 'free':
            return 'Free'
        elif self.plan_type == 'event':
            return f'Event ({self.max_teams} teams)'
        elif self.plan_type in ('pro_monthly', 'pro_yearly'):
            billing = 'Monthly' if self.plan_type == 'pro_monthly' else 'Yearly'
            return f'Pro {billing} ({self.games_per_month}/month, {self.max_teams} teams)'
        return 'Unknown'

    def __repr__(self):
        return f'<Subscription {self.plan_type} for Admin {self.admin_id}>'


class PaymentEvent(db.Model):
    """
    Log of all payment events from Stripe webhooks.
    Used for auditing and email triggers.
    """
    __tablename__ = 'payment_event'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=True)
    event_type = db.Column(db.String(50), nullable=False)  # checkout_completed, invoice_paid, subscription_cancelled, payment_failed
    stripe_event_id = db.Column(db.String(255), unique=True, nullable=False)
    stripe_customer_id = db.Column(db.String(255), nullable=True)
    amount = db.Column(db.Integer, nullable=True)  # in pence
    currency = db.Column(db.String(3), default='gbp')
    plan_type = db.Column(db.String(20), nullable=True)
    metadata_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<PaymentEvent {self.event_type} {self.stripe_event_id}>'


class BetaRequest(db.Model):
    """
    Beta access request model.

    Stores name and email from users requesting early access
    to the quiz app while it is in beta.
    """
    __tablename__ = 'beta_request'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(320), nullable=False)
    source = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<BetaRequest {self.email} ({self.source})'


class MediaUpload(db.Model):
    """
    Photo/video upload for task-based questions.

    Tracks the upload lifecycle (queued -> processing -> complete/failed)
    and the audit lifecycle (unaudited -> accepted/rejected).
    """
    __tablename__ = 'media_upload'

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    round_id = db.Column(db.Integer, db.ForeignKey('round.id'), nullable=False)
    question_id = db.Column(db.String(50), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)

    # File details
    original_filename = db.Column(db.String(500), nullable=False)
    storage_key = db.Column(db.String(500), nullable=True)  # DO Spaces key
    storage_url = db.Column(db.String(1000), nullable=True)  # Public/signed URL
    file_type = db.Column(db.String(20), nullable=False)  # image, video
    mime_type = db.Column(db.String(100), nullable=True)
    file_size_bytes = db.Column(db.Integer, nullable=True)
    duration_seconds = db.Column(db.Float, nullable=True)  # For video files

    # Upload status
    upload_status = db.Column(db.String(20), nullable=False, default='queued')  # queued, uploading, processing, complete, failed
    upload_progress = db.Column(db.Integer, default=0)  # 0-100
    error_message = db.Column(db.Text, nullable=True)

    # Audit status
    audit_status = db.Column(db.String(20), nullable=False, default='unaudited')  # unaudited, accepted, rejected_resubmit, rejected_final
    audit_notes = db.Column(db.Text, nullable=True)
    audited_at = db.Column(db.DateTime, nullable=True)
    audited_by = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    team = db.relationship('Team', backref=db.backref('media_uploads', lazy='dynamic'))
    round = db.relationship('Round', backref=db.backref('media_uploads', lazy='dynamic'))

    @property
    def is_complete(self):
        """Check if upload finished successfully."""
        return self.upload_status == 'complete'

    @property
    def is_rejected(self):
        """Check if submission was rejected."""
        return self.audit_status in ('rejected_resubmit', 'rejected_final')

    @property
    def can_resubmit(self):
        """Check if team can re-upload."""
        return self.audit_status == 'rejected_resubmit'

    def __repr__(self):
        return f'<MediaUpload {self.id} ({self.file_type}) {self.upload_status}/{self.audit_status}>'


class ChatMessage(db.Model):
    """
    In-app chat message between a team and the admin.

    Teams have one chat thread per game. Admin sees all threads.
    """
    __tablename__ = 'chat_message'

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    sender_type = db.Column(db.String(10), nullable=False)  # team, admin
    message_text = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    team = db.relationship('Team', backref=db.backref('chat_messages', lazy='dynamic'))

    def __repr__(self):
        return f'<ChatMessage {self.id} from {self.sender_type} in game {self.game_id}>'


class RoundBonus(db.Model):
    """
    Tracks bonus points awarded to a team for a round based on correct answer thresholds.

    Separate from Answer to avoid polluting the answer table with synthetic records.
    Recalculated when answers change (submit, audit reject, etc).
    """
    __tablename__ = 'round_bonus'

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    round_id = db.Column(db.Integer, db.ForeignKey('round.id'), nullable=False)
    bonus_points = db.Column(db.Float, default=0.0)
    correct_count = db.Column(db.Integer, default=0)  # How many correct at time of calculation
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Unique constraint: one bonus record per team/round
    __table_args__ = (
        db.UniqueConstraint('team_id', 'round_id', name='unique_round_bonus'),
    )

    # Relationships
    team = db.relationship('Team', backref=db.backref('round_bonuses', lazy='dynamic'))
    round = db.relationship('Round', backref=db.backref('round_bonuses', lazy='dynamic'))

    def __repr__(self):
        return f'<RoundBonus {self.bonus_points}pts for Team {self.team_id} Round {self.round_id}>'
