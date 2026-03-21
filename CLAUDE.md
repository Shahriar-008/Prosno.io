# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup
```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

### Run locally
```bash
python run.py
```

### Database and seed commands
```bash
flask init-db
flask create-admin
flask seed-demo
```

### Test commands
```bash
pytest
pytest tests/test_api.py::test_get_classes_returns_only_active
pytest -k api
```

### Lint/format
No dedicated lint/format configuration is currently present in this repository (no project-level black/ruff/flake8/isort config files).

## High-Level Architecture

### App initialization and startup flow
- Entry point: `run.py` creates the Flask app via `create_app()` and defines Flask CLI commands.
- Core factory: `app/__init__.py:create_app()` initializes extensions (`db`, `login_manager`, `csrf`, `limiter`), applies startup migrations, seeds base data/admin when needed, registers blueprints, and sets runtime integrations (cache, scheduler, optional Supabase auth).
- Global app export in `app/__init__.py` supports WSGI startup patterns (e.g., gunicorn-style import).

### Route architecture (blueprints)
Blueprints are split by domain in `app/routes/`:
- `main.py`: public pages, paper generation/builder flows, downloads, OMR flows
- `admin.py`: admin dashboard and content management
- `api.py`: JSON endpoints for dependent dropdowns and metadata fetches
- `auth.py`: authentication/account routes
- `quiz.py`: quiz/session behavior
- `bank.py`: question bank contribution/browse flows
- `moderation.py`: moderation/review workflows

### Data model shape
Core curriculum hierarchy in `app/models.py`:
- `Class -> Subject -> Chapter -> Question`

Other notable model groups:
- Auth/admin: `User`
- Generation/output: `GeneratedPaper`, `QuestionSet`, `OmrTemplate`, `GenerationLog`
- Question ecosystems: `ShortQuestion`, `CQQuestion`, `BankQuestion`
- Teacher/platform: `TeacherProfile`, badges/notifications/interactions/library models
- AI generation config/logging: `AIGeneratorConfig`, `AIGeneratorLog`

### Content generation stack
- DOCX generation: `app/utils/document_generator.py`
  - Handles Bengali numerals/text formatting, paper layout, teacher/student variants.
- PDF generation: `app/utils/pdf_generator.py`
  - Converts/serves PDF versions of generated artifacts.
- OMR generation: `app/utils/omr_generator.py`
  - Generates OMR templates/build outputs used by main routes.
- AI-assisted generation: `app/utils/ai_generator.py`
  - Provider-based generation pipeline (Gemini/OpenAI style integration), duplicate checks, logging/state handling.

### Security and access patterns
- Flask-Login based auth with role checks (`ROLE_ADMIN`, `ROLE_EDITOR`) and admin-only guards.
- CSRF protection is globally enabled; select JSON endpoints are explicitly exempted where needed.
- Rate limiting via Flask-Limiter on sensitive/API-heavy endpoints.
- Security headers and production cookie/security settings are configured in app setup.

### Runtime/deployment behavior
- Environment-driven config in `config.py`.
- Production-like env detection can remap output/upload paths (e.g., `/tmp` on hosted environments).
- Scheduler startup is guarded to avoid duplicate job runners under the Flask reloader.

## Repository-Specific Notes

- The README previously described only `main/admin/api`; current architecture includes additional blueprint modules (`auth`, `quiz`, `bank`, `moderation`).
- Startup includes in-app schema migration helpers in `app/__init__.py`; when adding model fields, check existing migration pattern there.

## Copilot Instructions Incorporated

From `.github/copilot-instructions.md`:
- Keep using the application-factory pattern and existing blueprint boundaries.
- Preserve security posture (admin guards, CSRF strategy, rate limits, session protections, security headers).
- For AI generation changes, follow existing provider abstraction and logging/config patterns.
- Do not apply GSD workflows unless explicitly requested by the user.
