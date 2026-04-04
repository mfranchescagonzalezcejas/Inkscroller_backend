# InkScroller Backend — Project Status

> **Cross-repo source of truth:** Obsidian under `1-PROJECTS/InkScroller/`
> **Repo role:** backend implementation status for the FastAPI service
> **Last updated:** 2026-04-04

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
| Backend phase state | M1 complete; deploy strategy pending |
| Current sprint mirror | Sprint 2 |
| Repo status | Active |

---

## 3. Completed in this repo

### M1 — Backend auth foundation

- Firebase ID token verification exists
- SQLite persistence exists
- `/users/me` exists
- `/users/me/preferences` GET/PUT exists
- Auth/user tests exist

### Public API already operational

- `/ping`
- `/docs`
- `/openapi.json`
- `/manga`
- `/manga/search`
- chapters/pages public API

### Repo hygiene completed

- tracked virtualenv files removed from git
- SQLite runtime artifacts are now ignored (`*.db-shm`, `*.db-wal`)

---

## 4. Remaining work in this repo

| Item | Status | Dependency type | Depends on |
|------|--------|-----------------|------------|
| `BTASK-003` Deploy strategy | Todo | none | Product/infra decision |
| Firebase env setup for live protected-endpoint validation | Todo | validation | Local secrets/config |
| Stable staging or production backend target | Todo | deploy | Deploy strategy |
| End-to-end validation with Flutter preferences/profile flows | Todo | validation | Frontend M3 completion |

---

## 5. Cross-repo dependencies

### Provided to frontend

| Contract | Status | Notes |
|---------|--------|-------|
| Public manga catalogue/search/detail/chapter endpoints | Available | Confirmed working locally |
| `/users/me` | Available in code | Requires Firebase env for live validation |
| `/users/me/preferences` | Available in code | Required by frontend M3 |
| Firebase token verification | Available in code | Requires backend env for live validation |

### Depends on frontend for full product value

| Topic | Dependency type | Notes |
|------|-----------------|-------|
| Profile UI consumption | soft | Backend is ready, UI is pending |
| Preferences UI / local-first chain | hard | Needed for real user-facing preference flow |
| Adaptive reader behavior | soft/hard | Backend exposes preference surface; frontend must consume it |

---

## 6. Known blockers / validation gaps

| Topic | Type | Impact |
|------|------|--------|
| `FIREBASE_PROJECT_ID` and related env not configured locally | validation | Protected endpoints reject requests during live testing |
| Deploy target not chosen | deploy | No stable remote URL for integration |

---

## 7. Source-of-truth links

### Obsidian

- `InkScroller/Gestión/Gestión del proyecto.md`
- `InkScroller/Gestión/Matriz de dependencias cross-repo.md`
- `InkScroller/Gestión/Protocolo de sincronización cross-repo.md`
- `InkScroller/Sprints/Sprint 2.md`
- `InkScroller/Tareas/_Índice de tareas.md`

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
