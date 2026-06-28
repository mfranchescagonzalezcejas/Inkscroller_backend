# Deployment — InkScroller Backend

> **Target:** Railway (3 environments)  
> **Last updated:** 2026-06-27

---

## Live URLs

Use the custom API domains for clients and smoke checks:

| Environment | Railway Environment | Firebase Project | API base URL | Health check |
|------------|---------------------|------------------|--------------|--------------|
| **dev** | `dev` | `inkscroller-aed59` | `https://api.dev.inkscroller.devdigi.dev` | `https://api.dev.inkscroller.devdigi.dev/ping` |
| **staging** | `staging` | `inkscroller-stg` | `https://api.stg.inkscroller.devdigi.dev` | `https://api.stg.inkscroller.devdigi.dev/ping` |
| **prod** | `production` | `inkscroller-8fa87` | `https://api.inkscroller.devdigi.dev` | `https://api.inkscroller.devdigi.dev/ping` |

Production and development `/ping` have been verified online and return `200 {"ok": true}`. The staging custom domain is reserved/configured for the staging environment and should be verified after that environment is deployed/routed.

The existing portfolio stays on `https://devdigi.dev` and `https://www.devdigi.dev`; those hostnames are not routed to Railway.

---

## Runtime model

- One Railway project hosts the backend service plus one Postgres service per environment.
- Railway serves each backend environment on port `8080`.
- `dev` and `staging` track the `develop` branch.
- `production` tracks the `main` branch.
- Firebase remains split by environment (`inkscroller-aed59`, `inkscroller-stg`, `inkscroller-8fa87`).
- Cloudflare DNS hosts the CNAME and TXT verification records for the Railway custom domains.

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

Railway deploys automatically from the connected GitHub mirror branch.

Canonical flow:

1. Changes are developed/reviewed in **GitLab** (Jira + Merge Requests)
2. Approved branch state is mirrored to **GitHub**
3. **Railway** autodeploys from GitHub (`develop` for dev/staging, `main` for production)

- `dev` / `staging` use the `develop` branch
- `production` uses the `main` branch

GitHub Actions validates mirror state; Railway remains the runtime deployment authority.

### Per-environment Railway setup

For each environment configure:

- `ENVIRONMENT` (`development`, `staging`, or `production`)
- `FIREBASE_PROJECT_ID`
- `FIREBASE_SERVICE_ACCOUNT_JSON_BASE64`
- `DATABASE_URL=${{Postgres.DATABASE_URL}}`
- `CORS_ORIGINS`
- optional runtime flags (`DEBUG`, `CACHE_TTL_SECONDS`, etc.)

### Custom domains and DNS

Each Railway environment has its own custom API hostname:

| Environment | Custom domain | DNS owner | Railway port |
|-------------|---------------|-----------|--------------|
| dev | `api.dev.inkscroller.devdigi.dev` | Cloudflare | `8080` |
| staging | `api.stg.inkscroller.devdigi.dev` | Cloudflare | `8080` |
| prod | `api.inkscroller.devdigi.dev` | Cloudflare | `8080` |

Cloudflare contains the Railway-provided CNAME records plus TXT verification records. Keep the portfolio records for `devdigi.dev` and `www.devdigi.dev` separate from the API records; the portfolio remains outside Railway.

Client applications should use the custom API base URL for their target environment. `CORS_ORIGINS` should list the frontend origins allowed to call the API; it should not be set to the API hostname just because the API hostname changed.

Production-like environments reject blank `CORS_ORIGINS` and reject `CORS_ORIGINS=*` because the API enables credentialed CORS for authenticated routes. The production-like safety check is enabled when any runtime environment variable (`ENVIRONMENT`, `RAILWAY_ENVIRONMENT_NAME`, or `RAILWAY_ENVIRONMENT`) is set to `production`, `prod`, `staging`, or `stage`, so a stale local `ENVIRONMENT=development` cannot override Railway production/staging. Use explicit trusted frontend origins instead, for example:

```env
ENVIRONMENT=production
CORS_ORIGINS=https://inkscroller-app.web.app,https://devdigi.dev,https://www.devdigi.dev
```

For local development only, wildcard CORS can still be requested explicitly with `ENVIRONMENT=development` and `CORS_ORIGINS=*`.

Current online verification: production and development return `200 {"ok": true}` on `/ping`; staging is not yet verified online and must be checked after staging deploy/routing.

Quick checks:

```bash
curl -fsS https://api.inkscroller.devdigi.dev/ping
curl -fsS https://api.dev.inkscroller.devdigi.dev/ping
curl -fsS https://api.stg.inkscroller.devdigi.dev/ping  # verify after staging deploy/routing
```

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
| `ENVIRONMENT` | — | `development` | Runtime environment; production-like values reject unsafe CORS together with Railway runtime env vars |
| `FIREBASE_PROJECT_ID` | ✅ | — | Firebase project ID |
| `FIREBASE_SERVICE_ACCOUNT_JSON_BASE64` | ✅ (Railway) | — | Base64-encoded Firebase service account JSON |
| `GOOGLE_APPLICATION_CREDENTIALS` | ✅ (local) | — | Path to service account JSON for local runs |
| `DATABASE_URL` | ✅ (Railway) | — | PostgreSQL connection string from Railway Postgres |
| `DB_PATH` | — | `./inkscroller.db` | SQLite path for local fallback only |
| `CORS_ORIGINS` | — | explicit frontend origins | Comma-separated allowed frontend origins; `*` is local-development only |
| `CACHE_TTL_SECONDS` | — | `300` | In-memory cache TTL |
| `MANGADEX_BASE_URL` | — | `https://api.mangadex.org` | MangaDex base URL |
| `JIKAN_BASE_URL` | — | `https://api.jikan.moe/v4` | Jikan base URL |

### Environment verification

Before closing a release, confirm in Railway logs and via the custom domain that:

- `Firebase Admin SDK initialized (project: inkscroller-8fa87)`
- `PostgreSQL pool ready via DATABASE_URL`
- `/ping` responds with `200 {"ok": true}` on the target custom API domain
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

## Scope note

This repository uses Railway as the active runtime and deployment path for all releases.
GitHub acts as deployment mirror; GitLab remains the primary collaboration workflow.

---

## Local Firebase Setup (for `/users/me` endpoints)

1. Download service account JSON from Firebase Console → Project Settings → Service Accounts
2. Save it **outside the repo** (e.g. `~/.ssh/inkscroller-firebase-key.json`)
3. Add to `.env`:

```env
FIREBASE_PROJECT_ID=inkscroller-aed59
GOOGLE_APPLICATION_CREDENTIALS=<path-outside-repo>/firebase-dev-service-account.json
```

> ⚠️ **Never commit the service account JSON.** It's covered by `.gitignore`.
