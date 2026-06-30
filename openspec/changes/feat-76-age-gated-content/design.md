# Design: Age-Based Manga Content Access

**Issue:** #76
**Based on:** spec.md, proposal.md
**Date:** 2026-06-29

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        HTTP Layer (api/manga.py)                │
│                                                                 │
│  search_manga(q, user_age)  list_manga(..., user_age)          │
│  get_manga(id, user_age)    chapters/pages(..., user_age)      │
│                                                                 │
│  get_user_age() ← dependency that resolves age from profile    │
└──────────────────────┬──────────────────────────────────────────┘
                       │ user_age: int | None
┌──────────────────────▼──────────────────────────────────────────┐
│                    Service Layer (manga_service.py)              │
│                                                                 │
│  _filter_by_age(manga_list, user_age)  ← NEW                    │
│  search(query, limit, user_age)        ← updated                │
│  list_manga(limit, offset, ..., user_age)  ← updated            │
│  get_by_id(manga_id, user_age)         ← updated                │
│                                                                 │
│  Uses: can_access_content(), CONTENT_AGE_LIMITS                 │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│                    Data Layer                                   │
│                                                                 │
│  Manga.contentRating: str | None  ← NEW field                   │
│  map_mangadex_manga() extracts contentRating  ← updated         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Search / List (filter silently)

```
Request → Route (resolves user_age) → Service.search(user_age) →
  MangaDex API or cache → full results → _filter_by_age(results, user_age) →
  filtered response
```

### Direct Access (block with 403)

```
Request → Route (resolves user_age) → Service.get_by_id(id, user_age) →
  MangaDex API or cache → result →
  can_access_content(result.contentRating, user_age)?
    YES → return result
    NO  → return None
  Route: result is None → double-check if manga exists → 403
```

## Component Design

### 1. Age Utility Module (`app/core/age.py`)

New file. Pure functions, no dependencies on project modules.

```python
from datetime import date

CONTENT_AGE_LIMITS: dict[str, int] = {
    "safe": 0,
    "suggestive": 16,
    "erotica": 18,
    "pornographic": 18,
}


def compute_age(birth_date: date | None) -> int | None:
    """Compute age from birth_date. Returns None if invalid."""
    if birth_date is None:
        return None
    today = date.today()
    if birth_date > today:
        return None
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


def can_access_content(
    content_rating: str | None,
    user_age: int | None,
) -> bool:
    """Determine if a user can access content with the given rating."""
    if content_rating is None:
        return True  # unknown → safe default
    min_age = CONTENT_AGE_LIMITS.get(content_rating)
    if min_age is None:
        return True  # unknown rating → safe default
    if user_age is None:
        return min_age == 0  # only safe (age 0) for guests/unknown
    return user_age >= min_age
```

### 2. Manga Model (`app/models/manga.py`)

Add field:
```python
contentRating: str | None = None
```

### 3. Manga Mapper (`app/services/manga_mapper.py`)

In `map_mangadex_manga()`, add:
```python
"contentRating": item.get("attributes", {}).get("contentRating"),
```

### 4. Manga Service (`app/services/manga_service.py`)

Add imports:
```python
from app.core.age import can_access_content, CONTENT_AGE_LIMITS
```

Add helper:
```python
def _filter_by_age(self, manga_list: list[dict], user_age: int | None) -> list[dict]:
    if user_age is None:
        return [m for m in manga_list if m.get("contentRating") in (None, "safe")]
    return [
        m for m in manga_list
        if can_access_content(m.get("contentRating"), user_age)
    ]
```

Update methods:
- `search(query, limit, user_age=None)`: filter before return
- `list_manga(limit, offset, ..., user_age=None)`: filter before return
- `get_by_id(manga_id, user_age=None)`: return None if blocked

### 5. Route Layer (`app/api/manga.py`)

Add optional auth dependency:
```python
async def get_current_user_optional(request: Request) -> dict | None:
    """Like get_current_user but returns None instead of 401."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    # ... same verification as get_current_user, but return None on failure
```

Add age resolution dependency:
```python
async def get_user_age(
    profile_service=Depends(get_profile_service),
    user=Depends(get_current_user_optional),
) -> int | None:
    if user is None:
        return None
    profile = await profile_service.get_profile(user["uid"])
    if profile is None or profile.birth_date is None:
        return None
    return compute_age(profile.birth_date)
```

Update routes with the `user_age` dependency.

## Caching Strategy

- Cache keys do NOT include user_age
- Filtering happens **after** cache retrieval
- This means cache is shared across users (good for hit rate)
- Slight CPU overhead to filter on every request (negligible — list iteration)

## Error Handling

### Direct access to restricted content

```python
manga = await service.get_by_id(manga_id, user_age=user_age)
if manga is None:
    # Check if it exists but is blocked
    full = await service.get_by_id(manga_id)  # no age filter
    if full and not can_access_content(full.get("contentRating"), user_age):
        min_age = CONTENT_AGE_LIMITS.get(full.get("contentRating"), 0)
        raise HTTPException(
            status_code=403,
            detail=f"This content is age-restricted (requires {min_age}+)",
        )
    raise HTTPException(status_code=404, detail="Manga not found")
```

### List/search — silent filtering

Restricted items are simply not included. No error, no log, no indication.

## Unchanged

- MangaDexClient._ALLOWED_CONTENT_RATINGS remains unchanged
- Cache infrastructure unchanged
- Jikan enrichment unchanged
- Response models unchanged (contentRating added to existing Manga model)

## Test Strategy

### Unit Tests

1. `test_can_access_content` — matrix of all combinations
2. `test_compute_age` — normal, None, future dates, boundary (15y364d vs 16y0d)
3. `test_filter_by_age` — mixed list with safe/suggestive/None
4. `test_search_filters_by_age` — mock client, verify filtering
5. `test_list_filters_by_age` — mock client, verify filtering
6. `test_get_by_id_blocks_suggestive` — verify None return

### Integration Tests

7. `test_guest_search_returns_safe_only` — full HTTP
8. `test_guest_get_suggestive_403` — full HTTP
9. `test_user_16_sees_suggestive` — full HTTP with auth
10. `test_user_15_blocked_from_suggestive` — full HTTP with auth

### Fixtures

- MangaDex payload example with safe and suggestive ratings
- User profile fixtures with specific birth_dates
