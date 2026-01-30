"""
AI Question Generator Service
Generates MCQ questions using AI APIs (OpenAI, etc.)
"""
import json
import time
import threading
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import requests

# Thread-safe state
_generator_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()


DEFAULT_PROMPT_TEMPLATE = """You are an expert question generator for the Bangladesh NCTB curriculum.
Generate {count} unique multiple choice questions (MCQ) for:

Class: {class_name}
Subject: {subject_name}  
Chapter: {chapter_name}

Requirements:
1. Questions must be relevant to the chapter content
2. Each question must have exactly 4 options
3. Include a mix of difficulty levels
4. Questions should be in Bengali (বাংলা) language
5. Make sure answers are factually correct

Return ONLY a valid JSON array with this format:
[
  {{
    "question_text": "প্রশ্নটি এখানে লিখুন?",
    "type": "simple",
    "answer_options": ["অপশন ১", "অপশন ২", "অপশন ৩", "অপশন ৪"],
    "correct_answer": "সঠিক অপশন"
  }}
]

For complex questions with sub-options, use:
[
  {{
    "question_text": "নিচের কোনটি সঠিক?",
    "type": "complex",
    "sub_options": ["i. প্রথম বিবৃতি", "ii. দ্বিতীয় বিবৃতি", "iii. তৃতীয় বিবৃতি"],
    "final_prompt": "উপরের কোনটি সঠিক?",
    "answer_options": ["শুধু i", "শুধু ii", "i ও ii", "সবগুলো"],
    "correct_answer": "i ও ii"
  }}
]

Generate exactly {count} questions. Return ONLY the JSON array, no other text."""


def get_question_hash(question_text: str) -> str:
    """Generate a hash of question text for duplicate detection"""
    # Normalize the text (lowercase, remove extra spaces)
    normalized = ' '.join(question_text.lower().split())
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()


def check_duplicate(question_text: str, chapter_id: int, db_session) -> bool:
    """Check if a similar question already exists in the chapter"""
    from app.models import Question
    
    # Get all questions in the chapter
    existing_questions = Question.query.filter_by(chapter_id=chapter_id).all()
    
    new_hash = get_question_hash(question_text)
    
    for q in existing_questions:
        if get_question_hash(q.question_text) == new_hash:
            return True
        
        # Also check for very similar text (80% match)
        if text_similarity(question_text, q.question_text) > 0.8:
            return True
    
    return False


def text_similarity(text1: str, text2: str) -> float:
    """Calculate simple text similarity using word overlap"""
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1 & words2
    union = words1 | words2
    
    return len(intersection) / len(union)


def call_gemini_api(api_key: str, model: str, prompt: str) -> Tuple[Optional[List[Dict]], int, Optional[str]]:
    """
    Call Google Gemini API to generate questions
    Returns: (questions_list, tokens_used, error_message)
    """
    try:
        # Gemini API endpoint
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        data = {
            'contents': [
                {
                    'parts': [
                        {'text': f"You are a helpful assistant that generates educational MCQ questions. Always respond with valid JSON only.\n\n{prompt}"}
                    ]
                }
            ],
            'generationConfig': {
                'temperature': 0.7,
                'maxOutputTokens': 4000,
                'responseMimeType': 'application/json'
            }
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=60)
        
        if response.status_code != 200:
            return None, 0, f"Gemini API Error: {response.status_code} - {response.text}"
        
        result = response.json()
        
        # Extract token count from usage metadata
        tokens_used = result.get('usageMetadata', {}).get('totalTokenCount', 0)
        
        # Get the content from Gemini response
        candidates = result.get('candidates', [])
        if not candidates:
            return None, tokens_used, "Gemini returned no candidates"
        
        content = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '')
        
        if not content:
            return None, tokens_used, "Gemini returned empty content"
        
        # Try to extract JSON from the response
        content = content.strip()
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            content = content.split('```')[1].split('```')[0].strip()
        
        questions = json.loads(content)
        
        if not isinstance(questions, list):
            return None, tokens_used, "API returned invalid format (not a list)"
        
        return questions, tokens_used, None
        
    except json.JSONDecodeError as e:
        return None, 0, f"Invalid JSON in Gemini response: {str(e)}"
    except requests.exceptions.Timeout:
        return None, 0, "Gemini API request timed out"
    except Exception as e:
        return None, 0, f"Gemini API Error: {str(e)}"


def call_openai_api(api_key: str, model: str, prompt: str) -> Tuple[Optional[List[Dict]], int, Optional[str]]:
    """
    Call OpenAI API to generate questions
    Returns: (questions_list, tokens_used, error_message)
    """
    try:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': 'You are a helpful assistant that generates educational MCQ questions. Always respond with valid JSON only.'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.7,
            'max_tokens': 4000
        }
        
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            json=data,
            timeout=60
        )
        
        if response.status_code != 200:
            return None, 0, f"API Error: {response.status_code} - {response.text}"
        
        result = response.json()
        tokens_used = result.get('usage', {}).get('total_tokens', 0)
        content = result['choices'][0]['message']['content'].strip()
        
        # Try to extract JSON from the response
        # Sometimes the API wraps it in markdown code blocks
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            content = content.split('```')[1].split('```')[0].strip()
        
        questions = json.loads(content)
        
        if not isinstance(questions, list):
            return None, tokens_used, "API returned invalid format (not a list)"
        
        return questions, tokens_used, None
        
    except json.JSONDecodeError as e:
        return None, 0, f"Invalid JSON in response: {str(e)}"
    except requests.exceptions.Timeout:
        return None, 0, "API request timed out"
    except Exception as e:
        return None, 0, f"API Error: {str(e)}"


def get_next_chapter(current_class_id: int, current_subject_id: int, current_chapter_id: int):
    """
    Get the next chapter in the cycle.
    Order: current chapter's next -> next subject's first chapter -> next class's first subject's first chapter
    Returns: (class_id, subject_id, chapter_id) or None if no more chapters
    """
    from app.models import Class, Subject, Chapter
    
    # Get current chapter's order
    current_chapter = Chapter.query.get(current_chapter_id) if current_chapter_id else None
    current_subject = Subject.query.get(current_subject_id) if current_subject_id else None
    current_class = Class.query.get(current_class_id) if current_class_id else None
    
    if not current_class:
        # Start from the first class
        first_class = Class.query.filter_by(is_active=True).order_by(Class.order).first()
        if not first_class:
            return None
        first_subject = Subject.query.filter_by(class_id=first_class.id, is_active=True).order_by(Subject.order).first()
        if not first_subject:
            return None
        first_chapter = Chapter.query.filter_by(subject_id=first_subject.id, is_active=True).order_by(Chapter.order).first()
        if not first_chapter:
            return None
        return first_class.id, first_subject.id, first_chapter.id
    
    # Try to get next chapter in current subject
    if current_chapter:
        next_chapter = Chapter.query.filter(
            Chapter.subject_id == current_subject_id,
            Chapter.is_active == True,
            Chapter.order > current_chapter.order
        ).order_by(Chapter.order).first()
        
        if next_chapter:
            return current_class_id, current_subject_id, next_chapter.id
    
    # No more chapters in this subject, try next subject
    if current_subject:
        next_subject = Subject.query.filter(
            Subject.class_id == current_class_id,
            Subject.is_active == True,
            Subject.order > current_subject.order
        ).order_by(Subject.order).first()
        
        if next_subject:
            first_chapter = Chapter.query.filter_by(
                subject_id=next_subject.id, 
                is_active=True
            ).order_by(Chapter.order).first()
            
            if first_chapter:
                return current_class_id, next_subject.id, first_chapter.id
    
    # No more subjects in this class, try next class
    next_class = Class.query.filter(
        Class.is_active == True,
        Class.order > current_class.order
    ).order_by(Class.order).first()
    
    if next_class:
        first_subject = Subject.query.filter_by(
            class_id=next_class.id, 
            is_active=True
        ).order_by(Subject.order).first()
        
        if first_subject:
            first_chapter = Chapter.query.filter_by(
                subject_id=first_subject.id, 
                is_active=True
            ).order_by(Chapter.order).first()
            
            if first_chapter:
                return next_class.id, first_subject.id, first_chapter.id
    
    # Cycle back to the start
    first_class = Class.query.filter_by(is_active=True).order_by(Class.order).first()
    if first_class:
        first_subject = Subject.query.filter_by(
            class_id=first_class.id, 
            is_active=True
        ).order_by(Subject.order).first()
        
        if first_subject:
            first_chapter = Chapter.query.filter_by(
                subject_id=first_subject.id, 
                is_active=True
            ).order_by(Chapter.order).first()
            
            if first_chapter:
                return first_class.id, first_subject.id, first_chapter.id
    
    return None


def run_generation_cycle(app):
    """
    Main generation loop that runs in a background thread.
    """
    from app.models import AIGeneratorConfig, AIGeneratorLog, Question, Class, Subject, Chapter
    from app import db
    
    global _stop_event
    
    with app.app_context():
        while not _stop_event.is_set():
            try:
                # Get config
                config = AIGeneratorConfig.query.first()
                if not config or not config.is_running:
                    break
                
                # Check rate limiting
                now = datetime.utcnow()
                if config.hour_started:
                    if now - config.hour_started > timedelta(hours=1):
                        # Reset hourly counter
                        config.requests_this_hour = 0
                        config.hour_started = now
                        db.session.commit()
                else:
                    config.hour_started = now
                    db.session.commit()
                
                if config.requests_this_hour >= config.max_requests_per_hour:
                    # Wait until the hour resets
                    wait_time = (config.hour_started + timedelta(hours=1) - now).total_seconds()
                    if wait_time > 0:
                        _stop_event.wait(min(wait_time, 60))  # Check every minute
                        continue
                
                # Get current position
                current_class = Class.query.get(config.current_class_id) if config.current_class_id else None
                current_subject = Subject.query.get(config.current_subject_id) if config.current_subject_id else None
                current_chapter = Chapter.query.get(config.current_chapter_id) if config.current_chapter_id else None
                
                if not current_chapter:
                    # Get the first chapter to start
                    next_pos = get_next_chapter(
                        config.current_class_id, 
                        config.current_subject_id, 
                        config.current_chapter_id
                    )
                    if not next_pos:
                        # No chapters available
                        log = AIGeneratorLog(
                            status='skipped',
                            error_message='No chapters available to process'
                        )
                        db.session.add(log)
                        db.session.commit()
                        _stop_event.wait(config.interval_minutes * 60)
                        continue
                    
                    config.current_class_id, config.current_subject_id, config.current_chapter_id = next_pos
                    db.session.commit()
                    
                    current_class = Class.query.get(config.current_class_id)
                    current_subject = Subject.query.get(config.current_subject_id)
                    current_chapter = Chapter.query.get(config.current_chapter_id)
                
                # Build the prompt
                prompt_template = config.prompt_template or DEFAULT_PROMPT_TEMPLATE
                prompt = prompt_template.format(
                    count=config.questions_per_request,
                    class_name=current_class.name,
                    subject_name=current_subject.name,
                    chapter_name=current_chapter.name
                )
                
                # Call the AI API based on provider
                start_time = time.time()
                if config.api_provider == 'gemini':
                    questions, tokens_used, error = call_gemini_api(
                        config.api_key,
                        config.model_name,
                        prompt
                    )
                else:
                    questions, tokens_used, error = call_openai_api(
                        config.api_key,
                        config.model_name,
                        prompt
                    )
                response_time = time.time() - start_time
                
                # Update request counter
                config.requests_this_hour += 1
                config.last_run_at = now
                
                if error:
                    # Log the error
                    log = AIGeneratorLog(
                        class_id=config.current_class_id,
                        subject_id=config.current_subject_id,
                        chapter_id=config.current_chapter_id,
                        status='error',
                        error_message=error,
                        tokens_used=tokens_used,
                        api_response_time=response_time
                    )
                    db.session.add(log)
                    config.total_errors += 1
                    db.session.commit()
                else:
                    # Process the generated questions
                    added_count = 0
                    duplicate_count = 0
                    
                    for q_data in questions:
                        question_text = q_data.get('question_text', '')
                        
                        if not question_text:
                            continue
                        
                        # Check for duplicates
                        if check_duplicate(question_text, config.current_chapter_id, db.session):
                            duplicate_count += 1
                            continue
                        
                        # Add the question
                        new_question = Question(
                            question_text=question_text,
                            question_type=q_data.get('type', 'simple'),
                            chapter_id=config.current_chapter_id,
                            answer_options=q_data.get('answer_options', []),
                            correct_answer=q_data.get('correct_answer', ''),
                            sub_options=q_data.get('sub_options'),
                            final_prompt=q_data.get('final_prompt'),
                            created_by=None  # AI generated
                        )
                        db.session.add(new_question)
                        added_count += 1
                    
                    # Log the result
                    log = AIGeneratorLog(
                        class_id=config.current_class_id,
                        subject_id=config.current_subject_id,
                        chapter_id=config.current_chapter_id,
                        status='success',
                        questions_generated=added_count,
                        duplicates_found=duplicate_count,
                        tokens_used=tokens_used,
                        api_response_time=response_time
                    )
                    db.session.add(log)
                    
                    # Update stats
                    config.total_questions_generated += added_count
                    config.total_duplicates_skipped += duplicate_count
                    
                    db.session.commit()
                
                # Move to next chapter
                next_pos = get_next_chapter(
                    config.current_class_id,
                    config.current_subject_id,
                    config.current_chapter_id
                )
                
                if next_pos:
                    config.current_class_id, config.current_subject_id, config.current_chapter_id = next_pos
                    db.session.commit()
                
                # Wait for the interval
                _stop_event.wait(config.interval_minutes * 60)
                
            except Exception as e:
                # Log unexpected errors
                try:
                    log = AIGeneratorLog(
                        status='error',
                        error_message=f"Unexpected error: {str(e)}"
                    )
                    db.session.add(log)
                    db.session.commit()
                except:
                    pass
                
                # Wait before retrying
                _stop_event.wait(60)
        
        # Clean up when stopped
        try:
            config = AIGeneratorConfig.query.first()
            if config:
                config.is_running = False
                db.session.commit()
        except:
            pass


def start_generator(app, start_class_id: int = None, start_subject_id: int = None, start_chapter_id: int = None):
    """Start the AI generator background thread"""
    global _generator_thread, _stop_event
    from app.models import AIGeneratorConfig
    from app import db
    
    with app.app_context():
        config = AIGeneratorConfig.query.first()
        if not config:
            return False, "Generator not configured. Please set up API key and settings first."
        
        if not config.api_key:
            return False, "API key not configured."
        
        if config.is_running:
            return False, "Generator is already running."
        
        # Set starting position if provided
        if start_class_id:
            config.current_class_id = start_class_id
        if start_subject_id:
            config.current_subject_id = start_subject_id
        if start_chapter_id:
            config.current_chapter_id = start_chapter_id
        
        config.is_running = True
        config.started_at = datetime.utcnow()
        db.session.commit()
    
    # Reset stop event and start thread
    _stop_event.clear()
    _generator_thread = threading.Thread(target=run_generation_cycle, args=(app,), daemon=True)
    _generator_thread.start()
    
    return True, "Generator started successfully."


def stop_generator(app):
    """Stop the AI generator background thread"""
    global _generator_thread, _stop_event
    from app.models import AIGeneratorConfig
    from app import db
    
    _stop_event.set()
    
    with app.app_context():
        config = AIGeneratorConfig.query.first()
        if config:
            config.is_running = False
            db.session.commit()
    
    if _generator_thread and _generator_thread.is_alive():
        _generator_thread.join(timeout=5)
    
    return True, "Generator stopped."


def get_generator_status(app) -> Dict:
    """Get current generator status"""
    from app.models import AIGeneratorConfig, AIGeneratorLog, Class, Subject, Chapter
    
    with app.app_context():
        config = AIGeneratorConfig.query.first()
        
        if not config:
            return {
                'configured': False,
                'is_running': False
            }
        
        # Get recent logs
        recent_logs = AIGeneratorLog.query.order_by(
            AIGeneratorLog.created_at.desc()
        ).limit(20).all()
        
        # Current position info
        current_class = Class.query.get(config.current_class_id) if config.current_class_id else None
        current_subject = Subject.query.get(config.current_subject_id) if config.current_subject_id else None
        current_chapter = Chapter.query.get(config.current_chapter_id) if config.current_chapter_id else None
        
        return {
            'configured': True,
            'is_running': config.is_running,
            'api_provider': config.api_provider,
            'model_name': config.model_name,
            'interval_minutes': config.interval_minutes,
            'questions_per_request': config.questions_per_request,
            'max_requests_per_hour': config.max_requests_per_hour,
            'requests_this_hour': config.requests_this_hour,
            'current_class': current_class.name if current_class else None,
            'current_subject': current_subject.name if current_subject else None,
            'current_chapter': current_chapter.name if current_chapter else None,
            'started_at': config.started_at.isoformat() if config.started_at else None,
            'last_run_at': config.last_run_at.isoformat() if config.last_run_at else None,
            'total_questions_generated': config.total_questions_generated,
            'total_duplicates_skipped': config.total_duplicates_skipped,
            'total_errors': config.total_errors,
            'recent_logs': [
                {
                    'id': log.id,
                    'status': log.status,
                    'class': log.class_ref.name if log.class_ref else None,
                    'subject': log.subject_ref.name if log.subject_ref else None,
                    'chapter': log.chapter_ref.name if log.chapter_ref else None,
                    'questions_generated': log.questions_generated,
                    'duplicates_found': log.duplicates_found,
                    'error_message': log.error_message,
                    'tokens_used': log.tokens_used,
                    'api_response_time': round(log.api_response_time, 2) if log.api_response_time else None,
                    'created_at': log.created_at.isoformat()
                }
                for log in recent_logs
            ]
        }
