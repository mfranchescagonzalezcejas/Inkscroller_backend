# InkScroller Backend — Project Status

> **Source of truth for public readers:** this repository (`README`, `docs/PROJECT_STATUS.md`, `docs/DEPLOYMENT.md`)
> **Repo role:** backend implementation and operational status for the FastAPI service
> **Last updated:** 2026-06-29 (age-gated content, library CRUD, profile metadata, account deletion)

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
| Current branch | `develop` |
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

- `GET /users/me/library` — list saved manga with age-based filtering
- `POST /users/me/library/{manga_id}` — add manga to library with content_rating storage
- `PATCH /users/me/library/{manga_id}` — update library status (reading/completed/plan_to_read/dropped/on_hold)
- `DELETE /users/me/library/{manga_id}` — remove manga from library
- Library tests exist with age-filtering scenarios

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
| `/manga/search` | GET | Search by query (max 5 results) |
| `/manga/{id}` | GET | Manga detail with MangaDex + Jikan enrichment |
| `/manga/tags` | GET | MangaDex filter tags |
| `/chapters/latest` | GET | Latest chapters for the home feed |
| `/chapters/manga/{id}` | GET | Chapter list filtered by language (age-gated) |
| `/chapters/{id}/pages` | GET | Page URLs via MangaDex@Home (age-gated) |
| `/users/me` | GET | Get or create authenticated user profile |
| `/users/me` | PATCH | Update profile (username, birth_date) |
| `/users/me` | DELETE | Delete account and all associated data |
| `/users/me/preferences` | GET | Get reading preferences |
| `/users/me/preferences` | PUT | Update reading preferences |
| `/users/me/library` | GET | List library entries (age-filtered) |
| `/users/me/library/{manga_id}` | POST | Add manga to library |
| `/users/me/library/{manga_id}` | PATCH | Update library status |
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

### Repo hygiene

- `.env.example` documents Railway/Firebase/Postgres variables
- Deployment workflow simplified: GitLab is source workflow, GitHub mirror feeds Railway deploys by branch/environment
- Frontend cloud environments should target the custom Railway API domains for dev/staging/prod

---

## 4. Remaining work in this repo

| Item | Priority | Notes |
|------|----------|-------|
| Deploy strategy | High | ✅ Complete — Railway + Postgres + Firebase per environment |
| Profile metadata | Medium | ✅ Complete — username, birth_date with immutability |
| Account deletion | Medium | ✅ Complete — DELETE /users/me with Firebase cleanup |
| Age-gated content enforcement | High | ✅ Complete — full route/service/middleware stack |
| Library CRUD | Medium | ✅ Complete — with content_rating storage and age filtering |
| Sprint 3 compliance pack | High | Active — backend support for release/legal evidence tracking |
| P0-B1..P0-B8 compliance closure | High | Active — evidence tracked against Railway runbooks/logs |
| MangaDex language configurable by user preference | Medium | Currently hardcoded to `en` |
| End-to-end validation with Flutter | Low | Dev/staging/prod Railway URLs validated; continue broader functional smoke coverage |

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
