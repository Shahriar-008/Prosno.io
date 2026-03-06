"""
cache.py — Flask-Caching abstraction for the Teacher Question Bank.

Uses RedisCache when REDIS_URL is configured, SimpleCache (in-memory) otherwise.
Graceful fallback: all cached endpoints work without Redis.

Usage:
    from app.utils.cache import cache, invalidate_browse_cache

    @cache.cached(timeout=3600, key_prefix='bank:browse:classes')
    def browse_classes(): ...

    # After a question is approved:
    invalidate_browse_cache(class_id=3, subject_id=12, chapter_id=45)
"""

import os
from flask_caching import Cache

cache = Cache()

# Key patterns
_KEY_CLASSES = 'bank:browse:classes'
_KEY_SUBJECTS = 'bank:browse:subjects:{class_id}'
_KEY_CHAPTERS = 'bank:browse:chapters:{subject_id}'
_KEY_CHAPTER_Q = 'bank:browse:chapter:{chapter_id}:q'
_KEY_LEADERBOARD = 'bank:leaderboard'


def init_cache(app):
    """
    Initialise Flask-Caching on the app.
    Uses RedisCache if REDIS_URL is set, SimpleCache otherwise.
    """
    redis_url = os.environ.get('REDIS_URL')
    if redis_url:
        app.config['CACHE_TYPE'] = 'RedisCache'
        app.config['CACHE_REDIS_URL'] = redis_url
        app.config.setdefault('CACHE_DEFAULT_TIMEOUT', 3600)
        print(f'Cache: RedisCache @ {redis_url}')
    else:
        app.config['CACHE_TYPE'] = 'SimpleCache'
        app.config.setdefault('CACHE_DEFAULT_TIMEOUT', 3600)
        print('Cache: SimpleCache (in-memory, no Redis configured)')
    cache.init_app(app)


def invalidate_browse_cache(class_id=None, subject_id=None, chapter_id=None):
    """
    Invalidate browse-hierarchy cache keys after a question is published or deleted.
    Call this after a visibility change so counts stay fresh.
    """
    try:
        keys_to_delete = [_KEY_CLASSES]
        if class_id:
            keys_to_delete.append(_KEY_SUBJECTS.format(class_id=class_id))
        if subject_id:
            keys_to_delete.append(_KEY_CHAPTERS.format(subject_id=subject_id))
        if chapter_id:
            keys_to_delete.append(_KEY_CHAPTER_Q.format(chapter_id=chapter_id))

        for key in keys_to_delete:
            cache.delete(key)
    except Exception:
        pass  # Never crash the main request on cache failure


def invalidate_leaderboard():
    """Invalidate the leaderboard cache key."""
    try:
        cache.delete(_KEY_LEADERBOARD)
    except Exception:
        pass


# Convenience key builders for use in route decorators
def class_key():
    return _KEY_CLASSES


def subject_key():
    from flask import request
    class_id = request.view_args.get('class_id', 0)
    return _KEY_SUBJECTS.format(class_id=class_id)


def chapter_key():
    from flask import request
    subject_id = request.view_args.get('subject_id', 0)
    return _KEY_CHAPTERS.format(subject_id=subject_id)


def chapter_q_key():
    from flask import request
    chapter_id = request.view_args.get('chapter_id', 0)
    diff = request.args.get('difficulty', 'all')
    sort = request.args.get('sort', 'newest')
    page = request.args.get('page', '1')
    return f'{_KEY_CHAPTER_Q.format(chapter_id=chapter_id)}:{diff}:{sort}:{page}'
