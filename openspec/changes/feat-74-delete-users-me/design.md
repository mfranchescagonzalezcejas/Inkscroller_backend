# Design: DELETE /users/me

**Change**: `feat/74-delete-users-me`
**Issue**: #74 — Automatic account and data deletion endpoint
**Status**: design
**Depends on**: spec (`openspec/changes/feat-74-delete-users-me/spec.md`)

## 1. Architecture

### Layer changes

```
┌─────────────────────────────────────────────────────────┐
│  app/api/users.py                                       │
│  ┌────────────────────────────────────────────────────┐ │
│  │ @router.delete("/me", status_code=204)              │ │
│  │ async def delete_me(current_user, user_service)     │ │
│  │   → awaits user_service.delete_account(uid)         │ │
│  └────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│  app/services/user_service.py                           │
│  ┌────────────────────────────────────────────────────┐ │
│  │ async def delete_account(firebase_uid)              │ │
│  │   1. await _delete_firebase_user(firebase_uid)      │ │
│  │   2. await _cleanup_local_data(firebase_uid)        │ │
│  └────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────┐ │
│  │ async def _delete_firebase_user(uid)                │ │
│  │   → checks firebase_admin._apps                    │ │
│  │   → asyncio.to_thread(delete_user_blocking, uid)   │ │
│  └────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│  app/core/firebase_auth.py                              │
│  ┌────────────────────────────────────────────────────┐ │
│  │ (no changes — reuse is_initialized pattern)        │ │
│  └────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│  app/core/exceptions.py                                 │
│  (no new exceptions — reuse upstream error pattern)     │
└─────────────────────────────────────────────────────────┘
```

### No new files
All changes are additive within existing files.

## 2. Method Details

### `UserService.delete_account(firebase_uid: str) -> None`

```python
async def delete_account(self, firebase_uid: str) -> None:
    """Delete the Firebase Auth user and all local data.

    Order: Firebase → local DB. If Firebase fails, local data is
    untouched — safe to retry.
    """
    await self._delete_firebase_user(firebase_uid)
    await self._cleanup_local_data(firebase_uid)
```

### `UserService._delete_firebase_user(firebase_uid: str) -> None`

```python
async def _delete_firebase_user(self, firebase_uid: str) -> None:
    """Delete the Firebase Auth user. Skips if SDK not initialized."""
    if not firebase_admin._apps:
        logger.info("Firebase Admin not initialized — skipping Auth user deletion.")
        return

    try:
        await asyncio.to_thread(firebase_admin.auth.delete_user, firebase_uid)
        logger.info("Deleted Firebase Auth user %s", firebase_uid)
    except firebase_admin.auth.UserNotFoundError:
        logger.info("Firebase user %s not found — already deleted.", firebase_uid)
    except Exception as exc:
        logger.error("Failed to delete Firebase Auth user %s: %s", firebase_uid, exc)
        raise UpstreamServiceError(
            "Firebase Auth", "Firebase Auth deletion failed."
        ) from exc
```

### `UserService._cleanup_local_data(firebase_uid: str) -> None`

```python
async def _cleanup_local_data(self, firebase_uid: str) -> None:
    """Delete all local data for the given UID in dependency order."""
    await self._db.execute(
        "DELETE FROM user_library WHERE firebase_uid = ?", firebase_uid
    )
    await self._db.execute(
        "DELETE FROM reading_preferences WHERE firebase_uid = ?", firebase_uid
    )
    await self._db.execute(
        "DELETE FROM users WHERE firebase_uid = ?", firebase_uid
    )
    await self._db.commit()
```

### Route: `app/api/users.py`

```python
@router.delete("/me", status_code=204)
async def delete_me(
    current_user: FirebaseTokenPayload = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> None:
    """Delete the authenticated account and all associated data."""
    await user_service.delete_account(current_user.uid)
```

## 3. Data Flow — Sequence

### Happy path

```
Client                  API                    UserService              Firebase Admin          SQLite/PG
  │                     │                        │                         │                     │
  │ DELETE /users/me    │                        │                         │                     │
  │────────────────────▶│                        │                         │                     │
  │                     │ verify token           │                         │                     │
  │                     │ (get_current_user)      │                         │                     │
  │                     │───────────────────────▶│                         │                     │
  │                     │                        │ delete_account(uid)     │                     │
  │                     │                        │────────────────────────▶│                     │
  │                     │                        │ _delete_firebase_user() │                     │
  │                     │                        │ asyncio.to_thread()     │                     │
  │                     │                        │─────────────────────────▶                     │
  │                     │                        │ delete_user(uid) ✓      │                     │
  │                     │                        │◀─────────────────────────                     │
  │                     │                        │                         │                     │
  │                     │                        │ _cleanup_local_data()   │                     │
  │                     │                        │──────────────────────────────────────────────▶│
  │                     │                        │ DELETE user_library ✓   │                     │
  │                     │                        │ DELETE reading_prefs ✓  │                     │
  │                     │                        │ DELETE users ✓          │                     │
  │                     │                        │ commit ✓                │                     │
  │                     │                        │◀──────────────────────────────────────────────│
  │                     │◀───────────────────────│                         │                     │
  │ 204 No Content      │                        │                         │                     │
  │◀────────────────────│                        │                         │                     │
```

### Firebase failure

```
  │                     │                        │                         │                     │
  │                     │                        │ asyncio.to_thread()     │                     │
  │                     │                        │─────────────────────────▶                     │
  │                     │                        │ delete_user(uid) ✗      │                     │
  │                     │                        │◀─────────────────────────                     │
  │                     │                        │                         │                     │
  │                     │                        │ raise UpstreamServiceError                    │
  │                     │                        │ (NO local cleanup)      │                     │
  │                     │◀───────────────────────│                         │                     │
  │ 502 Bad Gateway     │                        │                         │                     │
```

## 4. Firebase Mock Strategy (Tests)

```python
class UserAccountDeletionTests(unittest.TestCase):
    """Tests for DELETE /users/me endpoint."""

    def setUp(self):
        self.app = create_hermetic_test_app()
        self.db = asyncio.run(_make_test_db())
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_user] = self._fake_auth
        # Bootstrap the user
        asyncio.run(UserService(self.db).get_or_create_user(_FAKE_PAYLOAD))
        # Add some library entries and preferences for cleanup verification

    def tearDown(self):
        self.app.dependency_overrides.clear()
        asyncio.run(self.db.close())
```

### Firebase mock approach

Use `unittest.mock.patch` to replace `firebase_admin.auth.delete_user` at the service layer:

```python
@patch("app.services.user_service.firebase_admin._apps", [True])  # initialized
@patch("app.services.user_service.firebase_admin.auth.delete_user")
def test_delete_me_happy_path(self, mock_delete_user):
    mock_delete_user.return_value = None  # success

    with TestClient(self.app) as client:
        response = client.delete("/users/me", headers={"Authorization": "Bearer fake-token"})

    self.assertEqual(response.status_code, 204)
    mock_delete_user.assert_called_once_with(_FAKE_PAYLOAD.uid)

    # Verify local data is gone
    with TestClient(self.app) as client:
        get_response = client.get("/users/me", headers={"Authorization": "Bearer fake-token"})
    self.assertEqual(get_response.status_code, 401)  # user no longer exists → auth override still works but no DB row
```

Wait — after deletion, the user row is gone, but the `get_current_user` dependency override still returns the fake payload. The `get_or_create_user` would re-bootstrap the user. We need a different approach to verify cleanup.

Better approach: verify via direct DB query after deletion.

### Key test cases

| Test | Mock setup | Expected |
|------|-----------|----------|
| Happy path | `delete_user` succeeds | 204, all tables empty for UID |
| Idempotent repeat | `delete_user` raises `UserNotFoundError` | 204, no data change |
| Firebase failure | `delete_user` raises `Exception` | 502, local data preserved |
| Firebase not initialized | `firebase_admin._apps` empty | 204, local cleanup only |
| No auth token | — | 401 |
| Data cleanup | bootstrap + library + prefs before DELETE | All rows deleted for UID |

## 5. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Firebase call blocks event loop | Low | Medium | `asyncio.to_thread()` wraps sync call |
| DB error after Firebase deletion leaves inconsistent state | Low (Firebase deletion is irreversible) | Medium | Log error; Firebase user already gone so retry will skip Firebase step |
| Race condition: concurrent DELETE + PATCH | Low | Low | Deletion sweeps all tables per UID; concurrent PATCH may fail on FK after user row deleted |
| Race condition: concurrent DELETE requests | Low | Medium | Both run Firebase deletion — second gets UserNotFoundError, both proceed to local cleanup (idempotent) |

## 6. File Change Summary

| File | Change | Lines (est.) |
|------|--------|-------------|
| `app/api/users.py` | Add `delete_me()` route | +10 |
| `app/services/user_service.py` | Add `delete_account()`, `_delete_firebase_user()`, `_cleanup_local_data()` | +40 |
| `tests/api/users/test_users_auth.py` | Add `UserAccountDeletionTests` class | +120 |
