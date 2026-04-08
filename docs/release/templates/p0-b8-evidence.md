# Evidencia de Cierre — P0-B8: Smoke Tests + `/ping` Producción

> **Estado**: ✅ PASS — 2026-04-08  
> **Ítem checklist**: 5.1 (smoke tests) + 5.2 (health check `/ping` en prod)  
> **Rama**: `feature/p0-b8-smoke-prod-evidence`  
> **Ejecutado por**: shana1499 @ Mercedes-Laptop  

---

## Resumen ejecutivo

Se ejecutaron smoke tests automatizados en dos dimensiones:

1. **Tests unitarios** (`tests/test_app.py`) — cobertura de endpoints clave con servicios fake, sin dependencias externas
2. **Smoke contra prod** (`scripts/release/smoke_prod.sh`) — verificación real de endpoints en `https://inkscroller-backend-806863502436.us-central1.run.app`

Ambas dimensiones pasaron con resultado **100% PASS**.

---

## 1. Smoke Tests Unitarios — `tests/test_app.py`

### Comando ejecutado

```bash
source venv/bin/activate
python -m pytest tests/test_app.py -v --tb=short
```

### Entorno

| Variable | Valor |
|----------|-------|
| Plataforma | linux (Ubuntu) |
| Python | 3.12.10 |
| pytest | 9.0.3 |
| Fecha | 2026-04-08T21:59:16Z |
| Runner | shana1499 @ Mercedes-Laptop |

### Resultado

```
============================= test session starts ==============================
platform linux -- Python 3.12.10, pytest-9.0.3, pluggy-1.6.0
cachedir: .pytest_cache
rootdir: /home/shana1499/Git/InkScroller/Inkscroller_backend
plugins: anyio-4.12.1
collecting ... collected 8 items

tests/test_app.py::AppSmokeTests::test_chapters_route_passes_language_and_returns_items PASSED [ 12%]
tests/test_app.py::AppSmokeTests::test_chapters_route_returns_404_when_service_returns_empty PASSED [ 25%]
tests/test_app.py::AppSmokeTests::test_lifespan_initializes_shared_resources PASSED [ 37%]
tests/test_app.py::AppSmokeTests::test_list_manga_route_passes_query_params_to_service PASSED [ 50%]
tests/test_app.py::AppSmokeTests::test_manga_route_trims_id_before_calling_service PASSED [ 62%]
tests/test_app.py::AppSmokeTests::test_pages_route_trims_chapter_id_before_service_call PASSED [ 75%]
tests/test_app.py::AppSmokeTests::test_ping_returns_ok PASSED            [ 87%]
tests/test_app.py::AppSmokeTests::test_search_route_uses_overridden_manga_service PASSED [100%]

============================== 8 passed in 0.72s ===============================
```

### Cobertura de tests

| Test | Endpoint cubierto | Resultado |
|------|-------------------|-----------|
| `test_ping_returns_ok` | `GET /ping` | ✅ PASS |
| `test_lifespan_initializes_shared_resources` | Lifespan startup (cache + HTTP clients) | ✅ PASS |
| `test_manga_route_trims_id_before_calling_service` | `GET /manga/{id}` | ✅ PASS |
| `test_search_route_uses_overridden_manga_service` | `GET /manga/search?q=...` | ✅ PASS |
| `test_list_manga_route_passes_query_params_to_service` | `GET /manga?limit=&offset=&...` | ✅ PASS |
| `test_chapters_route_passes_language_and_returns_items` | `GET /chapters/manga/{id}?lang=` | ✅ PASS |
| `test_chapters_route_returns_404_when_service_returns_empty` | `GET /chapters/manga/{id}` 404 | ✅ PASS |
| `test_pages_route_trims_chapter_id_before_service_call` | `GET /chapters/{id}/pages` | ✅ PASS |

**Total: 8/8 PASS ✅**

---

## 2. Smoke Tests contra Producción — `scripts/release/smoke_prod.sh`

### Comando ejecutado

```bash
./scripts/release/smoke_prod.sh
```

### Entorno

| Variable | Valor |
|----------|-------|
| URL prod | `https://inkscroller-backend-806863502436.us-central1.run.app` |
| Timeout curl | 15s |
| Fecha | 2026-04-08T21:59:39Z |
| Runner | shana1499 @ Mercedes-Laptop |

### Resultado

```
== P0-B8 Smoke Test — Production ==
target: https://inkscroller-backend-806863502436.us-central1.run.app
date:   2026-04-08T21:59:39Z
runner: shana1499@Mercedes-Laptop

== 1. Health Check ==
  GET /ping                                     [PASS]  status=200  time=0.185066s

== 2. Manga Catalog (public, read-only) ==
  GET /manga?limit=1&offset=0                   [PASS]  status=200  time=0.181326s
  GET /manga/search?q=berserk                   [PASS]  status=200  time=0.640018s

== 3. Edge Cases (error handling) ==
  GET /manga/%20invalid-id%20 (404 expected)    [PASS]  status=404  time=0.465749s

== Summary ==
✅ ALL CHECKS PASSED — P0-B8 SMOKE: PASS
```

### Detalle por endpoint

| Endpoint | Status esperado | Status recibido | Tiempo | Resultado |
|----------|----------------|----------------|--------|-----------|
| `GET /ping` | 200 + `{"ok":true}` | 200 + `{"ok":true}` | 0.185s | ✅ PASS |
| `GET /manga?limit=1&offset=0` | 200 + `"data"` | 200 + datos MangaDex | 0.181s | ✅ PASS |
| `GET /manga/search?q=berserk` | 200 | 200 + resultados | 0.640s | ✅ PASS |
| `GET /manga/%20invalid-id%20` | 404 | 404 | 0.466s | ✅ PASS |

**Total: 4/4 PASS ✅**

### Respuesta raw de `/ping` en prod

```
HTTP/2 200
content-type: application/json
x-cloud-trace-context: 300763443e6edb2f87df82e416d0931d;o=1
date: Wed, 08 Apr 2026 21:59:10 GMT
server: Google Frontend
content-length: 11
alt-svc: h3=":443"; ma=2592000,h3-29=":443"; ma=2592000

{"ok":true}
```

---

## 3. Infraestructura del smoke script

El script `scripts/release/smoke_prod.sh` es **reproducible** y soporta:

- Configuración via variables de entorno (`PROD_URL`, `TIMEOUT`)
- Código de salida 0 (PASS total) o 1 (algún FAIL) — integrable en CI
- Output coloreado con PASS/FAIL por endpoint y tiempo de respuesta
- Categorías de verificación: health, catálogo público, edge cases

---

## 4. Decisión de cierre

| Criterio | Estado |
|----------|--------|
| 5.1 — Smoke tests pasan (`tests/test_app.py`) | ✅ PASS — 8/8 |
| 5.2 — Health check `/ping` responde 200 en prod | ✅ PASS — 0.185s |
| Smoke script reproducible disponible | ✅ `scripts/release/smoke_prod.sh` |
| Endpoints de catálogo responden en prod | ✅ PASS — 4/4 |

**Decisión: P0-B8 CERRADO — ✅ PASS (2026-04-08)**

---

## Referencias cruzadas

- Checklist: `docs/release/checklist-legal.md` → ítems 5.1 y 5.2 marcados ✅
- Script: `scripts/release/smoke_prod.sh`
- Tests: `tests/test_app.py` (8 tests de smoke)
- Control Tower V1.0 (Obsidian) → P0-B8 marcado ✅
- BTASK-010 / TASK-022 (Obsidian) → actualizados
