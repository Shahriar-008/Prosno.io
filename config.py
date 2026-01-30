"""
Configuration settings for Prosno.io
"""
import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration"""
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-super-secret-key-change-in-production'
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'prosno.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # Upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    
    # Generated files folder
    OUTPUT_FOLDER = os.path.join(basedir, 'output')


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    # In production, set these via environment variables
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'fallback-secret-key-change-this'
    
    # Support both DATABASE_URL and POSTGRES_URL (Vercel uses POSTGRES_URL)
    _db_url = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL') or os.environ.get('POSTGRES_PRISMA_URL')
    
    # Vercel Postgres uses postgres:// but SQLAlchemy needs postgresql://
    if _db_url and _db_url.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = _db_url.replace('postgres://', 'postgresql://', 1)
    elif _db_url:
        SQLALCHEMY_DATABASE_URI = _db_url
    else:
        # Fallback to SQLite for testing (won't persist on serverless)
        SQLALCHEMY_DATABASE_URI = 'sqlite:///prosno.db'


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
