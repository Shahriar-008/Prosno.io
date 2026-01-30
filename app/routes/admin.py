"""
Admin routes for Prosno.io
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime

from app import db
from app.models import User, Class, Subject, Chapter, Question, GeneratedPaper

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/login', methods=['GET', 'POST'])
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
            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('admin.dashboard'))
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
def delete_class(id):
    """Delete class"""
    class_obj = Class.query.get_or_404(id)
    db.session.delete(class_obj)
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
            order=int(order) if order else 0
        )
        db.session.add(new_subject)
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
def delete_subject(id):
    """Delete subject"""
    subject = Subject.query.get_or_404(id)
    db.session.delete(subject)
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
            order=int(order) if order else 0
        )
        db.session.add(new_chapter)
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
def delete_chapter(id):
    """Delete chapter"""
    chapter = Chapter.query.get_or_404(id)
    db.session.delete(chapter)
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
def delete_question(id):
    """Delete question"""
    question = Question.query.get_or_404(id)
    db.session.delete(question)
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
            flash(f'Error uploading questions: {str(e)}', 'error')
    
    chapters = Chapter.query.filter_by(is_active=True).all()
    return render_template('admin/bulk_upload.html', chapters=chapters)


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
