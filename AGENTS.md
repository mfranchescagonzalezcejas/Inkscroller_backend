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

## Performance
- Upstream calls need retry with exponential backoff
- Cache upstream results with SimpleCache (TTL-based)
- No blocking calls in async paths
