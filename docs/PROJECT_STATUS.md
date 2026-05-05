# InkScroller Backend — Project Status

> **Source of truth for public readers:** this repository (`README`, `docs/PROJECT_STATUS.md`, `docs/DEPLOYMENT.md`)
> **Repo role:** backend implementation and operational status for the FastAPI service
> **Last updated:** 2026-04-21 (Railway migration validated in dev / staging / prod)

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

| Environment | Railway Environment | Firebase Project | Backend URL |
|------------|---------------------|------------------|-------------|
| **dev** | `dev` | `inkscroller-aed59` | `https://inkscrollerbackend-dev.up.railway.app` |
| **staging** | `staging` | `inkscroller-stg` | `https://inkscrollerbackend-stg.up.railway.app` |
| **prod** | `production` | `inkscroller-8fa87` | `https://inkscrollerbackend-pro.up.railway.app` |

---

## 3. Completed in this repo

### M1 — Backend auth foundation

- Firebase Admin SDK for ID token verification
- `GET /users/me` — creates user row if not exists
- `GET /users/me/preferences` — reading preferences
- `PUT /users/me/preferences` — update `defaultReaderMode`, `defaultLanguage`
- Auth/user tests exist

### Public API already operational

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ping` | GET | Health check |
| `/docs` | — | Swagger UI |
| `/openapi.json` | — | OpenAPI spec |
| `/manga` | GET | Paginated manga list with filters |
| `/manga/search` | GET | Search by query (max 5 results) |
| `/manga/{id}` | GET | Manga detail with MangaDex + Jikan enrichment |
| `/chapters/manga/{id}` | GET | Chapter list filtered by language |
| `/chapters/{id}/pages` | GET | Page URLs via MangaDex@Home |

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
- Frontend cloud environments now target Railway dev/staging/prod URLs

---

## 4. Remaining work in this repo

| Item | Priority | Notes |
|------|----------|-------|
| Deploy strategy | High | ✅ Complete — Railway + Postgres + Firebase per environment |
| Sprint 3 compliance pack | High | Active — backend support for release/legal evidence tracking |
| P0-B1..P0-B8 compliance closure | High | Active — evidence tracked against Railway runbooks/logs |
| MangaDex language configurable by user preference | Medium | Currently hardcoded to `en` |
| End-to-end validation with Flutter | Low | Dev/staging/prod Railway URLs validated; continue broader functional smoke coverage |

### Sprint 3 — Compliance evidence focus

- Sprint 3 is currently active for backend-side compliance/release readiness support.
- Prioridad operativa: `BTASK-010` + cierre de ítems `P0-B1..P0-B8` con evidencia verificable.
- Regla documental: no marcar ítems P0 como cerrados sin evidencia explícita en checklist/status espejo.

---

## 5. Cross-repo dependencies

### Provided to frontend

| Contract | Status | Notes |
|---------|--------|-------|
| Public manga catalogue/search/detail/chapter | ✅ Available | Validated against Railway environments |
| `/users/me` | ✅ Implemented | Validated with Firebase per environment |
| `/users/me/preferences` | ✅ Implemented | Required by frontend M3 |
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

### Alternatives considered

| Platform | Pros | Cons |
|----------|------|------|
| **VPS / self-hosting** | Full control, potentially low cost | Higher ops burden, backups/security on us |

### Environment Variables Required

| Variable | Required | Notes |
|----------|----------|-------|
| `FIREBASE_PROJECT_ID` | Yes | Per-environment Firebase project |
| `FIREBASE_SERVICE_ACCOUNT_JSON_BASE64` | Yes (Railway) | Service account per environment |
| `DATABASE_URL` | Yes (Railway) | Injected from Railway Postgres |
| `DB_PATH` | No | Local fallback only |
| `CORS_ORIGINS` | No | Comma-separated, default: `*` |
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
