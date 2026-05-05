# TASK-027

Smoke test marker for release-flow validation.

## Active path

- Active production smoke script: `scripts/release/smoke_prod.sh`
- Active production target: Railway (`https://inkscrollerbackend-pro.up.railway.app`)
- Override target when needed with `PROD_URL=... ./scripts/release/smoke_prod.sh`

## Legacy note

Historical Cloud Run evidence remains under `docs/release/legacy/cloud-run/`.
