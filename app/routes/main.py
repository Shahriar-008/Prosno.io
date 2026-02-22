"""
Main routes for Prosno.io
"""
from datetime import datetime, date
from flask import Blueprint, render_template, request, jsonify, send_file, current_app, abort, session
import os

from app import db, csrf, limiter
from app.models import Class, Subject, Chapter, Question, GeneratedPaper, QuestionSet, GenerationLog
from app.utils.document_generator import generate_paper_from_db, generate_paper_to_memory
from app.utils.pdf_generator import generate_paper_to_memory_pdf

main_bp = Blueprint('main', __name__)

# --- Anti-scraping limits ---
MAX_QUESTIONS_PER_PAPER = 50       # Max questions allowed in one paper
MAX_CHAPTERS_PER_REQUEST = 5       # Max chapters that can be queried at once
DAILY_GENERATION_LIMIT = 10        # Max papers a logged-in user can generate per day


def _get_user_credits(user_id):
    """Return (used, limit, remaining) for the user's daily paper generation quota."""
    today_start = datetime.combine(date.today(), datetime.min.time())
    used = GenerationLog.query.filter(
        GenerationLog.user_id == user_id,
        GenerationLog.created_at >= today_start
    ).count()
    remaining = max(0, DAILY_GENERATION_LIMIT - used)
    return used, DAILY_GENERATION_LIMIT, remaining


def _log_generation(user_id, gen_type='db'):
    """Record a paper generation event for the credit system."""
    log = GenerationLog(user_id=user_id, generation_type=gen_type)
    db.session.add(log)


@main_bp.route('/')
def index():
    """Landing page"""
    classes = Class.query.filter_by(is_active=True).order_by(Class.order).all()
    return render_template('main/index.html', classes=classes)


@main_bp.route('/generate', methods=['GET', 'POST'])
def generate():
    """Question paper generation page"""
    classes = Class.query.filter_by(is_active=True).order_by(Class.order).all()
    return render_template('main/generate.html', classes=classes)


@main_bp.route('/get-subjects/<int:class_id>')
def get_subjects(class_id):
    """Get subjects for a class"""
    subjects = Subject.query.filter_by(
        class_id=class_id, 
        is_active=True
    ).order_by(Subject.order).all()
    
    return jsonify([{
        'id': s.id,
        'name': s.name,
        'name_bn': s.name_bn or s.name
    } for s in subjects])


@main_bp.route('/get-chapters/<int:subject_id>')
def get_chapters(subject_id):
    """Get chapters for a subject"""
    chapters = Chapter.query.filter_by(
        subject_id=subject_id,
        is_active=True
    ).order_by(Chapter.order).all()
    
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'name_bn': c.name_bn or c.name,
        'chapter_number': c.chapter_number
    } for c in chapters])


@main_bp.route('/get-question-count', methods=['POST'])
def get_question_count():
    """Get count of available questions for selected chapters"""
    data = request.get_json()
    chapter_ids = data.get('chapter_ids', [])
    
    if not chapter_ids:
        return jsonify({'count': 0})
    
    count = Question.query.filter(
        Question.chapter_id.in_(chapter_ids),
        Question.is_active == True
    ).count()
    
    return jsonify({'count': count})


@main_bp.route('/get-questions-for-chapters', methods=['POST'])
@limiter.limit("30 per minute")
def get_questions_for_chapters():
    """Get question previews for selected chapters (truncated, no full text)."""
    data = request.get_json()
    chapter_ids = data.get('chapter_ids', [])
    
    if not chapter_ids:
        return jsonify({'questions': []})
    
    # Limit chapters per request to prevent bulk scraping
    if len(chapter_ids) > MAX_CHAPTERS_PER_REQUEST:
        return jsonify({
            'error': f'Maximum {MAX_CHAPTERS_PER_REQUEST} chapters can be selected at once.'
        }), 400
    
    questions = Question.query.filter(
        Question.chapter_id.in_(chapter_ids),
        Question.is_active == True
    ).order_by(Question.chapter_id, Question.id).all()
    
    # Group by chapter
    chapters_info = {}
    for q in questions:
        if q.chapter_id not in chapters_info:
            chapter = Chapter.query.get(q.chapter_id)
            chapters_info[q.chapter_id] = {
                'id': chapter.id,
                'name': chapter.name_bn or chapter.name,
                'chapter_number': chapter.chapter_number
            }
    
    # Only send question text for preview — options/answers stay server-side
    return jsonify({
        'questions': [{
            'id': q.id,
            'question_text': q.question_text[:100] + '...' if len(q.question_text) > 100 else q.question_text,
            'full_text': q.question_text,
            'type': q.question_type,
            'chapter_id': q.chapter_id,
            'difficulty': q.difficulty
        } for q in questions],
        'chapters': chapters_info
    })


@main_bp.route('/generate-paper', methods=['POST'])
@limiter.limit("20 per minute")
@limiter.limit("10 per day")
def generate_paper():
    """Generate question paper"""
    # --- Credit check for logged-in users ---
    user = session.get('user')
    if user:
        _used, _limit, _remaining = _get_user_credits(user['id'])
        if _remaining <= 0:
            return jsonify({
                'error': 'Daily generation limit reached (0 credits left). Please wait until tomorrow.',
                'credits_exhausted': True
            }), 429

    data = request.get_json()
    
    class_id = data.get('class_id')
    subject_id = data.get('subject_id')
    chapter_ids = data.get('chapter_ids', [])
    question_ids = data.get('question_ids', [])  # Specific question IDs if selected
    question_count = data.get('question_count', 30)
    time_minutes = data.get('time_minutes', 30)
    paper_title = data.get('title', 'Home Test')
    randomize = data.get('randomize', False)
    omr_style = data.get('omr_style', True)
    
    # Validate input
    if not all([class_id, subject_id, chapter_ids]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Enforce chapter limit
    if len(chapter_ids) > MAX_CHAPTERS_PER_REQUEST:
        return jsonify({'error': f'Maximum {MAX_CHAPTERS_PER_REQUEST} chapters allowed per paper.'}), 400
    
    # Get class and subject info
    class_obj = Class.query.get(class_id)
    subject_obj = Subject.query.get(subject_id)
    
    if not class_obj or not subject_obj:
        return jsonify({'error': 'Invalid class or subject'}), 400
    
    # Fetch questions - either specific IDs or from chapters
    if question_ids:
        # Enforce question limit
        if len(question_ids) > MAX_QUESTIONS_PER_PAPER:
            return jsonify({
                'error': f'Maximum {MAX_QUESTIONS_PER_PAPER} questions allowed per paper.'
            }), 400
        
        # User selected specific questions
        questions = Question.query.filter(
            Question.id.in_(question_ids),
            Question.is_active == True
        ).all()
        # Preserve order if not randomizing
        if not randomize:
            question_order = {qid: idx for idx, qid in enumerate(question_ids)}
            questions = sorted(questions, key=lambda q: question_order.get(q.id, 0))
        else:
            import random
            random.shuffle(questions)
    else:
        # Random selection from chapters (legacy behavior)
        capped_count = min(question_count, MAX_QUESTIONS_PER_PAPER)
        questions = Question.query.filter(
            Question.chapter_id.in_(chapter_ids),
            Question.is_active == True
        ).order_by(db.func.random()).limit(capped_count).all()
    
    if not questions:
        return jsonify({'error': 'No questions found for selected criteria'}), 404
    
    # Prepare paper configuration
    paper_config = {
        'title': paper_title,
        'class_name': class_obj.name_bn or class_obj.name,
        'subject_name': subject_obj.name_bn or subject_obj.name,
        'time': time_minutes,
        'marks': len(questions)
    }
    
    # Generate the papers
    output_folder = current_app.config.get('OUTPUT_FOLDER', 'output')
    student_path, teacher_path = generate_paper_from_db(
        questions, paper_config, output_folder, omr_style=omr_style
    )
    
    # Save to database for tracking (including question IDs for regeneration)
    paper = GeneratedPaper(
        title=paper_title,
        class_id=class_id,
        subject_id=subject_id,
        chapter_ids=chapter_ids,
        question_ids=[q.id for q in questions],  # Store exact questions used
        question_count=len(questions),
        time_minutes=time_minutes,
        file_path=student_path,
        file_path_answers=teacher_path,
        omr_style=omr_style
    )
    db.session.add(paper)
    # Log generation for credit system
    if user:
        _log_generation(user['id'], gen_type='db')
    db.session.commit()
    
    return jsonify({
        'success': True,
        'paper_id': paper.id,
        'question_count': len(questions),
        'student_download': f'/download/{paper.id}/student',
        'teacher_download': f'/download/{paper.id}/teacher'
    })


@main_bp.route('/generate-custom-paper', methods=['POST'])
@limiter.limit("10 per minute")
def generate_custom_paper():
    """Generate DOCX paper from custom JSON questions (guest users).
    
    Expects JSON body:
    {
        "questions": [
            {"question_text": "...", "answer_options": ["A","B","C","D"], "correct_answer": "A"},
            ...
        ],
        "paper_config": {
            "title": "Home Test",
            "class_name": "...",
            "subject_name": "...",
            "time": 30,
            "marks": 10
        }
    }
    """
    # --- Credit check for logged-in users ---
    user = session.get('user')
    if user:
        _used, _limit, _remaining = _get_user_credits(user['id'])
        if _remaining <= 0:
            return jsonify({
                'error': 'Daily generation limit reached (0 credits left). Please wait until tomorrow.',
                'credits_exhausted': True
            }), 429

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        questions = data.get('questions', [])
        if not questions or not isinstance(questions, list):
            return jsonify({'error': 'Please provide at least one question'}), 400

        if len(questions) > 200:
            return jsonify({'error': 'Maximum 200 questions allowed'}), 400

        # Validate each question has required fields
        for i, q in enumerate(questions):
            if not q.get('question_text'):
                return jsonify({'error': f'Question {i+1} is missing question_text'}), 400
            if not q.get('answer_options') or len(q.get('answer_options', [])) < 2:
                return jsonify({'error': f'Question {i+1} needs at least 2 answer options'}), 400

        paper_config = data.get('paper_config', {})
        omr_style = data.get('omr_style', True)
        paper_config.setdefault('title', 'Home Test')
        paper_config.setdefault('marks', len(questions))
        paper_config.setdefault('time', len(questions))

        # Generate papers to disk
        import uuid
        output_folder = current_app.config.get('OUTPUT_FOLDER', 'output')
        student_path, teacher_path = generate_paper_from_db(
            questions, paper_config, output_folder, omr_style=omr_style
        )

        # Save to DB for download tracking (no class/subject IDs for custom papers)
        paper = GeneratedPaper(
            title=paper_config.get('title', 'Custom Paper'),
            question_count=len(questions),
            time_minutes=paper_config.get('time', 30),
            file_path=student_path,
            file_path_answers=teacher_path,
            custom_questions_json=questions,
            custom_paper_config=paper_config,
            omr_style=omr_style
        )
        db.session.add(paper)
        # Log generation for credit system
        if user:
            _log_generation(user['id'], gen_type='custom')
        db.session.commit()

        return jsonify({
            'success': True,
            'paper_id': paper.id,
            'question_count': len(questions),
            'student_download': f'/download/{paper.id}/student',
            'teacher_download': f'/download/{paper.id}/teacher'
        })

    except Exception as e:
        current_app.logger.error(f"Custom paper generation error: {e}")
        return jsonify({'error': 'Failed to generate paper. Please check your data.'}), 500


@main_bp.route('/download/<int:paper_id>/<paper_type>')
@limiter.limit("30 per minute")
def download_paper(paper_id, paper_type):
    """Download generated paper - supports DOCX (default) and PDF via ?format=pdf"""
    paper = GeneratedPaper.query.get_or_404(paper_id)
    
    if paper_type not in ('student', 'teacher'):
        abort(400, description="Invalid paper type")
    
    # Teacher copies (answer keys) require authentication, EXCEPT for custom papers
    # Custom papers are created by guest users so they should always be downloadable
    if paper_type == 'teacher' and not session.get('user') and not paper.custom_questions_json:
        abort(403, description="Authentication required for answer keys")
    
    # Determine requested format (docx or pdf)
    output_format = request.args.get('format', 'docx').lower()
    if output_format not in ('docx', 'pdf'):
        abort(400, description="Invalid format. Use 'docx' or 'pdf'.")
    
    show_answer = (paper_type == 'teacher')
    
    # PDF is always generated on-demand from stored question IDs
    if output_format == 'pdf':
        return _serve_pdf(paper, paper_type, show_answer)
    
    # --- DOCX path (existing logic) ---
    filename = (
        f"Question_Paper_{paper.id}.docx"
        if paper_type == 'student'
        else f"Question_Paper_With_Answers_{paper.id}.docx"
    )
    
    # Try to use existing file first
    file_path = paper.file_path if paper_type == 'student' else paper.file_path_answers
    if file_path and os.path.exists(file_path):
        paper.download_count += 1
        db.session.commit()
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    
    # File doesn't exist - try to regenerate
    
    # --- Custom paper regeneration (guest mode) ---
    if paper.custom_questions_json:
        custom_config = paper.custom_paper_config or {
            'title': paper.title or 'Custom Paper',
            'time': paper.time_minutes or 30,
            'marks': paper.question_count or len(paper.custom_questions_json)
        }
        student_buffer, teacher_buffer = generate_paper_to_memory(
            paper.custom_questions_json, custom_config
        )
        buffer = teacher_buffer if show_answer else student_buffer
        
        paper.download_count += 1
        db.session.commit()
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    
    # --- DB question regeneration (logged-in users) ---
    question_ids = paper.question_ids or []
    
    if question_ids:
        # Use exact stored question IDs (preserves order)
        questions = Question.query.filter(Question.id.in_(question_ids)).all()
        # Preserve original order
        question_order = {qid: idx for idx, qid in enumerate(question_ids)}
        questions = sorted(questions, key=lambda q: question_order.get(q.id, 0))
    else:
        # Fallback: try to get questions from stored chapters
        chapter_ids = paper.chapter_ids or []
        if not chapter_ids:
            return jsonify({
                'error': 'Cannot regenerate paper - no question data stored.'
            }), 404
        
        questions = Question.query.filter(
            Question.chapter_id.in_(chapter_ids),
            Question.is_active == True
        ).limit(paper.question_count).all()
    
    if not questions:
        return jsonify({
            'error': 'No questions found. The data may have been deleted.'
        }), 404
    
    # Prepare config for regeneration
    class_obj = Class.query.get(paper.class_id)
    subject_obj = Subject.query.get(paper.subject_id)
    
    paper_config = {
        'title': paper.title or 'Question Paper',
        'class_name': class_obj.name_bn if class_obj else '',
        'subject_name': subject_obj.name_bn if subject_obj else '',
        'time': paper.time_minutes or len(questions),
        'marks': len(questions)
    }
    
    # Generate to memory and serve directly
    student_buffer, teacher_buffer = generate_paper_to_memory(questions, paper_config)
    buffer = teacher_buffer if show_answer else student_buffer
    
    paper.download_count += 1
    db.session.commit()
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )


def _serve_pdf(paper, paper_type, show_answer):
    """Generate PDF on-demand from stored question IDs and serve it."""
    import traceback
    
    filename = (
        f"Question_Paper_{paper.id}.pdf"
        if paper_type == 'student'
        else f"Question_Paper_With_Answers_{paper.id}.pdf"
    )

    try:
        # Retrieve stored omr_style (default True for backward compat)
        omr_style = paper.omr_style if paper.omr_style is not None else True

        # --- Custom paper PDF (guest mode) ---
        if paper.custom_questions_json:
            custom_config = paper.custom_paper_config or {
                'title': paper.title or 'Custom Paper',
                'time': paper.time_minutes or 30,
                'marks': paper.question_count or len(paper.custom_questions_json)
            }

            student_buf, teacher_buf = generate_paper_to_memory_pdf(
                paper.custom_questions_json, custom_config,
                student_only=not show_answer,
                teacher_only=show_answer,
                omr_style=omr_style
            )
            buffer = teacher_buf if show_answer else student_buf

            if buffer is None:
                current_app.logger.error(f"PDF generation returned None for custom paper {paper.id}")
                return jsonify({'error': 'PDF generation failed'}), 500

            paper.download_count += 1
            db.session.commit()

            return send_file(
                buffer,
                as_attachment=True,
                download_name=filename,
                mimetype='application/pdf',
            )

        # --- DB paper PDF (logged-in users) ---
        # Fetch questions from DB
        question_ids = paper.question_ids or []
        if question_ids:
            questions = Question.query.filter(Question.id.in_(question_ids)).all()
            question_order = {qid: idx for idx, qid in enumerate(question_ids)}
            questions = sorted(
                questions, key=lambda q: question_order.get(q.id, 0)
            )
        else:
            chapter_ids = paper.chapter_ids or []
            if not chapter_ids:
                return jsonify({
                    'error': 'Cannot generate PDF - no question data stored.'
                }), 404
            questions = Question.query.filter(
                Question.chapter_id.in_(chapter_ids),
                Question.is_active == True
            ).limit(paper.question_count).all()

        if not questions:
            return jsonify({
                'error': 'No questions found. The data may have been deleted.'
            }), 404

        class_obj = Class.query.get(paper.class_id)
        subject_obj = Subject.query.get(paper.subject_id)

        paper_config = {
            'title': paper.title or 'Question Paper',
            'class_name': class_obj.name_bn if class_obj else '',
            'subject_name': subject_obj.name_bn if subject_obj else '',
            'time': paper.time_minutes or len(questions),
            'marks': len(questions),
        }

        # Only generate the version we need (halves processing time)
        student_buf, teacher_buf = generate_paper_to_memory_pdf(
            questions, paper_config,
            student_only=not show_answer,
            teacher_only=show_answer,
            omr_style=omr_style
        )
        buffer = teacher_buf if show_answer else student_buf

        if buffer is None:
            current_app.logger.error(f"PDF generation returned None buffer for paper {paper.id}")
            return jsonify({'error': 'PDF generation failed - buffer is None'}), 500

        paper.download_count += 1
        db.session.commit()

        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf',
        )
    except Exception as e:
        current_app.logger.error(f"PDF generation error for paper {paper.id}: {e}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'error': 'PDF generation failed. Please try again.'}), 500


@main_bp.route('/about')
def about():
    """About page"""
    return render_template('main/about.html')


@main_bp.route('/contact')
def contact():
    """Contact page"""
    return render_template('main/contact.html')


# ── SaaS Dashboard ────────────────────────────────────────────

def _require_user():
    """Return Supabase user dict or None. Use in routes to guard access."""
    return session.get('user')


@main_bp.route('/save-question-set', methods=['POST'])
@limiter.limit("30 per minute")
def save_question_set():
    """Save a question set to the user's account."""
    user = _require_user()
    if not user:
        return jsonify({'error': 'Please login to save question sets.', 'login_required': True}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided.'}), 400
    
    questions = data.get('questions', [])
    if not questions:
        return jsonify({'error': 'No questions to save.'}), 400
    
    name = data.get('name', '').strip()
    if not name:
        name = f"Question Set - {len(questions)} questions"
    
    qs = QuestionSet(
        user_id=user['id'],
        name=name[:200],
        questions_json=questions,
        paper_config=data.get('paper_config'),
        source=data.get('source', 'custom'),
        paper_id=data.get('paper_id'),
    )
    db.session.add(qs)
    db.session.commit()
    
    return jsonify({'success': True, 'id': qs.id, 'message': 'Question set saved!'})


@main_bp.route('/regenerate-from-set/<int:set_id>', methods=['POST'])
@limiter.limit("20 per minute")
def regenerate_from_set(set_id):
    """Regenerate a paper directly from a saved question set and return download links."""
    user = _require_user()
    if not user:
        return jsonify({'error': 'Login required.', 'login_required': True}), 401

    # Credit check
    _used, _limit, _remaining = _get_user_credits(user['id'])
    if _remaining <= 0:
        return jsonify({
            'error': 'Daily generation limit reached (0 credits left). Please wait until tomorrow.',
            'credits_exhausted': True
        }), 429

    qs = QuestionSet.query.filter_by(id=set_id, user_id=user['id']).first()
    if not qs:
        return jsonify({'error': 'Question set not found.'}), 404

    questions = qs.questions_json
    if not questions:
        return jsonify({'error': 'No questions in this set.'}), 400

    paper_config = qs.paper_config or {}
    paper_config.setdefault('title', qs.name or 'Question Paper')
    paper_config.setdefault('marks', len(questions))
    paper_config.setdefault('time', len(questions))
    omr_style = paper_config.pop('omr_style', True)

    output_folder = current_app.config.get('OUTPUT_FOLDER', 'output')

    if qs.source == 'db':
        # DB-sourced set: fetch actual Question objects by ID
        question_ids = [q.get('id') for q in questions if q.get('id')]
        if question_ids:
            db_questions = Question.query.filter(Question.id.in_(
                [int(qid) for qid in question_ids]
            )).all()
            if db_questions:
                order_map = {str(qid): idx for idx, qid in enumerate(question_ids)}
                db_questions = sorted(db_questions, key=lambda q: order_map.get(str(q.id), 0))
                student_path, teacher_path = generate_paper_from_db(
                    db_questions, paper_config, output_folder, omr_style=omr_style
                )
            else:
                # Fallback to custom-style generation if DB questions deleted
                student_path, teacher_path = generate_paper_from_db(
                    questions, paper_config, output_folder, omr_style=omr_style
                )
        else:
            student_path, teacher_path = generate_paper_from_db(
                questions, paper_config, output_folder, omr_style=omr_style
            )
    else:
        # Custom-sourced set
        student_path, teacher_path = generate_paper_from_db(
            questions, paper_config, output_folder, omr_style=omr_style
        )

    paper = GeneratedPaper(
        title=paper_config.get('title', 'Regenerated Paper'),
        question_count=len(questions),
        time_minutes=paper_config.get('time', 30),
        file_path=student_path,
        file_path_answers=teacher_path,
        custom_questions_json=questions,
        custom_paper_config=paper_config,
        omr_style=omr_style
    )
    db.session.add(paper)
    _log_generation(user['id'], gen_type=qs.source or 'custom')
    db.session.commit()

    return jsonify({
        'success': True,
        'paper_id': paper.id,
        'question_count': len(questions),
        'student_download': f'/download/{paper.id}/student',
        'teacher_download': f'/download/{paper.id}/teacher'
    })


@main_bp.route('/dashboard')
def dashboard():
    """User dashboard listing saved question sets."""
    user = _require_user()
    if not user:
        from flask import redirect, url_for, flash
        flash('Please login to access your dashboard.', 'info')
        return redirect(url_for('auth.login', next='/dashboard'))
    
    sets = QuestionSet.query.filter_by(user_id=user['id']).order_by(
        QuestionSet.updated_at.desc()
    ).all()
    
    # Credit / usage data
    credit_used, credit_limit, credit_remaining = _get_user_credits(user['id'])
    
    return render_template(
        'main/dashboard.html',
        question_sets=sets,
        credit_used=credit_used,
        credit_limit=credit_limit,
        credit_remaining=credit_remaining,
    )


@main_bp.route('/api/credits')
def api_credits():
    """Return current credit/usage info as JSON."""
    user = _require_user()
    if not user:
        return jsonify({'error': 'Login required.', 'login_required': True}), 401
    used, limit, remaining = _get_user_credits(user['id'])
    return jsonify({'used': used, 'limit': limit, 'remaining': remaining})


@main_bp.route('/question-set/<int:set_id>')
def view_question_set(set_id):
    """View a single saved question set (JSON)."""
    user = _require_user()
    if not user:
        return jsonify({'error': 'Login required.', 'login_required': True}), 401
    
    qs = QuestionSet.query.filter_by(id=set_id, user_id=user['id']).first()
    if not qs:
        return jsonify({'error': 'Question set not found.'}), 404
    
    result = qs.to_dict()
    result['questions'] = qs.questions_json
    return jsonify(result)


@main_bp.route('/question-set/<int:set_id>', methods=['PUT'])
def update_question_set(set_id):
    """Update a saved question set (name, questions, config)."""
    user = _require_user()
    if not user:
        return jsonify({'error': 'Login required.', 'login_required': True}), 401
    
    qs = QuestionSet.query.filter_by(id=set_id, user_id=user['id']).first()
    if not qs:
        return jsonify({'error': 'Question set not found.'}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided.'}), 400
    
    if 'name' in data:
        qs.name = data['name'][:200]
    if 'questions' in data and data['questions']:
        qs.questions_json = data['questions']
    if 'paper_config' in data:
        qs.paper_config = data['paper_config']
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Question set updated!'})


@main_bp.route('/question-set/<int:set_id>/delete', methods=['POST'])
def delete_question_set(set_id):
    """Delete a saved question set."""
    user = _require_user()
    if not user:
        return jsonify({'error': 'Login required.', 'login_required': True}), 401
    
    qs = QuestionSet.query.filter_by(id=set_id, user_id=user['id']).first()
    if not qs:
        return jsonify({'error': 'Question set not found.'}), 404
    
    db.session.delete(qs)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Question set deleted!'})
