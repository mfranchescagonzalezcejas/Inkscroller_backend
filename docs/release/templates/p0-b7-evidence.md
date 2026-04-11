# Evidencia Técnica — P0-B7: Upstream Request Privacy

> **Ítem P0:** P0-B7  
> **Descripción:** No se envían datos personales de usuarios (Firebase UID, email, tokens, PII) a MangaDex ni Jikan en requests backend.  
> **Checklist ref:** Checklist Legal § 3.1  
> **Estado:** ✅ PASS — 2026-04-08  
> **Rama:** `feature/p0-b7-upstream-data-privacy`  
> **Auditor:** Claude Code (claude-sonnet-4-6)  

---

## 1. Alcance de la Auditoría

Todos los puntos de contacto entre el backend InkScroller y las APIs upstream:

| Componente | Archivo | Función |
|------------|---------|---------|
| `MangaDexClient` | `app/sources/mangadex_client.py` | Cliente HTTP principal para MangaDex API |
| `JikanClient` | `app/sources/jikan_client.py` | Cliente HTTP para Jikan/MyAnimeList API |
| `MangaService` | `app/services/manga_service.py` | Orquesta llamadas a ambos clientes |
| `ChapterService` | `app/services/chapter_service.py` | Llamadas a MangaDex para capítulos |
| `ChapterPagesService` | `app/services/chapter_pages_service.py` | Llamadas a MangaDex para páginas |
| `main.py` (lifespan) | `main.py` | Inicialización de `httpx.AsyncClient` compartidos |
| `dependencies.py` | `app/core/dependencies.py` | Inyección de dependencias y autenticación |

---

## 2. Metodología de Auditoría

### 2.1 Revisión estática de firmas de métodos

Se inspeccionaron todos los parámetros de métodos públicos de `MangaDexClient` y `JikanClient`:

**MangaDexClient — métodos auditados:**

| Método | Parámetros (excl. self) | PII detectada |
|--------|------------------------|---------------|
| `search_manga` | `query`, `limit` | ❌ Ninguna |
| `get_manga` | `manga_id` | ❌ Ninguna |
| `get_chapters` | `manga_id`, `language`, `limit` | ❌ Ninguna |
| `get_latest_chapters` | `language`, `limit` | ❌ Ninguna |
| `get_manga_list_by_ids` | `manga_ids` | ❌ Ninguna |
| `get_chapter_pages` | `chapter_id` | ❌ Ninguna |
| `get_statistics` | `manga_ids` | ❌ Ninguna |
| `list_manga` | `limit`, `offset`, `title`, `demographic`, `status`, `order`, `included_tags`, `order_map` | ❌ Ninguna |

**JikanClient — métodos auditados:**

| Método | Parámetros (excl. self) | PII detectada |
|--------|------------------------|---------------|
| `search_manga` | `title` | ❌ Ninguna |

### 2.2 Revisión de headers HTTP

Los clientes HTTP se inicializan en `main.py` lifespan:

```python
app.state.mangadex_http = httpx.AsyncClient(
    base_url=settings.mangadex_base_url,
    timeout=httpx.Timeout(10.0),
)
app.state.jikan_http = httpx.AsyncClient(
    base_url=settings.jikan_base_url,
    timeout=httpx.Timeout(10.0),
)
```

**Verificación:** Ningún header adicional es configurado en los clientes. No hay `Authorization`, `X-User-Id`, `X-Firebase-Token`, ni headers custom que contengan PII.

### 2.3 Revisión de query params y body

Todos los métodos de ambos clientes usan exclusivamente:
- **IDs de contenido público:** `manga_id`, `chapter_id`, `manga_ids` — identificadores de la propia API MangaDex, no vinculados a usuarios.
- **Parámetros de búsqueda/filtro públicos:** `title`, `query`, `language`, `limit`, `offset`, `demographic`, `status`, `order`, `contentRating[]`, `includes[]` — parámetros de catálogo público.
- Ningún método hace `POST`/`PUT` con body que contenga datos de usuario.

### 2.4 Verificación de separación arquitectural

**Flujo usuarios (Firebase UID, email):**
```
Flutter → [Bearer Token] → FastAPI → verify_firebase_token() → FirebaseTokenPayload
                                                                         ↓
                                                                 UserService (SQLite local)
```

**Flujo contenido (MangaDex/Jikan):**
```
Flutter → GET /manga → MangaService → MangaDexClient → MangaDex API
Flutter → GET /manga/{id} → MangaService → MangaDexClient + JikanClient
Flutter → GET /chapters → ChapterService → MangaDexClient → MangaDex API
```

**Punto clave:** Los dos flujos son completamente independientes. El `FirebaseTokenPayload` (que contiene `uid`, `email`, `display_name`) **nunca llega** a `MangaService`, `ChapterService`, `ChapterPagesService`, `MangaDexClient` ni `JikanClient`.

La verificación de dependencias lo confirma:
- `get_manga_service()` toma `Request` → accede a `request.app.state.mangadex_http` y `request.app.state.jikan_http`.
- `get_current_user()` opera en capa de autenticación, retorna `FirebaseTokenPayload`.
- Las rutas de manga/chapters **no tienen** `current_user: FirebaseTokenPayload = Depends(get_current_user)` en su firma.

### 2.5 Revisión de endpoint especial `/manga/tags`

El endpoint `GET /manga/tags` en `app/api/manga.py` crea un `httpx.AsyncClient` ad-hoc:

```python
async with httpx.AsyncClient() as client:
    response = await client.get(
        "https://api.mangadex.org/manga/tag",
        timeout=10.0,
    )
```

**Verificación:** Solo hace un GET a una URL pública sin query params adicionales ni headers de usuario. Sin PII.

---

## 3. Resultado de Tests Formales

Tests en `tests/test_upstream_privacy.py` — ejecutados 2026-04-08:

```
test_jikan_client_init_only_accepts_http_client ... ok
test_mangadex_client_init_only_accepts_http_client ... ok
test_no_pii_params_in_any_public_method (JikanClient) ... ok
test_search_manga_only_accepts_title ... ok
test_all_method_signatures_match_whitelist (MangaDexClient) ... ok
test_allowed_params_are_content_identifiers_only ... ok
test_no_pii_params_in_any_public_method (MangaDexClient) ... ok

Ran 7 tests in 0.001s

OK
```

**Resultado: 7/7 PASS.**

---

## 4. Evidencia de No-Regresión

Los tests en `tests/test_upstream_privacy.py` funcionan como **guardia de regresión permanente**:

- Si alguien agrega un parámetro `user_id`, `email`, `token`, `uid` etc. a `MangaDexClient` o `JikanClient`, el test `test_no_pii_params_in_any_public_method` fallará.
- Si alguien cambia la firma de `search_manga` en JikanClient para agregar datos de usuario, el test `test_search_manga_only_accepts_title` fallará.
- Si alguien modifica `__init__` para aceptar credenciales de usuario, los tests de constructor fallarán.
- Si alguien agrega un método nuevo con parámetros no contemplados, `test_all_method_signatures_match_whitelist` fallará y requerirá revisión explícita.

---

## 5. Declaración de Cierre

**P0-B7 CERRADO — PASS.**

El código backend InkScroller, en la revisión auditada (rama `feature/p0-b7-upstream-data-privacy`), no transmite datos personales de usuarios a las APIs upstream MangaDex ni Jikan. La separación arquitectural entre el flujo de autenticación y el flujo de contenido es completa y verificable. Los tests de regresión garantizan que esta propiedad se mantenga en el futuro.

| Evidencia | Referencia |
|-----------|-----------|
| Auditoría estática de firmas | §2.1 y §2.2 de este documento |
| Revisión de inicialización HTTP | §2.2 de este documento |
| Verificación de separación arquitectural | §2.4 de este documento |
| Tests formales (7/7 PASS) | `tests/test_upstream_privacy.py` |
| Tracking | `docs/release/checklist-legal.md` § Bloque 3 / Tracking P0-B7 |

---

*Generado: 2026-04-08 | Rama: `feature/p0-b7-upstream-data-privacy` | Revisión: auditoria automática + tests unitarios*
