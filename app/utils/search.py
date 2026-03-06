"""
search.py — Meilisearch integration for the Teacher Question Bank.

Graceful: returns None / falls back to ilike SQL when MEILI_URL is not configured.

Environment variables:
    MEILI_URL  — Meilisearch host URL (e.g. http://localhost:7700)
    MEILI_KEY  — Meilisearch master / API key

Usage:
    from app.utils.search import sync_question_to_index, search_bank_questions

    # After a question is approved:
    sync_question_to_index(bq)

    # In the search endpoint (tries Meili first):
    results = search_bank_questions(q, filters, page, per_page)
    if results is None:
        # fall back to SQL
"""

import os
import logging

log = logging.getLogger(__name__)

INDEX_NAME = 'bank_questions'

_client = None   # lazily initialised


def _get_client():
    """Return a Meilisearch client, or None if not configured."""
    global _client
    if _client is not None:
        return _client

    url = os.environ.get('MEILI_URL', '').strip()
    if not url:
        return None

    try:
        import meilisearch
        key = os.environ.get('MEILI_KEY', '')
        _client = meilisearch.Client(url, key)
        # Ensure index exists with correct filterable/sortable attributes
        try:
            _client.create_index(INDEX_NAME, {'primaryKey': 'id'})
        except Exception:
            pass  # Already exists
        idx = _client.index(INDEX_NAME)
        idx.update_filterable_attributes([
            'class_id', 'subject_id', 'chapter_id',
            'question_type', 'difficulty', 'visibility',
        ])
        idx.update_sortable_attributes(['usage_count', 'created_at'])
        log.info(f'Meilisearch connected @ {url}')
        return _client
    except ImportError:
        log.warning('meilisearch package not installed — search falls back to SQL')
        return None
    except Exception as e:
        log.warning(f'Meilisearch unavailable ({e}) — falling back to SQL search')
        return None


def _bq_to_doc(bq) -> dict:
    """Convert a BankQuestion ORM object to a Meilisearch document."""
    return {
        'id': bq.id,
        'teacher_id': bq.teacher_id,
        'class_id': bq.class_id,
        'subject_id': bq.subject_id,
        'chapter_id': bq.chapter_id,
        'class_name': bq.class_ref.name if bq.class_ref else '',
        'subject_name': bq.subject_ref.name if bq.subject_ref else '',
        'chapter_name': bq.chapter_ref.name if bq.chapter_ref else '',
        'question_type': bq.question_type,
        'question_text': bq.question_text,
        'topic': bq.topic or '',
        'difficulty': bq.difficulty,
        'marks': bq.marks,
        'board': bq.board or '',
        'year': bq.year,
        'visibility': bq.visibility,
        'usage_count': bq.usage_count,
        'average_rating': bq.average_rating,
        'created_at': bq.created_at.isoformat() if bq.created_at else '',
    }


def sync_question_to_index(bq) -> bool:
    """
    Upsert a BankQuestion to the Meilisearch index.
    Returns True if synced, False if Meilisearch not available.
    """
    client = _get_client()
    if client is None:
        return False
    try:
        idx = client.index(INDEX_NAME)
        idx.update_documents([_bq_to_doc(bq)])
        return True
    except Exception as e:
        log.warning(f'Meili sync failed for question {bq.id}: {e}')
        return False


def delete_question_from_index(question_id: int) -> bool:
    """
    Remove a question from the Meilisearch index.
    Returns True if removed, False if unavailable.
    """
    client = _get_client()
    if client is None:
        return False
    try:
        client.index(INDEX_NAME).delete_document(question_id)
        return True
    except Exception as e:
        log.warning(f'Meili delete failed for question {question_id}: {e}')
        return False


def search_bank_questions(query: str, filters: dict, page: int, per_page: int):
    """
    Full-text search via Meilisearch.
    Returns a dict with 'items' (list of dicts) and 'total', or None if unavailable.
    Callers should fall back to SQL ilike when None is returned.
    """
    client = _get_client()
    if client is None:
        return None

    try:
        filter_parts = ["visibility = 'public'"]
        for key in ('class_id', 'subject_id', 'chapter_id'):
            if filters.get(key):
                filter_parts.append(f'{key} = {filters[key]}')
        if filters.get('question_type'):
            filter_parts.append(f"question_type = '{filters['question_type']}'")
        if filters.get('difficulty'):
            filter_parts.append(f"difficulty = '{filters['difficulty']}'")

        sort = []
        if filters.get('sort') == 'usage':
            sort = ['usage_count:desc']
        elif filters.get('sort') == 'newest':
            sort = ['created_at:desc']

        result = client.index(INDEX_NAME).search(
            query,
            {
                'filter': ' AND '.join(filter_parts),
                'sort': sort,
                'offset': (page - 1) * per_page,
                'limit': per_page,
            }
        )
        return {
            'items': result.get('hits', []),
            'total': result.get('estimatedTotalHits', 0),
        }
    except Exception as e:
        log.warning(f'Meilisearch search failed: {e}')
        return None


def bulk_sync_approved_questions(since=None):
    """
    Push all approved public questions (optionally since a given datetime) to Meilisearch.
    Used by the scheduled background job.
    Returns count of synced questions.
    """
    client = _get_client()
    if client is None:
        return 0

    from app.models import BankQuestion
    q = BankQuestion.query.filter_by(visibility='public', is_active=True)
    if since:
        q = q.filter(BankQuestion.updated_at >= since)

    questions = q.all()
    if not questions:
        return 0

    try:
        docs = [_bq_to_doc(bq) for bq in questions]
        # Batch in groups of 500
        batch_size = 500
        for i in range(0, len(docs), batch_size):
            client.index(INDEX_NAME).update_documents(docs[i:i + batch_size])
        log.info(f'Meili bulk sync: {len(docs)} questions pushed')
        return len(docs)
    except Exception as e:
        log.warning(f'Meili bulk sync failed: {e}')
        return 0
