"""
Main routes for Prosno.io
"""
import re
from datetime import datetime, date
from flask import Blueprint, render_template, request, jsonify, send_file, current_app, abort, session, redirect, url_for
import os
from sqlalchemy import or_

from app import db, csrf, limiter
from app.models import (
    Class, Subject, Chapter, Question, GeneratedPaper,
    QuestionSet, GenerationLog, ShortQuestion, CQQuestion, OmrTemplate,
    BankQuestion,
)
from app.utils.document_generator import generate_paper_from_db, generate_paper_to_memory
from app.utils.omr_generator import (
    generate_omr_pdf_to_memory,
    get_default_omr_config,
    get_omr_bubble_size_options,
    get_omr_general_rules,
    get_omr_layout_presets,
    get_omr_theme_options,
    normalize_omr_template_config,
)
from app.utils.pdf_generator import generate_paper_to_memory_pdf

main_bp = Blueprint('main', __name__)

# --- Anti-scraping limits ---
MAX_QUESTIONS_PER_PAPER = 50       # Max questions allowed in one paper
MAX_CHAPTERS_PER_REQUEST = 5       # Max chapters that can be queried at once
DAILY_GENERATION_LIMIT = 10        # Max papers a logged-in user can generate per day
OMR_TEMPLATE_NAME_MAX_LEN = 200


def _format_sitemap_lastmod(value):
    """Format datetimes for sitemap lastmod tags."""
    if not value:
        return None
    return value.date().isoformat()


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


@main_bp.route('/healthz')
@limiter.exempt
def healthz():
    """Lightweight liveness check for container health probes."""
    return jsonify({'status': 'ok'}), 200


@main_bp.route('/generate', methods=['GET', 'POST'])
def generate():
    """Question paper generation page"""
    classes = Class.query.filter_by(is_active=True).order_by(Class.order).all()
    return render_template('main/generate.html', classes=classes)


@main_bp.route('/get-subjects/<int:class_id>')
@limiter.limit("60 per minute")
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
@limiter.limit("60 per minute")
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
@limiter.limit("60 per minute")
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

    # --- Short Question section ---
    sq_config = None
    sq_include = data.get('sq_include', False)
    sq_question_ids = []
    if sq_include:
        import random as _rand
        sq_custom_questions = data.get('sq_custom_questions', [])

        if sq_custom_questions and isinstance(sq_custom_questions, list) and len(sq_custom_questions) > 0:
            # User provided custom SQ questions (DB mode custom toggle)
            sq_m = data.get('sq_include_count', len(sq_custom_questions))
            sq_n = data.get('sq_answer_count', sq_m)
            sq_marks = data.get('sq_marks', 2)
            sq_m = min(sq_m, len(sq_custom_questions))
            sq_n = min(sq_n, sq_m)
            for i, q in enumerate(sq_custom_questions):
                if not q.get('question_text'):
                    return jsonify({'error': f'Short question {i+1} is missing question_text'}), 400
            sq_config = {
                'questions': sq_custom_questions[:sq_m],
                'answer_count': sq_n,
                'marks_per_question': sq_marks,
            }
        else:
            sq_subject_id = data.get('sq_subject_id')
            sq_chapter_id = data.get('sq_chapter_id')
            sq_m = data.get('sq_include_count', 0)
            sq_n = data.get('sq_answer_count', 0)
            sq_marks = data.get('sq_marks', 2)

            if sq_m and sq_n:
                sq_query = ShortQuestion.query.filter(
                    ShortQuestion.is_active == True
                )
                if sq_subject_id:
                    sq_query = sq_query.filter_by(subject_id=sq_subject_id)
                if sq_chapter_id:
                    sq_query = sq_query.filter_by(chapter_id=sq_chapter_id)

                available_sq = sq_query.count()
                if sq_m > available_sq:
                    return jsonify({
                        'error': f'সংক্ষিপ্ত প্রশ্ন: {sq_m}টি চাওয়া হয়েছে কিন্তু মাত্র {available_sq}টি উপলব্ধ।'
                    }), 400
                if sq_n > sq_m:
                    return jsonify({
                        'error': 'সংক্ষিপ্ত প্রশ্ন: উত্তর সংখ্যা (N) মোট প্রশ্ন (M) এর চেয়ে বেশি হতে পারে না।'
                    }), 400

                sq_questions = sq_query.order_by(
                    db.func.random()
                ).limit(sq_m).all()
                sq_question_ids = [q.id for q in sq_questions]
                sq_config = {
                    'questions': [q.to_dict() for q in sq_questions],
                    'answer_count': sq_n,
                    'marks_per_question': sq_marks,
                }

    # --- Creative Question section ---
    cq_config = None
    cq_include = data.get('cq_include', False)
    cq_question_ids = []
    if cq_include:
        import random as _rand
        cq_custom_questions = data.get('cq_custom_questions', [])

        if cq_custom_questions and isinstance(cq_custom_questions, list) and len(cq_custom_questions) > 0:
            # User provided custom CQ questions (DB mode custom toggle)
            cq_m = data.get('cq_include_count', len(cq_custom_questions))
            cq_n = data.get('cq_answer_count', cq_m)
            cq_m = min(cq_m, len(cq_custom_questions))
            cq_n = min(cq_n, cq_m)
            for i, q in enumerate(cq_custom_questions):
                if not q.get('stem'):
                    return jsonify({'error': f'Creative question {i+1} is missing stem'}), 400
                if 'total_marks' not in q:
                    q['total_marks'] = (
                        int(q.get('marks_ka', 0)) + int(q.get('marks_kha', 0))
                        + int(q.get('marks_ga', 0)) + int(q.get('marks_gha', 0))
                    )
            cq_config = {
                'questions': cq_custom_questions[:cq_m],
                'answer_count': cq_n,
            }
        else:
            cq_subject_id = data.get('cq_subject_id')
            cq_chapter_id = data.get('cq_chapter_id')
            cq_board = data.get('cq_board')
            cq_year = data.get('cq_year')
            cq_m = data.get('cq_include_count', 0)
            cq_n = data.get('cq_answer_count', 0)

            if cq_m and cq_n:
                cq_query = CQQuestion.query.filter(
                    CQQuestion.is_active == True
                )
                if cq_subject_id:
                    cq_query = cq_query.filter_by(subject_id=cq_subject_id)
                if cq_chapter_id:
                    cq_query = cq_query.filter_by(chapter_id=cq_chapter_id)
                if cq_board:
                    cq_query = cq_query.filter_by(board=cq_board)
                if cq_year:
                    cq_query = cq_query.filter_by(year=cq_year)

                available_cq = cq_query.count()
                if cq_m > available_cq:
                    return jsonify({
                        'error': f'সৃজনশীল প্রশ্ন: {cq_m}টি চাওয়া হয়েছে কিন্তু মাত্র {available_cq}টি উপলব্ধ।'
                    }), 400
                if cq_n > cq_m:
                    return jsonify({
                        'error': 'সৃজনশীল প্রশ্ন: উত্তর সংখ্যা (N) মোট প্রশ্ন (M) এর চেয়ে বেশি হতে পারে না।'
                    }), 400

                cq_questions = cq_query.order_by(
                    db.func.random()
                ).limit(cq_m).all()
                cq_question_ids = [q.id for q in cq_questions]
                cq_config = {
                    'questions': [q.to_dict() for q in cq_questions],
                    'answer_count': cq_n,
                }

    # Prepare paper configuration
    # Total marks = MCQ count + SQ (answer_count × marks_per_question) + CQ (answer_count × marks_per_cq)
    total_marks = len(questions)  # MCQ marks (1 per question)
    if sq_config:
        total_marks += sq_config['answer_count'] * sq_config['marks_per_question']
    if cq_config:
        # Marks per CQ = sum of all sub-part marks for one CQ question
        # Use first question's total_marks as representative (they should all be equal)
        cq_marks_per_q = cq_config['questions'][0].get('total_marks', 10) if cq_config['questions'] else 10
        total_marks += cq_config['answer_count'] * cq_marks_per_q

    paper_config = {
        'title': paper_title,
        'class_name': class_obj.name_bn or class_obj.name,
        'subject_name': subject_obj.name_bn or subject_obj.name,
        'time': time_minutes,
        'marks': total_marks,
    }

    # Generate the papers
    output_folder = current_app.config.get('OUTPUT_FOLDER', 'output')
    try:
        student_path, teacher_path = generate_paper_from_db(
            questions, paper_config, output_folder,
            omr_style=omr_style,
            sq_config=sq_config,
            cq_config=cq_config,
        )
    except Exception as e:
        current_app.logger.error(f"Paper generation error: {e}")
        return jsonify({'error': 'Failed to generate paper. Please try again.'}), 500

    # Save to database for tracking (including question IDs for regeneration)
    custom_cfg = {}
    if sq_question_ids:
        custom_cfg['sq_question_ids'] = sq_question_ids
    if cq_question_ids:
        custom_cfg['cq_question_ids'] = cq_question_ids

    paper = GeneratedPaper(
        title=paper_title,
        class_id=class_id,
        subject_id=subject_id,
        chapter_ids=chapter_ids,
        question_ids=[q.id for q in questions],
        question_count=len(questions),
        time_minutes=time_minutes,
        file_path=student_path,
        file_path_answers=teacher_path,
        omr_style=omr_style,
        custom_paper_config={
            'title': paper_title,
            'class_name': class_obj.name_bn or class_obj.name,
            'subject_name': subject_obj.name_bn or subject_obj.name,
            'time': time_minutes,
            'marks': total_marks,
            'omr_style': omr_style,
            # Store sq/cq configs so PDF regeneration can reconstruct them
            'sq_config': sq_config,
            'cq_config': cq_config,
        } if (sq_config or cq_config) else custom_cfg if custom_cfg else None,
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
        sq_questions_raw = data.get('sq_questions', [])
        cq_questions_raw = data.get('cq_questions', [])

        # Require at least one question of any type
        if not questions and not sq_questions_raw and not cq_questions_raw:
            return jsonify({'error': 'Please provide at least one question'}), 400

        if not isinstance(questions, list):
            questions = []

        if len(questions) > 200:
            return jsonify({'error': 'Maximum 200 MCQ questions allowed'}), 400

        # Validate each MCQ question
        for i, q in enumerate(questions):
            if not q.get('question_text'):
                return jsonify({'error': f'Question {i+1} is missing question_text'}), 400
            if not q.get('answer_options') or len(q.get('answer_options', [])) < 2:
                return jsonify({'error': f'Question {i+1} needs at least 2 answer options'}), 400

        # Build sq_config from custom SQ questions if provided
        sq_config = None
        if sq_questions_raw and isinstance(sq_questions_raw, list) and len(sq_questions_raw) > 0:
            sq_cfg_raw = data.get('sq_config') or {}
            sq_m = min(int(sq_cfg_raw.get('include_count', len(sq_questions_raw))), len(sq_questions_raw))
            sq_n = min(int(sq_cfg_raw.get('answer_count', sq_m)), sq_m)
            sq_marks = int(sq_cfg_raw.get('marks', 2))
            # Validate SQ questions
            for i, q in enumerate(sq_questions_raw):
                if not q.get('question_text'):
                    return jsonify({'error': f'Short question {i+1} is missing question_text'}), 400
            sq_config = {
                'questions': sq_questions_raw[:sq_m],
                'answer_count': sq_n,
                'marks_per_question': sq_marks,
            }

        # Build cq_config from custom CQ questions if provided
        cq_config = None
        if cq_questions_raw and isinstance(cq_questions_raw, list) and len(cq_questions_raw) > 0:
            cq_cfg_raw = data.get('cq_config') or {}
            cq_m = min(int(cq_cfg_raw.get('include_count', len(cq_questions_raw))), len(cq_questions_raw))
            cq_n = min(int(cq_cfg_raw.get('answer_count', cq_m)), cq_m)
            # Validate CQ questions and compute total_marks if missing
            for i, q in enumerate(cq_questions_raw):
                if not q.get('stem'):
                    return jsonify({'error': f'Creative question {i+1} is missing stem'}), 400
                if 'total_marks' not in q:
                    q['total_marks'] = (
                        int(q.get('marks_ka', 0)) + int(q.get('marks_kha', 0))
                        + int(q.get('marks_ga', 0)) + int(q.get('marks_gha', 0))
                    )
            cq_config = {
                'questions': cq_questions_raw[:cq_m],
                'answer_count': cq_n,
            }

        paper_config = data.get('paper_config', {})
        omr_style = data.get('omr_style', True)
        paper_config.setdefault('title', 'Home Test')
        # Compute total marks across all question types
        total_marks = len(questions)  # MCQ: 1 mark each
        if sq_config:
            total_marks += sq_config['answer_count'] * sq_config['marks_per_question']
        if cq_config:
            cq_marks_per_q = cq_config['questions'][0].get('total_marks', 10) if cq_config['questions'] else 10
            total_marks += cq_config['answer_count'] * cq_marks_per_q
        paper_config.setdefault('marks', total_marks or len(questions))
        paper_config.setdefault('time', max(len(questions), 30))
        # Embed sq/cq configs in paper_config so they can be retrieved on PDF regeneration
        if sq_config:
            paper_config['sq_config'] = sq_config
        if cq_config:
            paper_config['cq_config'] = cq_config

        # Generate papers to disk
        import uuid
        output_folder = current_app.config.get('OUTPUT_FOLDER', 'output')
        student_path, teacher_path = generate_paper_from_db(
            questions, paper_config, output_folder,
            omr_style=omr_style,
            sq_config=sq_config,
            cq_config=cq_config,
        )

        # Compute effective question count for the paper record
        total_question_count = len(questions)
        if sq_config:
            total_question_count += len(sq_config['questions'])
        if cq_config:
            total_question_count += len(cq_config['questions'])

        # Save to DB for download tracking (no class/subject IDs for custom papers)
        paper = GeneratedPaper(
            title=paper_config.get('title', 'Custom Paper'),
            question_count=total_question_count,
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
            # Extract sq/cq configs stored at generation time (if any)
            stored_sq_config = custom_config.pop('sq_config', None)
            stored_cq_config = custom_config.pop('cq_config', None)

            student_buf, teacher_buf = generate_paper_to_memory_pdf(
                paper.custom_questions_json, custom_config,
                student_only=not show_answer,
                teacher_only=show_answer,
                omr_style=omr_style,
                sq_config=stored_sq_config,
                cq_config=stored_cq_config,
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

        # Retrieve sq/cq configs if they were stored (DB papers with CQ/SQ)
        stored_cfg = paper.custom_paper_config or {}
        stored_sq_config = stored_cfg.get('sq_config')
        stored_cq_config = stored_cfg.get('cq_config')
        # If marks were stored, use them (covers the case where total_marks was computed at generation)
        if stored_cfg.get('marks'):
            paper_config['marks'] = stored_cfg['marks']

        # Only generate the version we need (halves processing time)
        student_buf, teacher_buf = generate_paper_to_memory_pdf(
            questions, paper_config,
            student_only=not show_answer,
            teacher_only=show_answer,
            omr_style=omr_style,
            sq_config=stored_sq_config,
            cq_config=stored_cq_config,
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


@main_bp.route('/robots.txt')
def robots_txt():
    """Serve robots.txt with sitemap location and private path exclusions."""
    sitemap_url = url_for('main.sitemap_xml', _external=True)
    return current_app.response_class(
        render_template('seo/robots.txt', sitemap_url=sitemap_url),
        mimetype='text/plain',
    )


@main_bp.route('/sitemap.xml')
def sitemap_xml():
    """Serve an XML sitemap for crawlable public pages."""
    pages = [
        {
            'loc': url_for('main.index', _external=True),
            'changefreq': 'weekly',
            'priority': '1.0',
        },
        {
            'loc': url_for('main.generate', _external=True),
            'changefreq': 'weekly',
            'priority': '0.9',
        },
        {
            'loc': url_for('main.about', _external=True),
            'changefreq': 'monthly',
            'priority': '0.5',
        },
        {
            'loc': url_for('main.contact', _external=True),
            'changefreq': 'monthly',
            'priority': '0.5',
        },
        {
            'loc': url_for('quiz.join_page', _external=True),
            'changefreq': 'weekly',
            'priority': '0.6',
        },
    ]

    shared_sets = QuestionSet.query.filter(
        QuestionSet.is_shared == True,
        QuestionSet.share_token.isnot(None),
    ).all()
    for question_set in shared_sets:
        pages.append({
            'loc': url_for(
                'main.public_paper_view',
                share_token=question_set.share_token,
                _external=True,
            ),
            'lastmod': _format_sitemap_lastmod(
                question_set.updated_at or question_set.created_at
            ),
            'changefreq': 'weekly',
            'priority': '0.7',
        })

    return current_app.response_class(
        render_template('seo/sitemap.xml', pages=pages),
        mimetype='application/xml',
    )


# ── SaaS Dashboard ────────────────────────────────────────────

def _require_user():
    """Return Supabase user dict or None. Use in routes to guard access."""
    return session.get('user')


def _normalize_omr_template_name(value):
    """Normalize and validate an OMR template name."""
    name = str(value or '').strip()
    if not name:
        raise ValueError('Template name is required.')
    if len(name) > OMR_TEMPLATE_NAME_MAX_LEN:
        raise ValueError(
            f'Template name must be {OMR_TEMPLATE_NAME_MAX_LEN} characters or less.'
        )
    return name


def _slugify_omr_filename(name):
    """Convert a template name into a safe PDF filename."""
    slug = re.sub(r'[^A-Za-z0-9]+', '-', str(name or '').strip()).strip('-').lower()
    return slug or 'omr-template'


def _get_user_omr_template_or_404(template_id, user_id):
    """Fetch an OMR template owned by the given user or return None."""
    return OmrTemplate.query.filter_by(id=template_id, user_id=user_id).first()


def _serialize_omr_template(template):
    """Return the public JSON payload for an OMR template."""
    return template.to_dict()


@main_bp.route('/omr-builder')
def omr_builder():
    """Standalone OMR template builder."""
    user = _require_user()
    if not user:
        return redirect(url_for('auth.login', next='/omr-builder'))

    return render_template(
        'main/omr_builder.html',
        omr_default_config=get_default_omr_config(),
        omr_general_rules=get_omr_general_rules(),
        omr_layout_presets=get_omr_layout_presets(),
        omr_theme_options=get_omr_theme_options(),
        omr_bubble_sizes=get_omr_bubble_size_options(),
        initial_template_id=request.args.get('template', type=int),
    )


@main_bp.route('/api/omr/templates')
@limiter.limit("60 per minute")
def list_omr_templates():
    """List the current user's saved OMR templates."""
    user = _require_user()
    if not user:
        return jsonify({'error': 'Login required.', 'login_required': True}), 401

    templates = OmrTemplate.query.filter_by(user_id=user['id']).order_by(
        OmrTemplate.updated_at.desc()
    ).all()
    return jsonify({
        'templates': [_serialize_omr_template(template) for template in templates],
    })


@main_bp.route('/api/omr/templates', methods=['POST'])
@limiter.limit("30 per minute")
def create_omr_template():
    """Create a new private OMR template."""
    user = _require_user()
    if not user:
        return jsonify({'error': 'Login required.', 'login_required': True}), 401

    data = request.get_json() or {}
    try:
        name = _normalize_omr_template_name(data.get('name'))
        config_json = normalize_omr_template_config(data.get('config_json'))
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    template = OmrTemplate(
        user_id=user['id'],
        name=name,
        config_json=config_json,
        question_count=config_json['question_count'],
    )
    db.session.add(template)
    db.session.commit()

    return jsonify({
        'success': True,
        'template': _serialize_omr_template(template),
    })


@main_bp.route('/api/omr/templates/<int:template_id>')
@limiter.limit("60 per minute")
def get_omr_template(template_id):
    """Fetch a single OMR template owned by the current user."""
    user = _require_user()
    if not user:
        return jsonify({'error': 'Login required.', 'login_required': True}), 401

    template = _get_user_omr_template_or_404(template_id, user['id'])
    if not template:
        return jsonify({'error': 'OMR template not found.'}), 404

    return jsonify({'template': _serialize_omr_template(template)})


@main_bp.route('/api/omr/templates/<int:template_id>', methods=['PUT'])
@limiter.limit("30 per minute")
def update_omr_template(template_id):
    """Update an existing OMR template."""
    user = _require_user()
    if not user:
        return jsonify({'error': 'Login required.', 'login_required': True}), 401

    template = _get_user_omr_template_or_404(template_id, user['id'])
    if not template:
        return jsonify({'error': 'OMR template not found.'}), 404

    data = request.get_json() or {}
    try:
        name = _normalize_omr_template_name(data.get('name', template.name))
        config_json = normalize_omr_template_config(
            data.get('config_json', template.config_json)
        )
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    template.name = name
    template.config_json = config_json
    template.question_count = config_json['question_count']
    db.session.commit()

    return jsonify({
        'success': True,
        'template': _serialize_omr_template(template),
    })


@main_bp.route('/api/omr/templates/<int:template_id>/delete', methods=['POST'])
@limiter.limit("30 per minute")
def delete_omr_template(template_id):
    """Delete an existing OMR template."""
    user = _require_user()
    if not user:
        return jsonify({'error': 'Login required.', 'login_required': True}), 401

    template = _get_user_omr_template_or_404(template_id, user['id'])
    if not template:
        return jsonify({'error': 'OMR template not found.'}), 404

    db.session.delete(template)
    db.session.commit()
    return jsonify({'success': True})


@main_bp.route('/api/omr/render', methods=['POST'])
@limiter.limit("20 per minute")
def render_omr_template_pdf():
    """Render an OMR template as a PDF."""
    user = _require_user()
    if not user:
        return jsonify({'error': 'Login required.', 'login_required': True}), 401

    data = request.get_json() or {}
    try:
        name = _normalize_omr_template_name(data.get('name') or 'OMR Template')
        config_json = normalize_omr_template_config(data.get('config_json'))
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    template_id = data.get('template_id')
    try:
        template_id = int(template_id) if template_id else None
    except (TypeError, ValueError):
        return jsonify({'error': 'Template id must be a number.'}), 400
    if template_id:
        template = _get_user_omr_template_or_404(template_id, user['id'])
        if not template:
            return jsonify({'error': 'OMR template not found.'}), 404
        template.download_count = (template.download_count or 0) + 1
        db.session.commit()

    try:
        pdf_buffer = generate_omr_pdf_to_memory(config_json)
    except Exception as exc:
        current_app.logger.error(f'OMR render failed: {exc}')
        return jsonify({'error': 'Failed to generate OMR PDF.'}), 500
    filename = _slugify_omr_filename(name) + '.pdf'
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename,
    )


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
    
    source = data.get('source', 'custom')
    
    # For DB-sourced sets, enrich with full question data from DB.
    # The frontend preview endpoint strips answer_options/correct_answer
    # (anti-scraping), so we must fetch the complete data server-side.
    if source == 'db':
        question_ids = [q.get('id') for q in questions if q.get('id')]
        if question_ids:
            db_questions = Question.query.filter(
                Question.id.in_([int(qid) for qid in question_ids])
            ).all()
            if db_questions:
                order_map = {str(qid): idx for idx, qid in enumerate(question_ids)}
                db_questions = sorted(db_questions, key=lambda q: order_map.get(str(q.id), 0))
                questions = [q.to_dict() for q in db_questions]
    
    name = data.get('name', '').strip()
    if not name:
        name = f"Question Set - {len(questions)} questions"
    
    qs = QuestionSet(
        user_id=user['id'],
        name=name[:200],
        questions_json=questions,
        paper_config=data.get('paper_config'),
        source=source,
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
    omr_templates = OmrTemplate.query.filter_by(user_id=user['id']).order_by(
        OmrTemplate.updated_at.desc()
    ).all()
    
    # Credit / usage data
    credit_used, credit_limit, credit_remaining = _get_user_credits(user['id'])
    
    return render_template(
        'main/dashboard.html',
        question_sets=sets,
        omr_templates=omr_templates,
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


# ──────────────────────────────────────────────────────────
# Teacher Question Bank — Frontend Pages
# ──────────────────────────────────────────────────────────

@main_bp.route('/bank')
def bank_browse():
    """Question bank browse page (public, but auth enriches UX)."""
    user = _require_user()
    return render_template('main/bank_browse.html', user=user)


@main_bp.route('/bank/question/new')
def bank_question_new():
    """Question authoring form — requires login."""
    user = _require_user()
    if not user:
        flash('Please login to contribute questions.', 'info')
        return redirect(url_for('auth.login', next='/bank/question/new'))
    return render_template('main/bank_question_form.html', user=user)


@main_bp.route('/bank/library')
def bank_library():
    """Teacher's personal saved-question library."""
    user = _require_user()
    if not user:
        flash('Please login to view your library.', 'info')
        return redirect(url_for('auth.login', next='/bank/library'))
    return render_template('main/bank_library.html', user=user)


@main_bp.route('/bank/profile')
def bank_profile():
    """Teacher's own profile page."""
    user = _require_user()
    if not user:
        flash('Please login to view your profile.', 'info')
        return redirect(url_for('auth.login', next='/bank/profile'))
    return render_template('main/bank_profile.html', user=user)


@main_bp.route('/bank/teacher/<user_id>')
def bank_teacher_profile(user_id):
    """Public teacher profile page."""
    user = _require_user()
    return render_template(
        'main/bank_teacher_profile.html',
        user=user,
        teacher_id=user_id,
    )


@main_bp.route('/bank/notifications')
def bank_notifications():
    """Teacher notifications page."""
    user = _require_user()
    if not user:
        flash('Please login to view notifications.', 'info')
        return redirect(url_for('auth.login', next='/bank/notifications'))
    return render_template('main/bank_notifications.html', user=user)


@main_bp.route('/bank/leaderboard')
def bank_leaderboard():
    """Leaderboard page."""
    user = _require_user()
    return render_template('main/bank_leaderboard.html', user=user)


# ── Paper Builder ─────────────────────────────────────────────


@main_bp.route('/builder')
def builder():
    """Smart Paper Builder — drag & drop paper creation."""
    user = session.get('user')
    if not user:
        return redirect(url_for('auth.login'))
    classes = Class.query.filter_by(is_active=True).order_by(Class.order).all()
    return render_template('main/builder.html', classes=classes)


@main_bp.route('/api/builder/questions', methods=['POST'])
@limiter.limit("60 per minute")
def builder_fetch_questions():
    """Fetch questions across types (MCQ, SQ, CQ) for the paper builder."""
    user = _require_user()
    if not user:
        return jsonify({'error': 'Login required.'}), 401

    data = request.get_json() or {}
    chapter_ids = data.get('chapter_ids', [])
    question_types = data.get('question_types', ['mcq', 'sq', 'cq'])
    search_text = data.get('search', '').strip()
    difficulty = data.get('difficulty', '')
    page = max(1, data.get('page', 1))
    per_page = min(50, data.get('per_page', 20))

    if not chapter_ids:
        return jsonify({'mcq': [], 'sq': [], 'cq': [], 'total_counts': {}})

    if len(chapter_ids) > 10:
        return jsonify({'error': 'Maximum 10 chapters per request.'}), 400

    result = {}
    total_counts = {}
    offset = (page - 1) * per_page
    user_id = user.get('id')

    def _bank_base_query(question_type):
        query = BankQuestion.query.filter(
            BankQuestion.chapter_id.in_(chapter_ids),
            BankQuestion.is_active == True,
            BankQuestion.question_type == question_type,
        )
        if user_id:
            query = query.filter(
                or_(
                    BankQuestion.visibility == 'public',
                    BankQuestion.teacher_id == user_id,
                )
            )
        else:
            query = query.filter(BankQuestion.visibility == 'public')
        if difficulty:
            query = query.filter(BankQuestion.difficulty == difficulty)
        return query

    # MCQ
    if 'mcq' in question_types:
        q = _bank_base_query('MCQ')
        if search_text:
            q = q.filter(BankQuestion.question_text.ilike(f'%{search_text}%'))
        total_counts['mcq'] = q.count()
        mcq_rows = q.order_by(BankQuestion.chapter_id, BankQuestion.id).offset(offset).limit(per_page).all()
        result['mcq'] = [{
            'id': r.id,
            'question_text': r.question_text,
            'type': 'simple',
            'answer_options': r.answer_options or [],
            'correct_answer': r.correct_answer or '',
            'difficulty': r.difficulty,
            'chapter_id': r.chapter_id,
            'chapter_name': (r.chapter_ref.name_bn or r.chapter_ref.name) if r.chapter_ref else '',
            'marks': r.marks,
            'db_source': 'bank',
        } for r in mcq_rows]

    # SQ
    if 'sq' in question_types:
        q = _bank_base_query('SQ')
        if search_text:
            q = q.filter(BankQuestion.question_text.ilike(f'%{search_text}%'))
        total_counts['sq'] = q.count()
        sq_rows = q.order_by(BankQuestion.chapter_id, BankQuestion.id).offset(offset).limit(per_page).all()
        result['sq'] = [{
            'id': r.id,
            'question_text': r.question_text,
            'marks': r.marks or 2,
            'difficulty': r.difficulty,
            'chapter_id': r.chapter_id,
            'chapter_name': (r.chapter_ref.name_bn or r.chapter_ref.name) if r.chapter_ref else '',
            'db_source': 'bank',
        } for r in sq_rows]

    # CQ
    if 'cq' in question_types:
        q = _bank_base_query('CQ')
        if search_text:
            q = q.filter(
                or_(
                    BankQuestion.stem.ilike(f'%{search_text}%'),
                    BankQuestion.question_text.ilike(f'%{search_text}%'),
                )
            )
        total_counts['cq'] = q.count()
        cq_rows = q.order_by(BankQuestion.chapter_id, BankQuestion.id).offset(offset).limit(per_page).all()
        result['cq'] = [{
            'id': r.id,
            'question_text': r.question_text or '',
            'stem': r.stem or r.question_text or '',
            'part_ka': r.part_ka or '',
            'part_kha': r.part_kha or '',
            'part_ga': r.part_ga or '',
            'part_gha': r.part_gha or '',
            'marks_ka': r.marks_ka or 0,
            'marks_kha': r.marks_kha or 0,
            'marks_ga': r.marks_ga or 0,
            'marks_gha': r.marks_gha or 0,
            'total_marks': (r.marks_ka or 0) + (r.marks_kha or 0) + (r.marks_ga or 0) + (r.marks_gha or 0),
            'difficulty': r.difficulty,
            'chapter_id': r.chapter_id,
            'chapter_name': (r.chapter_ref.name_bn or r.chapter_ref.name) if r.chapter_ref else '',
            'board': r.board,
            'year': r.year,
            'db_source': 'bank',
        } for r in cq_rows]

    result['total_counts'] = total_counts
    return jsonify(result)


@main_bp.route('/api/builder/generate', methods=['POST'])
@limiter.limit("20 per minute")
@csrf.exempt
def builder_generate():
    """Generate a paper from the sections-based builder JSON."""
    user = _require_user()
    if not user:
        return jsonify({'error': 'Login required.'}), 401

    _used, _limit, _remaining = _get_user_credits(user['id'])
    if _remaining <= 0:
        return jsonify({
            'error': 'Daily generation limit reached.',
            'credits_exhausted': True,
        }), 429

    data = request.get_json()
    if not data or 'sections' not in data:
        return jsonify({'error': 'Missing sections data.'}), 400

    cfg = data.get('paper_config', {})
    sections = data.get('sections', [])

    class_id = cfg.get('class_id')
    subject_id = cfg.get('subject_id')
    class_obj = Class.query.get(class_id) if class_id else None
    subject_obj = Subject.query.get(subject_id) if subject_id else None
    paper_title = cfg.get('title', 'Question Paper')
    time_minutes = cfg.get('time_minutes', 60)
    omr_style = cfg.get('omr_style', True)

    # Resolve questions per section
    mcq_questions = []
    sq_config = None
    cq_config = None
    all_mcq_ids = []
    user_id = user.get('id')

    def _get_bank_question(question_id, question_type):
        q = BankQuestion.query.filter(
            BankQuestion.id == question_id,
            BankQuestion.question_type == question_type,
            BankQuestion.is_active == True,
        )
        if user_id:
            q = q.filter(
                or_(
                    BankQuestion.visibility == 'public',
                    BankQuestion.teacher_id == user_id,
                )
            )
        else:
            q = q.filter(BankQuestion.visibility == 'public')
        return q.first()

    for sec in sections:
        sec_type = sec.get('type', 'mcq')
        raw_questions = sec.get('questions', [])
        if not raw_questions:
            continue

        if sec_type == 'mcq':
            for item in raw_questions:
                if item.get('source') == 'db' and item.get('id'):
                    source = item.get('db_source')
                    if source in (None, 'bank'):
                        bq = _get_bank_question(item['id'], 'MCQ')
                        if bq:
                            mcq_questions.append({
                                'question_text': bq.question_text or '',
                                'answer_options': bq.answer_options or [],
                                'correct_answer': bq.correct_answer or '',
                                'type': 'simple',
                                'chapter_id': bq.chapter_id,
                            })
                            all_mcq_ids.append(bq.id)
                            continue
                    q = Question.query.get(item['id'])
                    if q and q.is_active:
                        mcq_questions.append(q)
                        all_mcq_ids.append(q.id)
                elif item.get('source') == 'custom':
                    mcq_questions.append({
                        'question_text': item.get('question_text', ''),
                        'answer_options': item.get('answer_options', []),
                        'correct_answer': item.get('correct_answer', ''),
                        'type': item.get('type', 'simple'),
                        'sub_options': item.get('sub_options', []),
                        'final_prompt': item.get('final_prompt', ''),
                    })

        elif sec_type == 'sq':
            sq_list = []
            for item in raw_questions:
                if item.get('source') == 'db' and item.get('id'):
                    source = item.get('db_source')
                    if source in (None, 'bank'):
                        bq = _get_bank_question(item['id'], 'SQ')
                        if bq:
                            sq_list.append({
                                'question_text': bq.question_text or '',
                                'marks': bq.marks or 2,
                            })
                            continue
                    q = ShortQuestion.query.get(item['id'])
                    if q and q.is_active:
                        sq_list.append(q.to_dict())
                elif item.get('source') == 'custom':
                    sq_list.append({
                        'question_text': item.get('question_text', ''),
                        'marks': item.get('marks', 2),
                    })
            if sq_list:
                sq_config = {
                    'questions': sq_list,
                    'answer_count': sec.get('answer_count', len(sq_list)),
                    'marks_per_question': sec.get('marks_per_question', 2),
                }

        elif sec_type == 'cq':
            cq_list = []
            for item in raw_questions:
                if item.get('source') == 'db' and item.get('id'):
                    source = item.get('db_source')
                    if source in (None, 'bank'):
                        bq = _get_bank_question(item['id'], 'CQ')
                        if bq:
                            cq_list.append({
                                'stem': bq.stem or bq.question_text or '',
                                'part_ka': bq.part_ka or '',
                                'part_kha': bq.part_kha or '',
                                'part_ga': bq.part_ga or '',
                                'part_gha': bq.part_gha or '',
                                'marks_ka': bq.marks_ka or 0,
                                'marks_kha': bq.marks_kha or 0,
                                'marks_ga': bq.marks_ga or 0,
                                'marks_gha': bq.marks_gha or 0,
                                'total_marks': (bq.marks_ka or 0) + (bq.marks_kha or 0) + (bq.marks_ga or 0) + (bq.marks_gha or 0),
                                'board': bq.board,
                                'year': bq.year,
                            })
                            continue
                    q = CQQuestion.query.get(item['id'])
                    if q and q.is_active:
                        cq_list.append(q.to_dict())
                elif item.get('source') == 'custom':
                    cq_list.append(item)
            if cq_list:
                cq_config = {
                    'questions': cq_list,
                    'answer_count': sec.get('answer_count', len(cq_list)),
                }

    if not mcq_questions and not sq_config and not cq_config:
        return jsonify({'error': 'No questions in any section.'}), 400

    # Calculate total marks
    total_marks = len(mcq_questions)
    if sq_config:
        total_marks += sq_config['answer_count'] * sq_config['marks_per_question']
    if cq_config:
        cq_m = cq_config['questions'][0].get('total_marks', 10) if cq_config['questions'] else 10
        total_marks += cq_config['answer_count'] * cq_m

    paper_config = {
        'title': paper_title,
        'class_name': (class_obj.name_bn or class_obj.name) if class_obj else cfg.get('class_name', ''),
        'subject_name': (subject_obj.name_bn or subject_obj.name) if subject_obj else cfg.get('subject_name', ''),
        'time': time_minutes,
        'marks': total_marks,
    }

    output_folder = current_app.config.get('OUTPUT_FOLDER', 'output')
    try:
        student_path, teacher_path = generate_paper_from_db(
            mcq_questions, paper_config, output_folder,
            omr_style=omr_style,
            sq_config=sq_config,
            cq_config=cq_config,
        )
    except Exception as e:
        current_app.logger.error(f"Builder generate error: {e}")
        return jsonify({'error': 'Failed to generate paper.'}), 500

    # Compute effective question counts
    total_q = len(mcq_questions)
    if sq_config:
        total_q += len(sq_config['questions'])
    if cq_config:
        total_q += len(cq_config['questions'])

    # Get chapter_ids from MCQ questions
    chapter_ids = set()
    for q in mcq_questions:
        if hasattr(q, 'chapter_id') and q.chapter_id:
            chapter_ids.add(q.chapter_id)
        elif isinstance(q, dict) and q.get('chapter_id'):
            chapter_ids.add(q.get('chapter_id'))
    chapter_ids = list(chapter_ids)

    paper = GeneratedPaper(
        title=paper_title,
        class_id=class_id,
        subject_id=subject_id,
        chapter_ids=chapter_ids if chapter_ids else None,
        question_ids=all_mcq_ids if all_mcq_ids else None,
        question_count=total_q,
        time_minutes=time_minutes,
        file_path=student_path,
        file_path_answers=teacher_path,
        omr_style=omr_style,
        custom_paper_config={
            **paper_config,
            'omr_style': omr_style,
            'sq_config': sq_config,
            'cq_config': cq_config,
        } if (sq_config or cq_config) else None,
    )
    db.session.add(paper)
    _log_generation(user['id'], gen_type='builder')
    db.session.commit()

    return jsonify({
        'success': True,
        'paper_id': paper.id,
        'question_count': total_q,
        'total_marks': total_marks,
        'student_download': f'/download/{paper.id}/student',
        'teacher_download': f'/download/{paper.id}/teacher',
    })


# ── Shareable Paper Links ─────────────────────────────────────


@main_bp.route('/question-set/<int:set_id>/share', methods=['POST'])
def toggle_share(set_id):
    """Toggle sharing on/off for a question set. Generates share_token if needed."""
    user = _require_user()
    if not user:
        return jsonify({'error': 'Login required.', 'login_required': True}), 401

    qs = QuestionSet.query.filter_by(id=set_id, user_id=user['id']).first()
    if not qs:
        return jsonify({'error': 'Question set not found.'}), 404

    data = request.get_json() or {}
    enable = data.get('enable', not (qs.is_shared or False))  # Toggle by default

    if enable and not qs.share_token:
        qs.share_token = QuestionSet.generate_share_token()

    qs.is_shared = enable
    db.session.commit()

    share_url = None
    if qs.share_token:
        share_url = request.host_url.rstrip('/') + f'/paper/{qs.share_token}'

    return jsonify({
        'success': True,
        'is_shared': qs.is_shared,
        'share_token': qs.share_token,
        'share_url': share_url,
    })


@main_bp.route('/paper/<share_token>')
def public_paper_view(share_token):
    """Public paper viewer — anyone with the link can view and practice."""
    qs = QuestionSet.query.filter_by(share_token=share_token).first()

    if not qs or not qs.is_shared:
        return render_template('main/paper_unavailable.html'), 404

    # Strip correct answers from questions for the initial view (anti-cheating)
    safe_questions = []
    for q in (qs.questions_json or []):
        safe_q = {
            'question_text': q.get('question_text', ''),
            'answer_options': q.get('answer_options', []),
            'type': q.get('type', 'simple'),
        }
        if q.get('type') == 'complex':
            safe_q['sub_options'] = q.get('sub_options', [])
            safe_q['final_prompt'] = q.get('final_prompt', '')
        safe_questions.append(safe_q)

    paper_config = qs.paper_config or {}
    share_url = request.url

    return render_template(
        'main/paper_view.html',
        question_set=qs,
        questions=safe_questions,
        paper_config=paper_config,
        share_url=share_url,
        share_token=share_token,
    )


@main_bp.route('/paper/<share_token>/submit', methods=['POST'])
@csrf.exempt  # Public endpoint — no CSRF cookie for anonymous users
@limiter.limit("30 per minute")
def submit_practice(share_token):
    """Student submits practice answers. Returns score and answer key."""
    qs = QuestionSet.query.filter_by(share_token=share_token).first()

    if not qs or not qs.is_shared:
        return jsonify({'error': 'Paper not available.'}), 404

    data = request.get_json()
    if not data or 'responses' not in data:
        return jsonify({'error': 'No answers provided.'}), 400

    responses = data['responses']  # {"0": "selected_answer", "1": "..."}
    questions = qs.questions_json or []

    correct = 0
    total = len(questions)
    results = []

    for idx, q in enumerate(questions):
        student_answer = responses.get(str(idx))
        correct_answer = q.get('correct_answer', '')
        is_correct = (student_answer == correct_answer) if student_answer else False
        if is_correct:
            correct += 1

        results.append({
            'question_index': idx,
            'student_answer': student_answer,
            'correct_answer': correct_answer,
            'is_correct': is_correct,
        })

    percentage = round((correct / total) * 100) if total > 0 else 0

    return jsonify({
        'score': correct,
        'total': total,
        'percentage': percentage,
        'results': results,
    })


@main_bp.route('/paper/<share_token>/api')
def paper_api(share_token):
    """JSON API for shared paper metadata (Open Graph, embeds, etc.)."""
    qs = QuestionSet.query.filter_by(share_token=share_token).first()

    if not qs or not qs.is_shared:
        return jsonify({'error': 'Paper not available.'}), 404

    paper_config = qs.paper_config or {}
    return jsonify({
        'title': paper_config.get('title', qs.name),
        'class_name': paper_config.get('class_name', ''),
        'subject_name': paper_config.get('subject_name', ''),
        'question_count': len(qs.questions_json) if qs.questions_json else 0,
        'marks': paper_config.get('marks', 0),
        'time': paper_config.get('time', 0),
    })
