# Deployment — InkScroller Backend

> **Target:** Google Cloud Run (3 environments)  
> **Last updated:** 2026-04-06

---

## Live URLs

| Environment | GCP Project | Firebase Project | Cloud Run URL |
|------------|-------------|------------------|---------------|
| **dev** | `inkscroller-aed59` | `inkscroller-aed59` | `https://inkscroller-backend-708894048002.us-central1.run.app` |
| **staging** | `inkscroller-stg` | `inkscroller-stg` | `https://inkscroller-backend-391760656950.us-central1.run.app` |
| **prod** | `inkscroller-8fa87` | `inkscroller-8fa87` | `https://inkscroller-backend-806863502436.us-central1.run.app` |

---

## Docker

```bash
# Build
docker build -t inkscroller-backend:latest .

# Run locally
docker run -p 8080:8080 \
  -e FIREBASE_PROJECT_ID=inkscroller-aed59 \
  -e GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/firebase-key.json \
  inkscroller-backend:latest
```

> Cloud Run uses port **8080** (not 8000). The Dockerfile already exposes 8080.

---

## Deploy to Cloud Run

```bash
# 1. Build and push image to GCR (example: dev)
docker build -t gcr.io/inkscroller-aed59/inkscroller-backend:latest .
docker push gcr.io/inkscroller-aed59/inkscroller-backend:latest

# 2. Deploy
gcloud run deploy inkscroller-backend \
  --image gcr.io/inkscroller-aed59/inkscroller-backend:latest \
  --platform managed \
  --region us-central1 \
  --project inkscroller-aed59 \
  --allow-unauthenticated \
  --set-env-vars FIREBASE_PROJECT_ID=inkscroller-aed59,DB_PATH=/app/data/inkscroller.db
```

For staging/prod, replace `inkscroller-aed59` with `inkscroller-stg` or `inkscroller-8fa87`.

---

## Multiple Flavor Support

One backend image serves all flavors — just change `FIREBASE_PROJECT_ID` at deploy time:

| Flavor | GCP Project | `FIREBASE_PROJECT_ID` |
|--------|-------------|----------------------|
| dev | `inkscroller-aed59` | `inkscroller-aed59` |
| staging | `inkscroller-stg` | `inkscroller-stg` |
| prod | `inkscroller-8fa87` | `inkscroller-8fa87` |

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FIREBASE_PROJECT_ID` | ✅ | — | Firebase project ID |
| `GOOGLE_APPLICATION_CREDENTIALS` | ✅ (local) | — | Path to service account JSON (not needed on Cloud Run with Workload Identity) |
| `DB_PATH` | — | `./inkscroller.db` | SQLite database path |
| `CORS_ORIGINS` | — | `*` | Comma-separated allowed origins |
| `CACHE_TTL_SECONDS` | — | `300` | In-memory cache TTL |
| `MANGADEX_BASE_URL` | — | `https://api.mangadex.org` | MangaDex base URL |
| `JIKAN_BASE_URL` | — | `https://api.jikan.moe/v4` | Jikan base URL |

### Verificación operacional de env vars en prod (P0-B1)

Antes de marcar release en **GO** para producción, ejecutar y adjuntar evidencia:

```bash
./scripts/release/verify_prod_env_cloud_run.sh
```

- Si no hay acceso real a `gcloud`/proyecto prod, registrar el estado como **MANUAL PENDING**.
- No marcar P0-B1 como `✅` en `docs/release/checklist-legal.md` sin output real de `gcloud run services describe`.
- Completar evidencia en: `docs/release/templates/p0-b1-evidence-template.md`.

---

## Known Gotchas

| Issue | Solution |
|-------|---------|
| Cloud Run expects port 8080 | Dockerfile already exposes 8080; uvicorn binds to `0.0.0.0:8080` |
| Cold starts take 10–30 s | Flutter client uses 60 s Dio timeout |
| `gcr.io` vs Artifact Registry | `gcr.io` (Container Registry legacy) doesn't require billing; Artifact Registry does |
| Fish shell PATH | `fish_add_path ~/google-cloud-sdk/bin` (not `export PATH=...`) |

---

## Local Firebase Setup (for `/users/me` endpoints)

1. Download service account JSON from Firebase Console → Project Settings → Service Accounts
2. Save it **outside the repo** (e.g. `~/.ssh/inkscroller-firebase-key.json`)
3. Add to `.env`:

```env
FIREBASE_PROJECT_ID=inkscroller-aed59
GOOGLE_APPLICATION_CREDENTIALS=/home/<user>/.ssh/inkscroller-firebase-key.json
```

> ⚠️ **Never commit the service account JSON.** It's covered by `.gitignore`.

---

## Installing Prerequisites (Ubuntu 24.04)

### Docker

```bash
sudo apt update && sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update && sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```

### Google Cloud CLI

```bash
curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-496.0.0-linux-x86_64.tar.gz
tar -xf google-cloud-cli-496.0.0-linux-x86_64.tar.gz
./google-cloud-sdk/install.sh
# Fish shell:
fish_add_path ~/google-cloud-sdk/bin
```
