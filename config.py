"""
Configuration settings for Prosno.io
"""
import os
import secrets
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


def generate_secret_key():
    """Generate a secure secret key for development. In production, always use SECRET_KEY env var."""
    return secrets.token_hex(32)


class Config:
    """Base configuration"""
    SITE_NAME = os.environ.get('SITE_NAME') or 'Prosno.io'
    SITE_URL = (os.environ.get('SITE_URL') or '').rstrip('/')
    DEFAULT_META_DESCRIPTION = (
        'Prosno.io helps Bangladeshi teachers generate MCQ question papers, '
        'answer keys, PDFs, and live quizzes in minutes.'
    )
    DEFAULT_OG_IMAGE = os.environ.get('DEFAULT_OG_IMAGE') or 'img/og-default.svg'
    SUPPORT_EMAIL = os.environ.get('SUPPORT_EMAIL') or 'support@prosno.io'

    # Security - IMPORTANT: Set SECRET_KEY environment variable in production
    SECRET_KEY = os.environ.get('SECRET_KEY') or generate_secret_key()
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')
    
    # Session security settings
    SESSION_COOKIE_SECURE = bool(os.environ.get('RENDER') or os.environ.get('DYNO') or os.environ.get('PRODUCTION'))
    SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access to session cookie
    SESSION_COOKIE_SAMESITE = 'Lax'  # Protect against CSRF
    
    # Database - Handle PostgreSQL URL for psycopg3 driver
    _database_url = os.environ.get('DATABASE_URL')
    if _database_url:
        if _database_url.startswith('postgres://'):
            SQLALCHEMY_DATABASE_URI = _database_url.replace('postgres://', 'postgresql+psycopg://', 1)
        elif _database_url.startswith('postgresql://'):
            SQLALCHEMY_DATABASE_URI = _database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
        else:
            SQLALCHEMY_DATABASE_URI = _database_url
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'instance', 'prosno.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # Upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or os.path.join(basedir, 'uploads')
    
    # Generated files folder - use /tmp on production for ephemeral storage
    OUTPUT_FOLDER = os.environ.get('OUTPUT_FOLDER') or os.path.join(basedir, 'output')
    
    # On Render/Heroku/Coolify, use /tmp for file generation (ephemeral but writable)
    if os.environ.get('RENDER') or os.environ.get('DYNO') or os.environ.get('PRODUCTION'):
        OUTPUT_FOLDER = '/tmp/prosno_output'
        UPLOAD_FOLDER = '/tmp/prosno_uploads'


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    
    # Production requires SECRET_KEY to be set (checked at runtime in create_app)
    SECRET_KEY = os.environ.get('SECRET_KEY') or generate_secret_key()
    
    # Enforce secure cookies in production
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    
    # Database - Render uses DATABASE_URL with postgres:// prefix
    # SQLAlchemy with psycopg3 requires postgresql+psycopg:// so we fix it here
    _database_url = os.environ.get('DATABASE_URL')
    if _database_url:
        if _database_url.startswith('postgres://'):
            SQLALCHEMY_DATABASE_URI = _database_url.replace('postgres://', 'postgresql+psycopg://', 1)
        elif _database_url.startswith('postgresql://'):
            SQLALCHEMY_DATABASE_URI = _database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
        else:
            SQLALCHEMY_DATABASE_URI = _database_url
    else:
        SQLALCHEMY_DATABASE_URI = None


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    SKIP_STARTUP_TASKS = True
    # Disable caching in tests so browse endpoints always hit the DB
    CACHE_TYPE = 'NullCache'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
