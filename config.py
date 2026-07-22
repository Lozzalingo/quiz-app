"""
Flask application configuration.

Loads settings from environment variables with sensible defaults.
Includes separate configurations for development and production.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Get the base directory for relative paths
basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration class for Flask application."""

    # Flask core settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    GA_MEASUREMENT_ID = os.getenv('GA_MEASUREMENT_ID', '')

    # Database configuration - PostgreSQL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://localhost:5432/quiz_app'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Admin configuration
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'admin123'

    # Application settings
    BASE_URL = os.environ.get('BASE_URL') or 'http://localhost:5777'

    # SocketIO settings
    SOCKETIO_ASYNC_MODE = 'eventlet'

    # Stripe
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

    # Rate limiting defaults
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = 'memory://'
    RATELIMIT_DEFAULT = '200 per day, 50 per hour'
    RATELIMIT_HEADERS_ENABLED = True

    # DigitalOcean Spaces (S3-compatible) for media uploads
    DO_SPACES_KEY = os.environ.get('DO_SPACES_KEY', '')
    DO_SPACES_SECRET = os.environ.get('DO_SPACES_SECRET', '')
    DO_SPACES_BUCKET = os.environ.get('DO_SPACES_BUCKET', 'aitshirts-laurence-dot-computer')
    DO_SPACES_REGION = os.environ.get('DO_SPACES_REGION', 'sfo3')
    DO_SPACES_ENDPOINT = os.environ.get('DO_SPACES_ENDPOINT', 'https://sfo3.digitaloceanspaces.com')
    DO_SPACES_CDN_ENDPOINT = os.environ.get('DO_SPACES_CDN_ENDPOINT', 'https://aitshirts-laurence-dot-computer.sfo3.cdn.digitaloceanspaces.com')
    DO_SPACES_FOLDER = os.environ.get('DO_SPACES_FOLDER', 'fat-big-quiz')

    # Upload settings
    MAX_UPLOAD_SIZE_MB = 100
    MAX_VIDEO_DURATION_SECONDS = 60


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    RATELIMIT_ENABLED = False  # Disable rate limiting in dev


class ProductionConfig(Config):
    """Production configuration with enhanced security."""
    DEBUG = False

    # Secret key from environment (required in production)
    SECRET_KEY = os.environ.get('SECRET_KEY')

    # Session security
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Rate limiting disabled - was causing hangs
    RATELIMIT_ENABLED = False


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'postgresql://localhost:5432/quiz_app_test'
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False


# Configuration map
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
