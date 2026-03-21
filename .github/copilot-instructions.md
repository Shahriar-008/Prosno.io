# Prosno.io - AI Coding Agent Instructions

## Project Overview
Bengali MCQ question paper generator for Bangladesh NCTB curriculum (Classes 1-10). Flask app with SQLAlchemy, Bootstrap 5, DOCX generation.

## Architecture

### Application Factory
[app/__init__.py](../app/__init__.py) uses `create_app()` with auto-seeding on first run:
- Auto-creates admin user, seeds NCTB classes (1-10), applies schema migrations
- Extensions (`db`, `login_manager`, `csrf`, `limiter`) initialized at module level
- Global `app = create_app()` at bottom enables `gunicorn app:app`

### Blueprint Structure
| Blueprint | Prefix | Purpose |
|-----------|--------|---------|
| `main_bp` | `/` | Public: landing, paper generation |
| `admin_bp` | `/admin` | Protected admin panel (all routes `@login_required`) |
| `api_bp` | `/api` | JSON endpoints for frontend (CSRF-exempt) |

### Data Model Hierarchy
```
Class → Subject → Chapter → Question
```
All content models have: `name`, `name_bn` (bilingual), `is_active` (soft-delete), `order` (sorting).

Additional models: `User`, `GeneratedPaper`, `AIGeneratorConfig`, `AIGeneratorLog`, `ActivityLog`

### Question Types
- `simple` - Standard MCQ with 4 options (`answer_options`, `correct_answer`)
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
- CSRF enabled globally; API routes use `@csrf.exempt` since they're read-only or JSON-based
- Session regeneration on login to prevent session fixation
- Security headers added via `add_security_headers()` in app factory

### User Roles
- `ROLE_ADMIN` - Full access, delete, manage users
- `ROLE_EDITOR` - Add/edit content only

### Document Generation
[app/utils/document_generator.py](../app/utils/document_generator.py):
- Two-column DOCX layout with `to_bengali_numeral()` for Bengali numbers
- Student copy (clean) vs Teacher copy (●-marked correct answers)
- Bengali font: `Nirmala UI` (DOCX), `Noto Sans Bengali` (web)
- Math expressions use OMML (Office Math Markup Language) for fractions/superscripts

### AI Generator
[app/utils/ai_generator.py](../app/utils/ai_generator.py):
- Supports **Gemini** (default: `gemini-2.0-flash`) and **OpenAI** providers
- Background thread with `_generator_thread` and `_stop_event` for cancellation
- Duplicate detection: MD5 hash + 80% text similarity check
- Prompt template: `DEFAULT_PROMPT_TEMPLATE` with `{class_name}`, `{subject_name}`, `{chapter_name}`, `{count}` placeholders

## Environment Variables
| Variable | Purpose | Default |
|----------|---------|---------|
| `SECRET_KEY` | Flask session encryption | Auto-generated (warn in prod) |
| `DATABASE_URL` | PostgreSQL connection | SQLite `instance/prosno.db` |
| `ADMIN_USERNAME/PASSWORD/EMAIL` | Initial admin credentials | Admin / 12345 / admin@prosno.io |
| `RENDER` or `DYNO` | Production detection | Uses `/tmp` for file storage |

<!-- GSD Configuration — managed by get-shit-done installer -->
# Instructions for GSD

- Use the get-shit-done skill when the user asks for GSD or uses a `gsd-*` command.
- Treat `/gsd-...` or `gsd-...` as command invocations and load the matching file from `.github/skills/gsd-*`.
- When a command says to spawn a subagent, prefer a matching custom agent from `.github/agents`.
- Do not apply GSD workflows unless the user explicitly asks for them.
- After completing any `gsd-*` command (or any deliverable it triggers: feature, bug fix, tests, docs, etc.), ALWAYS: (1) offer the user the next step by prompting via `ask_user`; repeat this feedback loop until the user explicitly indicates they are done.
<!-- /GSD Configuration -->
