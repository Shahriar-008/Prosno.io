"""
Prosno.io - Question Paper Generator
Flask Application Factory
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_class=Config):
    """Application factory pattern"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = 'admin.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')

    # Create database tables and seed if empty
    with app.app_context():
        db.create_all()
        # Auto-seed if no classes exist
        from app.models import Class
        if Class.query.count() == 0:
            print("No classes found. Auto-seeding NCTB curriculum...")
            _seed_nctb_data()

    return app


def _seed_nctb_data():
    """Seed NCTB curriculum data if database is empty"""
    from app.models import Class, Subject, Chapter
    
    # Minimal NCTB data for Classes 1-10
    NCTB_DATA = {
        1: {"name": "Class 1", "name_bn": "১ম শ্রেণি", "level": "Primary"},
        2: {"name": "Class 2", "name_bn": "২য় শ্রেণি", "level": "Primary"},
        3: {"name": "Class 3", "name_bn": "৩য় শ্রেণি", "level": "Primary"},
        4: {"name": "Class 4", "name_bn": "৪র্থ শ্রেণি", "level": "Primary"},
        5: {"name": "Class 5", "name_bn": "৫ম শ্রেণি", "level": "Primary"},
        6: {"name": "Class 6", "name_bn": "৬ষ্ঠ শ্রেণি", "level": "Secondary"},
        7: {"name": "Class 7", "name_bn": "৭ম শ্রেণি", "level": "Secondary"},
        8: {"name": "Class 8", "name_bn": "৮ম শ্রেণি", "level": "Secondary"},
        9: {"name": "Class 9", "name_bn": "৯ম শ্রেণি", "level": "Secondary"},
        10: {"name": "Class 10", "name_bn": "১০ম শ্রেণি", "level": "Secondary"},
    }
    
    # Common subjects for all classes
    SUBJECTS = [
        {"name": "Bangla", "name_bn": "বাংলা", "code": "BAN"},
        {"name": "English", "name_bn": "ইংরেজি", "code": "ENG"},
        {"name": "Mathematics", "name_bn": "গণিত", "code": "MATH"},
        {"name": "Science", "name_bn": "বিজ্ঞান", "code": "SCI"},
        {"name": "Bangladesh & Global Studies", "name_bn": "বাংলাদেশ ও বিশ্বপরিচয়", "code": "BGS"},
        {"name": "Religion", "name_bn": "ধর্ম", "code": "REL"},
        {"name": "ICT", "name_bn": "তথ্য ও যোগাযোগ প্রযুক্তি", "code": "ICT"},
    ]
    
    try:
        for class_num, class_data in NCTB_DATA.items():
            cls = Class(
                name=class_data["name"],
                name_bn=class_data["name_bn"],
                level=class_data["level"],
                order=class_num,
                is_active=True
            )
            db.session.add(cls)
            db.session.flush()
            
            for idx, subj_data in enumerate(SUBJECTS, 1):
                subj = Subject(
                    name=subj_data["name"],
                    name_bn=subj_data["name_bn"],
                    code=subj_data["code"],
                    class_id=cls.id,
                    order=idx,
                    is_active=True
                )
                db.session.add(subj)
                db.session.flush()
                
                # Add 5 sample chapters per subject
                for ch_num in range(1, 6):
                    chap = Chapter(
                        name=f"Chapter {ch_num}",
                        name_bn=f"অধ্যায় {ch_num}",
                        chapter_number=ch_num,
                        subject_id=subj.id,
                        order=ch_num,
                        is_active=True
                    )
                    db.session.add(chap)
        
        db.session.commit()
        print("NCTB curriculum seeded successfully!")
    except Exception as e:
        db.session.rollback()
        print(f"Error seeding database: {e}")


# Create app instance for gunicorn (allows `gunicorn app:app`)
app = create_app()
