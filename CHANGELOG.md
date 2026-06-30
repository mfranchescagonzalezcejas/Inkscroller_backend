# Changelog

## v1.0.0-beta.1

First beta release.

### Features

- **Age-gated content**: manga access restricted by user age. Birth date required on profile, content filtered by `contentRating` (safe / suggestive / erotica / pornographic). Guest users see only safe content.
- **DELETE /users/me**: authenticated users can delete their own account.
- **Profile metadata contract**: PATCH /users/me supports `displayName`, `birthDate`, `avatarUrl`, `bio`. Explicit `null` allowed for nullable fields.
- **Readiness endpoint**: GET /ready returns 200 when DB is reachable, 503 otherwise. Configurable timeout via `READY_TIMEOUT` env var.

### Fixes

- **Hardened production CORS**: explicit allowed origins instead of wildcard in production.
- **Dockerignore credentials**: `.env`, `*.db`, and other sensitive files excluded from Docker build context.
- **PII sanitization**: Firebase UIDs masked in log messages.
- **Fail-closed age check**: chapters and manga default to restricted when age cannot be determined.
- **Hermetic integration tests**: tests no longer depend on external services or shared state.

### Docs

- API reference updated with new endpoints (`DELETE /users/me`, `PATCH /users/me`, age-gating behavior).
- Railway custom domains documentation.
- Docstrings added to new/modified functions and models.

### Internal

- SDD planning artifacts for age-gating and delete-user features.
- Ruff formatting and lint fixes across codebase.
