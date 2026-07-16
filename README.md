# InkScroller Backend

![FastAPI](https://img.shields.io/badge/FastAPI-0.128-009688?style=flat-square&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?style=flat-square&logo=railway&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-279_✔️-brightgreen?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

**InkScroller** is a full-stack manga reading platform. This repository contains the **backend API** — a FastAPI service that proxies and enriches data from [MangaDex](https://mangadex.org) and [Jikan/MyAnimeList](https://jikan.moe), with Firebase authentication, age-gated content access, user preferences, and personal manga libraries.

> **TFM — Máster en Desarrollo de Aplicaciones Web y Móviles**
> *Entrega: 20 de julio de 2026*
>
> Ver [`inkscroller_frontend`](https://github.com/mfranchescagonzalezcejas/inkscroller_frontend) para el repositorio principal del proyecto con todos los entregables del TFM.

---

## 📋 Índice

- [TFM Deliverables](#tfm-deliverables)
- [Deployment](#deployment)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [API Reference](#api-reference)
- [Age Gating](#age-gating--content-rating-thresholds)
- [Running Locally](#running-locally)
- [Project Structure](#project-structure)
- [Quality Gates](#quality-gates)
- [TFM Deliverables](#tfm-deliverables)
- [Atribución y Disclaimer](#atribución-y-disclaimer)
- [License](#license)

---

## 🚀 Deployment

**Production API:** [`https://api.inkscroller.devdigi.dev`](https://api.inkscroller.devdigi.dev)

| Environment | URL | Health Check |
|------------|-----|-------------|
| **Production** | `https://api.inkscroller.devdigi.dev` | [`/ping`](https://api.inkscroller.devdigi.dev/ping) → `{"ok": true}` |
| Development | `https://api.dev.inkscroller.devdigi.dev` | [`/ping`](https://api.dev.inkscroller.devdigi.dev/ping) |
| Staging | `https://api.stg.inkscroller.devdigi.dev` | [`/ping`](https://api.stg.inkscroller.devdigi.dev/ping) |

**API Documentation (ReDoc):** [`https://api.inkscroller.devdigi.dev/redoc`](https://api.inkscroller.devdigi.dev/redoc)

**Swagger UI:** [`https://api.inkscroller.devdigi.dev/docs`](https://api.inkscroller.devdigi.dev/docs)

> Full deployment guide (Railway environments, Firebase secrets, PostgreSQL): [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)

---

## ✨ Features

| Area | Description |
|------|-------------|
| **Manga catalogue** | Browse, filter, and paginate the MangaDex catalogue |
| **Search** | Title-based manga search with pagination (`limit`, `offset`) |
| **Detail enrichment** | MangaDex data augmented with Jikan/MAL metadata (score, rank, authors, genres) |
| **Chapter listing** | Per-manga chapter list with language filtering |
| **Page URLs** | MangaDex@Home image URLs for any chapter |
| **Auth** | Firebase ID token verification on protected endpoints |
| **User profile** | Auto-created user row on first authenticated request (`/users/me`) |
| **Preferences** | Reading preferences per user (`defaultReaderMode`, `defaultLanguage`, `demographic_filter`, `content_rating_filter`) |
| **Demographic filter** | Multi-value demographic filtering with `unspecified` union support |
| **Caching** | In-memory 5-minute TTL cache on all service calls |
| **Health check** | Liveness probe at `/ping` and readiness at `/ready` |
| **Profile metadata** | `username` and `birth_date` on authenticated user profile |
| **Account deletion** | Full account and data deletion (`DELETE /users/me`) |
| **Library** | Personal manga library with CRUD, content-rating storage, and age-based filtering |
| **Age-gated content** | Content access enforcement by age (safe/suggestive/erotica/pornographic) + demographic gating |
| **Home feed** | Latest chapters endpoint for the home screen (`/chapters/latest`) |
| **Security headers** | X-Content-Type-Options, X-Frame-Options, HSTS, CSP reporting |
| **Quality gates** | Pre-commit hooks (ruff lint, format) + pre-push (mypy, tests) + GGA AI review |
| **Cursor pagination** | Tamper-proof cursor-based pagination for demographic union scans |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.128 |
| HTTP client | httpx (async) |
| Data validation | Pydantic v2 |
| ASGI server | Uvicorn |
| Auth | Firebase Admin SDK |
| Persistence | PostgreSQL on Railway (`DATABASE_URL`) / SQLite local fallback |
| Runtime | Python 3.12 |
| Testing | unittest (279 tests) |
| Linting | Ruff 0.15.9 |
| Type checking | mypy |
| Deploy | Railway (production / dev / staging) |
| Container | Docker multi-stage build |

---

## 📡 API Reference

### Public Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/ping` | Liveness probe → `{"ok": true}` |
| `GET` | `/ready` | Readiness probe — DB connectivity → `{"ready": true}` or `503` |
| `GET` | `/manga` | Paginated manga list (`limit`, `offset`, `title`, `demographic`, `status`, `order`, `genre`, `content_rating`) |
| `GET` | `/manga/search?q=` | Paginated title search |
| `GET` | `/manga/capabilities` | API capability contract (demographic filter version, pagination type) |
| `GET` | `/manga/tags` | MangaDex filter tags grouped by type (genre, theme, format, content) |
| `GET` | `/manga/genres` | Flat list of available genre tags |
| `GET` | `/manga/{id}` | Manga detail with Jikan enrichment |
| `GET` | `/chapters/latest` | Latest chapters for home feed (age-filtered) |
| `GET` | `/chapters/manga/{id}` | Chapter list for a manga (filtered by `lang`, default `en`) |
| `GET` | `/chapters/{id}/pages` | Page image URLs via MangaDex@Home |
| `POST` | `/csp-report` | CSP violation reports (logging only, no PII) |

### Authenticated Endpoints (requires `Authorization: Bearer <firebase-id-token>`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/users/me` | Get or create user profile |
| `PATCH` | `/users/me` | Update profile — `username` and/or `birth_date` |
| `DELETE` | `/users/me` | Delete account and all associated data |
| `GET` | `/users/me/preferences` | Get reading preferences |
| `PUT` | `/users/me/preferences` | Update preferences (`defaultReaderMode`, `defaultLanguage`, `demographic_filter`, `content_rating_filter`) |
| `GET` | `/users/me/library` | List library entries (age-filtered) |
| `POST` | `/users/me/library/{manga_id}` | Add manga to library |
| `PATCH` | `/users/me/library/{manga_id}` | Update library entry status |
| `DELETE` | `/users/me/library/{manga_id}` | Remove manga from library |

### Demographic Filter Contract

`GET /manga/capabilities` advertises the supported demographic-filter contract:

```json
{
  "demographic_filter": {
    "contract_version": 1,
    "null_union": true,
    "pagination": "cursor-v1"
  }
}
```

- `unspecified` is a local API token for the union of titles with a null or missing source demographic; it is never forwarded to MangaDex.
- Requires an authenticated user aged 18 or older.
- Queries including it use cursor-based pagination.
- A missing, expired, tampered, or mismatched cursor returns HTTP 409.

---

## 🔒 Age Gating — Content Rating Thresholds

Content from MangaDex is classified into four age tiers. Access is enforced at the route and service layers:

| Tier | Content Rating | Access |
|------|---------------|--------|
| 0+ | `safe` | All users (including unauthenticated guests) |
| 16+ | `suggestive` | Authenticated users aged 16+ |
| 18+ | `erotica` | Authenticated users aged 18+ |
| 18+ | `pornographic` | Authenticated users aged 18+ |

- **Guest users** (unauthenticated): only `safe` content is accessible.
- **Age computation**: derived from `birth_date` on the user profile. Guests have no age → safe-only.
- **Demographic gating**: content without a publication demographic (doujinshi/self-published) requires 18+.
- **403 responses**: restricted content returns `403` with a message like `"This content is age-restricted (requires 16+)"`.
- **Library**: `content_rating` is stored when adding to library; GET library filters entries by the caller's age automatically.
- **birth_date immutability**: once set, `birth_date` cannot be changed (prevents age-gating bypass).

---

## 💻 Running Locally

```bash
# 1. Create and activate virtualenv
python -m venv venv
source venv/bin/activate        # Linux / macOS
# venv\Scripts\activate         # Windows

# 2. Install dependencies
python -m pip install -r requirements.txt -r requirements-dev.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — set FIREBASE_PROJECT_ID and either
# GOOGLE_APPLICATION_CREDENTIALS (local) or FIREBASE_SERVICE_ACCOUNT_JSON_BASE64 (Railway).

# 4. Start server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

| URL | Description |
|-----|-------------|
| `http://localhost:8000/ping` | Liveness probe |
| `http://localhost:8000/ready` | Readiness probe (DB check) |
| `http://localhost:8000/docs` | Swagger UI |
| `http://localhost:8000/redoc` | ReDoc |

> **Windows note:** Use `python -m pip` and `python -m uvicorn` — never bare `pip`/`uvicorn`.

---

## 📁 Project Structure

```
Inkscroller_backend/
├── main.py                        # App entry — mounts all routers
├── Dockerfile                     # Multi-stage build for Railway / container deploys
├── pyproject.toml                 # Project config (versions, mypy, pytest)
├── requirements.txt               # Production dependencies
├── requirements-dev.txt           # Dev dependencies (testing, linting)
│
├── app/
│   ├── api/                       # FastAPI route handlers
│   │   ├── health.py              # GET /ping, GET /ready
│   │   ├── manga.py               # GET /manga, /manga/search, /manga/{id}, /manga/tags
│   │   ├── chapters.py            # GET /chapters/latest, /chapters/manga/{id}, /chapters/{id}/pages
│   │   ├── users.py               # GET/PATCH/DELETE /users/me, prefs, library CRUD
│   │   └── security.py            # POST /csp-report
│   │
│   ├── core/
│   │   ├── age.py                 # Age computation and content restriction rules
│   │   ├── cache.py               # SimpleCache — TTL-based in-memory cache (max 1000 entries)
│   │   ├── config.py              # Settings via env vars
│   │   ├── firebase_auth.py       # Firebase ID token verification middleware
│   │   ├── dependencies.py        # FastAPI DI factories
│   │   ├── db_adapter.py          # Database adapter (SQLite / PostgreSQL)
│   │   ├── database.py            # Database bootstrap and migration helpers
│   │   ├── exceptions.py          # Global exception handlers
│   │   ├── logging.py             # Structured logging configuration
│   │   ├── resilience.py          # Retry decorator with exponential backoff
│   │   └── manga_tags.py          # MangaDex genre tag UUID mappings
│   │
│   ├── models/                    # Pydantic response models
│   │   ├── manga.py
│   │   ├── chapter.py
│   │   └── user.py                # UserProfile, UserPreferences
│   │
│   ├── services/                  # Business logic
│   │   ├── manga_service.py       # Manga catalogue, search, demographic union, cursor pagination
│   │   ├── manga_mapper.py        # MangaDex → standardised dict mapping
│   │   ├── chapter_service.py     # Chapter listing, latest feed with age gating
│   │   ├── chapter_pages_service.py
│   │   ├── jikan_mapper.py        # Jikan/MAL → standardised dict mapping
│   │   └── user_service.py        # User CRUD, preferences, library
│   │
│   └── sources/                   # External API clients (async httpx)
│       ├── mangadex_client.py
│       └── jikan_client.py
│
└── tests/
    ├── api/                       # Route and authenticated endpoint tests
    ├── core/                      # Cache tests
    ├── services/                  # Service/mapper unit tests
    └── compliance/                # API/legal compliance audit tests
```

---

## ✅ Quality Gates

The project uses [pre-commit](https://pre-commit.com) to automatically enforce code quality.

### Gates

| Gate | Trigger | What it checks |
|------|---------|----------------|
| **ruff lint** | `git commit` | Static analysis, unused imports, common bugs |
| **ruff format** | `git commit` | Code style matches project config |
| **mypy** | `git push` | Type correctness for public API |
| **unit tests** | `git push` | All **279 tests** pass |
| **GGA (optional)** | `git commit` | AI-powered code review via OpenCode |

### Developer setup (one-time)

```bash
python -m pip install pre-commit
pre-commit install
pre-commit install --hook-type pre-push
```

### Skip on demand

```bash
SKIP=ruff-lint git commit     # skip lint only
SKIP=gga git push             # skip AI review
git commit --no-verify        # skip all hooks
```

---

## 📦 TFM Deliverables

| Item | URL |
|------|-----|
| 🗂️ **Frontend repo** | [mfranchescagonzalezcejas/inkscroller_frontend](https://github.com/mfranchescagonzalezcejas/inkscroller_frontend) |
| ⚙️ **Backend repo** | [mfranchescagonzalezcejas/Inkscroller_backend](https://github.com/mfranchescagonzalezcejas/Inkscroller_backend) |
| 🔌 **Deployed API** | [`https://api.inkscroller.devdigi.dev`](https://api.inkscroller.devdigi.dev) |
| 📖 **API Docs (ReDoc)** | [`https://api.inkscroller.devdigi.dev/redoc`](https://api.inkscroller.devdigi.dev/redoc) |
| 📽️ **Slides** | Work in progress — not published yet |
| 🎬 **Demo video** | Work in progress — not published yet |
| 👤 **Test user** | Not required — users can create an account from the app with email/password registration |

> El proyecto completo consiste en un **frontend Flutter** + **backend FastAPI**.
> Para la entrega del TFM, usar el repositorio frontend como referencia principal:
> [`mfranchescagonzalezcejas/inkscroller_frontend`](https://github.com/mfranchescagonzalezcejas/inkscroller_frontend)

---

## 📝 Atribución y Disclaimer

InkScroller Backend agrega datos de las siguientes fuentes externas:

- **MangaDex** — fuente primaria de catálogo, capítulos e imágenes de manga. InkScroller no está afiliado a MangaDex. Todo el contenido pertenece a sus respectivos autores y grupos de scanlation. Se respetan los [Términos de Servicio de MangaDex](https://mangadex.org/about/terms-of-service).
- **Jikan / MyAnimeList** — capa de enriquecimiento de metadatos (score, rank, géneros). Jikan es un servicio no oficial de terceros. InkScroller no está afiliado a MyAnimeList ni a Jikan. Se respetan los [Términos de Uso de MyAnimeList](https://myanimelist.net/about/terms_of_use).

Este proyecto actúa como **proxy de lectura**. No almacena ni redistribuye imágenes de manga. Los derechos sobre el contenido pertenecen a sus titulares originales.

Para consultas legales o solicitudes de takedown, ver [`docs/legal/api-compliance.md`](docs/legal/api-compliance.md).

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
