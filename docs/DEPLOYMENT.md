# Deployment — InkScroller Backend

> **Target:** Railway (3 environments)  
> **Last updated:** 2026-04-21

---

## Live URLs

| Environment | Railway Environment | Firebase Project | Backend URL |
|------------|---------------------|------------------|-------------|
| **dev** | `dev` | `inkscroller-aed59` | `https://inkscrollerbackend-dev.up.railway.app` |
| **staging** | `staging` | `inkscroller-stg` | `https://inkscrollerbackend-stg.up.railway.app` |
| **prod** | `production` | `inkscroller-8fa87` | `https://inkscrollerbackend-pro.up.railway.app` |

---

## Runtime model

- One Railway project hosts the backend service plus one Postgres service per environment.
- `dev` and `staging` track the `develop` branch.
- `production` tracks the `main` branch.
- Firebase remains split by environment (`inkscroller-aed59`, `inkscroller-stg`, `inkscroller-8fa87`).

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

Railway injects `PORT` dynamically; the Dockerfile already respects `${PORT:-8080}`.

---

## Deploy to Railway

Railway deploys automatically from the connected GitHub branch.

- `dev` / `staging` use the `develop` branch
- `production` uses the `main` branch

GitHub Actions validates `main`; Railway handles the actual deployment.

### Per-environment Railway setup

For each environment configure:

- `FIREBASE_PROJECT_ID`
- `FIREBASE_SERVICE_ACCOUNT_JSON_BASE64`
- `DATABASE_URL=${{Postgres.DATABASE_URL}}`
- `CORS_ORIGINS`
- optional runtime flags (`DEBUG`, `CACHE_TTL_SECONDS`, etc.)

---

## Multiple Flavor Support

One backend image serves all flavors — change environment variables per Railway environment:

| Flavor | Railway env | `FIREBASE_PROJECT_ID` |
|--------|-------------|----------------------|
| dev | `dev` | `inkscroller-aed59` |
| staging | `staging` | `inkscroller-stg` |
| prod | `production` | `inkscroller-8fa87` |

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FIREBASE_PROJECT_ID` | ✅ | — | Firebase project ID |
| `FIREBASE_SERVICE_ACCOUNT_JSON_BASE64` | ✅ (Railway) | — | Base64-encoded Firebase service account JSON |
| `GOOGLE_APPLICATION_CREDENTIALS` | ✅ (local) | — | Path to service account JSON for local runs |
| `DATABASE_URL` | ✅ (Railway) | — | PostgreSQL connection string from Railway Postgres |
| `DB_PATH` | — | `./inkscroller.db` | SQLite path for local fallback only |
| `CORS_ORIGINS` | — | `*` | Comma-separated allowed origins |
| `CACHE_TTL_SECONDS` | — | `300` | In-memory cache TTL |
| `MANGADEX_BASE_URL` | — | `https://api.mangadex.org` | MangaDex base URL |
| `JIKAN_BASE_URL` | — | `https://api.jikan.moe/v4` | Jikan base URL |

### Production verification

Before closing a production release, confirm in Railway logs that:

- `Firebase Admin SDK initialized (project: inkscroller-8fa87)`
- `PostgreSQL pool ready via DATABASE_URL`
- `/ping` responds with `200`
- authenticated `/users/*` routes return `200` with a production Firebase token

---

## Known Gotchas

| Issue | Solution |
|-------|---------|
| Railway injects `PORT` | Dockerfile already uses `${PORT:-8080}` |
| Missing Firebase secret falls back to ADC and breaks auth | Ensure `FIREBASE_SERVICE_ACCOUNT_JSON_BASE64` is set per environment |
| Wrong Firebase project per environment causes 401s | Match `FIREBASE_PROJECT_ID` and service-account JSON to the target environment |
| SQLite is not the production path anymore | Use Railway Postgres via `DATABASE_URL` |

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
