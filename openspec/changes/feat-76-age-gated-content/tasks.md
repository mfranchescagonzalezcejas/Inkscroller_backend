# Tasks: Age-Based Manga Content Access

**Issue:** #76
**Date:** 2026-06-29

## Task List

### Phase 1: Core Domain Changes

#### T1.1 — Add contentRating field to Manga model
- **File:** `app/models/manga.py`
- **Change:** Add `contentRating: str | None = None` field
- **Test:** Verify field exists on model instantiation

#### T1.2 — Extract contentRating in manga mapper
- **File:** `app/services/manga_mapper.py`
- **Change:** In `map_mangadex_manga()`, add `"contentRating": item.get("attributes", {}).get("contentRating")`
- **Test:** Verify mapper extracts contentRating from MangaDex payload fixtures

### Phase 2: Age Utility Module

#### T2.1 — Create app/core/age.py
- **File:** `app/core/age.py` (NEW)
- **Content:**
  - `CONTENT_AGE_LIMITS` dict
  - `compute_age(birth_date)` function
  - `can_access_content(content_rating, user_age)` function
- **Tests:**
  - `test_compute_age_normal`: valid birth_date returns correct age
  - `test_compute_age_none`: None input returns None
  - `test_compute_age_future_date`: future date returns None
  - `test_compute_age_boundary`: 15y364d vs 16y0d
  - `test_can_access_content_safe`: all ages can access
  - `test_can_access_content_suggestive_16`: 16+ can access
  - `test_can_access_content_suggestive_15`: 15 cannot access
  - `test_can_access_content_none_rating`: None → True
  - `test_can_access_content_none_age`: None age → only safe
  - `test_can_access_content_unknown_rating`: unknown rating → True

### Phase 3: Service Layer Filtering

#### T3.1 — Add _filter_by_age to MangaService
- **File:** `app/services/manga_service.py`
- **Change:** Add `_filter_by_age(manga_list, user_age)` method. Import `can_access_content`
- **Tests:**
  - `test_filter_by_age_guest`: None user_age → only safe/None
  - `test_filter_by_age_16`: 16 → safe + suggestive
  - `test_filter_by_age_12`: 12 → only safe

#### T3.2 — Update search() to filter by age
- **File:** `app/services/manga_service.py`
- **Change:** Add `user_age: int | None = None` param, call `_filter_by_age` before returning
- **Tests:**
  - `test_search_filters_by_age_guest`: verify filtering applied
  - `test_search_skips_filter_when_none`: backward compatible

#### T3.3 — Update list_manga() to filter by age
- **File:** `app/services/manga_service.py`
- **Change:** Add `user_age: int | None = None` param, filter before return
- **Tests:**
  - `test_list_filters_by_age_guest`: verify filtering applied

#### T3.4 — Update get_by_id() to block restricted access
- **File:** `app/services/manga_service.py`
- **Change:** Add `user_age: int | None = None` param, return None if manga is restricted
- **Tests:**
  - `test_get_by_id_returns_none_for_restricted_suggestive`
  - `test_get_by_id_returns_manga_for_allowed`

### Phase 4: Route Layer Integration

#### T4.1 — Add optional auth and user_age dependencies
- **File:** `app/core/dependencies.py` or `app/api/manga.py`
- **Change:** Add `get_current_user_optional()`, `get_user_age()` dependencies
- **Note:** May need to refactor dependencies to expose ProfileService

#### T4.2 — Update manga routes with age checking
- **File:** `app/api/manga.py`
- **Change:** Add `user_age` dependency to:
  - `search_manga()` — pass to service.search
  - `list_manga()` — pass to service.list_manga
  - `get_manga()` — check access, return 403 if blocked
  - Chapter/pages routes — check access, return 403 if blocked
- **Tests:**
  - `test_guest_search_returns_safe_only` (integration)
  - `test_guest_get_suggestive_403`
  - `test_user_16_sees_suggestive`
  - `test_user_12_blocked_from_suggestive`
  - `test_get_chapters_restricted_403`

#### T4.3 — Update library routes with age filtering
- **File:** `app/api/users.py` → library endpoints
- **Change:** Apply `_filter_by_age` on library manga lists

### Phase 5: Testing & Verification

#### T5.1 — Unit tests for age module
- **File:** `tests/core/test_age.py` (NEW)
- All test cases from T2.1

#### T5.2 — Unit tests for service layer filtering
- **File:** Add to existing manga service tests
- All test cases from T3.1–T3.4

#### T5.3 — Integration tests for routes
- **File:** Add to existing manga route tests
- All test cases from T4.2

---

## Review Workload Forecast

- **Estimated changed lines:** ~250 (new: 150, modified: 100)
- **Chained PRs recommended:** No (under 400 lines)
- **Files touched:** 7 (4 new files/modules, 3 modified)
