"""
Quiz routes for Prosno.io — Online Quiz Mode
Handles quiz creation, student join, play, submit, results, and leaderboard.
"""
import time
import secrets
from datetime import datetime
from flask import (
    Blueprint, render_template, request, jsonify, session,
    redirect, url_for, abort, current_app
)
from app import db, csrf, limiter
from app.models import Quiz, QuizSession, QuestionSet

quiz_bp = Blueprint('quiz', __name__, url_prefix='/quiz')

# ── In-memory leaderboard cache (smart optimization polling) ──────────
_leaderboard_cache = {}


def _require_teacher():
    """Return Supabase user dict or None."""
    return session.get('user')


# ═══════════════════════════════════════════════════════════════════════
#  TEACHER ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@quiz_bp.route('/create', methods=['POST'])
@limiter.limit("20 per hour")
def create_quiz():
    """Teacher creates a quiz from a saved question set."""
    user = _require_teacher()
    if not user:
        return jsonify({'error': 'Login required.', 'login_required': True}), 401

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided.'}), 400

    set_id = data.get('question_set_id')
    if not set_id:
        return jsonify({'error': 'No question set selected.'}), 400

    # Fetch the question set (must belong to this user)
    qs = QuestionSet.query.filter_by(id=set_id, user_id=user['id']).first()
    if not qs:
        return jsonify({'error': 'Question set not found.'}), 404

    if not qs.questions_json or len(qs.questions_json) == 0:
        return jsonify({'error': 'Question set is empty.'}), 400

    # Create quiz with a snapshot of questions
    try:
        quiz = Quiz(
            join_code=Quiz.generate_join_code(),
            title=data.get('title', qs.name)[:200],
            question_set_id=qs.id,
            teacher_user_id=user['id'],
            questions_json=qs.questions_json,
            time_limit_minutes=min(int(data.get('time_limit', 30)), 120),
            shuffle_questions=data.get('shuffle_questions', True),
            shuffle_options=data.get('shuffle_options', True),
            show_results_to_students=data.get('show_results', True),
        )
        db.session.add(quiz)
        db.session.commit()

        return jsonify({
            'success': True,
            'quiz': quiz.to_dict(),
            'lobby_url': url_for('quiz.lobby', code=quiz.join_code),
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create quiz: {str(e)}'}), 500


@quiz_bp.route('/<code>/lobby')
def lobby(code):
    """Teacher's quiz lobby — see who joined, start/manage quiz."""
    quiz = Quiz.query.filter_by(join_code=code).first_or_404()

    # Check if current user is the teacher (owner)
    user = _require_teacher()
    is_teacher = user and user['id'] == quiz.teacher_user_id

    if not is_teacher:
        # Maybe a student trying to access lobby — redirect to join
        return redirect(url_for('quiz.join_page', code=code))

    students = quiz.sessions.order_by(QuizSession.joined_at.asc()).all()
    return render_template('quiz/quiz_lobby.html',
                           quiz=quiz, students=students, is_teacher=True)


@quiz_bp.route('/<code>/start', methods=['POST'])
@limiter.limit("10 per hour")
def start_quiz(code):
    """Teacher starts the quiz."""
    user = _require_teacher()
    if not user:
        return jsonify({'error': 'Login required.'}), 401

    quiz = Quiz.query.filter_by(join_code=code).first_or_404()
    if user['id'] != quiz.teacher_user_id:
        return jsonify({'error': 'Not authorized.'}), 403

    if quiz.status != 'waiting':
        return jsonify({'error': f'Quiz already {quiz.status}.'}), 400

    quiz.status = 'active'
    quiz.started_at = datetime.utcnow()
    db.session.commit()

    # Clear leaderboard cache
    _leaderboard_cache.pop(code, None)

    return jsonify({'success': True, 'status': 'active'})


@quiz_bp.route('/<code>/end', methods=['POST'])
@limiter.limit("10 per hour")
def end_quiz(code):
    """Teacher ends the quiz early."""
    user = _require_teacher()
    if not user:
        return jsonify({'error': 'Login required.'}), 401

    quiz = Quiz.query.filter_by(join_code=code).first_or_404()
    if user['id'] != quiz.teacher_user_id:
        return jsonify({'error': 'Not authorized.'}), 403

    quiz.status = 'ended'
    quiz.ended_at = datetime.utcnow()
    db.session.commit()

    _leaderboard_cache.pop(code, None)
    return jsonify({'success': True, 'status': 'ended'})


@quiz_bp.route('/<code>/status')
def quiz_status(code):
    """Poll endpoint — returns quiz status + student list (for lobby auto-refresh)."""
    quiz = Quiz.query.filter_by(join_code=code).first_or_404()
    students = quiz.sessions.order_by(QuizSession.joined_at.asc()).all()

    return jsonify({
        'status': quiz.status,
        'student_count': len(students),
        'students': [s.to_dict() for s in students],
    })


@quiz_bp.route('/<code>/results')
def results(code):
    """Quiz results page — teacher sees full analytics."""
    quiz = Quiz.query.filter_by(join_code=code).first_or_404()

    user = _require_teacher()
    is_teacher = user and user['id'] == quiz.teacher_user_id

    if quiz.status != 'ended' and not is_teacher:
        # Students can only see results after quiz ends
        return redirect(url_for('quiz.join_page', code=code))

    sessions = quiz.sessions.order_by(QuizSession.score.desc()).all()
    submitted = [s for s in sessions if s.status == 'submitted']

    # Compute question-level analytics
    question_stats = []
    if quiz.questions_json and submitted:
        for idx, q in enumerate(quiz.questions_json):
            correct_count = 0
            for s in submitted:
                if s.responses_json and s.responses_json.get(str(idx)) == q.get('correct_answer'):
                    correct_count += 1
            pct = round((correct_count / len(submitted)) * 100) if submitted else 0
            question_stats.append({
                'index': idx + 1,
                'text': q.get('question_text', '')[:100],
                'correct_count': correct_count,
                'total': len(submitted),
                'percentage': pct,
            })

    # Summary stats
    scores = [s.score for s in submitted]
    stats = {
        'total_students': len(sessions),
        'submitted': len(submitted),
        'average': round(sum(scores) / len(scores), 1) if scores else 0,
        'highest': max(scores) if scores else 0,
        'lowest': min(scores) if scores else 0,
        'total_questions': len(quiz.questions_json) if quiz.questions_json else 0,
    }
    if stats['total_questions'] > 0:
        pass_count = sum(1 for s in scores if s >= stats['total_questions'] * 0.4)
        stats['pass_rate'] = round((pass_count / len(submitted)) * 100) if submitted else 0
    else:
        stats['pass_rate'] = 0

    return render_template('quiz/quiz_results.html',
                           quiz=quiz, sessions=submitted, stats=stats,
                           question_stats=question_stats, is_teacher=is_teacher)


@quiz_bp.route('/<code>/leaderboard')
def leaderboard(code):
    """Smart-cached leaderboard JSON endpoint (polled every 5s)."""
    cached = _leaderboard_cache.get(code)
    if cached and (time.time() - cached['ts']) < 5:
        return jsonify(cached['data'])

    quiz = Quiz.query.filter_by(join_code=code).first_or_404()
    sessions = quiz.sessions.filter(
        QuizSession.status == 'submitted'
    ).order_by(QuizSession.score.desc()).all()

    data = {
        'quiz_status': quiz.status,
        'leaderboard': [
            {
                'rank': idx + 1,
                'name': s.student_name,
                'score': s.score,
                'total': s.total_questions,
                'percentage': s.score_percentage,
                'time_taken': s.time_taken_seconds,
            }
            for idx, s in enumerate(sessions)
        ],
    }

    _leaderboard_cache[code] = {'data': data, 'ts': time.time()}
    return jsonify(data)


@quiz_bp.route('/<code>/export')
def export_results(code):
    """Export quiz results as CSV."""
    user = _require_teacher()
    if not user:
        return redirect(url_for('auth.login'))

    quiz = Quiz.query.filter_by(join_code=code).first_or_404()
    if user['id'] != quiz.teacher_user_id:
        abort(403)

    sessions = quiz.sessions.order_by(QuizSession.score.desc()).all()
    submitted = [s for s in sessions if s.status == 'submitted']

    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Rank', 'Student Name', 'Score', 'Total Questions',
                     'Percentage', 'Time Taken (sec)', 'Submitted At'])

    for idx, s in enumerate(submitted, 1):
        writer.writerow([
            idx,
            s.student_name,
            s.score,
            s.total_questions,
            f'{s.score_percentage}%',
            s.time_taken_seconds or '',
            s.submitted_at.strftime('%Y-%m-%d %H:%M') if s.submitted_at else '',
        ])

    from flask import Response
    csv_data = output.getvalue()
    output.close()

    filename = f'quiz_{quiz.join_code}_results.csv'
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


# ═══════════════════════════════════════════════════════════════════════
#  STUDENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@quiz_bp.route('/join', defaults={'code': None})
@quiz_bp.route('/join/<code>')
def join_page(code=None):
    """Student join page — enter quiz code + name."""
    return render_template('quiz/quiz_join.html', code=code or '')


@quiz_bp.route('/<code>/join', methods=['POST'])
@limiter.limit("30 per minute")
def join_quiz(code):
    """Student joins a quiz."""
    quiz = Quiz.query.filter_by(join_code=code).first()
    if not quiz:
        return jsonify({'error': 'Invalid quiz code. Please check and try again.'}), 404

    if quiz.status == 'ended':
        return jsonify({'error': 'This quiz has already ended.'}), 400

    data = request.get_json()
    name = (data.get('name', '') if data else '').strip()
    if not name or len(name) < 1:
        return jsonify({'error': 'Please enter your name.'}), 400

    # Check for duplicate names in this quiz
    existing = QuizSession.query.filter_by(
        quiz_id=quiz.id, student_name=name
    ).first()
    if existing:
        # Resume existing session
        session['quiz_token'] = existing.session_token
        session['quiz_code'] = code
        return jsonify({
            'success': True,
            'resumed': True,
            'status': quiz.status,
            'redirect': url_for('quiz.play', code=code) if quiz.is_active else None,
        })

    # Create new session
    token = secrets.token_hex(32)
    qs = QuizSession(
        quiz_id=quiz.id,
        student_name=name[:100],
        session_token=token,
    )
    db.session.add(qs)
    db.session.commit()

    session['quiz_token'] = token
    session['quiz_code'] = code

    return jsonify({
        'success': True,
        'resumed': False,
        'status': quiz.status,
        'redirect': url_for('quiz.play', code=code) if quiz.is_active else None,
    })


@quiz_bp.route('/<code>/play')
def play(code):
    """Student quiz-taking page."""
    quiz = Quiz.query.filter_by(join_code=code).first_or_404()

    # Verify student session
    token = session.get('quiz_token')
    if not token:
        return redirect(url_for('quiz.join_page', code=code))

    qs = QuizSession.query.filter_by(session_token=token, quiz_id=quiz.id).first()
    if not qs:
        return redirect(url_for('quiz.join_page', code=code))

    if qs.status == 'submitted':
        return redirect(url_for('quiz.score', code=code))

    if quiz.status == 'waiting':
        return redirect(url_for('quiz.waiting', code=code))

    if quiz.status == 'ended':
        return redirect(url_for('quiz.score', code=code))

    # Prepare questions (without correct answers!)
    import random
    import copy

    questions = copy.deepcopy(quiz.questions_json)

    # Build a deterministic shuffled order using the session token as seed
    if quiz.shuffle_questions:
        rng = random.Random(token + 'q')
        indices = list(range(len(questions)))
        rng.shuffle(indices)
        questions = [questions[i] for i in indices]
    else:
        indices = list(range(len(questions)))

    # Shuffle options per question
    if quiz.shuffle_options:
        for q in questions:
            if 'answer_options' in q and isinstance(q['answer_options'], list):
                rng_opt = random.Random(token + str(q.get('question_text', '')))
                rng_opt.shuffle(q['answer_options'])

    # Strip correct answers from questions sent to client
    safe_questions = []
    for q in questions:
        safe_q = {
            'question_text': q.get('question_text', ''),
            'answer_options': q.get('answer_options', []),
            'type': q.get('type', 'simple'),
        }
        if q.get('type') == 'complex':
            safe_q['sub_options'] = q.get('sub_options', [])
            safe_q['final_prompt'] = q.get('final_prompt', '')
        safe_questions.append(safe_q)

    # Store the shuffle order in session so we can grade correctly
    session['quiz_order'] = indices
    qs.status = 'in_progress'
    db.session.commit()

    return render_template('quiz/quiz_play.html',
                           quiz=quiz, questions=safe_questions,
                           session_id=qs.id, student_name=qs.student_name)


@quiz_bp.route('/<code>/waiting')
def waiting(code):
    """Student waiting room — quiz hasn't started yet."""
    quiz = Quiz.query.filter_by(join_code=code).first_or_404()

    token = session.get('quiz_token')
    if not token:
        return redirect(url_for('quiz.join_page', code=code))

    qs = QuizSession.query.filter_by(session_token=token, quiz_id=quiz.id).first()
    if not qs:
        return redirect(url_for('quiz.join_page', code=code))

    if quiz.is_active:
        return redirect(url_for('quiz.play', code=code))

    return render_template('quiz/quiz_waiting.html', quiz=quiz, student_name=qs.student_name)


@quiz_bp.route('/<code>/submit', methods=['POST'])
@limiter.limit("10 per minute")
def submit_quiz(code):
    """Student submits their answers."""
    quiz = Quiz.query.filter_by(join_code=code).first_or_404()

    token = session.get('quiz_token')
    if not token:
        return jsonify({'error': 'Session expired. Please rejoin.'}), 401

    qs = QuizSession.query.filter_by(session_token=token, quiz_id=quiz.id).first()
    if not qs:
        return jsonify({'error': 'Session not found.'}), 404

    if qs.status == 'submitted':
        return jsonify({'error': 'Already submitted.', 'redirect': url_for('quiz.score', code=code)}), 400

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided.'}), 400

    responses = data.get('responses', {})
    time_taken = data.get('time_taken_seconds', 0)

    # Map shuffled indices back to original question indices
    shuffle_order = session.get('quiz_order', list(range(len(quiz.questions_json))))
    original_responses = {}
    for shuffled_idx_str, answer in responses.items():
        shuffled_idx = int(shuffled_idx_str)
        if shuffled_idx < len(shuffle_order):
            original_idx = shuffle_order[shuffled_idx]
            original_responses[str(original_idx)] = answer

    qs.responses_json = original_responses
    qs.time_taken_seconds = min(int(time_taken), quiz.time_limit_minutes * 60 + 60)
    qs.submitted_at = datetime.utcnow()

    # Auto-grade
    qs.grade(quiz.questions_json)
    qs.status = 'submitted'

    db.session.commit()

    # Invalidate leaderboard cache
    _leaderboard_cache.pop(code, None)

    return jsonify({
        'success': True,
        'score': qs.score,
        'total': qs.total_questions,
        'percentage': qs.score_percentage,
        'redirect': url_for('quiz.score', code=code),
    })


@quiz_bp.route('/<code>/score')
def score(code):
    """Student score page after submission."""
    quiz = Quiz.query.filter_by(join_code=code).first_or_404()

    token = session.get('quiz_token')
    student_session = None
    if token:
        student_session = QuizSession.query.filter_by(
            session_token=token, quiz_id=quiz.id
        ).first()

    # Get leaderboard
    all_submitted = quiz.sessions.filter(
        QuizSession.status == 'submitted'
    ).order_by(QuizSession.score.desc()).all()

    # Find student's rank
    rank = None
    if student_session:
        for idx, s in enumerate(all_submitted, 1):
            if s.id == student_session.id:
                rank = idx
                break

    return render_template('quiz/quiz_score.html',
                           quiz=quiz, student=student_session,
                           leaderboard=all_submitted, rank=rank)


# ═══════════════════════════════════════════════════════════════════════
#  TEACHER QUIZ LIST (for dashboard integration)
# ═══════════════════════════════════════════════════════════════════════

@quiz_bp.route('/my-quizzes')
def my_quizzes():
    """JSON endpoint — list teacher's quizzes."""
    user = _require_teacher()
    if not user:
        return jsonify({'error': 'Login required.'}), 401

    quizzes = Quiz.query.filter_by(
        teacher_user_id=user['id']
    ).order_by(Quiz.created_at.desc()).all()

    return jsonify({
        'quizzes': [q.to_dict() for q in quizzes],
    })
