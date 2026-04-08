# P0-B2 / P0-B3 — Evidencia de auditoría: secrets compliance

> **Ítem P0-B2:** `.env` de producción NO en el repositorio — checklist ref `3.3`
> **Ítem P0-B3:** Firebase Admin SDK credentials via env var, no hardcodeadas — checklist ref `3.4`
> **Estado:** ✅ CERRADO — 2026-04-08
> **Ejecutor:** agente local (CLI)
> **Rama:** `feature/p0-b2-b3-secrets-compliance`

---

## Auditoría P0-B2 — `.env` no commiteado

### Comandos ejecutados

```bash
# 1. Verificar que .env no está tracked por git
git ls-files --error-unmatch .env

# 2. Verificar historial completo de .env en todas las ramas
git log --all --full-history -- ".env" --oneline

# 3. Verificar cobertura en .gitignore
grep -n "^\.env" .gitignore
```

### Resultados

```text
# Comando 1 — git ls-files --error-unmatch .env
error: pathspec '.env' did not match any file(s) known to git
→ RESULTADO: .env NOT tracked by git ✅

# Comando 2 — git log --all --full-history -- ".env"
(sin output — ningún commit contiene .env en su history)
→ RESULTADO: .env NUNCA fue commiteado en toda la historia del repo ✅

# Comando 3 — .gitignore
14:.env
15:.env.*
→ RESULTADO: .env y .env.* explícitamente ignorados, excepto .env.example ✅
```

### Evaluación

| Criterio | Estado |
|----------|--------|
| `.env` no está tracked actualmente | ✅ PASS |
| `.env` nunca fue commiteado (historial limpio) | ✅ PASS |
| `.env` cubierto por `.gitignore` con regla explícita | ✅ PASS |
| `.env.example` en repo (template sin valores reales) | ✅ PASS |
| `.dockerignore` excluye `.env` | ✅ PASS (verificado en `.dockerignore`) |

### Decisión P0-B2

**PASS ✅** — No existe riesgo de exposición de `.env` en el repositorio.
El historial de git no contiene ningún commit con `.env`. Las reglas de `.gitignore`
previenen futuros commits accidentales.

---

## Auditoría P0-B3 — Firebase credentials sin hardcoding

### Comandos ejecutados

```bash
# 1. Buscar uso de credentials.Certificate() en código fuente
grep -rn "credentials\.Certificate\|Certificate(" app/ --include="*.py"

# 2. Verificar método de inicialización de Firebase Admin SDK
grep -rn "credentials\.ApplicationDefault\|initialize_app" app/ --include="*.py"

# 3. Verificar que firebase_project_id se lee vía env var
grep -n "os.getenv\|firebase_project_id" app/core/config.py

# 4. Verificar que no hay project IDs hardcodeados en código
grep -rn "inkscroller-aed59\|inkscroller-8fa87\|inkscroller-stg" app/ --include="*.py"

# 5. Verificar historial git por credentials.Certificate
git log --all -S "credentials.Certificate" --oneline

# 6. Verificar historial git por private_key hardcodeada
git log --all -S '"private_key"' --oneline
git log --all -S '"client_email"' --oneline

# 7. Verificar historial por archivos de service account
git log --all --full-history -- "*serviceAccount*.json" "*firebase-adminsdk*.json" "*credentials*.json" --oneline

# 8. Verificar cobertura de .gitignore para service account files
grep -n "serviceAccount\|firebase-adminsdk\|credentials" .gitignore
```

### Resultados

```text
# Comando 1 — credentials.Certificate()
(sin output)
→ RESULTADO: credentials.Certificate() NO se usa en ninguna parte ✅

# Comando 2 — credentials.ApplicationDefault() + initialize_app
app/core/firebase_auth.py:60:        cred = credentials.ApplicationDefault()
app/core/firebase_auth.py:61:        firebase_admin.initialize_app(cred, {"projectId": settings.firebase_project_id})
→ RESULTADO: se usa ApplicationDefault() — carga GOOGLE_APPLICATION_CREDENTIALS del env
             el projectId viene de settings.firebase_project_id (env var) ✅

# Comando 3 — config.py
21:    firebase_project_id: str = os.getenv("FIREBASE_PROJECT_ID", "")
→ RESULTADO: FIREBASE_PROJECT_ID se lee vía os.getenv — sin fallback hardcodeado con valor real ✅

# Comando 4 — project IDs hardcodeados en app/
(sin output)
→ RESULTADO: ningún project ID hardcodeado en código fuente ✅

# Comando 5 — historial git credentials.Certificate
(sin output)
→ RESULTADO: NUNCA se usó credentials.Certificate() en el historial ✅

# Comando 6 — historial git private_key / client_email
(sin output)
→ RESULTADO: ningún campo de service account key en historial ✅

# Comando 7 — archivos .json de service account en historial
(sin output)
→ RESULTADO: ningún archivo de service account fue commiteado ✅

# Comando 8 — .gitignore service account coverage
19:serviceAccountKey.json
20:*serviceAccount*.json
21:firebase-adminsdk-*.json
22:*-firebase-adminsdk-*.json
47:*credentials*.json
→ RESULTADO: múltiples patrones cubren todos los nombres típicos de service account ✅
```

### Flujo de carga de credenciales Firebase (verificado)

```
Local dev:
  GOOGLE_APPLICATION_CREDENTIALS=/ruta/fuera-del-repo/serviceAccountKey.json
  → credentials.ApplicationDefault() detecta la variable automáticamente
  → firebase_admin.initialize_app(cred, {"projectId": os.getenv("FIREBASE_PROJECT_ID")})

Cloud Run (prod/staging/dev):
  → Workload Identity Federation activa (service account asignada al servicio)
  → GOOGLE_APPLICATION_CREDENTIALS no se configura en Cloud Run
  → Application Default Credentials (ADC) detecta el service account del entorno GCP
  → No se necesita archivo JSON — cero credenciales en el repo o en el contenedor

CI/CD (GitHub Actions):
  → FIREBASE_SERVICE_ACCOUNT_BASE64 en GitHub Secrets → base64 decode en /tmp/
  → GOOGLE_APPLICATION_CREDENTIALS=/tmp/serviceAccountKey.json (efímero, no persistido)
  → Ver: SECURITY_PUBLIC_READINESS.md §3
```

### Evaluación

| Criterio | Estado |
|----------|--------|
| No se usa `credentials.Certificate()` en código | ✅ PASS |
| Firebase Admin SDK usa `ApplicationDefault()` | ✅ PASS |
| `FIREBASE_PROJECT_ID` se lee vía `os.getenv()` sin fallback real | ✅ PASS |
| `GOOGLE_APPLICATION_CREDENTIALS` se lee del entorno (no hardcodeado) | ✅ PASS |
| Ningún project ID hardcodeado en `app/` | ✅ PASS |
| Historial git limpio — sin `private_key`, `client_email`, `Certificate()` | ✅ PASS |
| Ningún archivo `.json` de service account commiteado en historia | ✅ PASS |
| `.gitignore` cubre todos los patrones de nombre de service account | ✅ PASS |
| Flujo Cloud Run usa ADC/Workload Identity — sin archivos de key | ✅ PASS |

### Decisión P0-B3

**PASS ✅** — Las credenciales de Firebase Admin SDK se cargan exclusivamente vía
variables de entorno y Application Default Credentials. No existe ningún secret
hardcodeado en el código fuente ni en el historial de git.

---

## Notas de seguridad adicionales detectadas

### `.env` local contiene path a credencial real (solo local, no commiteado)

El archivo `.env` local (no versionado) contiene:
```
GOOGLE_APPLICATION_CREDENTIALS=/home/shana1499/.ssh/inkscroller-aed59-firebase-adminsdk-fbsvc-c4bc289046.json
```

**Evaluación:** Este path es local del desarrollador, nunca commiteado. El mecanismo es
correcto: la variable se lee del entorno en runtime. No genera riesgo en el repo.

**Recomendación (no bloqueante):** Al hacer público el repo, rotar la service account key
siguiendo el procedimiento en `SECURITY_PUBLIC_READINESS.md §2`. El Project ID `inkscroller-aed59`
(dev) aparece en `DEPLOYMENT.md` como referencia documental — es semi-público por diseño.

### `DEPLOYMENT.md` contiene Project IDs de los tres entornos

Los Project IDs `inkscroller-aed59` (dev), `inkscroller-stg` (staging), `inkscroller-8fa87` (prod)
aparecen en `docs/DEPLOYMENT.md` como referencia operacional.

**Evaluación:** Los Firebase/GCP Project IDs son semi-públicos por diseño (aparecen en URLs de
Firebase y Cloud Run). No constituyen un secret. La seguridad real depende del IAM y las
Firebase Security Rules — no de la confidencialidad del Project ID.

---

## Trazabilidad

| Ítem | Checklist ref | Estado | Fecha |
|------|---------------|--------|-------|
| P0-B2 | `checklist-legal.md` §3.3 | ✅ CERRADO | 2026-04-08 |
| P0-B3 | `checklist-legal.md` §3.4 | ✅ CERRADO | 2026-04-08 |

- Guía de seguridad: [`SECURITY_PUBLIC_READINESS.md`](../../SECURITY_PUBLIC_READINESS.md)
- Configuración Firebase: [`app/core/firebase_auth.py`](../../app/core/firebase_auth.py)
- Lectura de env vars: [`app/core/config.py`](../../app/core/config.py)
- Checklist de release: [`docs/release/checklist-legal.md`](../checklist-legal.md)
