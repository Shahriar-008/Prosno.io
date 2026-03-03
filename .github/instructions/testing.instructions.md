---
applyTo: '**/*.py'
description: 'Guidelines for writing tests and test automation using pytest.'
---

# Testing Instructions

- Use `pytest` for unit and integration tests.
- Place unit tests next to modules in `tests/` directory using `test_*.py` filenames.
- Aim for clear, small tests: one logical assertion per test when reasonable.
- Use `pytest` fixtures for shared setup; prefer function-scoped fixtures unless expensive.
- Mock external dependencies using `unittest.mock` or `pytest-mock` to keep unit tests deterministic.
- For integration tests that require services (DB, S3, external APIs), use environment-based toggles and separate `integration` markers.
- Run tests locally with coverage:

```bash
python -m pip install -r requirements.txt
pip install pytest pytest-cov
pytest --cov=app tests/
```

- Add CI job to run `pytest --cov` and fail on coverage below project threshold.
- When generating tests programmatically, ensure they are readable and include rationale comments for non-obvious cases.
