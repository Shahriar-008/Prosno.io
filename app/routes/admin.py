"""
Admin routes for Prosno.io
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse, urljoin

from app import db, limiter


def is_safe_url(target: str) -> bool:
    """
    Validate that the redirect URL is safe to prevent open redirect attacks.
    Only allows internal URLs (same host or relative paths).
    """
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc
from app.models import (
    User, Class, Subject, Chapter, Question, GeneratedPaper,
    AIGeneratorConfig, AIGeneratorLog, ActivityLog,
    ShortQuestion, CQQuestion,
    ROLE_ADMIN, ROLE_EDITOR, admin_required,
)

admin_bp = Blueprint('admin', __name__)


def log_activity(action, entity_type, entity_id=None, entity_name=None, details=None):
    """Helper function to log user activities"""
    log = ActivityLog(
        user_id=current_user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        details=details
    )
    db.session.add(log)


@admin_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("3 per minute", methods=["POST"])
def login():
    """Admin login page"""
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False)
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            # Check if user is active
            if hasattr(user, 'is_active_user') and not user.is_active_user:
                flash('Your account has been disabled. Contact admin.', 'error')
                return render_template('admin/login.html')
            
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Clear and regenerate session to prevent session fixation attacks
            session.clear()
            
            login_user(user, remember=remember)
            
            # Validate redirect URL to prevent open redirect attacks
            next_page = request.args.get('next')
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('admin/login.html')


@admin_bp.route('/logout')
@login_required
def logout():
    """Logout user"""
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('admin.login'))


@admin_bp.route('/')
@admin_bp.route('/dashboard')
@login_required
def dashboard():
    """Admin dashboard"""
    stats = {
        'classes': Class.query.count(),
        'subjects': Subject.query.count(),
        'chapters': Chapter.query.count(),
        'questions': Question.query.count(),
        'papers_generated': GeneratedPaper.query.count(),
        'total_downloads': db.session.query(db.func.sum(GeneratedPaper.download_count)).scalar() or 0
    }
    
    recent_papers = GeneratedPaper.query.order_by(
        GeneratedPaper.created_at.desc()
    ).limit(5).all()
    
    return render_template('admin/dashboard.html', stats=stats, recent_papers=recent_papers)


# ========== Class Management ==========
@admin_bp.route('/classes')
@login_required
def classes():
    """List all classes"""
    classes = Class.query.order_by(Class.order).all()
    return render_template('admin/classes.html', classes=classes)


@admin_bp.route('/classes/add', methods=['GET', 'POST'])
@login_required
def add_class():
    """Add new class"""
    if request.method == 'POST':
        name = request.form.get('name')
        name_bn = request.form.get('name_bn')
        level = request.form.get('level')
        order = request.form.get('order', 0)
        
        new_class = Class(
            name=name,
            name_bn=name_bn,
            level=level,
            order=int(order) if order else 0
        )
        db.session.add(new_class)
        db.session.commit()
        flash('Class added successfully!', 'success')
        return redirect(url_for('admin.classes'))
    
    return render_template('admin/class_form.html', class_obj=None)


@admin_bp.route('/classes/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_class(id):
    """Edit class"""
    class_obj = Class.query.get_or_404(id)
    
    if request.method == 'POST':
        class_obj.name = request.form.get('name')
        class_obj.name_bn = request.form.get('name_bn')
        class_obj.level = request.form.get('level')
        class_obj.order = int(request.form.get('order', 0))
        class_obj.is_active = request.form.get('is_active') == 'on'
        
        db.session.commit()
        flash('Class updated successfully!', 'success')
        return redirect(url_for('admin.classes'))
    
    return render_template('admin/class_form.html', class_obj=class_obj)


@admin_bp.route('/classes/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_class(id):
    """Delete class - admin only"""
    class_obj = Class.query.get_or_404(id)
    name = class_obj.name
    db.session.delete(class_obj)
    log_activity('delete', 'class', entity_id=id, entity_name=name)
    db.session.commit()
    flash('Class deleted successfully!', 'success')
    return redirect(url_for('admin.classes'))


# ========== Subject Management ==========
@admin_bp.route('/subjects')
@login_required
def subjects():
    """List all subjects"""
    subjects = Subject.query.order_by(Subject.class_id, Subject.order).all()
    return render_template('admin/subjects.html', subjects=subjects)


@admin_bp.route('/subjects/add', methods=['GET', 'POST'])
@login_required
def add_subject():
    """Add new subject"""
    if request.method == 'POST':
        name = request.form.get('name')
        name_bn = request.form.get('name_bn')
        code = request.form.get('code')
        class_id = request.form.get('class_id')
        order = request.form.get('order', 0)
        
        new_subject = Subject(
            name=name,
            name_bn=name_bn,
            code=code,
            class_id=int(class_id),
            order=int(order) if order else 0,
            created_by_id=current_user.id
        )
        db.session.add(new_subject)
        db.session.flush()  # Get the ID
        log_activity('add', 'subject', entity_id=new_subject.id, entity_name=name)
        db.session.commit()
        flash('Subject added successfully!', 'success')
        return redirect(url_for('admin.subjects'))
    
    classes = Class.query.filter_by(is_active=True).order_by(Class.order).all()
    return render_template('admin/subject_form.html', subject=None, classes=classes)


@admin_bp.route('/subjects/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_subject(id):
    """Edit subject"""
    subject = Subject.query.get_or_404(id)
    
    if request.method == 'POST':
        subject.name = request.form.get('name')
        subject.name_bn = request.form.get('name_bn')
        subject.code = request.form.get('code')
        subject.class_id = int(request.form.get('class_id'))
        subject.order = int(request.form.get('order', 0))
        subject.is_active = request.form.get('is_active') == 'on'
        
        db.session.commit()
        flash('Subject updated successfully!', 'success')
        return redirect(url_for('admin.subjects'))
    
    classes = Class.query.filter_by(is_active=True).order_by(Class.order).all()
    return render_template('admin/subject_form.html', subject=subject, classes=classes)


@admin_bp.route('/subjects/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_subject(id):
    """Delete subject - admin only"""
    subject = Subject.query.get_or_404(id)
    name = subject.name
    db.session.delete(subject)
    log_activity('delete', 'subject', entity_id=id, entity_name=name)
    db.session.commit()
    flash('Subject deleted successfully!', 'success')
    return redirect(url_for('admin.subjects'))


# ========== Chapter Management ==========
@admin_bp.route('/chapters')
@login_required
def chapters():
    """List all chapters"""
    chapters = Chapter.query.order_by(Chapter.subject_id, Chapter.order).all()
    return render_template('admin/chapters.html', chapters=chapters)


@admin_bp.route('/chapters/add', methods=['GET', 'POST'])
@login_required
def add_chapter():
    """Add new chapter"""
    if request.method == 'POST':
        name = request.form.get('name')
        name_bn = request.form.get('name_bn')
        chapter_number = request.form.get('chapter_number')
        subject_id = request.form.get('subject_id')
        order = request.form.get('order', 0)
        
        new_chapter = Chapter(
            name=name,
            name_bn=name_bn,
            chapter_number=int(chapter_number) if chapter_number else None,
            subject_id=int(subject_id),
            order=int(order) if order else 0,
            created_by_id=current_user.id
        )
        db.session.add(new_chapter)
        db.session.flush()  # Get the ID
        log_activity('add', 'chapter', entity_id=new_chapter.id, entity_name=name)
        db.session.commit()
        flash('Chapter added successfully!', 'success')
        return redirect(url_for('admin.chapters'))
    
    subjects = Subject.query.filter_by(is_active=True).order_by(Subject.order).all()
    return render_template('admin/chapter_form.html', chapter=None, subjects=subjects)


@admin_bp.route('/chapters/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_chapter(id):
    """Edit chapter"""
    chapter = Chapter.query.get_or_404(id)
    
    if request.method == 'POST':
        chapter.name = request.form.get('name')
        chapter.name_bn = request.form.get('name_bn')
        chapter_number = request.form.get('chapter_number')
        chapter.chapter_number = int(chapter_number) if chapter_number else None
        chapter.subject_id = int(request.form.get('subject_id'))
        chapter.order = int(request.form.get('order', 0))
        chapter.is_active = request.form.get('is_active') == 'on'
        
        db.session.commit()
        flash('Chapter updated successfully!', 'success')
        return redirect(url_for('admin.chapters'))
    
    subjects = Subject.query.filter_by(is_active=True).order_by(Subject.order).all()
    return render_template('admin/chapter_form.html', chapter=chapter, subjects=subjects)


@admin_bp.route('/chapters/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_chapter(id):
    """Delete chapter - admin only"""
    chapter = Chapter.query.get_or_404(id)
    name = chapter.name
    db.session.delete(chapter)
    log_activity('delete', 'chapter', entity_id=id, entity_name=name)
    db.session.commit()
    flash('Chapter deleted successfully!', 'success')
    return redirect(url_for('admin.chapters'))


# ========== Question Management ==========
@admin_bp.route('/questions')
@login_required
def questions():
    """List all questions"""
    page = request.args.get('page', 1, type=int)
    chapter_filter = request.args.get('chapter', type=int)
    
    query = Question.query.order_by(Question.created_at.desc())
    
    if chapter_filter:
        query = query.filter_by(chapter_id=chapter_filter)
    
    questions = query.paginate(page=page, per_page=20)
    chapters = Chapter.query.filter_by(is_active=True).all()
    
    return render_template('admin/questions.html', 
                          questions=questions, 
                          chapters=chapters,
                          current_chapter=chapter_filter)


@admin_bp.route('/questions/add', methods=['GET', 'POST'])
@login_required
def add_question():
    """Add new question"""
    if request.method == 'POST':
        question_text = request.form.get('question_text')
        question_type = request.form.get('question_type', 'simple')
        chapter_id = request.form.get('chapter_id')
        difficulty = request.form.get('difficulty', 'medium')
        
        # Get answer options
        options = [
            request.form.get('option_1'),
            request.form.get('option_2'),
            request.form.get('option_3'),
            request.form.get('option_4')
        ]
        correct_answer = request.form.get('correct_answer')
        
        # Handle complex questions
        sub_options = None
        final_prompt = None
        if question_type == 'complex':
            sub_options = request.form.getlist('sub_options')
            final_prompt = request.form.get('final_prompt')
        
        new_question = Question(
            question_text=question_text,
            question_type=question_type,
            chapter_id=int(chapter_id),
            answer_options=options,
            correct_answer=correct_answer,
            sub_options=sub_options,
            final_prompt=final_prompt,
            difficulty=difficulty,
            created_by=current_user.id
        )
        db.session.add(new_question)
        db.session.flush()  # Get the ID
        log_activity('add', 'question', entity_id=new_question.id, entity_name=question_text[:50])
        db.session.commit()
        flash('Question added successfully!', 'success')
        return redirect(url_for('admin.questions'))
    
    chapters = Chapter.query.filter_by(is_active=True).all()
    return render_template('admin/question_form.html', question=None, chapters=chapters)


@admin_bp.route('/questions/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_question(id):
    """Edit question"""
    question = Question.query.get_or_404(id)
    
    if request.method == 'POST':
        question.question_text = request.form.get('question_text')
        question.question_type = request.form.get('question_type', 'simple')
        question.chapter_id = int(request.form.get('chapter_id'))
        question.difficulty = request.form.get('difficulty', 'medium')
        
        # Get answer options
        options = [
            request.form.get('option_1'),
            request.form.get('option_2'),
            request.form.get('option_3'),
            request.form.get('option_4')
        ]
        question.answer_options = options
        question.correct_answer = request.form.get('correct_answer')
        
        # Handle complex questions
        if question.question_type == 'complex':
            question.sub_options = request.form.getlist('sub_options')
            question.final_prompt = request.form.get('final_prompt')
        else:
            question.sub_options = None
            question.final_prompt = None
        
        question.is_active = request.form.get('is_active') == 'on'
        
        db.session.commit()
        flash('Question updated successfully!', 'success')
        return redirect(url_for('admin.questions'))
    
    chapters = Chapter.query.filter_by(is_active=True).all()
    return render_template('admin/question_form.html', question=question, chapters=chapters)


@admin_bp.route('/questions/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_question(id):
    """Delete question - admin only"""
    question = Question.query.get_or_404(id)
    db.session.delete(question)
    log_activity('delete', 'question', entity_id=id)
    db.session.commit()
    flash('Question deleted successfully!', 'success')
    return redirect(url_for('admin.questions'))


@admin_bp.route('/questions/bulk-upload', methods=['GET', 'POST'])
@login_required
def bulk_upload_questions():
    """Bulk upload questions from JSON"""
    if request.method == 'POST':
        import json
        
        chapter_id = request.form.get('chapter_id')
        json_data = request.form.get('json_data')
        
        try:
            questions = json.loads(json_data)
            count = 0
            
            for q in questions:
                new_question = Question(
                    question_text=q.get('question_text'),
                    question_type=q.get('type', 'simple'),
                    chapter_id=int(chapter_id),
                    answer_options=q.get('answer_options', []),
                    correct_answer=q.get('correct_answer', ''),
                    sub_options=q.get('sub_options'),
                    final_prompt=q.get('final_prompt'),
                    created_by=current_user.id
                )
                db.session.add(new_question)
                count += 1
            
            db.session.commit()
            flash(f'Successfully uploaded {count} questions!', 'success')
            return redirect(url_for('admin.questions'))
            
        except json.JSONDecodeError:
            flash('Invalid JSON format', 'error')
        except Exception as e:
            current_app.logger.error(f'Bulk upload error: {e}')
            flash('Error uploading questions. Please check your data format.', 'error')
    
    classes = Class.query.filter_by(is_active=True).order_by(Class.order).all()
    return render_template('admin/bulk_upload.html', classes=classes)


# ========== Generated Papers ==========
@admin_bp.route('/papers')
@login_required
def papers():
    """List all generated papers"""
    page = request.args.get('page', 1, type=int)
    papers = GeneratedPaper.query.order_by(
        GeneratedPaper.created_at.desc()
    ).paginate(page=page, per_page=20)
    
    return render_template('admin/papers.html', papers=papers)


# ========== AI Question Generator ==========
@admin_bp.route('/ai-generator')
@login_required
def ai_generator():
    """AI Generator dashboard"""
    from app.utils.ai_generator import get_generator_status, DEFAULT_PROMPT_TEMPLATE
    from flask import current_app
    
    config = AIGeneratorConfig.query.first()
    
    # Create default config if not exists
    if not config:
        config = AIGeneratorConfig(
            prompt_template=DEFAULT_PROMPT_TEMPLATE,
            questions_per_request=5,
            interval_minutes=5,
            max_requests_per_hour=20
        )
        db.session.add(config)
        db.session.commit()
    
    classes = Class.query.filter_by(is_active=True).order_by(Class.order).all()
    status = get_generator_status(current_app._get_current_object())
    
    return render_template('admin/ai_generator.html', 
                          config=config, 
                          classes=classes, 
                          status=status,
                          default_prompt=DEFAULT_PROMPT_TEMPLATE)


@admin_bp.route('/ai-generator/settings', methods=['POST'])
@login_required
@admin_required
def ai_generator_settings():
    """Update AI Generator settings"""
    from app.utils.ai_generator import DEFAULT_PROMPT_TEMPLATE
    
    config = AIGeneratorConfig.query.first()
    if not config:
        config = AIGeneratorConfig()
        db.session.add(config)
    
    # Update settings
    config.api_key = request.form.get('api_key', config.api_key)
    config.api_provider = request.form.get('api_provider', 'openai')
    config.model_name = request.form.get('model_name', 'gpt-4o-mini')
    config.questions_per_request = int(request.form.get('questions_per_request', 5))
    config.interval_minutes = int(request.form.get('interval_minutes', 5))
    config.max_requests_per_hour = int(request.form.get('max_requests_per_hour', 20))
    
    prompt = request.form.get('prompt_template', '').strip()
    config.prompt_template = prompt if prompt else DEFAULT_PROMPT_TEMPLATE
    
    db.session.commit()
    flash('Settings saved successfully!', 'success')
    
    return redirect(url_for('admin.ai_generator'))


@admin_bp.route('/ai-generator/start', methods=['POST'])
@login_required
@admin_required
def ai_generator_start():
    """Start the AI generator"""
    from app.utils.ai_generator import start_generator
    from flask import current_app
    
    start_class_id = request.form.get('start_class_id', type=int)
    start_subject_id = request.form.get('start_subject_id', type=int)
    start_chapter_id = request.form.get('start_chapter_id', type=int)
    
    success, message = start_generator(
        current_app._get_current_object(),
        start_class_id,
        start_subject_id,
        start_chapter_id
    )
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('admin.ai_generator'))


@admin_bp.route('/ai-generator/stop', methods=['POST'])
@login_required
@admin_required
def ai_generator_stop():
    """Stop the AI generator"""
    from app.utils.ai_generator import stop_generator
    from flask import current_app
    
    success, message = stop_generator(current_app._get_current_object())
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('admin.ai_generator'))


@admin_bp.route('/ai-generator/status')
@login_required
def ai_generator_status():
    """Get current AI generator status (JSON)"""
    from app.utils.ai_generator import get_generator_status
    from flask import current_app
    
    status = get_generator_status(current_app._get_current_object())
    return jsonify(status)


@admin_bp.route('/ai-generator/logs')
@login_required
def ai_generator_logs():
    """View AI generator logs"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    
    query = AIGeneratorLog.query
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    logs = query.order_by(AIGeneratorLog.created_at.desc()).paginate(page=page, per_page=50)
    
    return render_template('admin/ai_generator_logs.html', logs=logs, status_filter=status_filter)


@admin_bp.route('/ai-generator/reset-stats', methods=['POST'])
@login_required
@admin_required
def ai_generator_reset_stats():
    """Reset AI generator statistics"""
    config = AIGeneratorConfig.query.first()
    if config:
        config.total_questions_generated = 0
        config.total_duplicates_skipped = 0
        config.total_errors = 0
        config.requests_this_hour = 0
        db.session.commit()
        flash('Statistics reset successfully!', 'success')
    
    return redirect(url_for('admin.ai_generator'))


@admin_bp.route('/ai-generator/clear-logs', methods=['POST'])
@login_required
@admin_required
def ai_generator_clear_logs():
    """Clear all AI generator logs"""
    AIGeneratorLog.query.delete()
    db.session.commit()
    flash('Logs cleared successfully!', 'success')
    
    return redirect(url_for('admin.ai_generator'))


# ========== User Management (Admin Only) ==========
@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """List all users - admin only"""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)


@admin_bp.route('/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    """Add new user - admin only"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', ROLE_EDITOR)
        
        # Password validation
        if not password or len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('admin/user_form.html', user=None, ROLE_ADMIN=ROLE_ADMIN, ROLE_EDITOR=ROLE_EDITOR)
        
        # Validate
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'error')
            return render_template('admin/user_form.html', user=None)
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists!', 'error')
            return render_template('admin/user_form.html', user=None)
        
        new_user = User(
            username=username,
            email=email,
            role=role,
            is_admin=(role == ROLE_ADMIN),
            created_by_id=current_user.id
        )
        new_user.set_password(password)
        db.session.add(new_user)
        
        log_activity('add', 'user', entity_name=username, details={'role': role})
        db.session.commit()
        
        flash(f'User "{username}" created successfully!', 'success')
        return redirect(url_for('admin.users'))
    
    return render_template('admin/user_form.html', user=None, ROLE_ADMIN=ROLE_ADMIN, ROLE_EDITOR=ROLE_EDITOR)


@admin_bp.route('/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(id):
    """Edit user - admin only"""
    user = User.query.get_or_404(id)
    
    # Prevent editing self through this form (use profile instead)
    if user.id == current_user.id:
        flash('Use profile settings to edit your own account.', 'info')
        return redirect(url_for('admin.users'))
    
    if request.method == 'POST':
        user.username = request.form.get('username')
        user.email = request.form.get('email')
        user.role = request.form.get('role', ROLE_EDITOR)
        user.is_admin = (user.role == ROLE_ADMIN)
        user.is_active_user = request.form.get('is_active') == 'on'
        
        # Only update password if provided
        new_password = request.form.get('password')
        if new_password:
            user.set_password(new_password)
        
        log_activity('edit', 'user', entity_id=user.id, entity_name=user.username)
        db.session.commit()
        
        flash('User updated successfully!', 'success')
        return redirect(url_for('admin.users'))
    
    return render_template('admin/user_form.html', user=user, ROLE_ADMIN=ROLE_ADMIN, ROLE_EDITOR=ROLE_EDITOR)


@admin_bp.route('/users/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_user(id):
    """Delete user - admin only"""
    user = User.query.get_or_404(id)
    
    # Prevent self-deletion
    if user.id == current_user.id:
        flash('You cannot delete your own account!', 'error')
        return redirect(url_for('admin.users'))
    
    username = user.username
    db.session.delete(user)
    log_activity('delete', 'user', entity_name=username)
    db.session.commit()
    
    flash(f'User "{username}" deleted successfully!', 'success')
    return redirect(url_for('admin.users'))


# ========== Activity Log (Admin Only) ==========
@admin_bp.route('/activity-log')
@login_required
@admin_required
def activity_log():
    """View activity log - admin only"""
    page = request.args.get('page', 1, type=int)
    user_filter = request.args.get('user', type=int)
    action_filter = request.args.get('action')
    
    query = ActivityLog.query
    
    if user_filter:
        query = query.filter_by(user_id=user_filter)
    if action_filter:
        query = query.filter_by(action=action_filter)
    
    logs = query.order_by(ActivityLog.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    users = User.query.all()
    return render_template('admin/activity_log.html', logs=logs, users=users, 
                         current_user_filter=user_filter, current_action_filter=action_filter)


# ========== Short Question Management ==========
@admin_bp.route('/short-questions')
@login_required
def short_questions():
    """List all short questions"""
    page = request.args.get('page', 1, type=int)
    subject_filter = request.args.get('subject', type=int)
    chapter_filter = request.args.get('chapter', type=int)

    query = ShortQuestion.query.filter_by(is_active=True)

    if subject_filter:
        query = query.filter_by(subject_id=subject_filter)
    if chapter_filter:
        query = query.filter_by(chapter_id=chapter_filter)

    questions = query.order_by(
        ShortQuestion.created_at.desc()
    ).paginate(page=page, per_page=20)

    subjects = Subject.query.filter_by(
        is_active=True
    ).order_by(Subject.order).all()

    return render_template(
        'admin/short_questions.html',
        questions=questions,
        subjects=subjects,
        current_subject=subject_filter,
        current_chapter=chapter_filter,
    )


@admin_bp.route('/short-questions/new', methods=['GET', 'POST'])
@login_required
def add_short_question():
    """Add new short question"""
    if request.method == 'POST':
        subject_id = request.form.get('subject_id', type=int)
        chapter_id = request.form.get('chapter_id', type=int) or None
        question_text = request.form.get('question_text', '').strip()
        marks = request.form.get('marks', 2, type=int)

        if not subject_id or not question_text:
            flash('বিষয় এবং প্রশ্ন আবশ্যক।', 'error')
            classes = Class.query.filter_by(is_active=True).order_by(Class.order).all()
            return render_template(
                'admin/short_question_form.html', question=None, classes=classes,
                selected_class_id=None
            )

        sq = ShortQuestion(
            subject_id=subject_id,
            chapter_id=chapter_id,
            question_text=question_text,
            marks=marks,
            created_by=current_user.id,
        )
        db.session.add(sq)
        db.session.flush()
        log_activity(
            'create', 'short_question',
            entity_id=sq.id,
            entity_name=question_text[:50],
        )
        db.session.commit()
        flash('সংক্ষিপ্ত প্রশ্ন সফলভাবে যোগ করা হয়েছে!', 'success')
        return redirect(url_for('admin.short_questions'))

    classes = Class.query.filter_by(is_active=True).order_by(Class.order).all()
    return render_template(
        'admin/short_question_form.html', question=None, classes=classes,
        selected_class_id=None
    )


@admin_bp.route('/short-questions/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_short_question(id):
    """Edit short question"""
    sq = ShortQuestion.query.get_or_404(id)

    if request.method == 'POST':
        sq.subject_id = request.form.get('subject_id', type=int)
        sq.chapter_id = request.form.get('chapter_id', type=int) or None
        sq.question_text = request.form.get('question_text', '').strip()
        sq.marks = request.form.get('marks', 2, type=int)

        log_activity(
            'edit', 'short_question',
            entity_id=sq.id,
            entity_name=sq.question_text[:50],
        )
        db.session.commit()
        flash('সংক্ষিপ্ত প্রশ্ন আপডেট করা হয়েছে!', 'success')
        return redirect(url_for('admin.short_questions'))

    classes = Class.query.filter_by(is_active=True).order_by(Class.order).all()
    selected_class_id = sq.subject.class_id if sq.subject else None
    return render_template(
        'admin/short_question_form.html', question=sq, classes=classes,
        selected_class_id=selected_class_id
    )


@admin_bp.route('/short-questions/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_short_question(id):
    """Soft-delete short question — admin only"""
    sq = ShortQuestion.query.get_or_404(id)
    sq.is_active = False
    log_activity(
        'delete', 'short_question',
        entity_id=sq.id,
        entity_name=sq.question_text[:50],
    )
    db.session.commit()
    flash('সংক্ষিপ্ত প্রশ্ন মুছে ফেলা হয়েছে!', 'success')
    return redirect(url_for('admin.short_questions'))


# ========== Creative Question Management ==========
@admin_bp.route('/cq-questions')
@login_required
def cq_questions():
    """List all creative questions"""
    page = request.args.get('page', 1, type=int)
    subject_filter = request.args.get('subject', type=int)
    chapter_filter = request.args.get('chapter', type=int)

    query = CQQuestion.query.filter_by(is_active=True)

    if subject_filter:
        query = query.filter_by(subject_id=subject_filter)
    if chapter_filter:
        query = query.filter_by(chapter_id=chapter_filter)

    questions = query.order_by(
        CQQuestion.created_at.desc()
    ).paginate(page=page, per_page=20)

    subjects = Subject.query.filter_by(
        is_active=True
    ).order_by(Subject.order).all()

    return render_template(
        'admin/cq_questions.html',
        questions=questions,
        subjects=subjects,
        current_subject=subject_filter,
        current_chapter=chapter_filter,
    )


@admin_bp.route('/cq-questions/new', methods=['GET', 'POST'])
@login_required
def add_cq_question():
    """Add new creative question"""
    if request.method == 'POST':
        subject_id = request.form.get('subject_id', type=int)
        chapter_id = request.form.get('chapter_id', type=int) or None
        stem = request.form.get('stem', '').strip()

        if not subject_id or not stem:
            flash('বিষয় এবং উদ্দীপক আবশ্যক।', 'error')
            classes = Class.query.filter_by(is_active=True).order_by(Class.order).all()
            return render_template(
                'admin/cq_question_form.html', question=None, classes=classes,
                selected_class_id=None
            )

        cq = CQQuestion(
            subject_id=subject_id,
            chapter_id=chapter_id,
            stem=stem,
            part_ka=request.form.get('part_ka', '').strip() or None,
            part_kha=request.form.get('part_kha', '').strip() or None,
            part_ga=request.form.get('part_ga', '').strip() or None,
            part_gha=request.form.get('part_gha', '').strip() or None,
            marks_ka=request.form.get('marks_ka', 1, type=int),
            marks_kha=request.form.get('marks_kha', 2, type=int),
            marks_ga=request.form.get('marks_ga', 3, type=int),
            marks_gha=request.form.get('marks_gha', 4, type=int),
            created_by=current_user.id,
        )
        db.session.add(cq)
        db.session.flush()
        log_activity(
            'create', 'cq_question',
            entity_id=cq.id,
            entity_name=stem[:50],
        )
        db.session.commit()
        flash('সৃজনশীল প্রশ্ন সফলভাবে যোগ করা হয়েছে!', 'success')
        return redirect(url_for('admin.cq_questions'))

    classes = Class.query.filter_by(is_active=True).order_by(Class.order).all()
    return render_template(
        'admin/cq_question_form.html', question=None, classes=classes,
        selected_class_id=None
    )


@admin_bp.route('/cq-questions/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_cq_question(id):
    """Edit creative question"""
    cq = CQQuestion.query.get_or_404(id)

    if request.method == 'POST':
        cq.subject_id = request.form.get('subject_id', type=int)
        cq.chapter_id = request.form.get('chapter_id', type=int) or None
        cq.stem = request.form.get('stem', '').strip()
        cq.part_ka = request.form.get('part_ka', '').strip() or None
        cq.part_kha = request.form.get('part_kha', '').strip() or None
        cq.part_ga = request.form.get('part_ga', '').strip() or None
        cq.part_gha = request.form.get('part_gha', '').strip() or None
        cq.marks_ka = request.form.get('marks_ka', 1, type=int)
        cq.marks_kha = request.form.get('marks_kha', 2, type=int)
        cq.marks_ga = request.form.get('marks_ga', 3, type=int)
        cq.marks_gha = request.form.get('marks_gha', 4, type=int)

        log_activity(
            'edit', 'cq_question',
            entity_id=cq.id,
            entity_name=cq.stem[:50],
        )
        db.session.commit()
        flash('সৃজনশীল প্রশ্ন আপডেট করা হয়েছে!', 'success')
        return redirect(url_for('admin.cq_questions'))

    classes = Class.query.filter_by(is_active=True).order_by(Class.order).all()
    selected_class_id = cq.subject.class_id if cq.subject else None
    return render_template(
        'admin/cq_question_form.html', question=cq, classes=classes,
        selected_class_id=selected_class_id
    )


@admin_bp.route('/cq-questions/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_cq_question(id):
    """Soft-delete creative question — admin only"""
    cq = CQQuestion.query.get_or_404(id)
    cq.is_active = False
    log_activity(
        'delete', 'cq_question',
        entity_id=cq.id,
        entity_name=cq.stem[:50],
    )
    db.session.commit()
    flash('সৃজনশীল প্রশ্ন মুছে ফেলা হয়েছে!', 'success')
    return redirect(url_for('admin.cq_questions'))
