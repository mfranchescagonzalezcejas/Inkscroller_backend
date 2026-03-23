# Inkscroller Backend

![FastAPI](https://img.shields.io/badge/FastAPI-0.128-009688?style=flat-square&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

REST API backend for the **Inkscroller** manga reader. Built with FastAPI and Python 3.12, it aggregates data from two external sources to provide a unified manga reading experience:

- **[MangaDex](https://api.mangadex.org)** — manga catalogue, chapter lists, and page image URLs via MangaDex@Home.
- **[Jikan](https://api.jikan.moe/v4)** (MyAnimeList unofficial) — enriches manga detail with scores, rankings, authors, genres, and publication dates.

---

## Features

- 📚 **Manga catalogue** — browse, filter, and paginate the MangaDex catalogue
- 🔍 **Search** — fast title-based manga search (up to 5 results)
- 📖 **Detail enrichment** — MangaDex data augmented with Jikan/MAL metadata (score, rank, authors, genres)
- 📑 **Chapter listing** — per-manga chapter list with language filtering
- 🖼️ **Page URLs** — MangaDex@Home image URLs for any chapter
- ⚡ **In-memory caching** — 5-minute TTL cache on all service calls
- 🏥 **Health check** — liveness probe at `/ping`

---

## Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Framework | FastAPI | 0.128 |
| HTTP client | httpx (async) | 0.28 |
| Data validation | Pydantic | v2 |
| ASGI server | Uvicorn | latest |
| Runtime | Python | 3.12 |

---

## Architecture

```
HTTP Request
     │
     ▼
┌─────────────┐
│   Router    │  app/api/  (FastAPI APIRouter per domain)
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│   Service   │────▶│  SimpleCache │  app/core/cache.py (TTL 5 min, in-process)
└──────┬──────┘     └──────────────┘
       │
       ▼
┌─────────────┐
│   Source    │  app/sources/  (async httpx clients)
└──────┬──────┘
       │
  ┌────┴─────────────────────┐
  ▼                          ▼
MangaDex API            Jikan API
(manga, chapters,     (MAL enrichment:
 pages via @Home)      score, rank,
                       authors, genres)
```

**Data flow for `/manga/{id}`:**

```
Router → MangaService → MangaDexClient → MangaDex API
                    ↘
                     JikanClient → Jikan API
                    ↙
              merge (best-effort, Jikan fills gaps)
                    ↓
              Manga response
```

---

## Project Structure

```
Inkscroller_backend/
├── main.py                          # App entry point — mounts all routers
├── requirements.txt
│
└── app/
    ├── api/                         # FastAPI route handlers
    │   ├── health.py                # GET /ping
    │   ├── manga.py                 # GET /manga, /manga/search, /manga/{id}
    │   ├── chapters.py              # GET /chapters/manga/{id}
    │   └── pages.py                 # GET /chapters/{id}/pages
    │
    ├── core/
    │   ├── cache.py                 # SimpleCache — TTL-based in-memory cache
    │   └── config.py                # Settings — env var configuration
    │
    ├── models/                      # Pydantic response models
    │   ├── manga.py                 # Manga model (unified MangaDex + Jikan fields)
    │   └── chapter.py               # Chapter model
    │
    ├── services/                    # Business logic and data mapping
    │   ├── manga_service.py         # MangaService — list, search, get by ID + enrichment
    │   ├── manga_mapper.py          # map_mangadex_manga(), map_jikan_manga()
    │   ├── chapter_service.py       # ChapterService — chapter list with filtering
    │   ├── chapter_pages_service.py # ChapterPagesService — page URL assembly
    │   └── chapter_mapper.py        # map_mangadex_chapter()
    │
    └── sources/                     # External API clients (async httpx)
        ├── mangadex_client.py       # MangaDexClient
        └── jikan_client.py          # JikanClient
```

---

## API Reference

### Health

| Method | Path | Description | Response |
|---|---|---|---|
| `GET` | `/ping` | Liveness check | `{"ok": true}` |

---

### Manga

#### `GET /manga` — Paginated manga list

| Parameter | Type | Default | Description |
|---|---|---|---|
| `limit` | `int` | `20` | Items per page (1–100) |
| `offset` | `int` | `0` | Pagination offset |
| `title` | `string` | — | Filter by title (partial match) |
| `demographic` | `string` | — | Filter by demographic (`shounen`, `shoujo`, `josei`, `seinen`) |
| `status` | `string` | — | Filter by status (`ongoing`, `completed`, `hiatus`, `cancelled`) |
| `order` | `string` | — | Sort order (`latest`, `title`) |

**Response:**
```json
{
  "data": [ Manga ],
  "total": 1000,
  "limit": 20,
  "offset": 0
}
```

---

#### `GET /manga/search` — Search by title

| Parameter | Type | Required | Description |
|---|---|---|---|
| `q` | `string` | ✅ | Search query (min length 1) |

Returns at most **5 results**.

**Response:** `Manga[]`

---

#### `GET /manga/{manga_id}` — Manga detail (with Jikan enrichment)

| Parameter | Type | Description |
|---|---|---|
| `manga_id` | `string` | MangaDex manga UUID |

**Response:** `Manga`

Returns `404` if the manga is not found on MangaDex.

---

### Chapters

#### `GET /chapters/manga/{manga_id}` — Chapter list

| Parameter | Type | Default | Description |
|---|---|---|---|
| `manga_id` | `string` | — | MangaDex manga UUID |
| `lang` | `string` | `"en"` | Translated language code |

Chapters are sorted ascending by number. **Empty chapters** (zero pages, no external URL) are filtered out — only readable or externally-linked chapters are returned.

Returns `404` if no chapters are found.

**Response:** `Chapter[]`

---

#### `GET /chapters/{chapter_id}/pages` — Page image URLs

| Parameter | Type | Description |
|---|---|---|
| `chapter_id` | `string` | MangaDex chapter UUID |

Fetches image URLs from **MangaDex@Home**. The URL pattern is:
`{baseUrl}/data/{hash}/{filename}`

**Response:**
```json
{
  "readable": true,
  "external": false,
  "pages": [
    "https://uploads.mangadex.org/data/<hash>/page-001.jpg",
    "https://uploads.mangadex.org/data/<hash>/page-002.jpg"
  ]
}
```

When a chapter is externally hosted (e.g., on publisher site) or not found, the response is:
```json
{
  "readable": false,
  "external": true,
  "pages": []
}
```

---

## Data Models

### `Manga`

Unified model — MangaDex fields are always present; Jikan fields are filled in on detail requests (`GET /manga/{id}`).

| Field | Type | Source | Description |
|---|---|---|---|
| `id` | `str` | MangaDex | MangaDex manga UUID |
| `title` | `str` | MangaDex | Title (English preferred, first available otherwise) |
| `description` | `str \| null` | MangaDex / Jikan | Synopsis (Jikan fills if missing) |
| `coverUrl` | `str \| null` | MangaDex | Cover image URL (256px, `uploads.mangadex.org`) |
| `demographic` | `str \| null` | MangaDex / Jikan | Target demographic (`shounen`, `shoujo`, etc.) |
| `status` | `str \| null` | MangaDex / Jikan | Publication status (`ongoing`, `completed`, etc.) |
| `score` | `float \| null` | Jikan | MAL weighted score |
| `rank` | `int \| null` | Jikan | MAL rank by score |
| `popularity` | `int \| null` | Jikan | MAL popularity rank |
| `members` | `int \| null` | Jikan | MAL member count |
| `favorites` | `int \| null` | Jikan | MAL favorites count |
| `authors` | `str[]` | Jikan | Author names |
| `serialization` | `str \| null` | Jikan | Magazine/serialization name |
| `genres` | `str[]` | Jikan | Genre names (lowercase) |
| `chapters` | `int \| null` | MangaDex | Total chapter count |
| `startYear` | `int \| null` | Jikan | Publication start year |
| `endYear` | `int \| null` | Jikan | Publication end year |

---

### `Chapter`

| Field | Type | Description |
|---|---|---|
| `id` | `str` | MangaDex chapter UUID |
| `number` | `str \| null` | Chapter number (e.g. `"12"`, `"12.5"`) |
| `title` | `str \| null` | Chapter title |
| `date` | `datetime \| null` | Publish date (UTC ISO 8601) |
| `readable` | `bool` | `true` if hosted on MangaDex (pages > 0) |
| `external` | `bool` | `true` if chapter links to an external URL |
| `externalUrl` | `str \| null` | External chapter URL (e.g. publisher website) |

---

## Data Enrichment

The `GET /manga/{manga_id}` endpoint merges data from two sources:

```
1. MangaDexClient.get_manga(id)
      → map_mangadex_manga()
      → base Manga dict (id, title, cover, demographic, status, description)
           ↓
2. JikanClient.search_manga(title)
      → map_jikan_manga()
      → enrichment dict (score, rank, popularity, authors, genres, serialization, years...)
           ↓
3. Merge strategy:
      For each Jikan field:
        if result[field] in (None, [], ""):   ← MangaDex had nothing
            result[field] = jikan_value       ← fill from Jikan
      (MangaDex values are NEVER overwritten)
```

**Fault tolerance:** the entire Jikan step is wrapped in a `try/except`. If Jikan is unavailable, rate-limited, or returns no match, the MangaDex data is returned as-is. **Jikan never breaks the API.**

---

## Caching

All three services (`MangaService`, `ChapterService`, `ChapterPagesService`) use an instance-level `SimpleCache`:

```python
class SimpleCache:
    def __init__(self, ttl_seconds: int = 300):  # 5 minutes default
        self._store: dict[str, tuple[float, Any]] = {}
```

| Property | Value |
|---|---|
| TTL | 5 minutes (300 seconds) |
| Scope | In-process, per service instance |
| Storage | Plain Python dict |
| Invalidation | Lazy (expired entries removed on read) |
| Shared across workers | ❌ No — each process has its own cache |
| Persistent across restarts | ❌ No |

Cache keys include all relevant parameters, so `GET /manga?limit=20&offset=0` and `GET /manga?limit=20&offset=20` are cached separately.

---

## Running Locally

```bash
# 1. Clone the repository
git clone <repo-url>
cd Inkscroller_backend

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Linux / macOS
# venv\Scripts\activate          # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:

| URL | Description |
|---|---|
| `http://localhost:8000` | Local access |
| `http://0.0.0.0:8000` | All interfaces (LAN access) |
| `http://localhost:8000/docs` | Swagger UI (interactive docs) |
| `http://localhost:8000/redoc` | ReDoc documentation |
| `http://localhost:8000/openapi.json` | OpenAPI schema |

---

## Environment / Configuration

Configuration is handled via `app/core/config.py` using environment variables. All settings have sensible defaults and require no `.env` file for local development.

| Variable | Default | Description |
|---|---|---|
| `MANGADEX_BASE_URL` | `https://api.mangadex.org` | MangaDex API base URL |
| `JIKAN_BASE_URL` | `https://api.jikan.moe/v4` | Jikan API base URL |
| `CACHE_TTL_SECONDS` | `300` | Cache TTL in seconds |
| `DEBUG` | `false` | Enable debug mode |

> **Note:** The external API clients (`MangaDexClient`, `JikanClient`) currently hardcode their base URLs directly. The `Settings` class in `config.py` exposes the env vars but the clients do not yet consume them — the defaults match, so behavior is identical.

---

## Contributing

Contributions are welcome. Please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes using [Conventional Commits](https://www.conventionalcommits.org/)
4. Open a pull request

---

## License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.
