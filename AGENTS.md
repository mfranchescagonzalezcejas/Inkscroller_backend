# Coding Standards — Inkscroller Backend

## Language & Style
- Python 3.12+ with type hints on all functions
- Follow Ruff (v0.15.9) linting and formatting rules
- Use Pydantic v2 for all request/response models
- Async/await for all I/O operations
- Conventional commits: `type(scope): description`

## Architecture
- Clean Architecture: api/ → services/ → sources/
- FastAPI routes in app/api/, no business logic there
- Services in app/services/, no HTTP details
- External API clients in app/sources/
- Database access through DatabaseAdapter abstraction

## Error Handling
- Use exceptions.py handlers, never raw try/except in routes
- Auth errors → AuthError (401)
- Validation errors → PreferencesValidationError (422)
- Conflicts → ProfileConflictError (409)
- Upstream failures → UpstreamServiceError (502)

## Security
- All secrets via environment variables, never hardcoded
- Bearer token auth via Firebase Admin SDK
- PII must be masked in logs (_mask_uid)
- No SQL injection risk: use parameterized queries always
- Age-gating enforced server-side, not just frontend

## Testing
- unittest with hermetic test app (create_hermetic_test_app)
- No real Firebase credentials in tests
- Use dependency_overrides for mocks
- Tests in tests/ mirroring app/ structure

## Local Quality Commands
All quality gates run in CI — run these locally before pushing.

```bash
# Activate the venv first
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Lint + format check (app/, main.py, tests/)
ruff check app/ main.py tests/
ruff format --check app/ main.py tests/

# Type check (app/ and main.py only — see [tool.mypy] in pyproject.toml)
mypy app/ main.py

# Tests with coverage threshold (75% — see [tool.coverage.report])
pytest --cov=app --cov-report=term-missing tests/
```

Quick run during development: `pytest tests/ -x` (no coverage, fail fast).

## Pre-commit / Pre-push Hooks
The `.pre-commit-config.yaml` wires three groups of hooks into the git
lifecycle:

- **pre-commit** (every commit): `ruff check` + `ruff format`. Fast, no AI.
- **pre-push** (every push): `mypy`, `pytest --cov-fail-under=75`, and
  `gga run --ci` (Gentleman Guardian Angel AI review). Heavier, runs
  once per push instead of every commit.
- **Skip on demand** (any hook): `SKIP=<hook-id> git <cmd>`. Examples:
  `SKIP=gga git push` to bypass the AI review, `SKIP=mypy,tests git push`
  to skip both.
- **Skip GGA globally for one push**: `SKIP=gga git push`.
- **Reinstall hooks** after pulling config changes:
  `source venv/bin/activate && pre-commit install -f -t pre-commit -t pre-push`.

## Performance
- Upstream calls need retry with exponential backoff
- Cache upstream results with SimpleCache (TTL-based)
- No blocking calls in async paths
