# P0-B1 — Guía de verificación: Variables de entorno en Cloud Run (prod)

> **Ítem:** P0-B1 — Variables de entorno de producción configuradas en Cloud Run  
> **Checklist ref:** `docs/release/checklist-legal.md` § 5.3  
> **Estado actual:** ⏳ Pendiente de ejecución manual  
> **Fecha de creación:** 2026-04-08  

---

## Por qué es P0 bloqueante

Si las variables de entorno no están configuradas en Cloud Run prod, el backend arranca
con valores vacíos o por defecto:

- `FIREBASE_PROJECT_ID=""` → Firebase Admin SDK falla al inicializar → **todas las rutas autenticadas retornan 401/500**
- `CORS_ORIGINS="*"` (default) → expone la API a cualquier origen en producción
- `DB_PATH="./inkscroller.db"` → la base de datos puede perderse entre revisiones de Cloud Run (el filesystem de contenedores es efímero)

No se puede cerrar P0-B1 sin acceso a la consola de GCP/Cloud Run. Esta guía proporciona
los comandos exactos para que el operador los ejecute manualmente.

---

## Variables requeridas en Cloud Run prod

| Variable | ¿Requerida? | Valor esperado en prod | Fuente |
|----------|-------------|------------------------|--------|
| `FIREBASE_PROJECT_ID` | ✅ BLOQUEANTE | `inkscroller-8fa87` | Firebase Console → Project settings |
| `GOOGLE_APPLICATION_CREDENTIALS` | ❌ No en Cloud Run | — | Usar Workload Identity en GCP; no configurar en Cloud Run |
| `DEBUG` | ✅ | `false` | Hardcoded para prod |
| `CORS_ORIGINS` | ✅ | URL(s) del frontend Flutter pro (no `*`) | A confirmar con equipo |
| `MANGADEX_BASE_URL` | 🟡 Opcional | `https://api.mangadex.org` | Default válido |
| `JIKAN_BASE_URL` | 🟡 Opcional | `https://api.jikan.moe/v4` | Default válido |
| `CACHE_TTL_SECONDS` | 🟡 Opcional | `300` (5 min) | Default válido |
| `DB_PATH` | ✅ | `/app/data/inkscroller.db` o ruta en volumen montado | Confirmar con arquitectura de persistencia |

> **Nota sobre `GOOGLE_APPLICATION_CREDENTIALS`:** En Cloud Run con Workload Identity
> habilitada, el SDK de Firebase Admin usa la service account del servicio directamente —
> no se necesita un archivo JSON. Si Workload Identity **no** está activa, se debe montar
> el JSON via Secret Manager y configurar esta variable.

---

## Comandos de verificación (ejecutar tú)

### Opción rápida reproducible (script)

```bash
./scripts/release/verify_prod_env_cloud_run.sh
```

Si el entorno local no tiene `gcloud` autenticado o no tiene permisos al proyecto prod,
el script termina en estado `MANUAL PENDING` y deja comandos copy-paste + expected output
para ejecutar desde una terminal con acceso real.

### 1. Ver todas las env vars actuales en Cloud Run prod

```bash
gcloud run services describe inkscroller-backend \
  --region us-central1 \
  --project inkscroller-8fa87 \
  --format="value(spec.template.spec.containers[0].env)"
```

Alternativa en formato YAML completo (más legible):

```bash
gcloud run services describe inkscroller-backend \
  --region us-central1 \
  --project inkscroller-8fa87 \
  --format yaml | grep -A 50 "env:"
```

### 2. Verificar variables individualmente

```bash
# Verificar FIREBASE_PROJECT_ID
gcloud run services describe inkscroller-backend \
  --region us-central1 \
  --project inkscroller-8fa87 \
  --format="value(spec.template.spec.containers[0].env)" \
  | grep FIREBASE_PROJECT_ID

# Verificar DEBUG (debe ser false en prod)
gcloud run services describe inkscroller-backend \
  --region us-central1 \
  --project inkscroller-8fa87 \
  --format="value(spec.template.spec.containers[0].env)" \
  | grep DEBUG

# Verificar CORS_ORIGINS (no debe ser "*" en prod)
gcloud run services describe inkscroller-backend \
  --region us-central1 \
  --project inkscroller-8fa87 \
  --format="value(spec.template.spec.containers[0].env)" \
  | grep CORS_ORIGINS
```

### 3. Configurar variables faltantes (si la verificación muestra vacíos)

```bash
gcloud run services update inkscroller-backend \
  --region us-central1 \
  --project inkscroller-8fa87 \
  --set-env-vars \
    FIREBASE_PROJECT_ID=inkscroller-8fa87,\
    DEBUG=false,\
    MANGADEX_BASE_URL=https://api.mangadex.org,\
    JIKAN_BASE_URL=https://api.jikan.moe/v4,\
    CACHE_TTL_SECONDS=300,\
    DB_PATH=/app/data/inkscroller.db
```

> ⚠️ **No incluir `GOOGLE_APPLICATION_CREDENTIALS` en Cloud Run** si usás Workload Identity.
> Si necesitás credenciales via JSON, montarlas con Secret Manager:
> ```bash
> gcloud run services update inkscroller-backend \
>   --region us-central1 \
>   --project inkscroller-8fa87 \
>   --set-secrets GOOGLE_APPLICATION_CREDENTIALS=firebase-sa-key:latest
> ```

### 4. Smoke test post-configuración

```bash
# Health check
curl -s https://inkscroller-backend-806863502436.us-central1.run.app/ping

# Debe retornar: {"status": "ok"} o similar

# Verificar que CORS no está abierto en prod (el header solo debe aceptar origen prod)
curl -I -H "Origin: https://example.com" \
  https://inkscroller-backend-806863502436.us-central1.run.app/ping \
  | grep -i "access-control-allow-origin"
```

---

## Checklist de cierre manual de P0-B1

Ejecutar en orden. Marcar cada ítem solo cuando la salida de los comandos lo confirme.

```
[ ] 1. `gcloud run services describe` muestra FIREBASE_PROJECT_ID=inkscroller-8fa87
[ ] 2. `gcloud run services describe` muestra DEBUG=false
[ ] 3. `gcloud run services describe` muestra CORS_ORIGINS ≠ "*" (o se acepta "*" con justificación documentada)
[ ] 4. `curl /ping` devuelve 200 OK en prod
[ ] 5. Ninguna variable de entorno sensible está hardcodeada en el código fuente
       (Verificar: `grep -r "inkscroller-8fa87\|FIREBASE" app/ --include="*.py"`)
[ ] 6. `.env` de prod NO está en el repositorio
       (Verificar: `git log --all --full-history -- .env | head -5` → debe estar vacío o gitignored)

Fecha de verificación: ___________
Ejecutado por: ___________
```

---

## Qué falta para cerrar P0-B1

P0-B1 **no puede cerrarse localmente** porque requiere acceso a la consola de GCP con
permisos sobre el proyecto `inkscroller-8fa87`. Pasos pendientes:

1. **Ejecutar los comandos de verificación** del bloque anterior sobre el entorno prod.
2. **Corregir** cualquier variable faltante o incorrecta con `gcloud run services update`.
3. **Documentar** la evidencia (output de `gcloud run services describe`) en un comment
   en el issue o en este archivo bajo la sección "Evidencias de cierre".
4. **Actualizar** el estado en `checklist-legal.md` § Tracking P0 de `⏳ pendiente` a `✅ AAAA-MM-DD`.

---

## Evidencias de cierre

> Usar esta plantilla: [`docs/release/templates/p0-b1-evidence-template.md`](./templates/p0-b1-evidence-template.md)
> *(Completar cuando se ejecuten los comandos de verificación con acceso real a GCP)*

### Ejecución más reciente (operacional)

- **Fecha:** 2026-04-08
- **Ejecutor:** agente local (CLI)
- **Resultado:** **FAIL** (P0-B1 sigue pendiente)
- **Resumen de salida real:**
  - `FIREBASE_PROJECT_ID=inkscroller-8fa87` ✅
  - `DB_PATH=/app/data/inkscroller.db` ✅
  - `DEBUG=false` no aparece explícitamente en env vars ❌
  - `CORS_ORIGINS` no aparece explícitamente en env vars (riesgo de default `*`) ❌
  - `GET /ping` retorna `HTTP 200` ✅

> Hasta que `DEBUG` y `CORS_ORIGINS` queden explícitos en Cloud Run prod y se vuelva a ejecutar
> la verificación con output documentado en plantilla, **P0-B1 no se marca como ✅**.

```
Fecha: ___________
Ejecutado por: ___________
Output de gcloud run services describe (fragmento env):
---
(pegar output aquí)
---
Decisión: ☐ CONFORME  ☐ NO CONFORME (listar gaps)
```

---

## Referencias cruzadas

- [`docs/DEPLOYMENT.md`](../DEPLOYMENT.md) — proceso completo de deploy y URLs de Cloud Run
- [`docs/release/checklist-legal.md`](./checklist-legal.md) — checklist de compliance y tracking P0
- [`docs/release/templates/p0-b1-evidence-template.md`](./templates/p0-b1-evidence-template.md) — formato estándar de evidencia para P0-B1
- [`.env.example`](../../.env.example) — referencia de variables de entorno del backend
- [`app/core/config.py`](../../app/core/config.py) — código que lee las env vars en runtime
