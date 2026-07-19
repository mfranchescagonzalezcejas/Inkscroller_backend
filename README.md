<!-- ────────────────────────────────────────────────────────────── -->
<!--  InkScroller Backend README (EN) — matching frontend style    -->
<!-- ────────────────────────────────────────────────────────────── -->

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0f172a,25:1e40af,50:0d9488,75:3b82f6,100:0f172a&height=220&section=header&text=InkScroller&fontSize=56&fontColor=fafafa&fontAlignY=38&desc=FastAPI%20Backend%20%E2%80%A2%20Clean%20Architecture%20%E2%80%A2%20MangaDex%20Proxy&descAlignY=58&descSize=16&descColor=fafafa&animation=fadeIn" width="100%"/>

[![FastAPI](https://img.shields.io/badge/FastAPI-0.128-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?style=for-the-badge&logo=railway&logoColor=white)](https://railway.app)
[![Tests](https://img.shields.io/badge/Tests-318%20%E2%9C%94-0d9488?style=for-the-badge)](https://github.com/mfranchescagonzalezcejas/Inkscroller_backend/actions)
[![License](https://img.shields.io/badge/license-MIT-0d9488?style=for-the-badge)](LICENSE)

<br/>

[![Frontend](https://img.shields.io/badge/frontend-InkScroller%20Flutter-02569B?logo=flutter&style=for-the-badge)](https://github.com/mfranchescagonzalezcejas/inkscroller_frontend)
[![Spanish](https://img.shields.io/badge/Leer%20en%20espa%C3%B1ol-README.es.md-0d9488?style=for-the-badge)](README.es.md)

</div>

<br/>

<div align="center">
  <sub><b>· &nbsp; A B O U T &nbsp; ·</b></sub>
</div>

<br/>

**InkScroller** is a full-stack manga reading platform. This repository contains the **backend API** — a FastAPI service that proxies and enriches data from [MangaDex](https://mangadex.org) and [Jikan/MyAnimeList](https://jikan.moe), with Firebase authentication, age-gated content access, user preferences, and personal manga libraries.

The backend serves as the data layer for the [InkScroller Flutter app](https://github.com/mfranchescagonzalezcejas/inkscroller_frontend), providing a unified API for catalogue browsing, search, chapter listing, and image proxying.

🎓 &nbsp;**TFM submission** — See [TFM Deliverables](#tfm-deliverables) below.

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## Table of Contents

- [Deployment](#deployment)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [API Reference](#api-reference)
- [Age Gating](#age-gating)
- [Running Locally](#running-locally)
- [Project Structure](#project-structure)
- [Quality Gates](#quality-gates)
- [TFM Deliverables](#tfm-deliverables)
- [Attribution & Disclaimer](#attribution--disclaimer)
- [License](#license)

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## 🚀 Deployment

**Production API:** [`https://api.inkscroller.devdigi.dev`](https://api.inkscroller.devdigi.dev)

| Environment | URL | Status |
|------------|-----|--------|
| **Production** | `https://api.inkscroller.devdigi.dev` | ✅ [`/ping`](https://api.inkscroller.devdigi.dev/ping) |
| Development | `https://api.dev.inkscroller.devdigi.dev` | ✅ [`/ping`](https://api.dev.inkscroller.devdigi.dev/ping) |
| Staging | `https://api.stg.inkscroller.devdigi.dev` | ✅ [`/ping`](https://api.stg.inkscroller.devdigi.dev/ping) |

📖 **API Documentation:** [`ReDoc`](https://api.inkscroller.devdigi.dev/redoc) · [`Swagger UI`](https://api.inkscroller.devdigi.dev/docs) · [`OpenAPI JSON`](https://api.inkscroller.devdigi.dev/openapi.json)

> Full deployment guide: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## ✨ Features

| Area | Description |
|------|-------------|
| **Manga catalogue** | Browse, filter, and paginate the MangaDex catalogue |
| **Search** | Title-based manga search with pagination |
| **Detail enrichment** | MangaDex data augmented with Jikan/MAL metadata |
| **Demographic filter** | Multi-value filtering with `unspecified` union support |
| **Content rating filter** | Age-based content filtering |
| **Chapter listing** | Per-manga chapter list with language filtering |
| **Page URLs** | MangaDex@Home image URLs for any chapter |
| **Home feed** | Latest chapters with age gating |
| **Auth** | Firebase ID token verification |
| **User profiles** | Auto-created on first authenticated request |
| **Preferences** | Reading mode, language, demographic, content rating |
| **Library** | Personal manga library with age-based filtering |
| **Account deletion** | Full account and data deletion |
| **Age-gated content** | Content + demographic enforcement by age |
| **Cursor pagination** | Tamper-proof HMAC-signed cursor tokens |
| **Rate limiting** | Sliding-window in-memory per IP (30 req/min public, 60 auth, 10 CSP) |
| **Security headers** | X-Content-Type-Options, X-Frame-Options, HSTS, CSP-RO, Permissions-Policy |
| **Output sanitization** | `html.escape()` on all upstream text fields (XSS prevention) |
| **Token revocation** | Firebase `check_revoked=True` — revoked sessions rejected immediately |
| **Caching** | In-memory LRU cache with TTL (1000 entries max) |
| **Quality gates** | Pre-commit hooks + pre-push (mypy, 318 tests) |

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.128 |
| HTTP client | httpx (async) |
| Data validation | Pydantic v2 |
| ASGI server | Uvicorn |
| Auth | Firebase Admin SDK |
| Database | PostgreSQL (Railway) / SQLite (local) |
| Runtime | Python 3.12 |
| Testing | unittest (318 tests) |
| Linting | Ruff 0.15.9 |
| Type checking | mypy |
| Deployment | Railway (prod / dev / staging) |
| Container | Docker multi-stage build |

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## 📡 API Reference

### Public

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/ping` | Liveness probe → `{"ok": true}` |
| `GET` | `/ready` | Readiness probe → `{"ready": true}` or `503` |
| `GET` | `/manga` | Paginated list with filters |
| `GET` | `/manga/search?q=` | Title search with pagination |
| `GET` | `/manga/capabilities` | API capability contract |
| `GET` | `/manga/tags` | MangaDex filter tags by type |
| `GET` | `/manga/genres` | Flat list of available genres |
| `GET` | `/manga/{id}` | Manga detail with Jikan enrichment |
| `GET` | `/chapters/latest` | Latest chapters (age-filtered) |
| `GET` | `/chapters/manga/{id}` | Chapter list by language |
| `GET` | `/chapters/{id}/pages` | Page images via MangaDex@Home |
| `POST` | `/csp-report` | CSP violation reports (origin-validated, PII-safe) |

### Authenticated

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/users/me` | Get or create user profile |
| `PATCH` | `/users/me` | Update profile |
| `DELETE` | `/users/me` | Delete account and all data |
| `GET` | `/users/me/preferences` | Get reading preferences |
| `PUT` | `/users/me/preferences` | Update preferences |
| `GET` | `/users/me/library` | List library (age-filtered) |
| `POST` | `/users/me/library/{manga_id}` | Add manga to library |
| `PATCH` | `/users/me/library/{manga_id}` | Update library entry |
| `DELETE` | `/users/me/library/{manga_id}` | Remove from library |

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## 🔒 Age Gating

| Tier | Content Rating | Access |
|------|---------------|--------|
| 0+ | `safe` | All users (including guests) |
| 16+ | `suggestive` | Authenticated users aged 16+ |
| 18+ | `erotica` | Authenticated users aged 18+ |
| 18+ | `pornographic` | Authenticated users aged 18+ |

- **Guests**: only `safe` content.
- **Age**: derived from `birth_date` on profile.
- **Demographic gating**: null-demographic (doujinshi) requires 18+.
- **403**: restricted content returns minimum age required.
- **Library**: filtered by caller's age automatically.
- **birth_date**: immutable once set.

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## 💻 Running Locally

```bash
python -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

| URL | Description |
|-----|-------------|
| `http://localhost:8000/docs` | Swagger UI |
| `http://localhost:8000/redoc` | ReDoc |
| `http://localhost:8000/ping` | Liveness probe |

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## 📁 Project Structure

```
Inkscroller_backend/
├── main.py                     # App entry
├── Dockerfile                  # Multi-stage build
├── pyproject.toml              # Project config
│
├── app/
│   ├── api/                    # FastAPI route handlers
│   ├── core/                   # Framework & cross-cutting
│   ├── models/                 # Pydantic models
│   ├── services/               # Business logic
│   └── sources/                # External API clients
│
├── tests/                      # 279 tests
├── docs/                       # Documentation
├── README.md
├── CHANGELOG.md
└── AGENTS.md                   # Coding standards
```

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## ✅ Quality Gates

| Gate | When | What runs |
|------|------|-----------|
| **ruff lint** | `git commit` | Static analysis, unused imports, bugs |
| **ruff format** | `git commit` | Code style enforcement |
| **mypy** | `git push` | Type correctness |
| **unit tests** | `git push` | 318 tests — all green |
| **GGA** | `git push` | AI code review via OpenCode |

```bash
pip install pre-commit
pre-commit install && pre-commit install --hook-type pre-push
```

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## 📦 TFM Deliverables

<div align="center">

<table>
<thead>
<tr><th>Item</th><th>URL</th></tr>
</thead>
<tbody>
<tr><td>🗂️ <b>Frontend repo</b></td><td><a href="https://github.com/mfranchescagonzalezcejas/inkscroller_frontend">mfranchescagonzalezcejas/inkscroller_frontend</a></td></tr>
<tr><td>⚙️ <b>Backend repo</b></td><td><a href="https://github.com/mfranchescagonzalezcejas/Inkscroller_backend">mfranchescagonzalezcejas/Inkscroller_backend</a></td></tr>
<tr><td>📦 <b>App releases</b></td><td><a href="https://github.com/mfranchescagonzalezcejas/inkscroller_frontend/releases">GitHub Releases</a></td></tr>
<tr><td>🔌 <b>Backend API</b></td><td><a href="https://api.inkscroller.devdigi.dev">api.inkscroller.devdigi.dev</a> · <a href="https://api.inkscroller.devdigi.dev/redoc">ReDoc</a></td></tr>
<tr><td>📽️ <b>Slides</b></td><td>Work in progress</td></tr>
<tr><td>🎬 <b>Demo video</b></td><td>Work in progress</td></tr>
<tr><td>👤 <b>Test user</b></td><td>Not required — register from the app</td></tr>
</tbody>
</table>

</div>

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## 📝 Attribution & Disclaimer

InkScroller Backend aggregates data from external sources:

- **MangaDex** — primary catalogue, chapters, and page images. InkScroller is not affiliated with MangaDex. Content belongs to its respective authors and scanlation groups. [Terms of Service](https://mangadex.org/about/terms-of-service).
- **Jikan / MyAnimeList** — metadata enrichment (score, rank, genres). InkScroller is not affiliated with MyAnimeList or Jikan. [Terms of Use](https://myanimelist.net/about/terms_of_use).

This project acts as a **reading proxy**. It does not host, store, or redistribute manga images.

For legal inquiries or takedown requests, see [`docs/legal/api-compliance.md`](docs/legal/api-compliance.md).

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

<br/>

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0f172a,50:0d9488,100:0f172a&height=120&section=footer&animation=fadeIn" width="100%"/>
