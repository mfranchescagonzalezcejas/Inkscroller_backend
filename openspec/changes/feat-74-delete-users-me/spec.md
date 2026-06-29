# Spec: DELETE /users/me

**Change**: `feat/74-delete-users-me`
**Issue**: #74 — Automatic account and data deletion endpoint
**Status**: spec
**Depends on**: proposal (`openspec/changes/feat-74-delete-users-me/proposal.md`)

## 1. Requirements

### Functional

| ID | Requirement | Priority |
|----|-------------|----------|
| F1 | Authenticated users can delete their account via `DELETE /users/me` | P0 |
| F2 | The Firebase Auth user is deleted via `firebase_admin.auth.delete_user()` | P0 |
| F3 | Local data (user_library, reading_preferences, users row) is deleted in order | P0 |
| F4 | Operation is idempotent — repeating DELETE returns 204 | P0 |
| F5 | If Firebase Auth deletion fails, local data is NOT modified | P0 |
| F6 | If Firebase Auth user was already deleted (UserNotFoundError), skip Firebase step | P0 |
| F7 | When Firebase Admin SDK is not initialized (CI/test), skip Firebase deletion silently | P1 |
| F8 | The endpoint returns 204 No Content with no body | P0 |
| F9 | Unauthenticated requests return 401 Unauthorized | P0 |

### Non-Functional

| ID | Requirement |
|----|-------------|
| NF1 | Firebase Admin SDK call runs via `asyncio.to_thread()` to avoid blocking the event loop |
| NF2 | Deletion is safe to retry — no partial state on retry |
| NF3 | No other user's data is exposed or deleted |

## 2. Endpoint Contract

### Request

```
DELETE /users/me
Authorization: Bearer <firebase-id-token>
```

### Responses

| Status | Body | When |
|--------|------|------|
| 204 | — | Successful deletion (first call or repeat) |
| 401 | `{"error": "authentication_error", "detail": "..."}` | Missing or invalid token |
| 502 | `{"error": "upstream_error", "detail": "..."}` | Firebase Auth deletion failed |

### Error detail values

| Condition | Status | `error` | `detail` |
|-----------|--------|---------|----------|
| No auth token | 401 | `authentication_error` | "Authentication required." |
| Invalid/expired token | 401 | `authentication_error` | From existing `AuthError` |
| Firebase deletion timeout/network error | 502 | `upstream_error` | "Firebase Auth deletion failed." |

## 3. Scenarios

### 3.1 Happy path — new deletion

**Given** an authenticated user with profile, preferences, and library entries
**When** they send `DELETE /users/me`
**Then** Firebase Auth user is deleted
**And** `user_library` entries for that UID are deleted
**And** `reading_preferences` for that UID are deleted
**And** `users` row for that UID is deleted
**And** response is 204 with no body

### 3.2 Idempotent — repeat deletion

**Given** the user was already deleted (local and Firebase)
**When** they send `DELETE /users/me` again
**Then** Firebase step returns `UserNotFoundError` → skip
**And** local cleanup runs (deletes 0 rows)
**And** response is 204 with no body

### 3.3 Firebase Auth failure — abort

**Given** Firebase Auth service is unreachable
**When** user sends `DELETE /users/me`
**Then** `firebase_admin.auth.delete_user()` raises an exception
**And** no local data is modified
**And** response is 502 with `{"error": "upstream_error", "detail": "Firebase Auth deletion failed."}`

### 3.4 CI / test environment — Firebase not initialized

**Given** the app is running without Firebase Admin SDK (CI/test)
**When** user sends `DELETE /users/me`
**Then** Firebase deletion is silently skipped
**And** local data is deleted normally
**And** response is 204 with no body

### 3.5 Unauthenticated request

**Given** no valid Bearer token
**When** request is sent to `DELETE /users/me`
**Then** response is 401

### 3.6 Local DB failure after Firebase deletion

**Given** Firebase Auth deletion succeeded
**When** local DB DELETE queries fail (e.g., constraint, connection lost)
**Then** the Firebase user is already deleted (irreversible)
**And** response propagates the DB error
**And** error is logged

## 4. Data Cleanup Order

Explicit DELETEs, no CASCADE:

```
Step 1: DELETE FROM user_library WHERE firebase_uid = ?
Step 2: DELETE FROM reading_preferences WHERE firebase_uid = ?
Step 3: DELETE FROM users WHERE firebase_uid = ?
```

All three execute within the same adapter pattern (execute + commit).

## 5. Acceptance Criteria

| ID | Criterion | Verifies |
|----|-----------|----------|
| AC1 | Authenticated user receives 204 after DELETE | F1, F8 |
| AC2 | User profile data is removed from DB (users, reading_preferences, user_library) | F3 |
| AC3 | Second DELETE returns 204 without error | F4 |
| AC4 | Firebase Auth user is deleted (integration test with mock) | F2 |
| AC5 | Firebase UserNotFoundError does not block local cleanup | F6 |
| AC6 | Firebase deletion failure returns 502 and local data is preserved | F5 |
| AC7 | Request without token returns 401 | F9 |
| AC8 | Firebase Admin not initialized → local cleanup still works | F7 |
| AC9 | `asyncio.to_thread()` is used for the Firebase call | NF1 |

## 6. Key Files

| File | Change |
|------|--------|
| `app/api/users.py` | Add `DELETE /users/me` route |
| `app/services/user_service.py` | Add `delete_account()` method |
| `app/core/exceptions.py` | Possibly no new exception needed (reuse upstream error pattern) |
| `tests/api/users/test_users_auth.py` | Add test class or methods for deletion scenarios |
