# Proposal: DELETE /users/me

**Change**: `feat/74-delete-users-me`
**Issue**: #74 — Automatic account and data deletion endpoint
**Status**: proposal

## Problem

The InkScroller backend has no automatic endpoint for authenticated users to delete their account and associated data. This blocks Google Play compliance, which requires an in-app account/data deletion path for apps that support account creation.

## Proposed Solution

Add `DELETE /users/me` for authenticated Firebase users that:
1. Verifies authentication (existing `get_current_user` dependency)
2. Deletes the Firebase Auth user via `firebase_admin.auth.delete_user(uid)` (synchronous call wrapped in `asyncio.to_thread()`)
3. Deletes local data in order: user_library → reading_preferences → users (no CASCADE on FKs)
4. Returns HTTP 204 No Content on success

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Firebase Auth deletion | Yes, from backend | Full Google Play compliance, no external support flow needed |
| Deletion order | Firebase → local DB | If Firebase fails, local data untouched — safe to retry |
| Firebase failure | Abort, don't delete local | Prevents orphan data without the parent Firebase account |
| Idempotency | 204 on repeat | Frontend-friendly; Firebase `UserNotFoundError` skips step gracefully |
| Response | 204 No Content | Standard for DELETE with no body; idempotent |
| Firebase SDK sync call | `asyncio.to_thread()` | Avoid blocking the event loop |

## Key Flows

### Happy path
```
DELETE /users/me [Bearer token]
  → verify Firebase token (existing)
  → firebase_admin.auth.delete_user(uid) ✓
  → DELETE user_library WHERE firebase_uid = ?
  → DELETE reading_preferences WHERE firebase_uid = ?
  → DELETE users WHERE firebase_uid = ?
  → 204 No Content
```

### Firebase user already deleted (idempotent)
```
DELETE /users/me [Bearer token]
  → verify Firebase token ✓
  → firebase_admin.auth.delete_user(uid) → UserNotFoundError → skip
  → DELETE user_library / reading_preferences / users WHERE firebase_uid = ?
  → 204 No Content
```

### Firebase deletion fails
```
DELETE /users/me [Bearer token]
  → verify Firebase token ✓
  → firebase_admin.auth.delete_user(uid) → ✗ timeout/network error
  → abort, DO NOT delete local data
  → return 502 with error detail
```

### CI / test environment (Firebase Admin not initialized)
```
DELETE /users/me [Bearer token]
  → verify token via dependency override (test fake)
  → Firebase Admin not initialized → skip deletion
  → DELETE FROM users WHERE firebase_uid = ?
  → 204 No Content
```

## Out of Scope
- Rate limiting
- Email/SMS confirmation before deletion
- Soft-delete or account recovery
- Frontend UI changes (separate Flutter issue `inkscroller_frontend#17`)

### Cleanup order (no CASCADE on FK)
Tables do NOT have `ON DELETE CASCADE`. Explicit DELETEs in order:
1. `DELETE FROM user_library WHERE firebase_uid = ?`
2. `DELETE FROM reading_preferences WHERE firebase_uid = ?`
3. `DELETE FROM users WHERE firebase_uid = ?`

### Firebase failure → HTTP 502
When `firebase_admin.auth.delete_user()` fails (timeout, network, unexpected error), return `_error_response(502, "upstream_error", ...)` matching the existing upstream error pattern in `exceptions.py`.
