# Evidencia Técnica — P0-B4 y P0-B5: Image Cache & Bulk Download Compliance

> **Ítems P0:** P0-B4 y P0-B5  
> **P0-B4 Descripción:** No se cachean binarios de imágenes en el servidor (solo URLs/metadatos).  
> **P0-B5 Descripción:** No existe endpoint ni funcionalidad de bulk download de capítulos o imágenes.  
> **Checklist ref:** Checklist Legal §1.2 (P0-B4) y §1.3 (P0-B5)  
> **Estado:** ✅ PASS — 2026-04-09  
> **Rama:** `feature/p0-b4-b5-final-backend-compliance`  
> **Auditor:** Claude Code (claude-sonnet-4-6)  

---

## 1. Alcance de la Auditoría

### 1.1 Componentes auditados para P0-B4 (caché de imágenes)

| Componente | Archivo | Función |
|------------|---------|---------|
| `SimpleCache` | `app/core/cache.py` | Implementación de caché in-memory |
| `ChapterPagesService` | `app/services/chapter_pages_service.py` | Único servicio que opera con datos de páginas/imágenes |
| `ChapterService` | `app/services/chapter_service.py` | Servicio de metadatos de capítulos |
| `MangaService` | `app/services/manga_service.py` | Servicio de metadatos de manga |
| `chapters` router | `app/api/chapters.py` | Endpoints de capítulos |
| `manga` router | `app/api/manga.py` | Endpoints de manga |
| SQLite DB | `app/core/database.py` | DDL de base de datos persistente |

### 1.2 Componentes auditados para P0-B5 (bulk download)

| Componente | Archivo | Función |
|------------|---------|---------|
| `chapters` router | `app/api/chapters.py` | Todos los endpoints de capítulos |
| `manga` router | `app/api/manga.py` | Todos los endpoints de manga |
| `users` router | `app/api/users.py` | Endpoints de usuarios |
| `health` router | `app/api/health.py` | Health check |
| `MangaDexClient` | `app/sources/mangadex_client.py` | Cliente upstream MangaDex |

---

## 2. Auditoría P0-B4 — No binarios de imágenes cacheados

### 2.1 Análisis de `SimpleCache`

**Archivo:** `app/core/cache.py`

```python
class SimpleCache:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def set(self, key: str, value: Any) -> None:
        expires_at = time.time() + self.ttl
        self._store[key] = (expires_at, value)
```

**Hallazgos:**
- El almacenamiento es un `dict` en memoria RAM del proceso Python.
- Acepta tipo `Any` — no restringe bytes, pero el análisis de todos los callers confirma que **ninguno almacena `bytes` ni `bytearray`**.
- Sin persistencia a disco, sin Redis, sin almacenamiento externo.
- TTL de 5 minutos por defecto — los datos expiran automáticamente.

### 2.2 Análisis del caller crítico: `ChapterPagesService.get_pages()`

**Archivo:** `app/services/chapter_pages_service.py`

Este es el **único punto** donde el backend procesa datos relacionados con imágenes de páginas:

```python
async def get_pages(self, chapter_id: str) -> dict:
    # ...
    payload = await self._client.get_chapter_pages(chapter_id)
    
    base_url = payload.get("baseUrl")
    chapter = payload.get("chapter", {})
    hash_ = chapter.get("hash")
    files = chapter.get("data", [])

    # Construcción de URLs — no descarga de binarios
    pages = [f"{base_url}/data/{hash_}/{file}" for file in files]

    result = {
        "readable": True,
        "external": False,
        "pages": pages,        # ← lista de strings URL, no bytes
    }

    self._cache.set(cache_key, result)  # ← cachea el dict con URLs
    return result
```

**Verificación crítica:**
- `self._client.get_chapter_pages(chapter_id)` → llama a `MangaDex /at-home/server/{chapter_id}` → retorna **metadata JSON** (baseUrl, hash, lista de nombres de archivo).
- El backend **no hace ninguna request adicional** para descargar el contenido binario de las imágenes.
- `pages = [f"{base_url}/data/{hash_}/{file}" for file in files]` → construye **URLs como strings**.
- Lo que se cachea es `result = {"readable": bool, "external": bool, "pages": [str, str, ...]}` → **dict de metadatos con URLs**.
- El cliente Flutter recibe estas URLs y **hace sus propias requests directas al CDN de MangaDex** para obtener las imágenes.

### 2.3 Análisis de `MangaDexClient.get_chapter_pages()`

**Archivo:** `app/sources/mangadex_client.py`

```python
async def get_chapter_pages(self, chapter_id: str) -> dict:
    response = await self.client.get(f"/at-home/server/{chapter_id}")
    response.raise_for_status()
    return response.json()    # ← solo JSON metadata, nunca bytes de imagen
```

**Hallazgos:**
- Llama a `MangaDex /at-home/server/{chapter_id}` — endpoint que retorna metadata del servidor de imágenes.
- `.json()` retorna el payload JSON: `{"baseUrl": "https://...", "chapter": {"hash": "...", "data": [...]}}`.
- **No se hace ninguna request a las URLs de imágenes**. Solo se obtiene el mapa de rutas.

### 2.4 Análisis de metadatos cacheados en otros servicios

| Servicio | Cache key format | Tipo de valor cacheado |
|----------|-----------------|------------------------|
| `ChapterPagesService` | `pages:{chapter_id}` | `dict` con `pages: list[str]` (URLs) |
| `ChapterService` | `chapters:{manga_id}:{lang}` | `list[dict]` con metadatos de capítulos |
| `ChapterService` | `chapters:latest:home:v4:{lang}:{limit}` | `list[dict]` con metadatos de home |
| `MangaService` | `manga:{manga_id}` | `dict` con metadatos Pydantic |
| `MangaService` | `manga:list:{...params}` | `dict` con `data: list[dict]` |
| `MangaService` | `search:{query}:{limit}` | `list[dict]` con resultados |
| `manga` endpoint | `mangadex:tags` | `dict` con grupos de tags (strings) |

**coverUrl en MangaService:**
```python
cover_url = f"{COVER_BASE_URL}/{manga_id}/{cover_file}.256.jpg" if cover_file else None
```
→ `coverUrl` es un **string URL** de la imagen de portada en el CDN de MangaDex. No se descarga ni almacena el binario.

### 2.5 Análisis de DB SQLite

**Archivo:** `app/core/database.py` — DDL completo:

```sql
CREATE TABLE IF NOT EXISTS users (
    firebase_uid  TEXT    PRIMARY KEY,
    email         TEXT    NOT NULL,
    display_name  TEXT,
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS reading_preferences (
    firebase_uid         TEXT    PRIMARY KEY REFERENCES users(firebase_uid),
    default_reader_mode  TEXT    NOT NULL DEFAULT 'vertical',
    default_language     TEXT    NOT NULL DEFAULT 'en',
    updated_at           TEXT    NOT NULL
);
```

**Hallazgos:** Las dos únicas tablas almacenan datos de usuario (texto) y preferencias de lectura (texto). **No hay columnas BLOB, IMAGE, BYTEA ni ningún tipo binario.**

### 2.6 Búsqueda de patrones de I/O de imágenes (grep formal)

**Búsqueda ejecutada:** `download|bulk|bytes|blob|open\(|write\(|save.*file|image.*data|binary|b64`  
**Archivos buscados:** todos los `.py` del proyecto  
**Resultado:** 1 match — `mangadex_client.py:151`: `"MangaDex doesn't support bulk"` (comentario, no código funcional)

**Búsqueda ejecutada:** `StreamingResponse|FileResponse|Response.*bytes|content.*type.*image|application.*octet`  
**Resultado:** 0 matches

---

## 3. Auditoría P0-B5 — No endpoint de bulk download

### 3.1 Inventario completo de endpoints

Auditoría de todos los routers registrados en la aplicación:

#### Router `chapters` — `app/api/chapters.py`

| Método | Path | Función | Retorna |
|--------|------|---------|---------|
| GET | `/chapters/latest` | `get_latest_home_chapters` | `list[HomeChapter]` — metadatos |
| GET | `/chapters/manga/{manga_id}` | `get_manga_chapters` | `list[Chapter]` — metadatos |
| GET | `/chapters/{chapter_id}/pages` | `get_chapter_pages` | `dict` con `pages: [URL, ...]` |

#### Router `manga` — `app/api/manga.py`

| Método | Path | Función | Retorna |
|--------|------|---------|---------|
| GET | `/manga/tags` | `list_tags` | `dict` con grupos de tags |
| GET | `/manga/genres` | `list_genres` | `dict` con géneros |
| GET | `/manga/search` | `search_manga` | `list[Manga]` — metadatos |
| GET | `/manga/{manga_id}` | `get_manga` | `Manga` — metadatos |
| GET | `/manga` | `list_manga` | paginación + `list[Manga]` |

#### Router `users` — `app/api/users.py`

| Método | Path | Función | Retorna |
|--------|------|---------|---------|
| GET | `/users/me` | `get_current_user_profile` | `UserProfile` |
| GET | `/users/me/preferences` | `get_preferences` | `ReadingPreferences` |
| PUT | `/users/me/preferences` | `update_preferences` | `ReadingPreferences` |

#### Router `health` — `app/api/health.py`

| Método | Path | Función | Retorna |
|--------|------|---------|---------|
| GET | `/ping` | `ping` | `{"ok": true}` |

**Total: 12 rutas. Ninguna contiene "download", "bulk", ni sirve contenido binario.**

### 3.2 Análisis de `/{chapter_id}/pages` — El endpoint más cercano al concepto

Este endpoint es el único que podría interpretarse como "acceso a imágenes", pero su comportamiento es:

1. Llama a `ChapterPagesService.get_pages(chapter_id)`
2. El servicio llama a `MangaDexClient.get_chapter_pages(chapter_id)` → MangaDex API `/at-home/server/{chapter_id}`
3. MangaDex retorna JSON con `{baseUrl, chapter: {hash, data: [filenames]}}`
4. El servicio **construye URLs** y retorna `{readable, external, pages: [url1, url2, ...]}`
5. **El backend nunca descarga el contenido de las imágenes.** Flutter carga cada imagen directamente desde el CDN de MangaDex.

Esto es **proxy de URLs** (legal), no **bulk download de binarios** (prohibido).

### 3.3 Confirmación arquitectural — MangaDex no soporta bulk

El comentario en `MangaDexClient.get_statistics()` confirma que la arquitectura fue diseñada con conciencia de esta restricción:

```python
async def get_statistics(self, manga_ids: list[str]) -> dict[str, Any]:
    """Fetch statistics (rating, follows) for multiple manga IDs.
    
    MangaDex doesn't support bulk - fetches one by one in parallel.
    """
```

### 3.4 Búsqueda de indicadores de bulk download

| Patrón buscado | Resultado |
|----------------|-----------|
| `zipfile` en servicios/routers | ❌ No encontrado |
| `tarfile` en servicios/routers | ❌ No encontrado |
| `shutil.make_archive` | ❌ No encontrado |
| `StreamingResponse` | ❌ No encontrado |
| `FileResponse` | ❌ No encontrado |
| path con `download` | ❌ No encontrado |
| path con `bulk` | ❌ No encontrado |
| función con nombre `download` | ❌ No encontrado |

---

## 4. Resultado de Tests Formales

Tests en `tests/test_image_cache_and_bulk_download.py` — ejecutados 2026-04-09:

```
tests/test_image_cache_and_bulk_download.py::TestNoBinaryCaching::test_chapter_pages_result_structure_is_urls_only PASSED
tests/test_image_cache_and_bulk_download.py::TestNoBinaryCaching::test_chapter_pages_service_caches_url_dict_not_bytes PASSED
tests/test_image_cache_and_bulk_download.py::TestNoBinaryCaching::test_chapter_service_caches_metadata_not_images PASSED
tests/test_image_cache_and_bulk_download.py::TestNoBinaryCaching::test_manga_service_caches_metadata_not_images PASSED
tests/test_image_cache_and_bulk_download.py::TestNoBinaryCaching::test_no_filesystem_image_storage PASSED
tests/test_image_cache_and_bulk_download.py::TestNoBinaryCaching::test_no_streaming_response_for_images PASSED
tests/test_image_cache_and_bulk_download.py::TestNoBinaryCaching::test_simple_cache_stores_any_not_bytes PASSED
tests/test_image_cache_and_bulk_download.py::TestNoBulkDownloadEndpoint::test_all_chapter_endpoints_use_get_method_only PASSED
tests/test_image_cache_and_bulk_download.py::TestNoBulkDownloadEndpoint::test_chapter_pages_returns_urls_not_binary_content PASSED
tests/test_image_cache_and_bulk_download.py::TestNoBulkDownloadEndpoint::test_chapters_router_endpoints_are_read_only_metadata PASSED
tests/test_image_cache_and_bulk_download.py::TestNoBulkDownloadEndpoint::test_mangadex_client_comment_confirms_no_bulk PASSED
tests/test_image_cache_and_bulk_download.py::TestNoBulkDownloadEndpoint::test_no_bulk_download_route_exists PASSED
tests/test_image_cache_and_bulk_download.py::TestNoBulkDownloadEndpoint::test_no_zip_archive_generation PASSED
tests/test_image_cache_and_bulk_download.py::TestNoBulkDownloadEndpoint::test_total_route_count_matches_expected PASSED

14 passed in 0.34s
```

**Resultado: 14/14 PASS.**

---

## 5. Evidencia de No-Regresión

Los tests en `tests/test_image_cache_and_bulk_download.py` funcionan como **guardia de regresión permanente**:

### Para P0-B4:
- Si alguien agrega lógica que descarga contenido binario de imágenes en `ChapterPagesService`, el test `test_chapter_pages_service_caches_url_dict_not_bytes` fallará (busca `.content`, `b64encode`, `BytesIO`).
- Si alguien agrega I/O de disco (open, write, shutil), `test_no_filesystem_image_storage` fallará.
- Si alguien agrega `StreamingResponse` o `FileResponse` para imágenes, `test_no_streaming_response_for_images` fallará.
- Si la estructura del resultado de `get_pages()` cambia y deja de ser un dict de URLs, `test_chapter_pages_result_structure_is_urls_only` fallará.

### Para P0-B5:
- Si alguien agrega una ruta con "download" o "bulk" en el path, `test_no_bulk_download_route_exists` fallará.
- Si el número total de rutas cambia (nueva ruta no auditada), `test_total_route_count_matches_expected` fallará y requerirá revisión explícita.
- Si alguien agrega lógica de ZIP/TAR, `test_no_zip_archive_generation` fallará.
- Si el set exacto de rutas de chapters cambia, `test_chapters_router_endpoints_are_read_only_metadata` fallará.

---

## 6. Declaración de Cierre

**P0-B4 CERRADO — PASS.**

El backend InkScroller no cachea binarios de imágenes en ninguna capa. El caché in-memory (`SimpleCache`) almacena exclusivamente URLs (strings) y metadatos (dicts Python). La arquitectura es explícitamente de **proxy de URLs**: el backend resuelve las rutas de las imágenes en el CDN de MangaDex y devuelve las URLs al cliente Flutter, que realiza sus propias requests. No existe persistencia de binarios en RAM estructurada, en SQLite ni en disco.

**P0-B5 CERRADO — PASS.**

El backend InkScroller no tiene ningún endpoint de bulk download. El inventario completo de 12 rutas ha sido auditado: todas son operaciones GET de consulta que retornan metadatos JSON o listas de URLs. Ninguna ruta genera archivos ZIP/TAR, descarga contenido binario en nombre del cliente, ni permite obtener múltiples capítulos en una sola operación de descarga.

| Evidencia | Referencia |
|-----------|-----------|
| Análisis de `SimpleCache` + todos los callers | §2.1 – §2.4 de este documento |
| DDL SQLite — cero columnas binarias | §2.5 de este documento |
| Búsqueda de patrones binarios (grep) | §2.6 de este documento |
| Inventario completo de 12 rutas API | §3.1 de este documento |
| Análisis arquitectural `/{chapter_id}/pages` | §3.2 de este documento |
| Búsqueda de indicadores bulk download | §3.4 de este documento |
| Tests formales (14/14 PASS) | `tests/test_image_cache_and_bulk_download.py` |
| Tracking | `docs/release/checklist-legal.md` §Bloque 1 / Tracking P0-B4, P0-B5 |

---

*Generado: 2026-04-09 | Rama: `feature/p0-b4-b5-final-backend-compliance` | Revisión: auditoría automática + tests unitarios*
