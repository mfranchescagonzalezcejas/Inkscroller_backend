# Security Public Readiness — InkScroller Backend

> Documento de referencia para evaluar qué está listo para ser público y qué requiere acción antes de publicar el repositorio.

---

## 1. Clasificación: public-safe vs private-only

### ✅ Public-safe (puede ir en repo público sin cambios)

| Archivo / Artefacto | Razón |
|---------------------|-------|
| `app/**` (código fuente Python) | No contiene secrets hardcodeados — todo via env vars |
| `main.py` | Entry point sin credenciales |
| `requirements.txt` | Dependencias públicas |
| `Dockerfile` | Build config — variables se inyectan en runtime |
| `tests/` | Tests con DI overrides, sin credenciales reales |
| `docs/` | Documentación técnica |
| `README.md` | Doc pública |
| `.env.example` | Template de env vars sin valores reales ✅ |
| `.dockerignore` | Excluye correctamente `.env` |

### 🔴 Private-only / Requiere acción antes de publicar

| Archivo / Artefacto | Riesgo | Acción requerida |
|---------------------|--------|------------------|
| `.env` | Contiene `FIREBASE_PROJECT_ID`, path al service account | **Nunca commitear** — ya en `.gitignore` ✅ |
| `serviceAccountKey.json` (o equivalente) | Firebase Admin SDK credentials — acceso completo al proyecto | Nunca commitear — usar secreto de CI o Workload Identity |
| `inkscroller.db` | Base de datos SQLite con datos de usuarios reales | Nunca commitear — ya en `.gitignore` ✅ |
| `GOOGLE_APPLICATION_CREDENTIALS` path | Si apunta a archivo local con credenciales | Usar variable en CI, no path local |
| Logs con tokens de usuario | Firebase ID tokens en logs de debug | Auditar handlers antes de publicar |

---

## 2. Política de rotación antes de hacer público

Antes de cambiar la visibilidad del repo a **público**, ejecutar en este orden:

1. **Rotar Service Account Key de Firebase**
   - Firebase Console → Project settings → Service accounts → Generate new private key
   - Revocar la key anterior en Google Cloud Console → IAM → Service Accounts
   - Actualizar `FIREBASE_SERVICE_ACCOUNT_BASE64` en GitHub Secrets
   - Si se usa Application Default Credentials (ADC) en Cloud Run: no hay key que rotar — ADC usa Workload Identity

2. **Rotar `FIREBASE_PROJECT_ID`** si hay dudas sobre exposición
   - Técnicamente el Project ID es semi-público (aparece en URLs de Firebase), pero si fue expuesto junto a la service account key, crear un proyecto nuevo

3. **Auditar historial de git** para secrets accidentalmente commiteados:
   ```bash
   git log --all -S "GOOGLE_APPLICATION_CREDENTIALS" --oneline
   git log --all -S "serviceAccountKey" --oneline
   git log --all -S "firebase" --full-history -- "*.json"
   ```
   - Si se encuentran: usar `git filter-repo` para purgar ANTES de hacer público

4. **Verificar que `inkscroller.db` no tiene historial commiteado**:
   ```bash
   git log --all --full-history -- "*.db" --oneline
   ```

5. **Revisar Firebase Security Rules** de Authentication y si hay Firestore/Storage

> **Regla de oro**: Si un secret fue commiteado en algún momento del historial, asumirlo como comprometido. Hacer público el repo solo expone lo que ya fue.

---

## 3. Instrucciones de CI: inyección de secrets en runtime

### Firebase Service Account

El archivo de service account de Firebase **no se commitea**. Se inyecta en CI desde GitHub Secrets.

#### Opción A — Service Account Key (simple, válida para proyectos pequeños)

**Paso 1** — Codificar el archivo (se hace una sola vez, localmente):

```bash
base64 -i serviceAccountKey.json | pbcopy  # macOS
base64 -w 0 serviceAccountKey.json | xclip  # Linux
```

**Paso 2** — Guardar en GitHub Secrets:

| Secret Name | Contenido |
|-------------|-----------|
| `FIREBASE_SERVICE_ACCOUNT_BASE64` | base64 del `serviceAccountKey.json` |
| `FIREBASE_PROJECT_ID` | ID del proyecto Firebase (ej: `inkscroller-dev`) |

**Paso 3** — Reconstruir en el workflow de CI:

```yaml
# .github/workflows/deploy.yml (fragmento)
- name: Restore Firebase service account
  run: |
    echo "${{ secrets.FIREBASE_SERVICE_ACCOUNT_BASE64 }}" | base64 --decode \
      > /tmp/serviceAccountKey.json
    echo "GOOGLE_APPLICATION_CREDENTIALS=/tmp/serviceAccountKey.json" >> $GITHUB_ENV
    echo "FIREBASE_PROJECT_ID=${{ secrets.FIREBASE_PROJECT_ID }}" >> $GITHUB_ENV

- name: Start server (with env)
  run: python -m uvicorn main:app --host 0.0.0.0 --port 8080
  env:
    GOOGLE_APPLICATION_CREDENTIALS: /tmp/serviceAccountKey.json
    FIREBASE_PROJECT_ID: ${{ secrets.FIREBASE_PROJECT_ID }}
```

#### Opción B — Workload Identity Federation (recomendado para Cloud Run)

En Google Cloud Run, se puede asignar una **Service Account** al servicio directamente. Esto elimina la necesidad de gestionar archivos de credenciales:

```bash
# Asignar service account al Cloud Run service
gcloud run services update inkscroller-backend \
  --service-account=inkscroller-backend@PROJECT_ID.iam.gserviceaccount.com \
  --region=us-central1
```

Con ADC (Application Default Credentials), el SDK de Firebase lo detecta automáticamente. `GOOGLE_APPLICATION_CREDENTIALS` no es necesario en este caso.

### Variables de entorno completas para CI

```yaml
# Ejemplo: pasar todas las env vars necesarias al contenedor
env:
  DEBUG: "false"
  FIREBASE_PROJECT_ID: ${{ secrets.FIREBASE_PROJECT_ID }}
  GOOGLE_APPLICATION_CREDENTIALS: /tmp/serviceAccountKey.json
  CORS_ORIGINS: "https://your-frontend-domain.com"
  DB_PATH: ./inkscroller.db
  MANGADEX_BASE_URL: "https://api.mangadex.org"
  JIKAN_BASE_URL: "https://api.jikan.moe/v4"
  CACHE_TTL_SECONDS: "300"
```

---

## 4. Checklist pre-publicación (portfolio/public release)

Ejecutar esta checklist antes de cambiar el repo a público:

### Secretos y configuración

- [ ] `.env` **NO está commiteado** en ningún branch ni tag
- [ ] `serviceAccountKey.json` (o cualquier `*.json` de service account) **NO está commiteado**
- [ ] `inkscroller.db` **NO está commiteado** (contiene datos de usuarios)
- [ ] No hay API keys hardcodeadas en `app/` — verificar con: `grep -r "AIza\|sk-\|Bearer \|firebase_admin.initialize_app" app/`
- [ ] Historial de git auditado: `git log --all -S "GOOGLE_APPLICATION_CREDENTIALS" --oneline`

### Firebase

- [ ] Service account key rotada o confirmada que nunca se commiteó
- [ ] Firebase Auth configurado correctamente (no permitir cualquier email sin validación)
- [ ] Firestore/Storage rules revisadas si aplican

### CI/CD

- [ ] GitHub Actions workflows funcionan con secrets inyectados
- [ ] Ningún workflow hace `echo $GOOGLE_APPLICATION_CREDENTIALS` ni loguea el contenido del archivo
- [ ] El Dockerfile no copia archivos de credenciales al build
- [ ] `.dockerignore` incluye `serviceAccountKey.json` y `.env`

### Código

- [ ] No hay `TODO: remove before release` o `FIXME: hardcoded` en el código
- [ ] `app/core/config.py` lee todo vía env vars (no tiene fallbacks hardcodeados con valores reales)
- [ ] Logs de producción no exponen tokens de usuario (`Authorization: Bearer <token>`)

### Documentación

- [ ] `README.md` explica cómo obtener credenciales de Firebase ✅
- [ ] `.env.example` está actualizado y sin valores reales ✅
- [ ] `docs/DEPLOYMENT.md` explica el proceso de CI/CD con secrets

### Licencia

- [ ] `LICENSE` file presente (README dice MIT pero el archivo podría no existir)
- [ ] Atribución a MangaDex y Jikan presente ✅

---

## 5. Archivos sensibles y su estado actual

| Archivo | En `.gitignore` | Commiteado actualmente | Estado |
|---------|----------------|----------------------|--------|
| `.env` | ✅ | ❌ — nunca commiteado (auditoría P0-B2 ✅) | ✅ Seguro |
| `inkscroller.db` | ✅ | ❌ | ✅ Seguro |
| `serviceAccountKey.json` | ✅ (línea 19) | ❌ — nunca commiteado (auditoría P0-B3 ✅) | ✅ Seguro |
| `*serviceAccount*.json` | ✅ (línea 20) | — | ✅ |
| `firebase-adminsdk-*.json` | ✅ (líneas 21-22) | — | ✅ |
| `*credentials*.json` | ✅ (línea 48) | — | ✅ |
| `venv/` | ✅ | — | ✅ |
| `__pycache__/` | ✅ | — | ✅ |

> **Auditoría P0-B2/B3 completada — 2026-04-08:**
> - `.env` nunca commiteado — historial git limpio — `.gitignore` cubre `.env` y `.env.*`
> - `serviceAccountKey.json` nunca commiteado — `.gitignore` cubre todos los patrones de nombre de service account
> - Firebase Admin SDK usa `credentials.ApplicationDefault()` + `FIREBASE_PROJECT_ID` via `os.getenv()` — sin hardcoding
> - Evidencia formal: `docs/release/templates/p0-b2-b3-evidence.md`

---

_Última actualización: 2026-04-08 — P0-B2 y P0-B3 cerrados con evidencia de auditoría_
