# InkScroller Backend

![FastAPI](https://img.shields.io/badge/FastAPI-0.128-009688?style=flat-square&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?style=flat-square&logo=railway&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

---

## Features

| Area | Description |
|------|-------------|
| **Manga catalogue** | Browse, filter, and paginate the MangaDex catalogue |
| **Search** | Title-based manga search (up to 5 results) |
| **Detail enrichment** | MangaDex data augmented with Jikan/MAL metadata (score, rank, authors, genres) |
| **Chapter listing** | Per-manga chapter list with language filtering |
| **Page URLs** | MangaDex@Home image URLs for any chapter |
| **Auth** | Firebase ID token verification on protected endpoints |
| **User profile** | Auto-created user row on first authenticated request (`/users/me`) |
| **Preferences** | Reading preferences per user (`defaultReaderMode`, `defaultLanguage`) |
| **Caching** | In-memory 5-minute TTL cache on all service calls |
| **Health check** | Liveness probe at `/ping` |
| **Profile metadata** | `username` and `birth_date` on authenticated user profile |
| **Account deletion** | Full account and data deletion (`DELETE /users/me`) |
| **Library** | Personal manga library with CRUD, content-rating storage, and age-based filtering |
| **Age-gated content** | Content access enforcement by age (safe/suggestive/erotica/pornographic) |
| **Home feed** | Latest chapters endpoint for the home screen (`/chapters/latest`) |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.128 |
| HTTP client | httpx (async) |
| Data validation | Pydantic v2 |
| ASGI server | Uvicorn |
| Auth | Firebase Admin SDK |
| Persistence | PostgreSQL on Railway (`DATABASE_URL`) / SQLite local fallback |
| Runtime | Python 3.12 |
| Deploy | Railway (dev / staging / production) |

---

## API Reference

### Public

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/ping` | Health check → `{"ok": true}` |
| `GET` | `/manga` | Paginated manga list (`limit`, `offset`, `title`, `demographic`, `status`, `order`) |
| `GET` | `/manga/search?q=` | Title search — max 5 results |
| `GET` | `/manga/{id}` | Manga detail with Jikan enrichment |
| `GET` | `/manga/tags` | MangaDex filter tags |
| `GET` | `/chapters/latest` | Latest chapters for the home feed |
| `GET` | `/chapters/manga/{id}` | Chapter list (filtered by `lang`, default `en`) |
| `GET` | `/chapters/{id}/pages` | Page image URLs via MangaDex@Home |

### Authenticated (requires `Authorization: Bearer <firebase-id-token>`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/users/me` | Get or create user profile |
| `PATCH` | `/users/me` | Update profile — `username` and/or `birth_date` (birth_date is immutable after first set) |
| `DELETE` | `/users/me` | Delete account and all associated data |
| `GET` | `/users/me/preferences` | Get reading preferences |
| `PUT` | `/users/me/preferences` | Update `defaultReaderMode` and/or `defaultLanguage` |
| `GET` | `/users/me/library` | List library entries (age-filtered) |
| `POST` | `/users/me/library/{manga_id}` | Add manga to library |
| `PATCH` | `/users/me/library/{manga_id}` | Update library status for a saved manga |
| `DELETE` | `/users/me/library/{manga_id}` | Remove manga from library |

> Full API details: [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md)

---

### Age Gating — Content Rating Thresholds

Content from MangaDex is classified into four age tiers. Access is enforced
at the route and service layers:

| Tier | Content Rating | Access |
|------|---------------|--------|
| 0+ | `safe` | All users (including unauthenticated guests) |
| 16+ | `suggestive` | Authenticated users aged 16+ |
| 18+ | `erotica` | Authenticated users aged 18+ |
| 18+ | `pornographic` | Authenticated users aged 18+ |

- **Guest users** (unauthenticated): only `safe` content is accessible.
- **Age computation**: derived from `birth_date` on the user profile. Guests have no age → safe-only.
- **403 responses**: restricted content returns `403` with a message like
  `"This content is age-restricted (requires 16+)"`.
- **Library**: `content_rating` is stored when adding to library; GET library
  filters entries by the caller's age automatically.
- **birth_date immutability**: once set, `birth_date` cannot be changed (prevents
  age-gating bypass).

---

## Running Locally

```bash
# 1. Create and activate virtualenv
python -m venv venv
source venv/bin/activate        # Linux / macOS
# venv\Scripts\activate         # Windows

# 2. Install dependencies
python -m pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — set FIREBASE_PROJECT_ID and either
# GOOGLE_APPLICATION_CREDENTIALS (local) or FIREBASE_SERVICE_ACCOUNT_JSON_BASE64 (Railway).
# Keep production/staging CORS origins explicit; use CORS_ORIGINS=* only for local development.

# 4. Start server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

| URL | Description |
|-----|-------------|
| `http://localhost:8000/ping` | Health check |
| `http://localhost:8000/docs` | Swagger UI |
| `http://localhost:8000/redoc` | ReDoc |

> **Windows note:** Use `python -m pip` and `python -m uvicorn` — never bare `pip`/`uvicorn` — to avoid launcher path issues.

---

## Deployment

Deployed to **Railway** across 3 environments:

| Environment | API base URL | Health check |
|------------|--------------|--------------|
| dev | `https://api.dev.inkscroller.devdigi.dev` | `https://api.dev.inkscroller.devdigi.dev/ping` |
| staging | `https://api.stg.inkscroller.devdigi.dev` | `https://api.stg.inkscroller.devdigi.dev/ping` |
| prod | `https://api.inkscroller.devdigi.dev` | `https://api.inkscroller.devdigi.dev/ping` |

Production and development `/ping` have been verified online. The staging custom domain is reserved for the staging environment and should be verified after that environment is deployed/routed.

Railway serves the backend on port `8080` in each environment. Cloudflare hosts the CNAME and TXT verification records for these custom API domains. The existing portfolio remains on `https://devdigi.dev` / `https://www.devdigi.dev` and is not routed to Railway.

> Full deployment guide (Railway environments, Firebase secrets, Postgres): [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)

---

## Project Structure

```
Inkscroller_backend/
├── main.py                        # App entry — mounts all routers
├── Dockerfile                     # Multi-stage build for Railway / container deploys
├── requirements.txt
│
└── app/
    ├── api/                       # FastAPI route handlers
    │   ├── health.py              # GET /ping
    │   ├── manga.py               # GET /manga, /manga/search, /manga/{id}, /manga/tags
    │   ├── chapters.py            # GET /chapters/latest, /chapters/manga/{id}, /chapters/{id}/pages
    │   └── users.py               # GET/PATCH/DELETE /users/me, prefs, library CRUD
    │
    ├── core/
    │   ├── age.py                 # Age computation and content restriction rules
    │   ├── cache.py               # SimpleCache — TTL-based in-memory cache
    │   ├── config.py              # Settings via env vars
    │   ├── firebase_auth.py       # Firebase ID token verification middleware
    │   ├── dependencies.py        # FastAPI DI factories
    │   ├── db_adapter.py          # Database adapter (SQLite / PostgreSQL)
    │   ├── database.py            # Database bootstrap and migration helpers
    │   ├── exceptions.py          # Global exception handlers
    │   ├── logging.py             # Structured logging configuration
    │   └── resilience.py          # Retry decorator with exponential backoff
    │
    ├── models/                    # Pydantic response models
    │   ├── manga.py
    │   ├── chapter.py
    │   └── user.py                # UserProfile, UserPreferences
    │
    ├── services/                  # Business logic
    │   ├── manga_service.py
    │   ├── chapter_service.py
    │   ├── chapter_pages_service.py
    │   └── user_service.py        # User creation, preference read/write
    │
    └── sources/                   # External API clients (async httpx)
        ├── mangadex_client.py
        └── jikan_client.py

tests/
├── api/                           # Route and authenticated endpoint tests
├── services/                      # Service/mapper unit tests
└── compliance/                    # API/legal compliance audit tests
```

---

## Contributing

InkScroller Backend is a public portfolio project maintained by the author.

External contributions are not actively accepted at this time, but issues,
feedback, and code review comments are welcome.

## Security Reporting

If you discover a security issue, **do not publish secrets or exploit details in a public issue**.

- Preferred: report privately through the main GitLab workflow (linked from project profile)
- If only GitHub is available, open a minimal issue without sensitive details and request private follow-up

General security posture and secret-handling guidance: [`SECURITY_PUBLIC_READINESS.md`](SECURITY_PUBLIC_READINESS.md)

---

## Atribución y Disclaimer

InkScroller Backend agrega datos de las siguientes fuentes externas:

- **MangaDex** — fuente primaria de catálogo, capítulos e imágenes de manga. InkScroller no está afiliado a MangaDex. Todo el contenido pertenece a sus respectivos autores y grupos de scanlation. Se respetan los [Términos de Servicio de MangaDex](https://mangadex.org/about/terms-of-service).
- **Jikan / MyAnimeList** — capa de enriquecimiento de metadatos (score, rank, géneros). Jikan es un servicio no oficial de terceros. InkScroller no está afiliado a MyAnimeList ni a Jikan. Se respetan los [Términos de Uso de MyAnimeList](https://myanimelist.net/about/terms_of_use).

Este proyecto actúa como **proxy de lectura**. No almacena ni redistribuye imágenes de manga. Los derechos sobre el contenido pertenecen a sus titulares originales.

Para consultas legales o solicitudes de takedown, ver [`docs/legal/api-compliance.md`](docs/legal/api-compliance.md).

---

## License

MIT License — see [LICENSE](LICENSE) for details.
