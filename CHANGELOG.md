# Changelog

## v1.0.1 — 2026-07-21

Hotfix release for post-v1.0.0 production stability and MangaDex upstream latency.

### Fixes

- **MangaDex upstream errors**: map transport failures to safe `502` responses and enforce upstream cooldown handling.
- **MangaDex statistics latency**: replace per-manga statistics fan-out with the bulk statistics endpoint to cut `/manga` cold-start latency from ~6s to ~1.2–1.5s in dev validation.

### Internal

- **Retry configuration**: `retryable_status_codes` is now authoritative and documented for MangaDex resilience behavior.
- **Regression coverage**: added focused MangaDex throttle/statistics tests and compliance coverage for the bulk statistics request.

---

## v1.0.0 — 2026-07-20

First stable release — TFM delivery.

### Features

- **Multi-demographic filter**: `GET /manga?demographic=shounen&demographic=shoujo` — multiple values via repetition. Supports `unspecified` token for null-demographic union.
- **Content rating filter**: `GET /manga?content_rating=safe` — override age-based defaults. Persisted in user preferences.
- **Demographic preferences**: `demographic_filter` field in user preferences, with validation against allowed values.
- **Security headers**: X-Content-Type-Options, X-Frame-Options, HSTS, X-XSS-Protection, Referrer-Policy on all responses.
- **CSP reporting**: `POST /csp-report` endpoint for browser CSP violation reports with PII-safe logging.
- **Cursor-based pagination**: Tamper-proof cursor tokens for demographic union scans. HMAC-signed snapshots with configurable `CURSOR_SECRET`.
- **Age-gated home feed**: `/chapters/latest` now filters by user age and demographic restrictions.
- **Auth-only dependency**: Firebase auth extracted to a reusable dependency, improving testability.
- **Tags service layer**: `/manga/tags` endpoint moved behind service layer, reuses shared httpx client.
- **CI quality gates**: Pre-commit hooks (ruff lint, format) + pre-push (mypy, 318 tests, coverage).
- **ReDoc documentation**: Full OpenAPI docs with server URLs, contact, license, and grouped tags.
- **Rate limiting**: Sliding-window in-memory rate limiter (30 req/min public, 60 auth, 10 CSP).
- **Token revocation**: `check_revoked=True` in Firebase `verify_id_token()` — revoked sessions rejected.
- **CSP origin validation**: `/csp-report` only accepts reports from configured CORS origins.
- **Output sanitization**: Upstream text returned raw — frontend sanitizes per rendering context.
- **LRU Cache**: Migrated from FIFO to proper LRU eviction with `OrderedDict`.
- **Permissions-Policy header**: All browser features restricted by default.
- **Debug lock**: `debug=False` forced in production-like environments.
- **User enumeration prevention**: Generic error messages for username/birth-date conflicts.
- **Rate-limit CORS**: 429 responses include `Access-Control-Allow-Origin` so browsers surface the error to frontend code.
- **Trusted proxy support**: `TRUSTED_PROXY` env var to use `X-Forwarded-For` behind Railway/Cloudflare.
- **Path-churn prevention**: Rate-limiter keys by route category, not raw path (max 3 buckets per client).
- **Body middleware O(n)**: Replaced `list.pop(0)` (quadratic) with index counter (linear).
- **CSP log sanitizer**: Strips all control characters below `0x20` except tab.

### Fixes

- **Search pagination**: MangaDex search results now properly paginate.
- **Pre-commit hooks**: Ruff lint, format, and unit tests run automatically on commit/push.
- **Sort regressions**: Fixed TypeError when `latestUploadedChapter` is None. Restored post-stats sort for popular/rating ordering.
- **Demographic age gate**: Normalize MangaDex `"none"` → `None` so `?demographic=unspecified` enforces 18+ gate correctly.
- **Cache hit age gate**: `get_by_id` cache path now checks `can_access_demographic` — no more demographic bypass on cache hits.
- **PII audit**: All Firebase UIDs masked via `_mask_uid`. No tokens or PII logged.
- **Security headers middleware**: Configurable CORS with hardened defaults.
- **HTTP client reuse**: `/manga/tags` now uses shared httpx client instead of creating a new connection per request.
- **Union scan stats**: `_fetch_statistics` deferred to page-level (~50x fewer requests). Full stat + sort only when ordering by popular/rating.
- **Library metadata**: Uses authoritative MangaDex data instead of client-provided fields.
- **Chapter pagination**: Chapter listing now paginates beyond 100 results.

### Judgment Day fixes

Dual adversarial review results:
- `total` pagination metadata now reflects age-filtered count
- Jikan enrichment no longer overwrites `demographic` or `contentRating`
- `SimpleCache` bounded to 1000 entries (later upgraded to LRU eviction in security audit #129)
- `/chapters/latest` age-gating properly normalizes demographic values

### Docs

- Complete README rewrite with TFM deliverables, API reference, test credentials, deployment info.
- Enhanced ReDoc with description, tags, servers, contact, and license information.
- Docstrings on all key public service functions (search, list_manga, get_by_id, mapper).

---

## v1.0.0-beta.1 — 2026-06-29

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
