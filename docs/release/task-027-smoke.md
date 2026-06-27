# TASK-027

Smoke test marker for release-flow validation.

## Active path

- Active production smoke script: `scripts/release/smoke_prod.sh`
- Active production target: Railway custom API domain (`https://api.inkscroller.devdigi.dev`)
- Run against the custom domain with `PROD_URL=https://api.inkscroller.devdigi.dev ./scripts/release/smoke_prod.sh`

## Nota

La validación de smoke para releases se mantiene únicamente en Railway.
