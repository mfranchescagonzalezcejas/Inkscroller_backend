<!-- ────────────────────────────────────────────────────────────── -->
<!--  InkScroller Backend README — matching frontend style         -->
<!-- ────────────────────────────────────────────────────────────── -->

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0f172a,25:1e40af,50:0d9488,75:3b82f6,100:0f172a&height=220&section=header&text=InkScroller&fontSize=56&fontColor=fafafa&fontAlignY=38&desc=FastAPI%20Backend%20%E2%80%A2%20Clean%20Architecture%20%E2%80%A2%20MangaDex%20Proxy&descAlignY=58&descSize=16&descColor=fafafa&animation=fadeIn" width="100%"/>

[![FastAPI](https://img.shields.io/badge/FastAPI-0.128-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?style=for-the-badge&logo=railway&logoColor=white)](https://railway.app)
[![Tests](https://img.shields.io/badge/Tests-279%20%E2%9C%94-0d9488?style=for-the-badge)](https://github.com/mfranchescagonzalezcejas/Inkscroller_backend/actions)
[![License](https://img.shields.io/badge/license-MIT-0d9488?style=for-the-badge)](LICENSE)

<br/>

[![Frontend](https://img.shields.io/badge/frontend-InkScroller%20Flutter-02569B?logo=flutter&style=for-the-badge)](https://github.com/mfranchescagonzalezcejas/inkscroller_frontend)

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

<!-- ─── LANGUAGE SWITCH ───────────────────────────────────────── -->

<div align="center">
  <sub><b>· &nbsp; L A N G U A G E &nbsp; ·</b></sub>
</div>

<br/>

<div align="center">

[🇬🇧 English](#english) · [🇪🇸 Español](#espanol)

</div>

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

<!-- ═════════════════════════════════════════════════════════════ -->
<!--                    E N G L I S H                             -->
<!-- ═════════════════════════════════════════════════════════════ -->

<a name="english"></a>

<div align="center">
  <sub><b>· &nbsp; T A B L E &nbsp; O F &nbsp; C O N T E N T S &nbsp; ·</b></sub>
</div>

- [Deployment](#deployment-en)
- [Features](#features-en)
- [Tech Stack](#tech-stack-en)
- [API Reference](#api-reference-en)
- [Age Gating](#age-gating-en)
- [Running Locally](#running-locally-en)
- [Project Structure](#project-structure-en)
- [Quality Gates](#quality-gates-en)
- [TFM Deliverables](#tfm-deliverables)
- [Attribution & Disclaimer](#attribution--disclaimer-en)
- [License](#license)

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

<!-- ─── DEPLOYMENT ─────────────────────────────────────────────── -->

<div align="center">
  <a name="deployment-en"></a>
  <sub><b>· &nbsp; D E P L O Y M E N T &nbsp; ·</b></sub>
</div>

<br/>

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

<!-- ─── FEATURES ───────────────────────────────────────────────── -->

<div align="center">
  <a name="features-en"></a>
  <sub><b>· &nbsp; F E A T U R E S &nbsp; ·</b></sub>
</div>

<br/>

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
| **Cursor pagination** | Tamper-proof cursor tokens for union scans |
| **Security headers** | X-Content-Type-Options, X-Frame-Options, HSTS, CSP |
| **Caching** | In-memory TTL cache (1000 entries max) |
| **Quality gates** | Pre-commit hooks + pre-push (mypy, 279 tests) |

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

<!-- ─── TECH STACK ─────────────────────────────────────────────── -->

<div align="center">
  <a name="tech-stack-en"></a>
  <sub><b>· &nbsp; T E C H &nbsp; S T A C K &nbsp; ·</b></sub>
</div>

<br/>

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.128 |
| HTTP client | httpx (async) |
| Data validation | Pydantic v2 |
| ASGI server | Uvicorn |
| Auth | Firebase Admin SDK |
| Database | PostgreSQL (Railway) / SQLite (local) |
| Runtime | Python 3.12 |
| Testing | unittest (279 tests) |
| Linting | Ruff 0.15.9 |
| Type checking | mypy |
| Deployment | Railway (prod / dev / staging) |
| Container | Docker multi-stage build |

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

<!-- ─── API REFERENCE ──────────────────────────────────────────── -->

<div align="center">
  <a name="api-reference-en"></a>
  <sub><b>· &nbsp; A P I &nbsp; R E F E R E N C E &nbsp; ·</b></sub>
</div>

<br/>

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
| `POST` | `/csp-report` | CSP violation reports (PII-safe) |

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

<!-- ─── AGE GATING ─────────────────────────────────────────────── -->

<div align="center">
  <a name="age-gating-en"></a>
  <sub><b>· &nbsp; A G E &nbsp; G A T I N G &nbsp; ·</b></sub>
</div>

<br/>

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

<!-- ─── RUNNING LOCALLY ────────────────────────────────────────── -->

<div align="center">
  <a name="running-locally-en"></a>
  <sub><b>· &nbsp; R U N N I N G &nbsp; L O C A L L Y &nbsp; ·</b></sub>
</div>

<br/>

```bash
# 1. Create and activate virtualenv
python -m venv venv
source venv/bin/activate

# 2. Install dependencies
python -m pip install -r requirements.txt -r requirements-dev.txt

# 3. Configure environment
cp .env.example .env
# Set FIREBASE_PROJECT_ID and credentials

# 4. Start server
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

<!-- ─── PROJECT STRUCTURE ──────────────────────────────────────── -->

<div align="center">
  <a name="project-structure-en"></a>
  <sub><b>· &nbsp; P R O J E C T &nbsp; S T R U C T U R E &nbsp; ·</b></sub>
</div>

<br/>

```
Inkscroller_backend/
├── main.py                     # App entry — mounts all routers
├── Dockerfile                  # Multi-stage build
├── pyproject.toml              # Project config
│
├── app/
│   ├── api/                    # FastAPI route handlers
│   ├── core/                   # Framework & cross-cutting
│   ├── models/                 # Pydantic response models
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

<!-- ─── QUALITY GATES ──────────────────────────────────────────── -->

<div align="center">
  <a name="quality-gates-en"></a>
  <sub><b>· &nbsp; Q U A L I T Y &nbsp; G A T E S &nbsp; ·</b></sub>
</div>

<br/>

| Gate | When | What runs |
|------|------|-----------|
| **ruff lint** | `git commit` | Static analysis, unused imports, bugs |
| **ruff format** | `git commit` | Code style enforcement |
| **mypy** | `git push` | Type correctness |
| **unit tests** | `git push` | 279 tests — all green |
| **GGA** | `git commit` | AI code review via OpenCode |

```bash
pip install pre-commit
pre-commit install && pre-commit install --hook-type pre-push
```

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

<!-- ─── TFM DELIVERABLES ───────────────────────────────────────── -->

<div align="center">
  <a name="tfm-deliverables"></a>
  <sub><b>· &nbsp; T F M &nbsp; D E L I V E R A B L E S &nbsp; ·</b></sub>
</div>

<br/>

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

<!-- ─── ATTRIBUTION ────────────────────────────────────────────── -->

<div align="center">
  <a name="attribution--disclaimer-en"></a>
  <sub><b>· &nbsp; A T T R I B U T I O N &nbsp; & &nbsp; D I S C L A I M E R &nbsp; ·</b></sub>
</div>

<br/>

InkScroller Backend aggregates data from external sources:

- **MangaDex** — primary catalogue, chapters, and page images. InkScroller is not affiliated with MangaDex. Content belongs to its respective authors and scanlation groups. [MangaDex Terms of Service](https://mangadex.org/about/terms-of-service).
- **Jikan / MyAnimeList** — metadata enrichment (score, rank, genres). InkScroller is not affiliated with MyAnimeList or Jikan. [MyAnimeList Terms of Use](https://myanimelist.net/about/terms_of_use).

This project acts as a **reading proxy**. It does not host, store, or redistribute manga images. All rights belong to their original owners.

For legal inquiries or takedown requests, see [`docs/legal/api-compliance.md`](docs/legal/api-compliance.md).

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

<!-- ─── LICENSE ─────────────────────────────────────────────────── -->

<div align="center">
  <a name="license"></a>
  <sub><b>· &nbsp; L I C E N S E &nbsp; ·</b></sub>
</div>

<br/>

MIT License — see [LICENSE](LICENSE) for details.

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

<!-- ═════════════════════════════════════════════════════════════ -->
<!--                   E S P A Ñ O L                              -->
<!-- ═════════════════════════════════════════════════════════════ -->

<a name="espanol"></a>

<div align="center">
  <sub><b>· &nbsp; I N D I C E &nbsp; ·</b></sub>
</div>

- [Despliegue](#despliegue)
- [Funcionalidades](#funcionalidades)
- [Stack Tecnológico](#stack-tecnologico)
- [Referencia API](#referencia-api)
- [Control de Edad](#control-de-edad)
- [Ejecución Local](#ejecucion-local)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Quality Gates](#quality-gates-es)
- [Entregables TFM](#entregables-tfm)
- [Atribución](#atribucion)
- [Licencia](#licencia-es)

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

<!-- ─── DESPLIEGUE ─────────────────────────────────────────────── -->

<div align="center">
  <a name="despliegue"></a>
  <sub><b>· &nbsp; D E S P L I E G U E &nbsp; ·</b></sub>
</div>

<br/>

**API de producción:** [`https://api.inkscroller.devdigi.dev`](https://api.inkscroller.devdigi.dev)

| Entorno | URL | Estado |
|---------|-----|--------|
| **Producción** | `https://api.inkscroller.devdigi.dev` | ✅ |
| Desarrollo | `https://api.dev.inkscroller.devdigi.dev` | ✅ |
| Staging | `https://api.stg.inkscroller.devdigi.dev` | ✅ |

📖 **Documentación API:** [`ReDoc`](https://api.inkscroller.devdigi.dev/redoc) · [`Swagger UI`](https://api.inkscroller.devdigi.dev/docs)

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

<!-- ─── FUNCIONALIDADES ────────────────────────────────────────── -->

<div align="center">
  <a name="funcionalidades"></a>
  <sub><b>· &nbsp; F U N C I O N A L I D A D E S &nbsp; ·</b></sub>
</div>

<br/>

| Área | Descripción |
|------|-------------|
| **Catálogo manga** | Navegar, filtrar y paginar el catálogo de MangaDex |
| **Búsqueda** | Búsqueda por título con paginación |
| **Enriquecimiento** | Datos MangaDex + metadatos Jikan/MAL |
| **Filtro demográfico** | Multivalor con soporte `unspecified` |
| **Listado de capítulos** | Por manga con filtro de idioma |
| **URLs de páginas** | Imágenes vía MangaDex@Home |
| **Home feed** | Últimos capítulos con control de edad |
| **Auth** | Verificación de token Firebase |
| **Perfiles** | Creación automática al autenticarse |
| **Preferencias** | Modo de lectura, idioma, filtros |
| **Biblioteca** | CRUD con filtrado por edad |
| **Control de edad** | Acceso restringido por contenido + demografía |
| **Paginación cursor** | Tokens a prueba de manipulaciones |

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

<!-- ─── STACK TECNOLÓGICO ──────────────────────────────────────── -->

<div align="center">
  <a name="stack-tecnologico"></a>
  <sub><b>· &nbsp; S T A C K &nbsp; T E C N O L Ó G I C O &nbsp; ·</b></sub>
</div>

<br/>

| Capa | Tecnología |
|------|-----------|
| Framework | FastAPI 0.128 |
| Cliente HTTP | httpx (async) |
| Validación | Pydantic v2 |
| Servidor ASGI | Uvicorn |
| Auth | Firebase Admin SDK |
| Base de datos | PostgreSQL (Railway) / SQLite (local) |
| Runtime | Python 3.12 |
| Tests | unittest (279 tests) |
| Linting | Ruff 0.15.9 |
| Type checking | mypy |
| Despliegue | Railway (prod / dev / staging) |
| Contenedor | Docker multi-stage |

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

<!-- ─── REFERENCIA API ─────────────────────────────────────────── -->

<div align="center">
  <a name="referencia-api"></a>
  <sub><b>· &nbsp; R E F E R E N C I A &nbsp; A P I &nbsp; ·</b></sub>
</div>

<br/>

### Público

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/ping` | Health check → `{"ok": true}` |
| `GET` | `/ready` | Readiness → `{"ready": true}` o `503` |
| `GET` | `/manga` | Lista paginada con filtros |
| `GET` | `/manga/search?q=` | Búsqueda por título |
| `GET` | `/manga/{id}` | Detalle con enriquecimiento Jikan |
| `GET` | `/chapters/latest` | Últimos capítulos (filtrados por edad) |
| `GET` | `/chapters/manga/{id}` | Capítulos por idioma |
| `GET` | `/chapters/{id}/pages` | URLs de imágenes |

### Autenticado

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/users/me` | Obtener perfil |
| `PATCH` | `/users/me` | Actualizar perfil |
| `DELETE` | `/users/me` | Eliminar cuenta |
| `PUT` | `/users/me/preferences` | Actualizar preferencias |
| `GET/POST` | `/users/me/library` | Gestionar biblioteca |

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

<!-- ─── CONTROL DE EDAD ────────────────────────────────────────── -->

<div align="center">
  <a name="control-de-edad"></a>
  <sub><b>· &nbsp; C O N T R O L &nbsp; D E &nbsp; E D A D &nbsp; ·</b></sub>
</div>

<br/>

| Nivel | Clasificación | Acceso |
|-------|--------------|--------|
| 0+ | `safe` | Todos los usuarios |
| 16+ | `suggestive` | Usuarios autenticados ≥ 16 años |
| 18+ | `erotica` | Usuarios autenticados ≥ 18 años |
| 18+ | `pornographic` | Usuarios autenticados ≥ 18 años |

- **Invitados**: solo contenido `safe`.
- **Edad**: calculada desde `birth_date` en el perfil.
- **Gate demográfico**: contenido sin demografía (doujinshi) requiere 18+.
- **403**: contenido restringido devuelve la edad mínima requerida.

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

<!-- ─── EJECUCIÓN LOCAL ────────────────────────────────────────── -->

<div align="center">
  <a name="ejecucion-local"></a>
  <sub><b>· &nbsp; E J E C U C I Ó N &nbsp; L O C A L &nbsp; ·</b></sub>
</div>

<br/>

```bash
python -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

| URL | Descripción |
|-----|-------------|
| `http://localhost:8000/docs` | Swagger UI |
| `http://localhost:8000/redoc` | ReDoc |

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

<!-- ─── ENTREGABLES TFM ────────────────────────────────────────── -->

<div align="center">
  <a name="entregables-tfm"></a>
  <sub><b>· &nbsp; E N T R E G A B L E S &nbsp; T F M &nbsp; ·</b></sub>
</div>

<br/>

<div align="center">

<table>
<thead>
<tr><th>Elemento</th><th>URL</th></tr>
</thead>
<tbody>
<tr><td>🗂️ <b>Repositorio frontend</b></td><td><a href="https://github.com/mfranchescagonzalezcejas/inkscroller_frontend">mfranchescagonzalezcejas/inkscroller_frontend</a></td></tr>
<tr><td>⚙️ <b>Repositorio backend</b></td><td><a href="https://github.com/mfranchescagonzalezcejas/Inkscroller_backend">mfranchescagonzalezcejas/Inkscroller_backend</a></td></tr>
<tr><td>🔌 <b>API desplegada</b></td><td><a href="https://api.inkscroller.devdigi.dev">api.inkscroller.devdigi.dev</a></td></tr>
<tr><td>📖 <b>Documentación API</b></td><td><a href="https://api.inkscroller.devdigi.dev/redoc">ReDoc</a></td></tr>
<tr><td>📽️ <b>Slides</b></td><td>En progreso</td></tr>
<tr><td>🎬 <b>Vídeo demo</b></td><td>En progreso</td></tr>
<tr><td>👤 <b>Usuario prueba</b></td><td>No requerido — registrarse desde la app</td></tr>
</tbody>
</table>

</div>

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

<!-- ─── ATRIBUCIÓN ─────────────────────────────────────────────── -->

<div align="center">
  <a name="atribucion"></a>
  <sub><b>· &nbsp; A T R I B U C I Ó N &nbsp; ·</b></sub>
</div>

<br/>

InkScroller Backend agrega datos de fuentes externas:

- **MangaDex** — catálogo principal, capítulos e imágenes. InkScroller no está afiliado a MangaDex. Todo el contenido pertenece a sus autores y grupos de scanlation.
- **Jikan / MyAnimeList** — enriquecimiento de metadatos (score, rank, géneros). InkScroller no está afiliado a MyAnimeList ni a Jikan.

Este proyecto actúa como **proxy de lectura**. No almacena ni redistribuye imágenes de manga.

Para consultas legales: [`docs/legal/api-compliance.md`](docs/legal/api-compliance.md)

<br/>

<div align="center">
  <a name="licencia-es"></a>
  <sub><b>· &nbsp; L I C E N C I A &nbsp; ·</b></sub>
</div>

<br/>

MIT License — ver [LICENSE](LICENSE).

<br/>

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0f172a,50:0d9488,100:0f172a&height=120&section=footer&animation=fadeIn" width="100%"/>
