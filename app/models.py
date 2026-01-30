"""
Database models for Prosno.io
"""
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    """Admin user model"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
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
    
    subjects = db.relationship('Subject', backref='class_ref', lazy='dynamic')
    
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
    
    chapters = db.relationship('Chapter', backref='subject', lazy='dynamic')
    
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
    
    questions = db.relationship('Question', backref='chapter', lazy='dynamic')
    
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


class GeneratedPaper(db.Model):
    """Track generated papers"""
    __tablename__ = 'generated_papers'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    chapter_ids = db.Column(db.JSON)  # List of chapter IDs
    question_count = db.Column(db.Integer)
    time_minutes = db.Column(db.Integer)
    file_path = db.Column(db.String(500))
    file_path_answers = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    download_count = db.Column(db.Integer, default=0)
    
    class_ref = db.relationship('Class', backref='papers')
    subject_ref = db.relationship('Subject', backref='papers')
    
    def __repr__(self):
        return f'<GeneratedPaper {self.id}>'
