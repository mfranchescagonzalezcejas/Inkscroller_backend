# Tasks: DELETE /users/me

**Change**: `feat/74-delete-users-me`
**Issue**: #74 — Automatic account and data deletion endpoint
**Status**: tasks
**Depends on**: spec + design

## Task Dependency Graph

```
Task 1 (exception handler)
  └── no deps
Task 2 (service layer)
  └── depends on: Task 1
Task 3 (route)
  └── depends on: Task 2
Task 4 (tests)
  └── depends on: Task 2, Task 3
```

## Task Breakdown

### Task 1 — Exception handling for Firebase upstream errors

**Description**: Verify that `UpstreamServiceError("Firebase Auth")` correctly maps to HTTP 502. The existing handler `handle_upstream_service_error` in `exceptions.py` already catches `UpstreamServiceError` and returns 502. No code change needed — just verification.

**Files affected**: `app/core/exceptions.py` (read-only verification)
**Lines**: 0 (no change)
**AC covered**: None directly (enables AC6)
**Risk**: None

---

### Task 2 — Add `delete_account()` to UserService

**Description**: Add three private methods to `UserService`:

1. `delete_account(firebase_uid: str) -> None` — public entry point, orchestrates Firebase deletion then local cleanup
2. `_delete_firebase_user(firebase_uid: str) -> None` — deletes Firebase Auth user
   - Check `firebase_admin._apps` → skip if empty (CI/test mode)
   - Wrap `firebase_admin.auth.delete_user(uid)` in `asyncio.to_thread()`
   - Catch `firebase_admin.auth.UserNotFoundError` → log and skip (idempotent)
   - Catch other exceptions → log and raise `UpstreamServiceError("Firebase Auth", ...)`
3. `_cleanup_local_data(firebase_uid: str) -> None` — deletes local DB rows
   - `DELETE FROM user_library WHERE firebase_uid = ?`
   - `DELETE FROM reading_preferences WHERE firebase_uid = ?`
   - `DELETE FROM users WHERE firebase_uid = ?`
   - `self._db.commit()`

**Imports to add**: `asyncio`, `firebase_admin`, `firebase_admin.auth`, `UpstreamServiceError`

**Files affected**: `app/services/user_service.py`
**Lines**: +40
**AC covered**: F2, F3, F4, F5, F6, F7, NF1
**Risk**: Low — additive changes, no existing behavior modified

---

### Task 3 — Add `DELETE /users/me` route

**Description**: Add the route to `app/api/users.py`:

```python
@router.delete("/me", status_code=204)
async def delete_me(
    current_user: FirebaseTokenPayload = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> None:
    """Delete the authenticated account and all associated data."""
    await user_service.delete_account(current_user.uid)
```

**Files affected**: `app/api/users.py`
**Lines**: +10
**AC covered**: F1, F8, F9 (via existing auth dependency)
**Risk**: None

---

### Task 4 — Write tests

**Description**: Add `UserAccountDeletionTests` class to `test_users_auth.py` with test cases for all scenarios.

**Test cases**:

| Test | Scenario | Key assertion |
|------|----------|--------------|
| `test_delete_me_removes_user_and_data` | Happy path | 204 + direct DB query shows no rows for UID |
| `test_delete_me_idempotent_repeat` | Second deletion | 204 (mock UserNotFoundError) |
| `test_delete_me_firebase_failure_aborts` | Firebase fails | 502 + direct DB query shows data preserved |
| `test_delete_me_skips_firebase_when_not_initialized` | CI/test mode | 204 + local data deleted (no Firebase mock needed) |
| `test_delete_me_unauthenticated` | No token | 401 |
| `test_delete_me_cleans_library_and_preferences` | Full data cleanup | Verify library + prefs rows deleted |

**Mock strategy**:
- Patch `firebase_admin._apps` to simulate initialized state
- Patch `firebase_admin.auth.delete_user` for success/failure scenarios
- Use direct `self.db.fetchone()` queries to verify cleanup

**Test class setup**:
```python
class UserAccountDeletionTests(unittest.TestCase):
    def setUp(self):
        self.app = create_hermetic_test_app()
        self.db = asyncio.run(_make_test_db())
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_user] = self._fake_auth
        # Bootstrap user + add library entries + add preferences
        asyncio.run(UserService(self.db).get_or_create_user(_FAKE_PAYLOAD))
        asyncio.run(UserService(self.db).add_to_library(_FAKE_PAYLOAD.uid, "manga-1"))
        asyncio.run(UserService(self.db).get_preferences(_FAKE_PAYLOAD.uid))

    def tearDown(self):
        self.app.dependency_overrides.clear()
        asyncio.run(self.db.close())

    @staticmethod
    async def _fake_auth() -> FirebaseTokenPayload:
        return _FAKE_PAYLOAD
```

**Files affected**: `tests/api/users/test_users_auth.py`
**Lines**: +130
**AC covered**: All 9 ACs
**Risk**: Low — hermetic tests, no real Firebase dependency

## Summary

| Task | Description | Files | Est. lines | Deps |
|------|------------|-------|-----------|------|
| 1 | Exception verification (read-only) | exceptions.py | 0 | — |
| 2 | UserService.delete_account() | user_service.py | +40 | T1 |
| 3 | DELETE /users/me route | users.py | +10 | T2 |
| 4 | Tests | test_users_auth.py | +130 | T2, T3 |
| **Total** | | | **+180** | |

## Review Workload Forecast

- **Total estimated changed lines**: ~180
- **400-line budget risk**: Low (well under 400)
- **Chained PRs recommended**: No
- **Decision needed before apply**: No
