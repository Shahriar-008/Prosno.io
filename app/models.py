"""
Database models for Prosno.io
"""
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, current_user
from flask import abort
from app import db, login_manager
from cryptography.fernet import Fernet
from flask import current_app
import os


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# User roles
ROLE_ADMIN = 'admin'      # Full access - can do everything
ROLE_EDITOR = 'editor'    # Can add content, limited delete


def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != ROLE_ADMIN:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


class User(UserMixin, db.Model):
    """Admin user model"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default=ROLE_EDITOR)  # 'admin' or 'editor'
    is_admin = db.Column(db.Boolean, default=False)  # Kept for backward compatibility
    is_active_user = db.Column(db.Boolean, default=True)  # Can disable users
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    last_login = db.Column(db.DateTime)
    
    # Relationships
    created_by = db.relationship('User', remote_side=[id], backref='created_users')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_master_admin(self):
        """Check if user is master admin"""
        return self.role == ROLE_ADMIN
    
    def can_delete(self):
        """Check if user can delete content"""
        return self.role == ROLE_ADMIN
    
    def can_manage_users(self):
        """Check if user can manage other users"""
        return self.role == ROLE_ADMIN
    
    def __repr__(self):
        return f'<User {self.username}>'


class Class(db.Model):
    """Class/Grade model"""
    __tablename__ = 'classes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # e.g., "Class 8", "অষ্টম শ্রেণি"
    name_bn = db.Column(db.String(100))  # Bengali name
    level = db.Column(db.String(50))  # e.g., "Secondary", "মাধ্যমিক"
    order = db.Column(db.Integer, default=0)  # For sorting
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    subjects = db.relationship('Subject', backref='class_ref', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Class {self.name}>'


class Subject(db.Model):
    """Subject model"""
    __tablename__ = 'subjects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    name_bn = db.Column(db.String(100))  # Bengali name
    code = db.Column(db.String(20))  # Subject code
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    chapters = db.relationship('Chapter', backref='subject', lazy='dynamic', cascade='all, delete-orphan')
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    
    def __repr__(self):
        return f'<Subject {self.name}>'


class Chapter(db.Model):
    """Chapter model"""
    __tablename__ = 'chapters'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    name_bn = db.Column(db.String(200))  # Bengali name
    chapter_number = db.Column(db.Integer)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    questions = db.relationship('Question', backref='chapter', lazy='dynamic', cascade='all, delete-orphan')
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    
    def __repr__(self):
        return f'<Chapter {self.name}>'


class Question(db.Model):
    """Question model"""
    __tablename__ = 'questions'
    
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(20), default='simple')  # 'simple', 'complex', 'cq', 'sq'

    # For complex questions (MCQ variant with sub-statements)
    sub_options = db.Column(db.JSON)  # List of sub-options (i, ii, iii …)
    final_prompt = db.Column(db.Text)  # Final question for complex type

    # For CQ (Creative Question / সৃজনশীল প্রশ্ন)
    # question_text holds the stimulus (উদ্দীপক)
    # cq_questions holds sub-questions: [{"text": "...", "marks": 1}, ...]
    cq_questions = db.Column(db.JSON)  # List of sub-questions with marks

    # Answer options and correct answer (MCQ / SQ)
    # For SQ, answer_options is [] and correct_answer holds the model answer
    answer_options = db.Column(db.JSON, nullable=False)  # List of 4 options
    correct_answer = db.Column(db.String(500), nullable=False)
    
    # Relationships
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=False)
    
    # Metadata
    difficulty = db.Column(db.String(20), default='medium')  # easy, medium, hard
    marks = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    def to_dict(self):
        """Convert question to dictionary for JSON export."""
        data = {
            'id': str(self.id),
            'question_text': self.question_text,
            'type': self.question_type,
            'answer_options': self.answer_options,
            'correct_answer': self.correct_answer,
        }
        if self.question_type == 'complex':
            data['sub_options'] = self.sub_options or []
            data['final_prompt'] = self.final_prompt or ''
        elif self.question_type == 'cq':
            data['cq_questions'] = self.cq_questions or []
        return data
    
    def __repr__(self):
        return f'<Question {self.id}>'


class GeneratedPaper(db.Model):
    """Track generated papers"""
    __tablename__ = 'generated_papers'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    chapter_ids = db.Column(db.JSON)  # List of chapter IDs
    question_ids = db.Column(db.JSON)  # List of specific question IDs used
    question_count = db.Column(db.Integer)
    time_minutes = db.Column(db.Integer)
    file_path = db.Column(db.String(500))
    file_path_answers = db.Column(db.String(500))
    custom_questions_json = db.Column(db.JSON)  # Stores custom questions for regeneration
    custom_paper_config = db.Column(db.JSON)    # Stores paper config for custom papers
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    download_count = db.Column(db.Integer, default=0)
    
    class_ref = db.relationship('Class', backref='papers')
    subject_ref = db.relationship('Subject', backref='papers')
    
    def __repr__(self):
        return f'<GeneratedPaper {self.id}>'


class AIGeneratorConfig(db.Model):
    """AI Generator configuration and state"""
    __tablename__ = 'ai_generator_config'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # API Configuration
    _api_key = db.Column('api_key', db.String(500))  # Internal encrypted storage
    api_provider = db.Column(db.String(50), default='gemini')  # gemini, openai
    model_name = db.Column(db.String(100), default='gemini-2.0-flash')
    
    # Generation Settings
    prompt_template = db.Column(db.Text)  # Custom prompt for generating questions
    questions_per_request = db.Column(db.Integer, default=5)
    interval_minutes = db.Column(db.Integer, default=5)
    
    # Rate Limiting
    max_requests_per_hour = db.Column(db.Integer, default=20)
    requests_this_hour = db.Column(db.Integer, default=0)
    hour_started = db.Column(db.DateTime)
    
    # Current State
    is_running = db.Column(db.Boolean, default=False)
    current_class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    current_subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    current_chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'))
    started_at = db.Column(db.DateTime)
    last_run_at = db.Column(db.DateTime)
    
    # Statistics
    total_questions_generated = db.Column(db.Integer, default=0)
    total_duplicates_skipped = db.Column(db.Integer, default=0)
    total_errors = db.Column(db.Integer, default=0)
    
    # Relationships
    current_class = db.relationship('Class', foreign_keys=[current_class_id])
    current_subject = db.relationship('Subject', foreign_keys=[current_subject_id])
    current_chapter = db.relationship('Chapter', foreign_keys=[current_chapter_id])
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def api_key(self):
        """Decrypts and returns the API key."""
        if not self._api_key:
            return None
        try:
            key = current_app.config.get('ENCRYPTION_KEY')
            if not key:
                # Fallback if no key configured (or development) logic could go here
                # For now, return raw if decryption fails or warn
                return self._api_key
            f = Fernet(key)
            return f.decrypt(self._api_key.encode()).decode()
        except Exception as e:
            # If decryption fails (e.g. key changed or bad data), return raw or None
            return self._api_key

    @api_key.setter
    def api_key(self, value):
        """Encrypts and stores the API key."""
        if not value:
            self._api_key = None
            return
        
        try:
            key = current_app.config.get('ENCRYPTION_KEY')
            if not key:
                # If no key, store as plaintext (dev mode fallback)
                self._api_key = value
                return
            f = Fernet(key)
            self._api_key = f.encrypt(value.encode()).decode()
        except Exception as e:
            # Fallback to plaintext if encryption fails
            self._api_key = value
    
    def __repr__(self):
        return f'<AIGeneratorConfig {self.id}>'


class AIGeneratorLog(db.Model):
    """Log of AI generator activities"""
    __tablename__ = 'ai_generator_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # What was processed
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'))
    
    # Results
    status = db.Column(db.String(20))  # success, error, duplicate, skipped
    questions_generated = db.Column(db.Integer, default=0)
    duplicates_found = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text)
    
    # API Stats
    tokens_used = db.Column(db.Integer, default=0)
    api_response_time = db.Column(db.Float)  # seconds
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    class_ref = db.relationship('Class', backref='ai_logs')
    subject_ref = db.relationship('Subject', backref='ai_logs')
    chapter_ref = db.relationship('Chapter', backref='ai_logs')
    
    def __repr__(self):
        return f'<AIGeneratorLog {self.id} - {self.status}>'


class ActivityLog(db.Model):
    """Track user activities for admin oversight"""
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # 'add', 'edit', 'delete'
    entity_type = db.Column(db.String(50), nullable=False)  # 'question', 'subject', 'chapter'
    entity_id = db.Column(db.Integer)
    entity_name = db.Column(db.String(200))  # For display purposes
    details = db.Column(db.JSON)  # Additional details
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='activities')
    
    def __repr__(self):
        return f'<ActivityLog {self.user_id} - {self.action} {self.entity_type}>'
