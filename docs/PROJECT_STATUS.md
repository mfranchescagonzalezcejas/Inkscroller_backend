# InkScroller Backend — Project Status

> **Cross-repo source of truth:** Obsidian under `1-PROJECTS/InkScroller/`
> **Repo role:** backend implementation status for the FastAPI service
> **Last updated:** 2026-04-08 (Sprint 3 active — compliance/release synchronization with Obsidian)

---

## 1. Purpose of this document

This file is the **backend-side status mirror** of the product's shared planning.

- Use **Obsidian** for product planning, sprint tracking, tasks, and cross-repo decisions
- Use this file for **backend implementation reality**
- If this file disagrees with Obsidian, update one of them immediately

---

## 2. Current phase

| Field | Value |
|------|-------|
| Product phase | Phase 5 — Identity & Adaptive Reading |
| Backend phase state | **Sprint 3 active — compliance/release support + hardening** |
| Current sprint mirror | Sprint 3 — **active** |
| Repo status | Active |
| Current branch | `develop` |
| Docker image | ✅ Created (`Dockerfile`, `.dockerignore`) |

---

### Cloud Run Deployments (Multi-project)

| Environment | GCP Project | Firebase Project | Cloud Run URL |
|------------|-------------|------------------|---------------|
| **dev** | `inkscroller-aed59` | `inkscroller-aed59` | `https://inkscroller-backend-708894048002.us-central1.run.app` |
| **staging** | `inkscroller-stg` | `inkscroller-stg` | `https://inkscroller-backend-391760656950.us-central1.run.app` |
| **prod** | `inkscroller-8fa87` | `inkscroller-8fa87` | `https://inkscroller-backend-806863502436.us-central1.run.app` |

---

## 3. Completed in this repo

### M1 — Backend auth foundation

- Firebase Admin SDK for ID token verification
- SQLite persistence with `aiosqlite`
- `GET /users/me` — creates user row if not exists
- `GET /users/me/preferences` — reading preferences
- `PUT /users/me/preferences` — update `defaultReaderMode`, `defaultLanguage`
- Auth/user tests exist

### Public API already operational

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ping` | GET | Health check |
| `/docs` | — | Swagger UI |
| `/openapi.json` | — | OpenAPI spec |
| `/manga` | GET | Paginated manga list with filters |
| `/manga/search` | GET | Search by query (max 5 results) |
| `/manga/{id}` | GET | Manga detail with MangaDex + Jikan enrichment |
| `/chapters/manga/{id}` | GET | Chapter list filtered by language |
| `/chapters/{id}/pages` | GET | Page URLs via MangaDex@Home |

### Infrastructure

- Structured logging with configurable level
- CORS configurable via env vars
- Retry with exponential backoff on upstream calls
- In-memory cache with TTL (5 min default)
- Global exception handlers
- Dependency injection factories
- Smoke tests with DI overrides
- **Docker** — Multi-stage Dockerfile for production deployment

### Repo hygiene

- Tracked virtualenv files removed from git
- SQLite runtime artifacts ignored (`*.db-shm`, `*.db-wal`)
- `.env.example` with all required variables documented

---

## 4. Remaining work in this repo

| Item | Priority | Notes |
|------|----------|-------|
| `BTASK-003` Deploy strategy | High | ✅ Complete — Google Cloud (Cloud Run) |
| `BTASK-010` Sprint 3 compliance pack | High | Active — backend support for release/legal evidence tracking |
| P0-B1..P0-B8 compliance closure | High | Active — sync evidence with Control Tower before release gate |
| Firebase env setup for live validation | Medium | `FIREBASE_PROJECT_ID` placeholder still in `.env` |
| MangaDex language configurable by user preference | Medium | Currently hardcoded to `en` |
| End-to-end validation with Flutter | Low | Frontend M3 is now complete, ready for testing |

### Sprint 3 — Compliance evidence focus (Control Tower alignment)

- Sprint 3 is currently active for backend-side compliance/release readiness support.
- Prioridad operativa: `BTASK-010` + cierre de ítems `P0-B1..P0-B8` con evidencia verificable.
- Regla documental: no marcar ítems P0 como cerrados sin evidencia explícita en checklist/status espejo.

---

## 5. Cross-repo dependencies

### Provided to frontend

| Contract | Status | Notes |
|---------|--------|-------|
| Public manga catalogue/search/detail/chapter | ✅ Available | Confirmed working locally |
| `/users/me` | ✅ Implemented | Requires Firebase env for live validation |
| `/users/me/preferences` | ✅ Implemented | Required by frontend M3 |
| Firebase token verification | ✅ Implemented | Requires backend env for live validation |

### Depends on frontend for full product value

| Topic | Dependency type | Notes |
|------|-----------------|-------|
| Profile UI consumption | soft | Backend is ready, frontend M3 is now complete |
| Preferences UI / local-first chain | soft | Frontend has local-first with offline sync |
| Adaptive reader behavior | soft | Backend exposes preference surface; frontend consumes it |

---

## 6. Deployment

### ✅ Chosen Target: Google Cloud (Cloud Run)

**Why Google Cloud:**
- Same project ID as Firebase (`inkscroller-aed59`)
- Cloud Run free tier: 2M requests/mes
- Native Firebase integration
- SQLite sufficient for current + future (10-20MB data)
- No card required for free tier

### Alternativas considered

| Platform | Pros | Cons |
|----------|------|------|
| **Oracle Cloud Always Free** | 200GB disk | Requires card verification, capacity issues |
| **Koyeb** | Very easy setup | No persistent storage (loses data on redeploy) |

### Docker Image

```bash
# Build
docker build -t inkscroller-backend:latest .

# Run locally
docker run -p 8000:8000 \
  -e FIREBASE_PROJECT_ID=inkscroller-aed59 \
  -e DB_PATH=/app/data/inkscroller.db \
  inkscroller-backend:latest
```

### Environment Variables Required

| Variable | Required | Notes |
|----------|----------|-------|
| `FIREBASE_PROJECT_ID` | Yes | Your Firebase project ID |
| `DB_PATH` | No | Default: `./inkscroller.db` |
| `CORS_ORIGINS` | No | Comma-separated, default: `*` |
| `CACHE_TTL_SECONDS` | No | Default: `300` |
| `MANGADEX_BASE_URL` | No | Default: `https://api.mangadex.org` |
| `JIKAN_BASE_URL` | No | Default: `https://api.jikan.moe/v4` |

### Alternative: Koyeb (if Oracle Cloud is too complex)

- Free tier: 1 service, no persistent storage
- Acceptable for current (~12KB SQLite) but NOT for future (favorites/progress need persistent storage)
- Cold starts: ~30s on first request

### Google Cloud Deployment Steps

```bash
# 1. Install Docker and gcloud CLI (see below)

# 2. Configure gcloud
gcloud init
gcloud auth login

# 3. Build and push to GCR
docker build -t gcr.io/inkscroller-aed59/inkscroller-backend:latest .
docker push gcr.io/inkscroller-aed59/inkscroller-backend:latest

# 4. Deploy to Cloud Run
gcloud run deploy inkscroller-backend \
  --image gcr.io/inkscroller-aed59/inkscroller-backend:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars FIREBASE_PROJECT_ID=inkscroller-aed59,DB_PATH=/app/data/inkscroller.db
```

### Install Docker (Ubuntu 24.04)

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg lsb-release

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
sudo systemctl start docker
```

### Install Google Cloud CLI

```bash
curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-496.0.0-linux-x86_64.tar.gz
tar -xf google-cloud-cli-496.0.0-linux-x86_64.tar.gz
./google-cloud-sdk/install.sh
echo 'export PATH="$HOME/google-cloud-sdk/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

---

## 7. Known blockers / validation gaps

| Topic | Type | Impact |
|------|------|--------|
| Staging `/users/me` fails for new users | validation | Expected — user doesn't exist in staging Firebase project yet |
| Deploy target | deploy | ✅ SOLVED — Google Cloud (Cloud Run), tested on physical device 2026-04-06 |

---

## 8. Source-of-truth links

### Obsidian

- `InkScroller/Gestión/Gestión del proyecto.md`
- `InkScroller/Gestión/Matriz de dependencias cross-repo.md`
- `InkScroller/Gestión/Protocolo de sincronización cross-repo.md`
- `InkScroller/Sprints/Sprint 2.md`
- `InkScroller/Tareas/_Índice de tareas.md`
- `InkScroller/QA/_Índice de QA.md`

### Repo docs

- `README.md`
- `docs/PROJECT_STATUS.md`

---

## 8. Update rules

Update this file when:

1. backend milestone state changes
2. deploy strategy changes
3. protected endpoints become live-testable in local/staging environments
4. frontend/backend contract changes in a way that affects sequencing

Do **not** use this file as the main task tracker. That lives in Obsidian.
