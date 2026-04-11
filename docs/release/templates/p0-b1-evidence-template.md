# P0-B1 — Plantilla de evidencia operacional (Cloud Run prod)

> **Uso:** completar después de ejecutar verificación real en GCP sobre `prod`.
> **No marcar P0-B1 como cerrado sin esta evidencia.**

---

## Metadatos

- **Fecha (UTC):** `2026-04-08 21:26`
- **Ejecutor:** `agente local (CLI) — claude-sonnet-4-6 / InkScroller SDD apply`
- **Proyecto GCP:** `inkscroller-8fa87`
- **Servicio Cloud Run:** `inkscroller-backend`
- **Región:** `us-central1`
- **Revisión desplegada:** `inkscroller-backend-00005-mj9`

---

## Comandos ejecutados

```bash
# Paso 1 — configurar variables faltantes
gcloud run services update inkscroller-backend \
  --region us-central1 \
  --project inkscroller-8fa87 \
  --update-env-vars DEBUG=false,CORS_ORIGINS=https://inkscroller-app.web.app

# Paso 2 — verificación completa
./scripts/release/verify_prod_env_cloud_run.sh

# Equivalentes manuales
gcloud run services describe inkscroller-backend \
  --region us-central1 \
  --project inkscroller-8fa87 \
  --format="value(spec.template.spec.containers[0].env)"

curl -i https://inkscroller-backend-806863502436.us-central1.run.app/ping
```

---

## Output snippet (textual)

```text
# gcloud output env snippet
{'name': 'FIREBASE_PROJECT_ID', 'value': 'inkscroller-8fa87'};{'name': 'DB_PATH', 'value': '/app/data/inkscroller.db'};{'name': 'DEBUG', 'value': 'false'};{'name': 'CORS_ORIGINS', 'value': 'https://inkscroller-app.web.app'}

# Script verify_prod_env_cloud_run.sh — salida completa
== P0-B1 prod env verification ==
service=inkscroller-backend region=us-central1 project=inkscroller-8fa87

== Cloud Run env dump ==
{'name': 'FIREBASE_PROJECT_ID', 'value': 'inkscroller-8fa87'};{'name': 'DB_PATH', 'value': '/app/data/inkscroller.db'};{'name': 'DEBUG', 'value': 'false'};{'name': 'CORS_ORIGINS', 'value': 'https://inkscroller-app.web.app'}

== Automated checks ==
[OK] FIREBASE_PROJECT_ID present and expected
[OK] DEBUG=false
[OK] CORS_ORIGINS configured and not wildcard
[OK] DB_PATH points to expected path

== Ping check ==
HTTP/2 200
content-type: application/json
date: Wed, 08 Apr 2026 21:26:05 GMT
content-length: 11

{"ok":true}
[OK] /ping returned HTTP 200

== Decision ==
PASS — All checks conform for P0-B1.
```

---

## Criterios evaluados

- [x] `FIREBASE_PROJECT_ID=inkscroller-8fa87`
- [x] `DEBUG=false`
- [x] `CORS_ORIGINS=https://inkscroller-app.web.app` (distinto de `*`)
- [x] `DB_PATH=/app/data/inkscroller.db`
- [x] `curl /ping` devuelve HTTP 200

---

## Resultado

- **Decisión:** `PASS ✅`
- **Gaps detectados en ejecución previa (2026-04-08 — FAIL):**
  - `DEBUG=false` no figuraba explícitamente en Cloud Run
  - `CORS_ORIGINS` no figuraba explícitamente (riesgo de default `*`)
- **Acciones correctivas aplicadas:**
  - Se ejecutó `gcloud run services update` con `--update-env-vars DEBUG=false,CORS_ORIGINS=https://inkscroller-app.web.app`
  - Deploy de nueva revisión `inkscroller-backend-00005-mj9` en `us-central1`
  - Se re-ejecutó `./scripts/release/verify_prod_env_cloud_run.sh` → resultado PASS (5/5 checks)

---

## Trazabilidad

- Checklist relacionado: `docs/release/checklist-legal.md` (Bloque 5, ítem 5.3 / P0-B1)
- Guía de verificación: `docs/release/env-vars-cloudrun-prod.md`
- Rama de cierre: `feature/p0-b1-prod-env-pass-evidence`
- Fecha de cierre P0-B1: `2026-04-08`
