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
    question_type = db.Column(db.String(20), default='simple')  # 'simple' or 'complex'
    
    # For complex questions
    sub_options = db.Column(db.JSON)  # List of sub-options
    final_prompt = db.Column(db.Text)  # Final question for complex type
    
    # Answer options and correct answer
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
        """Convert question to dictionary for JSON export"""
        data = {
            'id': str(self.id),
            'question_text': self.question_text,
            'type': self.question_type,
            'answer_options': self.answer_options,
            'correct_answer': self.correct_answer
        }
        if self.question_type == 'complex':
            data['sub_options'] = self.sub_options or []
            data['final_prompt'] = self.final_prompt or ''
        return data
    
    def __repr__(self):
        return f'<Question {self.id}>'


class ShortQuestion(db.Model):
    """Short answer question model (সংক্ষিপ্ত প্রশ্ন)"""
    __tablename__ = 'short_questions'

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(
        db.Integer, db.ForeignKey('subjects.id'), nullable=False
    )
    chapter_id = db.Column(
        db.Integer, db.ForeignKey('chapters.id'), nullable=True
    )
    question_text = db.Column(db.Text, nullable=False)
    marks = db.Column(db.Integer, default=2)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    subject = db.relationship(
        'Subject', backref=db.backref('short_questions', lazy='dynamic')
    )
    chapter = db.relationship(
        'Chapter', backref=db.backref('short_questions', lazy='dynamic')
    )
    creator = db.relationship('User', foreign_keys=[created_by])

    def to_dict(self):
        """Convert short question to dictionary."""
        return {
            'id': self.id,
            'question_text': self.question_text,
            'marks': self.marks,
            'type': 'short',
        }

    def __repr__(self):
        return f'<ShortQuestion {self.id}>'


class CQQuestion(db.Model):
    """Creative question model (সৃজনশীল প্রশ্ন)"""
    __tablename__ = 'cq_questions'

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(
        db.Integer, db.ForeignKey('subjects.id'), nullable=False
    )
    chapter_id = db.Column(
        db.Integer, db.ForeignKey('chapters.id'), nullable=True
    )
    stem = db.Column(db.Text, nullable=False)  # উদ্দীপক
    part_ka = db.Column(db.Text)   # ক sub-question
    part_kha = db.Column(db.Text)  # খ sub-question
    part_ga = db.Column(db.Text)   # গ sub-question
    part_gha = db.Column(db.Text)  # ঘ sub-question
    marks_ka = db.Column(db.Integer, default=1)
    marks_kha = db.Column(db.Integer, default=2)
    marks_ga = db.Column(db.Integer, default=3)
    marks_gha = db.Column(db.Integer, default=4)
    board = db.Column(db.String(100), nullable=True)   # Board name (e.g. ঢাকা বোর্ড)
    year = db.Column(db.Integer, nullable=True)         # Exam year
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    subject = db.relationship(
        'Subject', backref=db.backref('cq_questions', lazy='dynamic')
    )
    chapter = db.relationship(
        'Chapter', backref=db.backref('cq_questions', lazy='dynamic')
    )
    creator = db.relationship('User', foreign_keys=[created_by])

    @property
    def total_marks(self):
        """Compute sum of all part marks."""
        return (
            (self.marks_ka or 0)
            + (self.marks_kha or 0)
            + (self.marks_ga or 0)
            + (self.marks_gha or 0)
        )

    def to_dict(self):
        """Convert creative question to dictionary."""
        return {
            'id': self.id,
            'stem': self.stem,
            'part_ka': self.part_ka,
            'part_kha': self.part_kha,
            'part_ga': self.part_ga,
            'part_gha': self.part_gha,
            'marks_ka': self.marks_ka,
            'marks_kha': self.marks_kha,
            'marks_ga': self.marks_ga,
            'marks_gha': self.marks_gha,
            'total_marks': self.total_marks,
            'board': self.board,
            'year': self.year,
            'type': 'creative',
        }

    def __repr__(self):
        return f'<CQQuestion {self.id}>'


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
    omr_style = db.Column(db.Boolean, default=True)  # Show OMR circles on options
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    download_count = db.Column(db.Integer, default=0)
    
    class_ref = db.relationship('Class', backref='papers')
    subject_ref = db.relationship('Subject', backref='papers')
    
    def __repr__(self):
        return f'<GeneratedPaper {self.id}>'


class QuestionSet(db.Model):
    """Saved question sets for public users (SaaS dashboard)"""
    __tablename__ = 'question_sets'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False, index=True)  # Supabase UUID
    name = db.Column(db.String(200), nullable=False)
    questions_json = db.Column(db.JSON, nullable=False)  # Full question data
    paper_config = db.Column(db.JSON)  # Title, class, subject, time, marks, omr_style
    source = db.Column(db.String(20), default='custom')  # 'db' or 'custom'
    paper_id = db.Column(db.Integer, db.ForeignKey('generated_papers.id'))  # Optional link
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Sharing
    share_token = db.Column(db.String(16), unique=True, index=True)  # URL-safe random token
    is_shared = db.Column(db.Boolean, default=False)  # Whether the share link is active
    
    paper = db.relationship('GeneratedPaper', backref='question_sets')
    
    @staticmethod
    def generate_share_token():
        """Generate a unique URL-safe share token."""
        import secrets
        for _ in range(100):
            token = secrets.token_urlsafe(12)[:16]  # 16-char URL-safe token
            if not QuestionSet.query.filter_by(share_token=token).first():
                return token
        raise ValueError('Could not generate a unique share token')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'question_count': len(self.questions_json) if self.questions_json else 0,
            'source': self.source,
            'paper_config': self.paper_config,
            'share_token': self.share_token,
            'is_shared': self.is_shared or False,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else None,
        }
    
    def __repr__(self):
        return f'<QuestionSet {self.id} - {self.name}>'


class GenerationLog(db.Model):
    """Track paper generations per user for the credit/usage system"""
    __tablename__ = 'generation_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), nullable=False, index=True)  # Supabase UUID
    generation_type = db.Column(db.String(20), default='db')  # 'db' or 'custom'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<GenerationLog {self.id} user={self.user_id}>'


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


class Quiz(db.Model):
    """A live quiz created by a teacher from a question set"""
    __tablename__ = 'quizzes'

    id = db.Column(db.Integer, primary_key=True)
    join_code = db.Column(db.String(6), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)

    # Link to source
    question_set_id = db.Column(db.Integer, db.ForeignKey('question_sets.id'))
    teacher_user_id = db.Column(db.String(100), nullable=False, index=True)  # Supabase UUID

    # Snapshot of questions at quiz creation time (decoupled from source)
    questions_json = db.Column(db.JSON, nullable=False)

    # Quiz configuration
    time_limit_minutes = db.Column(db.Integer, default=30)
    shuffle_questions = db.Column(db.Boolean, default=True)
    shuffle_options = db.Column(db.Boolean, default=True)
    show_results_to_students = db.Column(db.Boolean, default=True)

    # State: waiting → active → ended
    status = db.Column(db.String(20), default='waiting')
    started_at = db.Column(db.DateTime)
    ended_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    question_set = db.relationship('QuestionSet', backref='quizzes')
    sessions = db.relationship('QuizSession', backref='quiz', lazy='dynamic',
                               cascade='all, delete-orphan')

    @staticmethod
    def generate_join_code():
        """Generate a unique 4-digit numeric join code."""
        import random
        for _ in range(100):  # max attempts
            code = str(random.randint(1000, 9999))
            if not Quiz.query.filter_by(join_code=code).first():
                return code
        raise ValueError('Could not generate a unique join code after 100 attempts')

    @property
    def student_count(self):
        return self.sessions.count()

    @property
    def is_active(self):
        return self.status == 'active'

    @property
    def is_ended(self):
        return self.status == 'ended'

    def to_dict(self):
        return {
            'id': self.id,
            'join_code': self.join_code,
            'title': self.title,
            'status': self.status,
            'student_count': self.student_count,
            'time_limit_minutes': self.time_limit_minutes,
            'question_count': len(self.questions_json) if self.questions_json else 0,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None,
        }

    def __repr__(self):
        return f'<Quiz {self.join_code} - {self.title}>'


class QuizSession(db.Model):
    """A student's participation in a quiz"""
    __tablename__ = 'quiz_sessions'

    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    student_name = db.Column(db.String(100), nullable=False)
    session_token = db.Column(db.String(64), unique=True, nullable=False, index=True)

    # Results
    score = db.Column(db.Integer, default=0)
    total_questions = db.Column(db.Integer, default=0)
    responses_json = db.Column(db.JSON)   # {"0": "selected_answer", "1": "selected_answer", ...}
    time_taken_seconds = db.Column(db.Integer)

    # State: joined → in_progress → submitted
    status = db.Column(db.String(20), default='joined')
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_at = db.Column(db.DateTime)

    @property
    def score_percentage(self):
        if not self.total_questions:
            return 0
        return round((self.score / self.total_questions) * 100)

    def grade(self, questions_json):
        """Auto-grade responses against the answer key. Call before committing."""
        if not self.responses_json or not questions_json:
            return
        correct = 0
        for idx, q in enumerate(questions_json):
            student_answer = self.responses_json.get(str(idx))
            if student_answer and student_answer == q.get('correct_answer'):
                correct += 1
        self.score = correct
        self.total_questions = len(questions_json)

    def to_dict(self, include_responses=False):
        data = {
            'id': self.id,
            'student_name': self.student_name,
            'score': self.score,
            'total_questions': self.total_questions,
            'score_percentage': self.score_percentage,
            'status': self.status,
            'time_taken_seconds': self.time_taken_seconds,
            'joined_at': self.joined_at.strftime('%H:%M') if self.joined_at else None,
            'submitted_at': self.submitted_at.strftime('%H:%M') if self.submitted_at else None,
        }
        if include_responses:
            data['responses'] = self.responses_json
        return data

    def __repr__(self):
        return f'<QuizSession {self.student_name} - Quiz {self.quiz_id}>'


# ─── Teacher Question Bank ────────────────────────────────────────────────────

class TeacherProfile(db.Model):
    """Per-teacher contribution profile (keyed by Supabase user_id)."""
    __tablename__ = 'teacher_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(200))

    # Trust / moderation
    is_trusted = db.Column(db.Boolean, default=False)
    trust_granted_at = db.Column(db.DateTime)
    trust_granted_by = db.Column(db.String(100))   # admin user_id

    # Cached counters (kept up-to-date by helpers after events)
    approved_questions_count = db.Column(db.Integer, default=0)
    reputation_score = db.Column(db.Integer, default=0)
    account_created_at = db.Column(db.DateTime, default=datetime.utcnow)

    questions_created = db.Column(db.Integer, default=0)
    questions_published = db.Column(db.Integer, default=0)
    questions_used = db.Column(db.Integer, default=0)
    total_downloads = db.Column(db.Integer, default=0)
    average_rating = db.Column(db.Numeric(3, 2), default=0.00)
    contributor_rank = db.Column(db.String(50), default='Newcomer')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    bank_questions = db.relationship(
        'BankQuestion', backref='teacher_profile', lazy='dynamic',
        foreign_keys='BankQuestion.teacher_id',
        primaryjoin='TeacherProfile.user_id == BankQuestion.teacher_id'
    )
    badges = db.relationship('TeacherBadge', backref='teacher_profile',
                             lazy='dynamic',
                             foreign_keys='TeacherBadge.teacher_id',
                             primaryjoin='TeacherProfile.user_id == TeacherBadge.teacher_id')

    def to_dict(self, public=False):
        data = {
            'user_id': self.user_id,
            'display_name': self.display_name or 'Anonymous Teacher',
            'questions_created': self.questions_created,
            'questions_published': self.questions_published,
            'questions_used': self.questions_used,
            'total_downloads': self.total_downloads,
            'average_rating': float(self.average_rating or 0),
            'reputation_score': self.reputation_score,
            'contributor_rank': self.contributor_rank,
            'is_trusted': self.is_trusted,
            'account_created_at': self.account_created_at.strftime('%Y-%m-%d') if self.account_created_at else None,
        }
        if not public:
            data['approved_questions_count'] = self.approved_questions_count
        return data

    def __repr__(self):
        return f'<TeacherProfile {self.user_id}>'


class BankQuestion(db.Model):
    """Teacher-contributed question in the shared question bank."""
    __tablename__ = 'bank_questions'

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.String(100), nullable=False, index=True)

    # Curriculum location
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'))

    # Question content
    question_type = db.Column(db.String(10), nullable=False)   # MCQ / SQ / CQ
    question_text = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text)
    explanation = db.Column(db.Text)

    # MCQ-specific
    answer_options = db.Column(db.JSON)
    correct_answer = db.Column(db.String(500))

    # CQ-specific
    stem = db.Column(db.Text)
    part_ka = db.Column(db.Text)
    part_kha = db.Column(db.Text)
    part_ga = db.Column(db.Text)
    part_gha = db.Column(db.Text)
    marks_ka = db.Column(db.SmallInteger)
    marks_kha = db.Column(db.SmallInteger)
    marks_ga = db.Column(db.SmallInteger)
    marks_gha = db.Column(db.SmallInteger)

    # Classification
    topic = db.Column(db.String(200))
    difficulty = db.Column(db.String(20), default='medium')    # easy/medium/hard
    marks = db.Column(db.SmallInteger, default=1)
    board = db.Column(db.String(100))
    year = db.Column(db.SmallInteger)

    # Publishing state
    # visibility: private / pending / public / rejected
    visibility = db.Column(db.String(20), default='private', index=True)
    # status: draft / submitted / approved / rejected
    status = db.Column(db.String(20), default='draft')
    published_at = db.Column(db.DateTime)
    rejected_at = db.Column(db.DateTime)
    rejection_reason = db.Column(db.Text)

    # Origin: manual / ai_generated / copied
    origin = db.Column(db.String(20), default='manual')
    source_question_id = db.Column(db.Integer,
                                   db.ForeignKey('bank_questions.id'))

    # Engagement counters
    usage_count = db.Column(db.Integer, default=0)
    download_count = db.Column(db.Integer, default=0)
    rating_total = db.Column(db.Integer, default=0)
    rating_count = db.Column(db.Integer, default=0)

    # Duplicate detection
    text_hash = db.Column(db.String(64), index=True)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    # Relationships
    class_ref = db.relationship('Class', backref='bank_questions')
    subject_ref = db.relationship('Subject', backref='bank_questions')
    chapter_ref = db.relationship('Chapter', backref='bank_questions')
    source_question = db.relationship('BankQuestion', remote_side=[id],
                                      backref='copies')

    @property
    def average_rating(self):
        if not self.rating_count:
            return 0.0
        return round(self.rating_total / self.rating_count, 2)

    def to_dict(self, include_answer=False):
        data = {
            'id': self.id,
            'teacher_id': self.teacher_id,
            'class_id': self.class_id,
            'subject_id': self.subject_id,
            'chapter_id': self.chapter_id,
            'question_type': self.question_type,
            'question_text': self.question_text,
            'topic': self.topic,
            'difficulty': self.difficulty,
            'marks': self.marks,
            'board': self.board,
            'year': self.year,
            'visibility': self.visibility,
            'status': self.status,
            'origin': self.origin,
            'source_question_id': self.source_question_id,
            'usage_count': self.usage_count,
            'download_count': self.download_count,
            'average_rating': self.average_rating,
            'rating_count': self.rating_count,
            'created_at': self.created_at.strftime('%Y-%m-%d') if self.created_at else None,
        }
        # MCQ fields
        if self.question_type == 'MCQ':
            data['answer_options'] = self.answer_options
            if include_answer:
                data['correct_answer'] = self.correct_answer
        # CQ fields
        if self.question_type == 'CQ':
            data.update({
                'stem': self.stem,
                'part_ka': self.part_ka,
                'part_kha': self.part_kha,
                'part_ga': self.part_ga,
                'part_gha': self.part_gha,
                'marks_ka': self.marks_ka,
                'marks_kha': self.marks_kha,
                'marks_ga': self.marks_ga,
                'marks_gha': self.marks_gha,
            })
        # SQ / full answer
        if include_answer:
            data['answer'] = self.answer
            data['explanation'] = self.explanation
        return data

    def __repr__(self):
        return f'<BankQuestion {self.id} [{self.question_type}]>'


class ModerationQueue(db.Model):
    """Admin review queue for bank questions from new (untrusted) teachers."""
    __tablename__ = 'moderation_queue'

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer,
                            db.ForeignKey('bank_questions.id', ondelete='CASCADE'),
                            nullable=False)
    submitted_by = db.Column(db.String(100), nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_by = db.Column(db.String(100))
    reviewed_at = db.Column(db.DateTime)
    decision = db.Column(db.String(20))           # approved / rejected
    admin_notes = db.Column(db.Text)
    priority = db.Column(db.SmallInteger, default=5)  # 1=high, 10=low

    question = db.relationship('BankQuestion', backref='moderation_entries')

    def to_dict(self):
        return {
            'id': self.id,
            'question_id': self.question_id,
            'submitted_by': self.submitted_by,
            'submitted_at': self.submitted_at.strftime('%Y-%m-%d %H:%M') if self.submitted_at else None,
            'reviewed_by': self.reviewed_by,
            'reviewed_at': self.reviewed_at.strftime('%Y-%m-%d %H:%M') if self.reviewed_at else None,
            'decision': self.decision,
            'admin_notes': self.admin_notes,
            'priority': self.priority,
        }

    def __repr__(self):
        return f'<ModerationQueue q={self.question_id} decision={self.decision}>'


class QuestionInteraction(db.Model):
    """Tracks what teachers do with bank questions (use, save, rate, copy)."""
    __tablename__ = 'question_interactions'

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer,
                            db.ForeignKey('bank_questions.id', ondelete='CASCADE'),
                            nullable=False)
    teacher_id = db.Column(db.String(100), nullable=False)
    # action_type: used / saved / copied / rated
    action_type = db.Column(db.String(20), nullable=False)
    rating_value = db.Column(db.SmallInteger)
    question_set_id = db.Column(db.Integer, db.ForeignKey('question_sets.id'))
    paper_id = db.Column(db.Integer, db.ForeignKey('generated_papers.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    question = db.relationship('BankQuestion', backref='interactions')

    __table_args__ = (
        db.UniqueConstraint('question_id', 'teacher_id', 'action_type',
                            name='uq_qi_question_teacher_action'),
    )

    def __repr__(self):
        return f'<QuestionInteraction {self.action_type} q={self.question_id}>'


class TeacherLibrary(db.Model):
    """Personal saved question library per teacher."""
    __tablename__ = 'teacher_library'

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.String(100), nullable=False, index=True)
    question_id = db.Column(db.Integer,
                            db.ForeignKey('bank_questions.id', ondelete='CASCADE'),
                            nullable=False)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)

    question = db.relationship('BankQuestion', backref='library_saves')

    __table_args__ = (
        db.UniqueConstraint('teacher_id', 'question_id', name='uq_tl_teacher_question'),
    )

    def __repr__(self):
        return f'<TeacherLibrary teacher={self.teacher_id} q={self.question_id}>'


class TeacherBadge(db.Model):
    """Gamification badges awarded to teachers."""
    __tablename__ = 'teacher_badges'

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.String(100), nullable=False, index=True)
    badge_slug = db.Column(db.String(50), nullable=False)
    badge_name = db.Column(db.String(100), nullable=False)
    badge_icon = db.Column(db.String(10), default='🏆')
    awarded_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('teacher_id', 'badge_slug', name='uq_tb_teacher_badge'),
    )

    def to_dict(self):
        return {
            'slug': self.badge_slug,
            'name': self.badge_name,
            'icon': self.badge_icon,
            'awarded_at': self.awarded_at.strftime('%Y-%m-%d') if self.awarded_at else None,
        }

    def __repr__(self):
        return f'<TeacherBadge {self.badge_slug} teacher={self.teacher_id}>'


class PublishPrompt(db.Model):
    """
    Tracks the post-paper 'publish to question bank?' prompt shown to teachers.
    Created after a paper is generated, resolved when teacher responds.
    """
    __tablename__ = 'publish_prompts'

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.String(100), nullable=False, index=True)
    paper_id = db.Column(db.Integer, db.ForeignKey('generated_papers.id'))
    question_set_id = db.Column(db.Integer, db.ForeignKey('question_sets.id'))
    question_ids = db.Column(db.JSON, nullable=False)  # [bank_question_id, ...]
    responded = db.Column(db.Boolean, default=False)
    decision = db.Column(db.String(20))           # publish / keep_private
    published_ids = db.Column(db.JSON)            # subset actually published
    responded_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    paper = db.relationship('GeneratedPaper', backref='publish_prompts')
    question_set = db.relationship('QuestionSet', backref='publish_prompts')

    def to_dict(self):
        return {
            'id': self.id,
            'teacher_id': self.teacher_id,
            'paper_id': self.paper_id,
            'question_set_id': self.question_set_id,
            'question_ids': self.question_ids or [],
            'responded': self.responded,
            'decision': self.decision,
            'published_ids': self.published_ids or [],
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None,
        }

    def __repr__(self):
        return f'<PublishPrompt id={self.id} decided={self.responded}>'


class TeacherNotification(db.Model):
    """
    In-app notification for a teacher — moderation outcomes, badge awards, trust grants.
    Teachers poll GET /api/v1/bank/notifications to see these.
    """
    __tablename__ = 'teacher_notifications'

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.String(100), nullable=False, index=True)

    # type: 'question_approved' / 'question_rejected' / 'badge_awarded' / 'trust_granted'
    notif_type = db.Column(db.String(30), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text)

    # Optional references
    question_id = db.Column(db.Integer, db.ForeignKey('bank_questions.id',
                            ondelete='SET NULL'))
    badge_slug = db.Column(db.String(50))

    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    question = db.relationship('BankQuestion', backref='notifications')

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.notif_type,
            'title': self.title,
            'body': self.body,
            'question_id': self.question_id,
            'badge_slug': self.badge_slug,
            'is_read': self.is_read,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else None,
        }

    def __repr__(self):
        return f'<TeacherNotification {self.notif_type} teacher={self.teacher_id}>'

