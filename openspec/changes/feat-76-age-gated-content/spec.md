# Specification: Age-Based Manga Content Access

**Issue:** #76
**Based on:** proposal.md
**Date:** 2026-06-29

## 1. Data Model Changes

### 1.1 Manga Model (`app/models/manga.py`)

Add field:
```python
contentRating: str | None = None
```

Valid values: `"safe"`, `"suggestive"`, `"erotica"`, `"pornographic"`, or `None`.
- Default is `None` (treated as safe)
- Existing records without the field will have `None`

## 2. Mapper Changes

### 2.1 map_mangadex_manga (`app/services/manga_mapper.py`)

Extract `contentRating` from the MangaDex payload attribute:
```python
"contentRating": item.get("attributes", {}).get("contentRating"),
```

- If the attribute is missing → `None`
- If the attribute is present → the string value (`"safe"`, `"s suggestive"`, etc.)

## 3. Age Utility

### 3.1 `compute_age(birth_date: date | None) -> int | None`

- If `birth_date` is `None` → return `None`
- If `birth_date` is in the future → return `None` (invalid)
- Otherwise → compute age as: `today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))`

### 3.2 `CONTENT_AGE_LIMITS`

```python
CONTENT_AGE_LIMITS: dict[str, int] = {
    "safe": 0,
    "suggestive": 16,
    "erotica": 18,
    "pornographic": 18,
}
```

### 3.3 `can_access_content(content_rating: str | None, user_age: int | None) -> bool`

| content_rating | user_age | Result |
|---|---|---|
| None (unknown) | any | True (treat as safe) |
| "safe" | any | True |
| "s suggestive" | None (guest or no birth_date) | False |
| "suggestive" | 15 or less | False |
| "suggestive" | 16+ | True |
| "erotica" | None or < 18 | False |
| "erotica" | 18+ | True |
| "pornographic" | None or < 18 | False |
| "pornographic" | 18+ | True |
| Unknown rating | any | True (conservative default) |

## 4. Service Layer Changes

### 4.1 Helper Method

```python
def _filter_by_age(self, manga_list: list[dict], user_age: int | None) -> list[dict]:
    """Filter out manga that the user cannot access due to age restrictions."""
    if user_age is None:
        # Guest or missing birth_date: only safe content
        return [m for m in manga_list if m.get("contentRating") in (None, "safe")]
    return [
        m for m in manga_list
        if can_access_content(m.get("contentRating"), user_age)
    ]
```

### 4.2 search(query, limit, user_age=None)

- Add `user_age: int | None = None` parameter
- Fetch results from cache or MangaDex as before
- Apply `_filter_by_age()` before returning
- Return filtered list

### 4.3 list_manga(limit, offset, ..., user_age=None)

- Add `user_age: int | None = None` parameter
- Fetch results as before
- Apply `_filter_by_age()` before returning response dict
- Note: cache key does NOT include user_age; filtering happens after cache hit

### 4.4 get_by_id(manga_id, user_age=None)

- Add `user_age: int | None = None` parameter
- Fetch manga as before
- After fetching, check `can_access_content(manga["contentRating"], user_age)`:
  - If False → return `None` (the route will raise 403)
  - If True → return manga as before

## 5. Route Changes

### 5.1 New Dependency (`app/api/manga.py`)

Add optional dependency to get user age:
```python
async def get_user_age(
    profile_service: ProfileService = Depends(get_profile_service),
    user: dict | None = Depends(get_current_user_optional),
) -> int | None:
    if user is None:
        return None  # guest
    profile = await profile_service.get_profile(user["uid"])
    if profile is None or profile.birth_date is None:
        return None  # missing birth_date
    return compute_age(profile.birth_date)
```

Where `get_current_user_optional` returns None instead of raising 401 when no auth header is present.

### 5.2 GET /manga/search

```python
async def search_manga(
    q: str = Query(...),
    service: MangaService = Depends(get_manga_service),
    user_age: int | None = Depends(get_user_age),
):
    return await service.search(q, user_age=user_age)
```

- Filtered silently: restricted manga are not returned

### 5.3 GET /manga

```python
async def list_manga(
    ...,
    service: MangaService = Depends(get_manga_service),
    user_age: int | None = Depends(get_user_age),
):
    return await service.list_manga(..., user_age=user_age)
```

- Filtered silently: restricted manga are not returned

### 5.4 GET /manga/{manga_id}

```python
async def get_manga(
    manga_id: str,
    service: MangaService = Depends(get_manga_service),
    user_age: int | None = Depends(get_user_age),
):
    manga = await service.get_by_id(manga_id, user_age=user_age)
    if manga is None:
        # Check if manga exists but is age-restricted
        full_manga = await service.get_by_id(manga_id)
        if full_manga and not can_access_content(full_manga.get("contentRating"), user_age):
            raise HTTPException(
                status_code=403,
                detail="This content is age-restricted",
            )
        raise HTTPException(status_code=404, detail="Manga not found")
    return manga
```

### 5.5 GET /manga/{id}/chapters and GET /manga/{id}/chapters/{chapter_id}/pages

- Same pattern: check manga access before returning chapter data
- If manga is age-restricted for the user → 403

### 5.6 Library routes

- When returning library manga list, apply `_filter_by_age()` filtering

## 6. Error Responses

### 6.1 403 Forbidden

```json
{
    "detail": "This content is age-restricted (requires 16+)"
}
```

The error message varies based on the required age:
- "This content is age-restricted (requires 16+)" for suggestive
- "This content is age-restricted (requires 18+)" for erotica/pornographic

### 6.2 No changes to 404 responses

If the manga doesn't exist OR the user can't access it, return 404 (existing behavior). The 403 is only for the case where the manga exists and the user explicitly requests it via direct access.

## 7. Test Requirements

### 7.1 Guest (unauthenticated)

- `test_guest_search_filters_suggestive`: guest searches → only safe manga in results
- `test_guest_list_filters_suggestive`: guest lists → only safe
- `test_guest_get_suggestive_returns_403`: guest GET /manga/{id} on suggestive → 403
- `test_guest_get_safe_returns_200`: guest GET /manga/{id} on safe → 200

### 7.2 Under-age user (e.g., 12 years old)

- `test_under_16_search_safe_only`: 12yo searches → only safe manga
- `test_under_16_get_suggestive_403`: 12yo GET suggestive → 403
- `test_under_16_get_safe_200`: 12yo GET safe → 200

### 7.3 Age-eligible user (16+)

- `test_age_16_sees_suggestive`: 16yo search → safe + suggestive
- `test_age_16_get_suggestive_200`: 16yo GET suggestive → 200
- `test_age_16_get_safe_200`: 16yo GET safe → 200
- `test_age_18_sees_all`: 18yo search → everything

### 7.4 Edge cases

- `test_missing_birth_date_treated_as_guest`: authenticated but no birth_date → safe only
- `test_future_birth_date_treated_as_guest`: authenticated with future birth_date → safe only
- `test_none_content_rating_treated_as_safe`: manga with None contentRating → accessible to all
- `test_boundary_age_15_vs_16`: 15 years 364 days vs 16 years 0 days

### 7.5 Direct access blocking

- `test_get_by_id_suggestive_under_16_returns_403`: explicit direct access blocked
- `test_get_chapters_for_restricted_manga_returns_403`: chapter access blocked
- `test_get_chapter_pages_for_restricted_manga_returns_403`: pages access blocked
