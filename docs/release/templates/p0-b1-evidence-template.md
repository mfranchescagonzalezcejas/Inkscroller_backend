# P0-B1 — Plantilla de evidencia operacional (Cloud Run prod)

> **Uso:** completar después de ejecutar verificación real en GCP sobre `prod`.
> **No marcar P0-B1 como cerrado sin esta evidencia.**

---

## Metadatos

- **Fecha (UTC):** `AAAA-MM-DD HH:mm`
- **Ejecutor:** `nombre/apellido o usuario`
- **Proyecto GCP:** `inkscroller-8fa87`
- **Servicio Cloud Run:** `inkscroller-backend`
- **Región:** `us-central1`

---

## Comandos ejecutados

```bash
gcloud run services describe inkscroller-backend \
  --region us-central1 \
  --project inkscroller-8fa87 \
  --format="value(spec.template.spec.containers[0].env)"

curl -i https://inkscroller-backend-806863502436.us-central1.run.app/ping
```

---

## Output snippet (pegar textual)

```text
# gcloud output env snippet
(pegar acá)

# curl /ping output snippet
(pegar acá)
```

---

## Criterios evaluados

- [ ] `FIREBASE_PROJECT_ID=inkscroller-8fa87`
- [ ] `DEBUG=false`
- [ ] `CORS_ORIGINS` distinto de `*` (o justificación explícita)
- [ ] `DB_PATH=/app/data/inkscroller.db` (o ruta persistente aprobada)
- [ ] `curl /ping` devuelve HTTP 200

---

## Resultado

- **Decisión:** `PASS` / `FAIL`
- **Gaps detectados:**
  - `(si aplica, listar)`
- **Acciones correctivas:**
  - `(si aplica, listar)`

---

## Trazabilidad

- Checklist relacionado: `docs/release/checklist-legal.md` (Bloque 5, ítem 5.3 / P0-B1)
- Guía de verificación: `docs/release/env-vars-cloudrun-prod.md`
