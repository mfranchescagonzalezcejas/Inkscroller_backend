# Checklist Legal — Release InkScroller Backend

> **Propósito:** Validar el cumplimiento legal y de APIs antes de promover a producción.  
> **Usar en:** Cada release a `staging` y `prod`.  
> **Referencia:** [`docs/legal/api-compliance.md`](../legal/api-compliance.md)

---

## Regla GO / NO-GO

> **Un NO en cualquier ítem marcado con 🔴 bloquea el release.**  
> Los ítems 🟡 son advertencias — documentar la decisión si se omiten.

---

## Bloque 1 — MangaDex

| # | Ítem | Criticidad | Estado |
|---|------|-----------|--------|
| 1.1 | El backend actúa como proxy — Flutter **no** llama a MangaDex directamente | 🔴 BLOQUEANTE | ☐ |
| 1.2 | No se cachean binarios de imágenes en el servidor (solo URLs) | 🔴 BLOQUEANTE | ✅ 2026-04-09 — PASS (ver [`templates/p0-b4-b5-evidence.md`](./templates/p0-b4-b5-evidence.md)) |
| 1.3 | No existe endpoint de bulk download de capítulos | 🔴 BLOQUEANTE | ✅ 2026-04-09 — PASS (ver [`templates/p0-b4-b5-evidence.md`](./templates/p0-b4-b5-evidence.md)) |
| 1.4 | El caché in-memory está activo (TTL 5 min) para reducir llamadas a MangaDex | 🟡 ADVERTENCIA | ☐ |
| 1.5 | Todos los clientes HTTP incluyen header `User-Agent: InkScroller-Backend/...` | 🟡 ADVERTENCIA | ☐ |
| 1.6 | Existe manejo de HTTP 429 (retry con backoff o log de warning) | 🟡 ADVERTENCIA | ☐ |
| 1.7 | El contenido con `contentRating: erotica/pornographic` está filtrado o requiere verificación de edad | 🔴 BLOQUEANTE | ✅ 2026-04-08 |
| 1.8 | La respuesta de capítulos incluye o puede incluir `scanlation_group` para atribución | 🟡 ADVERTENCIA | ☐ |

## Bloque 2 — Jikan / MyAnimeList

| # | Ítem | Criticidad | Estado |
|---|------|-----------|--------|
| 2.1 | Jikan solo se usa como capa de enriquecimiento (no es fuente primaria) | 🔴 BLOQUEANTE | ☐ |
| 2.2 | Existe fallback graceful si Jikan retorna error o 429 | 🟡 ADVERTENCIA | ☐ |
| 2.3 | No se expone un endpoint que devuelva catálogos de MAL en bulk | 🔴 BLOQUEANTE | ☐ |
| 2.4 | El caché in-memory cubre las llamadas frecuentes a Jikan | 🟡 ADVERTENCIA | ☐ |
| 2.5 | Existe feature flag `ENABLE_JIKAN_ENRICHMENT` en `.env.example` | 🟡 ADVERTENCIA | ☐ |

## Bloque 3 — Seguridad y privacidad

| # | Ítem | Criticidad | Estado |
|---|------|-----------|--------|
| 3.1 | No se envían datos de usuarios (Firebase UID, email) a MangaDex ni Jikan | 🔴 BLOQUEANTE | ✅ 2026-04-08 — PASS (ver [`templates/p0-b7-evidence.md`](./templates/p0-b7-evidence.md)) |
| 3.2 | Las variables de entorno sensibles NO están hardcodeadas (revisar `.env` vs código) | 🔴 BLOQUEANTE | ✅ 2026-04-08 — PASS (ver [`templates/p0-b2-b3-evidence.md`](./templates/p0-b2-b3-evidence.md)) |
| 3.3 | El `.env` de producción no está en el repositorio | 🔴 BLOQUEANTE | ✅ 2026-04-08 — PASS (ver [`templates/p0-b2-b3-evidence.md`](./templates/p0-b2-b3-evidence.md)) |
| 3.4 | Firebase Admin SDK credentials están configuradas via env var, no en el repo | 🔴 BLOQUEANTE | ✅ 2026-04-08 — PASS (ver [`templates/p0-b2-b3-evidence.md`](./templates/p0-b2-b3-evidence.md)) |

## Bloque 4 — Atribución y disclaimers

| # | Ítem | Criticidad | Estado |
|---|------|-----------|--------|
| 4.1 | El README del backend menciona que NO hay afiliación con MangaDex ni MAL | 🟡 ADVERTENCIA | ☐ |
| 4.2 | Existe documentación de cumplimiento en `docs/legal/api-compliance.md` actualizada | 🟡 ADVERTENCIA | ☐ |
| 4.3 | El proceso de takedown (`docs/legal/api-compliance.md §5`) está definido y el equipo lo conoce | 🟡 ADVERTENCIA | ☐ |

## Bloque 5 — Operacional (pre-deploy)

| # | Ítem | Criticidad | Estado |
|---|------|-----------|--------|
| 5.1 | Tests de smoke pasan (`tests/test_app.py`) | 🔴 BLOQUEANTE | ✅ 2026-04-08 — PASS — 8/8 (evidencia: [`templates/p0-b8-evidence.md`](./templates/p0-b8-evidence.md)) |
| 5.2 | Health check `/ping` responde correctamente en el entorno destino | 🔴 BLOQUEANTE | ✅ 2026-04-08 — PASS — HTTP 200 en prod (evidencia: [`templates/p0-b8-evidence.md`](./templates/p0-b8-evidence.md)) |
| 5.3 | Variables de entorno del entorno destino están configuradas en Cloud Run | 🔴 BLOQUEANTE | ✅ 2026-04-08 — PASS (ver [`env-vars-cloudrun-prod.md`](./env-vars-cloudrun-prod.md) y [`templates/p0-b1-evidence-template.md`](./templates/p0-b1-evidence-template.md)) |
| 5.4 | Revisión de logs de las últimas 24 hs — sin errores críticos ni picos de 429 | 🟡 ADVERTENCIA | ☐ |

---

## Resultado final

```
Fecha de release: ___________
Entorno: ☐ staging  ☐ prod
Revisado por: ___________

Bloqueos encontrados (ítems 🔴 en NO):
- [ ] Ninguno → GO ✅
- [ ] (listar si los hay) → NO-GO ❌

Advertencias documentadas:
- (listar ítems 🟡 en NO con justificación)

Decisión final: ☐ GO  ☐ NO-GO
Firma: ___________
```

---

## Planned / TODO — Deuda técnica detectada

> Estos ítems fueron detectados durante auditoría de compliance (2026-04-07).
> **No están implementados aún.** Deben resolverse antes del primer release público.
> No borrar hasta que el ítem correspondiente esté implementado y verificado.

| # | Gap | Ítem relacionado en checklist | Repos | Prioridad |
|---|-----|-------------------------------|-------|-----------|
| P-1 | Exponer `scanlation_group` en respuestas de capítulos (el serializer no lo incluye actualmente) | 1.8 | `Inkscroller_backend` | Media |
| P-2 | Implementar retry con backoff exponencial ante HTTP 429 de MangaDex | 1.6 | `Inkscroller_backend` | Media |
| P-3 | Agregar fallback graceful en cliente Jikan — retornar datos parciales ante error o 429 | 2.2 | `Inkscroller_backend` | Media |
| P-4 | Agregar `ENABLE_JIKAN_ENRICHMENT=true` a `.env.example` y leerlo en el servicio Jikan | 2.5 | `Inkscroller_backend` | Baja |
| P-5 | *(Para Flutter)* Crear pantalla About/Créditos con disclaimer de no afiliación a MangaDex y MAL | 3.4 (flutter) | `inkscroller_flutter` | Media |

---

---

## Tracking P0 — Estado de compliance por ítem (Control Tower V1.0)

> Espejo del tracking de Control Tower V1.0 en Obsidian. La fuente de verdad es Obsidian.
> Mantener sincronizado cuando cambia el estado de un ítem P0 en la fuente.

| Ítem | Descripción | Checklist ref | Estado |
|------|------------|---------------|--------|
| **P0-B1** | **Variables de entorno de producción configuradas en Cloud Run** | **5.3** | **✅ 2026-04-08** — PASS — revisión `00005-mj9` prod (guía: [`docs/release/env-vars-cloudrun-prod.md`](./env-vars-cloudrun-prod.md), evidencia: [`templates/p0-b1-evidence-template.md`](./templates/p0-b1-evidence-template.md)) |
| **P0-B2** | **`.env` de producción NO en el repositorio** | **3.3** | **✅ 2026-04-08** — PASS — auditoría repo + historial git limpio (evidencia: [`templates/p0-b2-b3-evidence.md`](./templates/p0-b2-b3-evidence.md)) |
| **P0-B3** | **Firebase Admin SDK credentials via env var, no hardcodeadas** | **3.4** | **✅ 2026-04-08** — PASS — ApplicationDefault() + os.getenv, sin Certificate(), sin hardcoding (evidencia: [`templates/p0-b2-b3-evidence.md`](./templates/p0-b2-b3-evidence.md)) |
| **P0-B4** | **No se cachean binarios de imágenes (solo URLs)** | **1.2** | **✅ 2026-04-09** — PASS — auditoría estática + 14 tests unitarios (evidencia: [`templates/p0-b4-b5-evidence.md`](./templates/p0-b4-b5-evidence.md)) |
| **P0-B5** | **No existe endpoint de bulk download** | **1.3** | **✅ 2026-04-09** — PASS — inventario completo de 12 rutas auditado + 14 tests unitarios (evidencia: [`templates/p0-b4-b5-evidence.md`](./templates/p0-b4-b5-evidence.md)) |
| **P0-B6** | **Contenido adulto filtrado (`contentRating=[safe,suggestive]`)** | **1.7** | **✅ 2026-04-08** |
| **P0-B7** | **No se envían datos de usuarios a MangaDex ni Jikan** | **3.1** | **✅ 2026-04-08** — PASS — auditoría estática + 7 tests (evidencia: [`templates/p0-b7-evidence.md`](./templates/p0-b7-evidence.md)) |
| **P0-B8** | **Tests de smoke pasan y `/ping` responde en prod** | **5.1 / 5.2** | **✅ 2026-04-08** — PASS — 8/8 smoke tests + `/ping` HTTP 200 en prod (evidencia: [`templates/p0-b8-evidence.md`](./templates/p0-b8-evidence.md)) |

### Cierre P0-B4 — PASS (2026-04-09)

P0-B4 **CERRADO** con auditoría estática completa y tests unitarios formales.

- **Auditoría ejecutada:**
  1. Análisis de `SimpleCache` (`app/core/cache.py`): almacenamiento in-memory `dict[str, tuple[float, Any]]` — sin persistencia a disco, sin Redis, sin almacenamiento externo.
  2. Análisis de `ChapterPagesService.get_pages()` (`app/services/chapter_pages_service.py`): cachea `{"readable": bool, "external": bool, "pages": [str, str, ...]}` — lista de strings URL, no bytes. El cliente MangaDex sólo llama a `/at-home/server/{chapter_id}` para obtener metadata JSON.
  3. `coverUrl` en `MangaService` es un string URL de CDN (`.256.jpg`) — no binario descargado.
  4. DDL SQLite (`app/core/database.py`): 2 tablas (`users`, `reading_preferences`) — cero columnas BLOB/IMAGE/BYTEA.
  5. Búsqueda `StreamingResponse|FileResponse|application/octet-stream` → 0 matches en todo el código.
  6. Búsqueda `b64encode|BytesIO|.read()|open(|write(` en servicios → 0 matches.
- **Tests formales:** `tests/test_image_cache_and_bulk_download.py` — 14/14 PASS (clases `TestNoBinaryCaching` y `TestNoBulkDownloadEndpoint`)
- **Resultado:** El backend actúa como proxy de URLs — obtiene rutas del CDN de MangaDex y las retorna al cliente. Nunca descarga ni almacena contenido binario de imágenes.
- **Evidencia completa:** [`docs/release/templates/p0-b4-b5-evidence.md`](./templates/p0-b4-b5-evidence.md)
- **Rama:** `feature/p0-b4-b5-final-backend-compliance`

### Cierre P0-B5 — PASS (2026-04-09)

P0-B5 **CERRADO** con inventario completo de endpoints auditado y tests unitarios formales.

- **Auditoría ejecutada:**
  1. Inventario completo de 12 rutas API (4 routers): `chapters` (3), `manga` (5), `users` (3), `health` (1).
  2. Ninguna ruta contiene "download" o "bulk" en path ni nombre de función.
  3. Único endpoint relacionado con imágenes `GET /{chapter_id}/pages`: retorna lista de URLs, nunca descarga binarios. El cliente Flutter carga las imágenes directamente desde el CDN de MangaDex.
  4. Búsqueda `zipfile|tarfile|ZipFile|TarFile|shutil.make_archive` en servicios/routers → 0 matches.
  5. El comentario en `MangaDexClient.get_statistics()` confirma diseño explícito: "MangaDex doesn't support bulk".
  6. Todos los endpoints de chapters usan método GET exclusivamente.
- **Tests formales:** `tests/test_image_cache_and_bulk_download.py` — 14/14 PASS (clase `TestNoBulkDownloadEndpoint` con 7 tests específicos)
- **Resultado:** No existe ningún endpoint de bulk download. El inventario de rutas está auditado y los tests protegen contra adición inadvertida.
- **Evidencia completa:** [`docs/release/templates/p0-b4-b5-evidence.md`](./templates/p0-b4-b5-evidence.md)
- **Rama:** `feature/p0-b4-b5-final-backend-compliance`

### Evidencias — P0-B6

- **Qué**: `contentRating=[safe, suggestive]` configurado como parámetro fijo en las queries a MangaDex. Excluye `erotica` y `pornographic` en todos los endpoints de catálogo y búsqueda.
- **Verificación**: Revisión de deploy logs en dev / staging / prod — revision `00006` desplegada en los tres entornos Cloud Run. Smoke test de muestra confirmó `leaks=0` (ningún resultado con rating restringido en respuesta).
- **Fecha de cierre**: 2026-04-08
- **Referencia cruzada**: Control Tower V1.0 (Obsidian) → P0-B6 marcado ✅ 2026-04-08

> ⚠️ **Nota de alcance**: La evidencia registrada corresponde a revisión indicada en tracking y deploy logs. La verificación formal end-to-end con QA automatizado queda pendiente como parte de P0-B8.

### Cierre P0-B1 — PASS (2026-04-08 21:26 UTC)

P0-B1 **CERRADO** con evidencia real de Cloud Run prod.

- **Acciones tomadas:**
  1. Se detectaron gaps: `DEBUG=false` y `CORS_ORIGINS` no configurados explícitamente.
  2. Se ejecutó `gcloud run services update` con `--update-env-vars DEBUG=false,CORS_ORIGINS=https://inkscroller-app.web.app`.
  3. Nueva revisión `inkscroller-backend-00005-mj9` desplegada en `us-central1`.
  4. Se re-ejecutó `./scripts/release/verify_prod_env_cloud_run.sh` → **PASS 5/5**.
- **Evidencia completa:** [`docs/release/templates/p0-b1-evidence-template.md`](./templates/p0-b1-evidence-template.md)
- **Guía de referencia:** [`docs/release/env-vars-cloudrun-prod.md`](./env-vars-cloudrun-prod.md)

### Evidencias registradas — P0-B1

| Fecha | Resultado | Notas |
|-------|-----------|-------|
| 2026-04-08 (primera ejecución) | FAIL | `DEBUG` y `CORS_ORIGINS` ausentes en Cloud Run |
| 2026-04-08 21:26 UTC (cierre) | **PASS ✅** | 5/5 checks — revisión `00005-mj9` prod |

**Env dump final (Cloud Run prod — revisión 00005-mj9):**
```text
FIREBASE_PROJECT_ID=inkscroller-8fa87  ✅
DB_PATH=/app/data/inkscroller.db       ✅
DEBUG=false                            ✅
CORS_ORIGINS=https://inkscroller-app.web.app  ✅ (no wildcard)
/ping → HTTP 200                       ✅
```

### Cierre P0-B2 — PASS (2026-04-08)

P0-B2 **CERRADO** con evidencia de auditoría de repositorio.

- **Auditoría ejecutada:**
  1. `git ls-files --error-unmatch .env` → `.env` no está tracked por git
  2. `git log --all --full-history -- ".env" --oneline` → sin historial — nunca commiteado
  3. `.gitignore` líneas 14-15: `.env` y `.env.*` cubiertos explícitamente
- **Evidencia completa:** [`docs/release/templates/p0-b2-b3-evidence.md`](./templates/p0-b2-b3-evidence.md)
- **Rama:** `feature/p0-b2-b3-secrets-compliance`

### Cierre P0-B3 — PASS (2026-04-08)

P0-B3 **CERRADO** con evidencia de auditoría de código y historial git.

- **Auditoría ejecutada:**
  1. `grep -rn "credentials\.Certificate" app/` → sin resultados — no se usa credencial hardcodeada
  2. `app/core/firebase_auth.py:60` usa `credentials.ApplicationDefault()` — carga desde env
  3. `app/core/config.py:21` usa `os.getenv("FIREBASE_PROJECT_ID", "")` — sin fallback real
  4. `grep -rn "inkscroller-aed59\|inkscroller-8fa87" app/` → sin resultados en código fuente
  5. `git log --all -S '"private_key"'` y `git log --all -S '"client_email"'` → sin historial
  6. `git log --all --full-history -- "*serviceAccount*.json"` → sin historial
- **Flujo certificado:** ADC (Application Default Credentials) en Cloud Run / Workload Identity. Archivo JSON de service account solo para dev local, fuera del repo.
- **Evidencia completa:** [`docs/release/templates/p0-b2-b3-evidence.md`](./templates/p0-b2-b3-evidence.md)
- **Rama:** `feature/p0-b2-b3-secrets-compliance`

### Cierre P0-B7 — PASS (2026-04-08)

P0-B7 **CERRADO** con auditoría estática completa de clientes upstream y tests unitarios formales.

- **Auditoría ejecutada:**
  1. Revisión de firmas de todos los métodos públicos de `MangaDexClient` (8 métodos) — 0 parámetros PII
  2. Revisión de firmas de todos los métodos públicos de `JikanClient` (1 método) — 0 parámetros PII
  3. Revisión de inicialización `httpx.AsyncClient` en `main.py` — sin headers de usuario
  4. Verificación de separación arquitectural: flujo de autenticación (Firebase/SQLite) independiente del flujo de contenido (MangaDex/Jikan)
  5. Revisión de endpoint ad-hoc `/manga/tags` — sin PII en request
- **Tests formales:** `tests/test_upstream_privacy.py` — 7/7 PASS
- **Resultado:** No hay transmisión de Firebase UID, email, tokens ni PII a APIs externas
- **Evidencia completa:** [`docs/release/templates/p0-b7-evidence.md`](./templates/p0-b7-evidence.md)
- **Rama:** `feature/p0-b7-upstream-data-privacy`

### Cierre P0-B8 — PASS (2026-04-08)

P0-B8 **CERRADO** con ejecución real de smoke tests y verificación directa contra producción.

- **Ejecución ejecutada:**
  1. `python -m pytest tests/test_app.py -v` → 8/8 PASS (0.72s) — Python 3.12.10, pytest 9.0.3
  2. `./scripts/release/smoke_prod.sh` → 4/4 PASS contra `https://inkscroller-backend-806863502436.us-central1.run.app`
  3. `curl -is "${PROD_URL}/ping"` → HTTP/2 200 `{"ok":true}` en 0.185s
  4. `GET /manga?limit=1` → HTTP 200 — catálogo MangaDex responde correctamente
  5. `GET /manga/search?q=berserk` → HTTP 200 — búsqueda responde correctamente
  6. `GET /manga/%20invalid-id%20` → HTTP 404 — manejo de errores correcto
- **Script reproducible:** `scripts/release/smoke_prod.sh` — soporta `PROD_URL` y `TIMEOUT` env vars, código de salida 0/1 (integrable en CI)
- **Resultado:** Todos los endpoints públicos responden correctamente en producción. `/ping` confirma uptime.
- **Evidencia completa:** [`docs/release/templates/p0-b8-evidence.md`](./templates/p0-b8-evidence.md)
- **Rama:** `feature/p0-b8-smoke-prod-evidence`

---

## Referencias

- [`docs/legal/api-compliance.md`](../legal/api-compliance.md) — reglas detalladas de cumplimiento
- [`docs/DEPLOYMENT.md`](../DEPLOYMENT.md) — proceso de deploy a Cloud Run
- [`docs/PROJECT_STATUS.md`](../PROJECT_STATUS.md) — estado actual del proyecto
