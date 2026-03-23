# Inkscroller Backend

REST API backend for the Inkscroller manga reader, built with **FastAPI** and **Python 3.12**.

It aggregates data from two external sources:

- **[MangaDex](https://api.mangadex.org)** — manga catalogue, chapter lists, and page image URLs.
- **[Jikan](https://api.jikan.moe/v4)** (MyAnimeList unofficial) — enriches manga detail with scores, rankings, authors, genres, and publication dates.

---

## Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.128 |
| HTTP client | httpx 0.28 (async) |
| Data validation | Pydantic v2 |
| ASGI server | Uvicorn |
| Python | 3.12 |

---

## Project structure

```
app/
  api/          # Route handlers (FastAPI routers)
  core/         # Config and in-memory cache (SimpleCache, TTL 5 min)
  models/       # Pydantic response models (Manga, Chapter)
  services/     # Business logic and data mappers
  sources/      # External API clients (MangaDexClient, JikanClient)
main.py         # Application entry point
requirements.txt
```

---

## Endpoints

### Health

| Method | Path | Description |
|---|---|---|
| GET | `/ping` | Liveness check — returns `{"ok": true}` |

### Manga

| Method | Path | Description |
|---|---|---|
| GET | `/manga` | Paginated manga list. Query params: `limit`, `offset`, `title`, `demographic`, `status`, `order` |
| GET | `/manga/search?q=` | Search manga by title (MangaDex, max 5 results) |
| GET | `/manga/{manga_id}` | Manga detail enriched with Jikan data |

### Chapters

| Method | Path | Description |
|---|---|---|
| GET | `/chapters/manga/{manga_id}` | Chapter list for a manga. Query param: `lang` (default `en`) |
| GET | `/chapters/{chapter_id}/pages` | Page image URLs for a chapter (via MangaDex@Home) |

---

## Data enrichment

The `/manga/{manga_id}` endpoint follows a two-step strategy:

1. Fetch core data from MangaDex (title, cover, demographic, status).
2. Search Jikan by title and fill in any missing fields (description, score, rank, authors, genres, publication years, etc.).

Jikan enrichment is **best-effort** — if it fails, the MangaDex data is returned as-is.

---

## Caching

All service calls use an in-process `SimpleCache` with a 5-minute TTL. The cache is per-process and is not shared across workers or restarts.

---

## Running locally

```bash
# Install dependencies
pip install -r requirements.txt

# Start the development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000` (local) or `http://192.168.1.38:8000` (LAN devices).  
Interactive docs: `http://localhost:8000/docs`

---

## Notes

- `app/core/config.py` is currently empty — configuration is hardcoded in the clients and services.
- The `jikan_mapper` file in `app/services/` contains a standalone `map_jikan_detail` mapper (used for future detail enrichment). The active mapper used by `MangaService` is inlined in `manga_service.py`.
- Chapter filtering removes entries with zero pages and no external URL, so only readable or externally-linked chapters are returned.
