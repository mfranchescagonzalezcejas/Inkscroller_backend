# Cleanup and Reorganization Plan

## Goal

Prepare the backend repository for a controlled cleanup/reorganization without mixing policy decisions, runtime changes, and broad file moves in the same step.

## Current High-Value Findings

### Repository hygiene
- `.engram/` is present in the repository and appears to be local tool state, not product code.
- `.gga` is tracked and appears stale/mis-scoped for this Python backend.
- Both `venv/` and `.venv/` exist locally, which adds workspace noise even if ignored.

### Documentation drift
- `README.md` structure references must stay aligned with current module names (auth module is `app/core/firebase_auth.py`).
- Deployment documentation is split between an active Railway story and legacy Cloud Run artifacts.

### Runtime/config drift
- `Dockerfile` uses Python 3.11 while the project context points to Python 3.12.

## Cleanup Principles

1. Do not delete compliance or release evidence until retention is explicitly decided.
2. Normalize documentation before large moves so the repo has one source of truth.
3. Separate runtime alignment from structural refactors.
4. Prefer small commits by concern: docs, policy, config, then moves.

## Phase 1 Lock — Active vs Legacy

### Active source of truth
- `README.md` is onboarding entrypoint and should point only to the active deployment path.
- `docs/DEPLOYMENT.md` is the canonical operational document for deployment/runtime behavior.
- Railway is the ACTIVE deployment narrative.

### Legacy or mixed artifacts
- `docs/release/legacy/cloud-run/env-vars-cloudrun-prod.md` is historical Cloud Run evidence.
- `scripts/release/legacy/cloud-run/verify_prod_env_cloud_run.sh` is a Cloud Run-specific validation script.
- `scripts/release/smoke_prod.sh` is still useful, but its default production URL assumption is legacy.
- Parts of `docs/release/` still mix active Railway language with Cloud Run-era compliance evidence.

## Retention Policy (Phase 1)

| Path / Pattern | Decision | Why |
|---|---|---|
| `README.md` | retain | Main onboarding and current project narrative. |
| `docs/DEPLOYMENT.md` | retain | Canonical active deployment documentation. |
| `docs/release/checklist-legal.md` | review-first | Compliance-sensitive and currently mixed between active and legacy wording. |
| `docs/release/legacy/cloud-run/env-vars-cloudrun-prod.md` | archive | Explicitly legacy Cloud Run operational evidence. |
| `docs/release/legacy/cloud-run/templates/p0-b1-evidence-template.md` | archive | Historical Cloud Run-specific closure evidence. |
| `docs/release/templates/p0-b2-b3-evidence.md` | retain | Still relevant as platform-agnostic compliance evidence. |
| `docs/release/templates/p0-b4-b5-evidence.md` | retain | Behavioral/compliance evidence remains useful beyond platform choice. |
| `docs/release/templates/p0-b7-evidence.md` | retain | Privacy-flow evidence is platform-agnostic. |
| `docs/release/templates/p0-b8-evidence.md` | review-first | Useful, but currently tied to legacy production endpoint assumptions. |
| `docs/release/task-027-smoke.md` | review-first | Needs purpose clarification before cleanup. |
| `scripts/release/legacy/cloud-run/verify_prod_env_cloud_run.sh` | archive | Hard-coupled to Cloud Run/gcloud flow. |
| `scripts/release/smoke_prod.sh` | review-first | Likely reusable, but requires Railway/current-prod alignment first. |
| `Dockerfile` | review-first | Python runtime version is not aligned with the rest of the repo. |
| `.gga` | remove | Mis-scoped TS/JS review config in a Python backend repo. |
| `.gitignore` | retain | Current ignore policy is useful and security-aligned. |

## Proposed Execution Order

### Phase 1 — Policy and scope lock
- Decide whether legacy Cloud Run files are kept, archived, or removed.
- Decide whether tracked tool-state artifacts should be removed from version control.
- Confirm the active deployment target and supported Python version.

### Phase 2 — Documentation normalization
- Update deployment docs to reflect the active operational path.
- Fix README structure references and stale file names.
- Cross-check security/release docs for broken assumptions.

### Phase 3 — Repository hygiene
- Remove or archive non-runtime artifacts approved in Phase 1.
- Keep ignored local-state patterns explicit in `.gitignore` if needed.
- Avoid mixing these changes with refactors.

### Phase 4 — Runtime and config alignment
- Reconcile Python version across Docker, CI, docs, and local tooling.
- Validate dependency/runtime assumptions before any broad reorganization.

### Phase 5 — Structural reorganization
- Reorganize modules/tests/docs only after docs and policy are stable.
- Keep moves incremental to preserve reviewability.

## Protected / Review-First Areas

- `docs/release/`
- `scripts/release/`
- `SECURITY_PUBLIC_READINESS.md`
- Deployment-related CI/workflow files

These areas may contain compliance or operational evidence and should not be deleted casually.

## Immediate Next Actions

1. Normalize docs and deployment narrative around Railway as the active path.
2. Confirm Python version target and then align `Dockerfile`.
3. Archive or remove approved legacy/tooling artifacts without mixing in refactors.
4. Start the actual reorganization only after the three points above are closed.
