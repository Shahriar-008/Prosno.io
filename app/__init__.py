"""
Prosno.io - Question Paper Generator
Flask Application Factory
"""
import os
import tempfile
import time

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
)


def create_app(config_class=Config):
    """Application factory pattern"""
    flask_app = Flask(__name__)
    flask_app.config.from_object(config_class)
    skip_startup_tasks = flask_app.config.get(
        'SKIP_STARTUP_TASKS', flask_app.config.get('TESTING', False)
    )

    from app.utils.seo import (
        default_meta_robots,
        default_og_image_url,
        get_site_url,
        should_send_noindex_header,
    )

    # Warn if SECRET_KEY not set from environment in production
    import warnings
    if not flask_app.debug and not os.environ.get('SECRET_KEY'):
        warnings.warn(
            "SECRET_KEY not set! Using auto-generated key. "
            "Set SECRET_KEY environment variable in production.",
            UserWarning
        )

    # Initialize extensions
    db.init_app(flask_app)
    login_manager.init_app(flask_app)
    csrf.init_app(flask_app)
    limiter.init_app(flask_app)

    # Initialize Flask-Caching (Redis if REDIS_URL set, SimpleCache fallback)
    from app.utils.cache import init_cache
    init_cache(flask_app)

    # ProxyFix for Render (handling HTTPS headers)
    from werkzeug.middleware.proxy_fix import ProxyFix
    flask_app.wsgi_app = ProxyFix(
        flask_app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
    )

    login_manager.login_view = 'admin.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    @flask_app.context_processor
    def inject_seo_defaults():
        """Expose sitewide SEO helpers to templates."""
        return {
            'default_meta_robots': default_meta_robots,
            'default_og_image_url': default_og_image_url,
            'site_url': get_site_url(),
        }

    # Add security headers to all responses
    @flask_app.after_request
    def add_security_headers(response):
        """Add security headers to prevent common attacks"""
        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        # Prevent MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        # Enable XSS filter in older browsers
        response.headers['X-XSS-Protection'] = '1; mode=block'
        # Referrer policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # Content Security Policy (basic policy - adjust as needed)
        if not flask_app.debug:
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
                "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com; "
                "img-src 'self' data:; "
                "connect-src 'self'"
            )
            # HSTS - only in production over HTTPS
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        if should_send_noindex_header(response):
            directive = (
                default_meta_robots()
                if (response.mimetype or '').lower() == 'text/html'
                else 'noindex, nofollow'
            )
            response.headers.setdefault('X-Robots-Tag', directive)

        return response

    # Initialize Supabase Auth client for public user auth
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    if supabase_url and supabase_key:
        try:
            from app.utils.supabase_auth import SupabaseAuth
            flask_app.config['SUPABASE_CLIENT'] = SupabaseAuth(supabase_url, supabase_key)
            print("Supabase Auth initialized successfully.")
        except Exception as e:
            print(f"Warning: Could not initialize Supabase Auth: {e}")
            flask_app.config['SUPABASE_CLIENT'] = None
    else:
        flask_app.config['SUPABASE_CLIENT'] = None
        if not flask_app.debug:
            warnings.warn(
                "SUPABASE_URL and SUPABASE_KEY not set. "
                "Public user authentication will be disabled.",
                UserWarning
            )

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    from app.routes.auth import auth_bp
    from app.routes.quiz import quiz_bp
    from app.routes.bank import bank_bp
    from app.routes.moderation import moderation_bp

    flask_app.register_blueprint(main_bp)
    flask_app.register_blueprint(admin_bp, url_prefix='/admin')
    flask_app.register_blueprint(api_bp, url_prefix='/api')
    flask_app.register_blueprint(auth_bp)
    flask_app.register_blueprint(quiz_bp)
    flask_app.register_blueprint(bank_bp, url_prefix='/api/v1/bank')
    flask_app.register_blueprint(moderation_bp, url_prefix='/api/v1/admin/bank')

    if not skip_startup_tasks:
        _run_startup_tasks_once(flask_app)

    return flask_app


def _run_startup_tasks_once(flask_app):
    """Run startup tasks once per container even under multi-worker servers."""
    lock_path = os.path.join(tempfile.gettempdir(), 'prosno_startup.lock')
    done_path = os.path.join(tempfile.gettempdir(), 'prosno_startup.done')
    timeout_seconds = int(os.environ.get('STARTUP_LOCK_TIMEOUT', '180'))
    poll_interval = float(os.environ.get('STARTUP_LOCK_POLL_INTERVAL', '1'))
    deadline = time.time() + timeout_seconds
    lock_fd = None

    if os.path.exists(done_path):
        return

    while True:
        if os.path.exists(done_path):
            return

        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(lock_fd, str(os.getpid()).encode('ascii'))
            break
        except FileExistsError as exc:
            if time.time() >= deadline:
                raise TimeoutError(
                    'Timed out waiting for application startup tasks to finish.'
                ) from exc
            time.sleep(poll_interval)

    try:
        if os.path.exists(done_path):
            return
        _run_startup_tasks(flask_app)
        with open(done_path, 'w', encoding='ascii') as marker_file:
            marker_file.write(str(os.getpid()))
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
        if os.path.exists(lock_path):
            os.remove(lock_path)


def _run_startup_tasks(flask_app):
    """Initialise writable folders, database state, and background jobs."""
    output_folder = flask_app.config.get('OUTPUT_FOLDER', 'output')
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Created output folder: {output_folder}")

    _initialise_database_with_retries(flask_app)
    _start_background_scheduler(flask_app)


def _initialise_database_with_retries(flask_app):
    """Retry startup database work so deployment can survive a slow database."""
    max_attempts = int(os.environ.get('STARTUP_DB_MAX_ATTEMPTS', '10'))
    retry_delay = float(os.environ.get('STARTUP_DB_RETRY_DELAY', '3'))

    for attempt in range(1, max_attempts + 1):
        try:
            with flask_app.app_context():
                db.create_all()
                _apply_schema_migrations(db)

                from app.models import Class, User, ROLE_ADMIN
                if Class.query.count() == 0:
                    print("No classes found. Auto-seeding NCTB curriculum...")
                    _seed_nctb_data()

                if User.query.filter_by(is_admin=True).count() == 0:
                    print("No admin user found. Creating default admin...")
                    _create_admin_user()

                admin_users = User.query.filter_by(is_admin=True).all()
                for user in admin_users:
                    if user.role != ROLE_ADMIN:
                        user.role = ROLE_ADMIN
                        print(f"Upgraded user '{user.username}' to admin role")
                db.session.commit()

            return
        except Exception as exc:
            if attempt >= max_attempts:
                raise
            print(
                f"Startup database attempt {attempt}/{max_attempts} failed: {exc}. "
                f"Retrying in {retry_delay} seconds..."
            )
            time.sleep(retry_delay)


def _start_background_scheduler(flask_app):
    """Start the in-process scheduler once outside the Werkzeug reloader."""
    _is_reloader_child = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    _reloader_active = flask_app.debug and not _is_reloader_child
    if _reloader_active:
        return

    try:
        from app.utils.scheduler import start_scheduler
        start_scheduler(flask_app)
    except Exception as exc:
        print(f'Warning: Could not start background scheduler: {exc}')


def _create_admin_user():
    """Create default admin user if none exists"""
    import os
    import warnings
    from app.models import User, ROLE_ADMIN
    
    # Use environment variables for production, fallback for dev
    username = os.environ.get('ADMIN_USERNAME', 'Admin')
    password = os.environ.get('ADMIN_PASSWORD', '12345')
    email = os.environ.get('ADMIN_EMAIL', 'admin@prosno.io')
    
    # Security: refuse to create admin with default password in production
    if not os.environ.get('ADMIN_PASSWORD'):
        import flask
        # Check if running in production (not debug mode)
        # We can't easily check app.debug here, so check for production env vars
        if os.environ.get('RENDER') or os.environ.get('DYNO') or os.environ.get('PRODUCTION') or os.environ.get('COOLIFY'):
            print(
                "\n" + "=" * 60 + "\n"
                "CRITICAL: ADMIN_PASSWORD not set in production!\n"
                "Admin user NOT created. Set ADMIN_PASSWORD env var.\n"
                "=" * 60 + "\n"
            )
            return
        else:
            warnings.warn(
                "\n" + "=" * 60 + "\n"
                "SECURITY WARNING: Using default admin password '12345'!\n"
                "Set ADMIN_PASSWORD environment variable in production.\n"
                "=" * 60 + "\n",
                UserWarning
            )
    
    try:
        user = User(username=username, email=email, is_admin=True, role=ROLE_ADMIN)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f"Admin user '{username}' created successfully!")
    except Exception as e:
        db.session.rollback()
        print(f"Error creating admin user: {e}")


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


# Track if migrations have been applied in this process to avoid duplicate runs
_migrations_applied = False


def _apply_schema_migrations(db):
    """Apply database schema migrations for new columns (works without shell access)"""
    global _migrations_applied
    if _migrations_applied:
        return  # Skip if already applied in this process
    
    from sqlalchemy import text, inspect
    from app.models import OmrTemplate
    
    try:
        inspector = inspect(db.engine)

        if 'omr_templates' not in inspector.get_table_names():
            OmrTemplate.__table__.create(bind=db.engine, checkfirst=True)
            inspector = inspect(db.engine)
        
        # Define migrations: (table_name, column_name, column_definition)
        migrations = [
            # User table migrations
            ('users', 'role', "VARCHAR(20) DEFAULT 'editor'"),
            ('users', 'is_active_user', "BOOLEAN DEFAULT TRUE"),
            ('users', 'created_by_id', "INTEGER REFERENCES users(id)"),
            # Subject table migrations
            ('subjects', 'created_by_id', "INTEGER REFERENCES users(id)"),
            # Chapter table migrations  
            ('chapters', 'created_by_id', "INTEGER REFERENCES users(id)"),
            # GeneratedPaper migrations
            ('generated_papers', 'question_ids', "JSON"),
            ('generated_papers', 'custom_questions_json', "JSON"),
            ('generated_papers', 'custom_paper_config', "JSON"),
            ('generated_papers', 'omr_style', "BOOLEAN DEFAULT TRUE"),
            ('omr_templates', 'download_count', "INTEGER DEFAULT 0"),
            # QuestionSet sharing migrations
            ('question_sets', 'share_token', "VARCHAR(16)"),
            ('question_sets', 'is_shared', "BOOLEAN DEFAULT FALSE"),
            # CQ board/year migrations
            ('cq_questions', 'board', "VARCHAR(100)"),
            ('cq_questions', 'year', "INTEGER"),
            # Teacher Question Bank migrations
            ('teacher_profiles', 'trust_granted_by', "VARCHAR(100)"),
            ('bank_questions', 'text_hash', "VARCHAR(64)"),
            ('bank_questions', 'origin', "VARCHAR(20) DEFAULT 'manual'"),
            ('bank_questions', 'source_question_id', "INTEGER REFERENCES bank_questions(id)"),
            ('bank_questions', 'rejection_reason', "TEXT"),
            ('bank_questions', 'is_active', "BOOLEAN DEFAULT TRUE"),
            ('teacher_badges', 'badge_icon', "VARCHAR(10) DEFAULT '🏆'"),
            ('publish_prompts', 'published_ids', "JSON"),
            ('question_interactions', 'question_set_id', "INTEGER REFERENCES question_sets(id)"),
            ('question_interactions', 'paper_id', "INTEGER REFERENCES generated_papers(id)"),
        ]
        
        for table_name, column_name, column_def in migrations:
            # Check if table exists
            if table_name not in inspector.get_table_names():
                continue
            
            # Check if column already exists
            existing_columns = [col['name'] for col in inspector.get_columns(table_name)]
            if column_name not in existing_columns:
                # Add the column
                sql = text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}')
                db.session.execute(sql)
                print(f"Added column '{column_name}' to table '{table_name}'")
        
        db.session.commit()
        _migrations_applied = True
        print("Schema migrations applied successfully!")
        
    except Exception as e:
        db.session.rollback()
        _migrations_applied = True  # Mark as applied even on error to prevent retries
        print(f"Schema migration error (may be OK if columns exist): {e}")


# Create app instance for gunicorn (allows `gunicorn app:app`)
if os.environ.get('PROSNO_SKIP_GLOBAL_APP') == '1':
    app = None
else:
    app = create_app()
