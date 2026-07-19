<!-- ────────────────────────────────────────────────────────────── -->
<!--  InkScroller Backend README (ES) — matching frontend style    -->
<!-- ────────────────────────────────────────────────────────────── -->

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0f172a,25:1e40af,50:0d9488,75:3b82f6,100:0f172a&height=220&section=header&text=InkScroller&fontSize=56&fontColor=fafafa&fontAlignY=38&desc=FastAPI%20Backend%20%E2%80%A2%20Clean%20Architecture%20%E2%80%A2%20MangaDex%20Proxy&descAlignY=58&descSize=16&descColor=fafafa&animation=fadeIn" width="100%"/>

[![FastAPI](https://img.shields.io/badge/FastAPI-0.128-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?style=for-the-badge&logo=railway&logoColor=white)](https://railway.app)
[![Tests](https://img.shields.io/badge/Tests-318%20%E2%9C%94-0d9488?style=for-the-badge)](https://github.com/mfranchescagonzalezcejas/Inkscroller_backend/actions)
[![Licencia](https://img.shields.io/badge/licencia-MIT-0d9488?style=for-the-badge)](LICENSE)

<br/>

[![Frontend](https://img.shields.io/badge/frontend-InkScroller%20Flutter-02569B?logo=flutter&style=for-the-badge)](https://github.com/mfranchescagonzalezcejas/inkscroller_frontend)
[![English](https://img.shields.io/badge/Read%20in%20english-README.md-0d9488?style=for-the-badge)](README.md)

</div>

<br/>

<div align="center">
  <sub><b>· &nbsp; S O B R E &nbsp; E L &nbsp; P R O Y E C T O &nbsp; ·</b></sub>
</div>

<br/>

**InkScroller** es una plataforma de lectura de manga full-stack. Este repositorio contiene la **API backend** — un servicio FastAPI que hace de proxy y enriquece datos de [MangaDex](https://mangadex.org) y [Jikan/MyAnimeList](https://jikan.moe), con autenticación Firebase, control de acceso por edad, preferencias de usuario y bibliotecas personales.

El backend sirve como capa de datos para la [app Flutter de InkScroller](https://github.com/mfranchescagonzalezcejas/inkscroller_frontend), proporcionando una API unificada para navegación de catálogo, búsqueda, listado de capítulos y proxy de imágenes.

🎓 &nbsp;**Entrega TFM** — Ver [Entregables TFM](#entregables-tfm) más abajo.

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## Índice

- [Despliegue](#despliegue)
- [Funcionalidades](#funcionalidades)
- [Stack Tecnológico](#stack-tecnológico)
- [Referencia API](#referencia-api)
- [Control de Edad](#control-de-edad)
- [Ejecución Local](#ejecución-local)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Quality Gates](#quality-gates)
- [Entregables TFM](#entregables-tfm)
- [Atribución](#atribución)
- [Licencia](#licencia)

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## 🚀 Despliegue

**API de producción:** [`https://api.inkscroller.devdigi.dev`](https://api.inkscroller.devdigi.dev)

| Entorno | URL | Estado |
|---------|-----|--------|
| **Producción** | `https://api.inkscroller.devdigi.dev` | ✅ [`/ping`](https://api.inkscroller.devdigi.dev/ping) |
| Desarrollo | `https://api.dev.inkscroller.devdigi.dev` | ✅ [`/ping`](https://api.dev.inkscroller.devdigi.dev/ping) |
| Staging | `https://api.stg.inkscroller.devdigi.dev` | ✅ [`/ping`](https://api.stg.inkscroller.devdigi.dev/ping) |

📖 **Documentación API:** [`ReDoc`](https://api.inkscroller.devdigi.dev/redoc) · [`Swagger UI`](https://api.inkscroller.devdigi.dev/docs)

> Guía de despliegue completa: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## ✨ Funcionalidades

| Área | Descripción |
|------|-------------|
| **Catálogo manga** | Navegar, filtrar y paginar el catálogo de MangaDex |
| **Búsqueda** | Búsqueda por título con paginación |
| **Enriquecimiento** | Datos MangaDex + metadatos Jikan/MAL |
| **Filtro demográfico** | Multivalor con soporte `unspecified` |
| **Filtro de clasificación** | Filtrado por edad (safe/suggestive/erotica/pornographic) |
| **Capítulos** | Listado por manga con filtro de idioma |
| **URLs de páginas** | Imágenes vía MangaDex@Home |
| **Home feed** | Últimos capítulos con control de edad |
| **Auth** | Verificación de token Firebase |
| **Perfiles** | Creación automática al autenticarse |
| **Preferencias** | Modo de lectura, idioma, filtros |
| **Biblioteca** | CRUD con filtrado por edad |
| **Borrado de cuenta** | Eliminación completa de datos |
| **Control de edad** | Acceso restringido por contenido + demografía |
| **Paginación cursor** | Tokens HMAC a prueba de manipulaciones |
| **Rate limiting** | Ventana deslizante por IP (30 req/min público, 60 auth, 10 CSP). Responses 429 incluyen CORS. Key por categoría de ruta. `TRUSTED_PROXY` para Railway/Cloudflare |
| **Cabeceras de seguridad** | X-Content-Type-Options, HSTS, CSP-RO, Permissions-Policy |
| **Sanitización output** | Texto de upstreams sin escapar — el frontend sanitiza según su contexto |
| **Revocación tokens** | `check_revoked=True` en Firebase — sesiones revocadas rechazadas |
| **Caché** | En memoria LRU con TTL (1000 entradas máx) |
| **Quality gates** | Pre-commit + pre-push (mypy, 318 tests) |

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## 🛠️ Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| Framework | FastAPI 0.128 |
| Cliente HTTP | httpx (async) |
| Validación | Pydantic v2 |
| Servidor ASGI | Uvicorn |
| Auth | Firebase Admin SDK |
| Base de datos | PostgreSQL (Railway) / SQLite (local) |
| Runtime | Python 3.12 |
| Tests | unittest (318 tests) |
| Linting | Ruff 0.15.9 |
| Type checking | mypy |
| Despliegue | Railway (prod / dev / staging) |
| Contenedor | Docker multi-stage |

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## 📡 Referencia API

### Público

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/ping` | Health check → `{"ok": true}` |
| `GET` | `/ready` | Readiness → `{"ready": true}` o `503` |
| `GET` | `/manga` | Lista paginada con filtros |
| `GET` | `/manga/search?q=` | Búsqueda por título |
| `GET` | `/manga/capabilities` | Contrato de capacidades |
| `GET` | `/manga/tags` | Tags de MangaDex por tipo |
| `GET` | `/manga/genres` | Lista de géneros disponibles |
| `GET` | `/manga/{id}` | Detalle con enriquecimiento Jikan |
| `GET` | `/chapters/latest` | Últimos capítulos (filtrados por edad) |
| `GET` | `/chapters/manga/{id}` | Capítulos por idioma |
| `GET` | `/chapters/{id}/pages` | URLs de imágenes vía MangaDex@Home |
| `POST` | `/csp-report` | Reportes CSP (sin PII) |

### Autenticado

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/users/me` | Obtener perfil |
| `PATCH` | `/users/me` | Actualizar perfil |
| `DELETE` | `/users/me` | Eliminar cuenta |
| `GET` | `/users/me/preferences` | Ver preferencias |
| `PUT` | `/users/me/preferences` | Actualizar preferencias |
| `GET` | `/users/me/library` | Listar biblioteca |
| `POST` | `/users/me/library/{manga_id}` | Añadir a biblioteca |
| `PATCH` | `/users/me/library/{manga_id}` | Actualizar entrada |
| `DELETE` | `/users/me/library/{manga_id}` | Eliminar de biblioteca |

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## 🔒 Control de Edad

| Nivel | Clasificación | Acceso |
|-------|--------------|--------|
| 0+ | `safe` | Todos los usuarios |
| 16+ | `suggestive` | Usuarios autenticados ≥ 16 años |
| 18+ | `erotica` | Usuarios autenticados ≥ 18 años |
| 18+ | `pornographic` | Usuarios autenticados ≥ 18 años |

- **Invitados**: solo contenido `safe`.
- **Edad**: calculada desde `birth_date` en el perfil.
- **Gate demográfico**: contenido sin demografía (doujinshi) requiere 18+.
- **403**: contenido restringido devuelve la edad mínima.
- **Biblioteca**: filtrada por edad automáticamente.
- **birth_date**: inmutable una vez establecida.

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## 💻 Ejecución Local

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

## 📁 Estructura del Proyecto

```
Inkscroller_backend/
├── main.py                     # Entry point
├── Dockerfile                  # Build multi-stage
├── pyproject.toml              # Config del proyecto
│
├── app/
│   ├── api/                    # Rutas FastAPI
│   ├── core/                   # Framework transversal
│   ├── models/                 # Modelos Pydantic
│   ├── services/               # Lógica de negocio
│   └── sources/                # Clientes API externos
│
├── tests/                      # 279 tests
├── docs/                       # Documentación
├── README.md
├── CHANGELOG.md
└── AGENTS.md                   # Estándares de código
```

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## ✅ Quality Gates

| Gate | Cuándo | Qué ejecuta |
|------|--------|-------------|
| **ruff lint** | `git commit` | Análisis estático, imports no usados |
| **ruff format** | `git commit` | Formato de código |
| **mypy** | `git push` | Corrección de tipos |
| **unit tests** | `git push` | 318 tests — todos verdes |
| **GGA** | `git push` | Code review con IA via OpenCode |

```bash
pip install pre-commit
pre-commit install && pre-commit install --hook-type pre-push
```

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## 📦 Entregables TFM

<div align="center">

<table>
<thead>
<tr><th>Elemento</th><th>URL</th></tr>
</thead>
<tbody>
<tr><td>🗂️ <b>Repo frontend</b></td><td><a href="https://github.com/mfranchescagonzalezcejas/inkscroller_frontend">mfranchescagonzalezcejas/inkscroller_frontend</a></td></tr>
<tr><td>⚙️ <b>Repo backend</b></td><td><a href="https://github.com/mfranchescagonzalezcejas/Inkscroller_backend">mfranchescagonzalezcejas/Inkscroller_backend</a></td></tr>
<tr><td>📦 <b>Releases app</b></td><td><a href="https://github.com/mfranchescagonzalezcejas/inkscroller_frontend/releases">GitHub Releases</a></td></tr>
<tr><td>🔌 <b>API backend</b></td><td><a href="https://api.inkscroller.devdigi.dev">api.inkscroller.devdigi.dev</a> · <a href="https://api.inkscroller.devdigi.dev/redoc">ReDoc</a></td></tr>
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

## 📝 Atribución

InkScroller Backend agrega datos de fuentes externas:

- **MangaDex** — catálogo principal, capítulos e imágenes. InkScroller no está afiliado a MangaDex. Todo el contenido pertenece a sus autores y grupos de scanlation. [Términos de Servicio](https://mangadex.org/about/terms-of-service).
- **Jikan / MyAnimeList** — enriquecimiento de metadatos (score, rank, géneros). InkScroller no está afiliado a MyAnimeList ni a Jikan. [Términos de Uso](https://myanimelist.net/about/terms_of_use).

Este proyecto actúa como **proxy de lectura**. No almacena ni redistribuye imágenes de manga.

Consultas legales: [`docs/legal/api-compliance.md`](docs/legal/api-compliance.md)

<br/>

<div align="center">
  <img width="55%" src="https://capsule-render.vercel.app/api?type=rect&color=0:0f172a,50:0d9488,100:0f172a&height=3" alt=""/>
</div>

<br/>

## 📄 Licencia

MIT License — ver [LICENSE](LICENSE).

<br/>

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0f172a,50:0d9488,100:0f172a&height=120&section=footer&animation=fadeIn" width="100%"/>
