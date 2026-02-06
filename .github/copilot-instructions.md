# Prosno.io - AI Coding Agent Instructions

## Project Overview
Bengali MCQ question paper generator for Bangladesh NCTB curriculum (Classes 1-10). Flask app with SQLAlchemy, Bootstrap 5, DOCX generation.

## Architecture

### Application Factory
[app/__init__.py](../app/__init__.py) uses `create_app()` with auto-seeding on first run:
- Auto-creates admin, seeds NCTB classes (1-10), applies schema migrations
- Extensions (`db`, `login_manager`, `csrf`, `limiter`) initialized at module level

### Blueprint Structure
| Blueprint | Prefix | Purpose |
|-----------|--------|---------|
| `main_bp` | `/` | Public: landing, paper generation |
| `admin_bp` | `/admin` | Protected admin panel |
| `api_bp` | `/api` | JSON endpoints for frontend |

### Data Model Hierarchy
```
Class → Subject → Chapter → Question
```
All content models have: `name`, `name_bn` (bilingual), `is_active` (soft-delete), `order` (sorting).

### Question Types
- `simple` - Standard MCQ with 4 options
- `complex` - Uses `sub_options` (i, ii, iii) + `final_prompt` for combination questions

## Development

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py  # Auto-seeds on first run
# Frontend: http://localhost:5000 | Admin: http://localhost:5000/admin (Admin / 12345)
```

## Key Patterns

### Adding New Model Fields
1. Add column in [app/models.py](../app/models.py)
2. Add migration tuple to `_apply_schema_migrations()` in [app/__init__.py](../app/__init__.py):
```python
migrations = [
    ('table_name', 'column_name', "TYPE DEFAULT value"),
]
```

### Activity Logging (Admin Routes)
```python
log_activity('create', 'question', entity_id=q.id, entity_name=q.question_text[:50])
```

### API Response Format
```python
return jsonify([{'id': c.id, 'name': c.name, 'name_bn': c.name_bn} for c in items])
```

### Security
- Admin routes: `@login_required`, sensitive actions: `@admin_required` decorator
- Rate limiting: `@limiter.limit("3 per minute")` on login
- CSRF enabled globally; exempt API routes with `@csrf.exempt`

### User Roles
- `ROLE_ADMIN` - Full access, delete, manage users
- `ROLE_EDITOR` - Add/edit content only

### Document Generation
[app/utils/document_generator.py](../app/utils/document_generator.py):
- Two-column DOCX layout with `to_bengali_numeral()` for Bengali numbers
- Student copy (clean) vs Teacher copy (●-marked correct answers)
- Bengali font: `Nirmala UI` (DOCX), `Noto Sans Bengali` (web)

### AI Generator
[app/utils/ai_generator.py](../app/utils/ai_generator.py):
- Background thread with `_generator_thread` and `_stop_event` for cancellation
- Duplicate detection: MD5 hash + 80% text similarity check
- Prompt template: `DEFAULT_PROMPT_TEMPLATE` with `{class_name}`, `{subject_name}`, `{chapter_name}`, `{count}` placeholders

## External Dependencies
- **Database**: PostgreSQL (prod via `DATABASE_URL`) / SQLite (dev at `instance/prosno.db`)
- **OpenAI API**: Configured in admin panel for AI question generation
- **Deployment**: Render/Heroku (uses `/tmp` for ephemeral files in production)
