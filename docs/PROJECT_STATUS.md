# InkScroller Backend — Project Status

> **Source of truth for public readers:** this repository (`README`, `docs/PROJECT_STATUS.md`, `docs/DEPLOYMENT.md`)
> **Repo role:** backend implementation and operational status for the FastAPI service
> **Last updated:** 2026-07-20 (v1.0.0 release readiness)

---

## 1. Purpose of this document

This file is the public status reference for backend implementation and operations.

- Keep this file aligned with released backend reality
- Keep links and references constrained to repository-visible artifacts
- Avoid internal-only tooling references not available to external readers

---

## 2. Current phase

| Field | Value |
|------|-------|
| Product phase | Phase 5 — Identity & Adaptive Reading |
| Backend phase state | **Sprint 3 active — compliance/release support + hardening** |
| Current sprint mirror | Sprint 3 — **active** |
| Repo status | Active |
| Current branch | `release/v1.0.0` (promoting to `main`) |
| Docker image | ✅ Created (`Dockerfile`, `.dockerignore`) |

---

### Railway Deployments (Multi-environment)

| Environment | Railway Environment | Firebase Project | API base URL | Health check |
|------------|---------------------|------------------|--------------|--------------|
| **dev** | `dev` | `inkscroller-aed59` | `https://api.dev.inkscroller.devdigi.dev` | `https://api.dev.inkscroller.devdigi.dev/ping` |
| **staging** | `staging` | `inkscroller-stg` | `https://api.stg.inkscroller.devdigi.dev` | `https://api.stg.inkscroller.devdigi.dev/ping` |
| **prod** | `production` | `inkscroller-8fa87` | `https://api.inkscroller.devdigi.dev` | `https://api.inkscroller.devdigi.dev/ping` |

Production and development custom-domain `/ping` checks return `200 {"ok": true}`. The staging custom domain is reserved/configured for the staging environment and should be verified after that environment is deployed/routed. Cloudflare hosts the Railway CNAME/TXT verification records for the API domains. The portfolio remains on `https://devdigi.dev` / `https://www.devdigi.dev` and is not routed to Railway.

---

## 3. Completed in this repo

### M1 — Backend auth foundation

- Firebase Admin SDK for ID token verification
- `GET /users/me` — creates user row if not exists
- `PATCH /users/me` — update profile (username, birth_date with immutability enforcement)
- `DELETE /users/me` — full account and data deletion with Firebase Auth cleanup
- `GET /users/me/preferences` — reading preferences
- `PUT /users/me/preferences` — update `defaultReaderMode`, `defaultLanguage`
- Auth/user tests exist

### M2 — Personal Library

- `GET /users/me/library` — list saved manga with age-based filtering, returns enriched `Manga` objects with `LibraryMetadata` (`library_status`, `chapters_read`, `added_at`, `updated_at`)
- `POST /users/me/library/{manga_id}` — add manga to library, caches complete metadata at insert time (title, cover, authors, genres, score, malId, chapters, etc.)
- `PATCH /users/me/library/{manga_id}` — update library status (`reading`/`completed`/`paused`)
- `PATCH /users/me/library/{manga_id}/progress` — update reading progress (`chapters_read`)
- `DELETE /users/me/library/{manga_id}` — remove manga from library
- Library tests exist with age-filtering scenarios, enriched metadata, and progress tracking

### M3 — Age-gated content access

- Age computation utility (`app/core/age.py`)
- Content rating thresholds: safe (0+), suggestive (16+), erotica (18+), pornographic (18+)
- Guest users restricted to safe-only content
- Service-layer filtering (`_filter_by_age`) on search, list, and detail
- Route-layer 403 enforcement on manga detail, chapters, chapter pages, and library
- Birth date immutability to prevent bypass

### Public API already operational

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ping` | GET | Health check |
| `/docs` | — | Swagger UI |
| `/openapi.json` | — | OpenAPI spec |
| `/manga` | GET | Paginated manga list with filters |
| `/manga/search` | GET | Search by query with pagination (max 100 results, enriched with ratings/demographics) |
| `/manga/{id}` | GET | Manga detail with MangaDex + Jikan enrichment (optional `?language=` param) |
| `/manga/tags` | GET | MangaDex filter tags |
| `/manga/capabilities` | GET | API capability contract (demographic filter version, cursor support) |
| `/chapters/latest` | GET | Latest chapters for the home feed |
| `/chapters/manga/{id}` | GET | Chapter list filtered by language (age-gated) |
| `/chapters/{id}/pages` | GET | Page URLs via MangaDex@Home (age-gated) |
| `/users/me` | GET | Get or create authenticated user profile |
| `/users/me` | PATCH | Update profile (username, birth_date) |
| `/users/me` | DELETE | Delete account and all associated data |
| `/users/me/preferences` | GET | Get reading preferences |
| `/users/me/preferences` | PUT | Update reading preferences |
| `/users/me/library` | GET | List library entries (age-filtered, enriched Manga objects) |
| `/users/me/library/{manga_id}` | POST | Add manga to library (caches metadata) |
| `/users/me/library/{manga_id}` | PATCH | Update library status (reading/completed/paused) |
| `/users/me/library/{manga_id}/progress` | PATCH | Update reading progress (`chapters_read`) |
| `/users/me/library/{manga_id}` | DELETE | Remove manga from library |

### Infrastructure

- Structured logging with configurable level
- CORS configurable via env vars
- Retry with exponential backoff on upstream calls
- In-memory cache with TTL (5 min default)
- Global exception handlers
- Dependency injection factories
- Smoke tests with DI overrides
- **Docker** — Multi-stage Dockerfile for Railway/container deployment
- **PostgreSQL** — production persistence path via `DATABASE_URL`

### Quality Gates & Code Review

- **pre-commit hooks** — ruff lint + ruff format on every commit, unit tests on push
- **AGENTS.md** — coding standards for AI-assisted code review
- **GGA (Gentleman Guardian Angel)** — AI code review with OpenCode, runs as pre-commit hook (local, no rate limits)
- **.coderabbit.yaml** — CodeRabbit configured in CLI-only mode to avoid Fair Usage rate limits
- **CodeRabbit CLI** — alternative AI review option, run manually with `coderabbit review --base develop`

### Repo hygiene

- `.env.example` documents Railway/Firebase/Postgres variables
- Deployment workflow: GitHub is source of truth, Railway deploys directly from branches/environments
- Frontend cloud environments should target the custom Railway API domains for dev/staging/prod

---

## 4. Remaining work in this repo

| Item | Priority | Status |
|------|----------|--------|
| Deploy strategy | High | ✅ Complete — Railway + Postgres + Firebase per environment |
| Profile metadata | Medium | ✅ Complete — username, birth_date with immutability |
| Account deletion | Medium | ✅ Complete — DELETE /users/me with Firebase cleanup |
| Age-gated content enforcement | High | ✅ Complete — full route/service/middleware stack, including safe-content demographic fix |
| Language preference for manga content | High | ✅ Complete — language-aware title/description resolution via `?language=` param |
| Manga type enrichment | Medium | ✅ Complete — `type` field populated from MangaDex originalLanguage mapping |
| Library enriched metadata | High | ✅ Complete — full Manga model cached at insert time, returned on library read |
| Reading progress tracking | Medium | ✅ Complete — `PATCH .../progress` with chapters_read, persisted in DB |
| Jikan enrichment by MAL ID | High | ✅ Complete — malId, chapters, score, rank via Jikan with MAL ID resolution |
| Security audit hardening | High | ✅ Complete — rate limiting, CSP, output contract, token revocation, debug lock |
| P0-B1..P0-B8 compliance closure | High | ✅ Complete — evidence tracked against Railway runbooks/logs |
| Library response documentation | Medium | ✅ Complete — README updated with LibraryMetadata model and progress endpoint |
| Documentation audit & stale cleanup | Low | ✅ Complete — CHANGELOG, PROJECT_STATUS, DEPLOYMENT, READMEs updated; .gga removed |

---

## 5. Cross-repo dependencies

### Provided to frontend

| Contract | Status | Notes |
|---------|--------|-------|
| Public manga catalogue/search/detail/chapter | ✅ Available | Validated against Railway environments |
| `/users/me` (GET) | ✅ Implemented | Validated with Firebase per environment |
| `/users/me` (PATCH — profile metadata) | ✅ Implemented | username + birth_date, birth_date immutable after set |
| `/users/me` (DELETE — account deletion) | ✅ Implemented | Full cleanup including Firebase Auth |
| `/users/me/preferences` | ✅ Implemented | Required by frontend M3 |
| `/users/me/library` (CRUD) | ✅ Implemented | Age-filtered library with content_rating |
| `/chapters/latest` (home feed) | ✅ Implemented | Latest chapters for home screen |
| Age-gated content access | ✅ Implemented | 403 on restricted content for underage/guest users |
| Firebase token verification | ✅ Implemented | Verified on Railway dev/staging/prod |

### Depends on frontend for full product value

| Topic | Dependency type | Notes |
|------|-----------------|-------|
| Profile UI consumption | soft | Backend is ready, frontend M3 is now complete |
| Preferences UI / local-first chain | soft | Frontend has local-first with offline sync |
| Adaptive reader behavior | soft | Backend exposes preference surface; frontend consumes it |

---

## 6. Deployment

### ✅ Chosen Target: Railway

**Why Railway:**
- simpler developer experience for multi-environment backend delivery
- easy environment-scoped variables and deploys
- Railway Postgres provides the production persistence path
- still compatible with Firebase Auth via Admin SDK

Railway serves each backend environment on port `8080`; clients should use the custom API domains rather than Railway-generated hostnames.

### Alternatives considered

| Platform | Pros | Cons |
|----------|------|------|
| **VPS / self-hosting** | Full control, potentially low cost | Higher ops burden, backups/security on us |

### Environment Variables Required

| Variable | Required | Notes |
|----------|----------|-------|
| `ENVIRONMENT` | No | Default: `development`; production-like values reject wildcard CORS with credentials |
| `FIREBASE_PROJECT_ID` | Yes | Per-environment Firebase project |
| `FIREBASE_SERVICE_ACCOUNT_JSON_BASE64` | Yes (Railway) | Service account per environment |
| `DATABASE_URL` | Yes (Railway) | Injected from Railway Postgres |
| `DB_PATH` | No | Local fallback only |
| `CORS_ORIGINS` | No | Comma-separated frontend origins; `*` is local-development only |
| `CACHE_TTL_SECONDS` | No | Default: `300` |
| `MANGADEX_BASE_URL` | No | Default: `https://api.mangadex.org` |
| `JIKAN_BASE_URL` | No | Default: `https://api.jikan.moe/v4` |

---

## 7. Known blockers / validation gaps

| Topic | Type | Impact |
|------|------|--------|
| Manga language still hardcoded to `en` | product/backend | Some manga return no chapters for users expecting other languages |
| Release/compliance docs still contain mixed deployment wording | documentation | Keep Railway-only narrative before final release sign-off |

---

## 8. Public references

### Repo docs

- `README.md`
- `docs/PROJECT_STATUS.md`
- `docs/DEPLOYMENT.md`
