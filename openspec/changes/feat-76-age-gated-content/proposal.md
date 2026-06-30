# Proposal: Age-Based Manga Content Access Rules

**Issue:** #76 — `feat(content): enforce age-based manga access rules`
**Status:** proposal
**Date:** 2026-06-29

## Intent & Goal

Provide age-appropriate manga access by enforcing content rating rules based on the user's verified age. This ensures compliance with content guidelines, improves user safety for minors, and aligns with MangaDex content rating practices.

## Scope

### In Scope

- Add `contentRating` field to the Manga model
- Extract `contentRating` from MangaDex API responses in the mapper
- Derive user age from `birth_date` on `UserProfile`
- Filter age-restricted content in list/search/home/library responses
- Block direct access to restricted manga detail/chapter/page resources with HTTP 403
- Guest (unauthenticated) users: treat as safe-only
- Tests covering: guest, under-16, 16+, 18+, missing/invalid birth_date

### Out of Scope

- Changing MangaDex-level content rating filters in `_ALLOWED_CONTENT_RATINGS`
- Admin UI for content rating management
- Content rating reporting or flagging
- Caching changes (existing cache is per-key; filtered lists will be per-user)

## Current Gap

Today, `MangaDexClient._ALLOWED_CONTENT_RATINGS = ["safe", "suggestive"]` filters at the API level, so all manga that reaches our system is either `safe` or `suggestive`. However, **both are served to all users regardless of age**. There is no:

- `contentRating` field on the Manga model
- Extraction of `contentRating` from MangaDex API payloads
- Age derivation from `birth_date` on `UserProfile`
- Content filtering by user age
- Error handling for blocked content

A guest user and a 12-year-old can access `suggestive` content intended for 16+.

## Approaches

### Approach A: Service-Layer Filtering (Recommended)

Add a filtering method on `MangaService` that each public method (`search`, `list_manga`, `get_by_id`) calls before returning results.

- `search()`: filter results list before returning
- `list_manga()`: filter results list before returning
- `get_by_id()`: raise 403 if manga is restricted for the user
- Library routes: filter library content list

**Pros:**
- Explicit per-method control
- Easy to test each method independently
- No magic middleware behavior
- Can differentiate between list filtering (silent removal) and detail blocking (403)

**Cons:**
- Must add the age check to every method manually
- Slightly more code per method

### Approach B: Middleware/Decorator

Add a `@require_age_for_content(rating)` decorator or a middleware that inspects the manga being accessed.

**Pros:**
- Centralized enforcement
- Less repetitive

**Cons:**
- Harder to differentiate list vs detail behavior
- Decorator on route handlers leaks content logic to the API layer
- Cannot easily filter lists at the middleware level (needs post-response filtering)
- Cache interaction is more opaque

## Recommended Approach: Approach A (Service-Layer Filtering)

The service layer is the right abstraction boundary because:
- The Manga model is the domain boundary; filtering by content rating is a domain concern
- List filtering (silent removal of restricted items) and detail blocking (403) are different behaviors that the service layer can express naturally
- Tests can mock the service and verify filtering without touching HTTP

### Implementation Plan

1. **Manga model** (`app/models/manga.py`): Add `contentRating: str | None = None`
2. **Manga mapper** (`app/services/manga_mapper.py`): Extract `contentRating` from `item["attributes"]["contentRating"]` in `map_mangadex_manga()`
3. **Age utility** (new function in `app/services/manga_service.py` or `app/core/age.py`):
   - `compute_age(birth_date: date) -> int | None`
   - `MIN_AGE_FOR_CONTENT: dict[str, int]` = `{"safe": 0, "suggestive": 16, "erotica": 18, "pornographic": 18}`
   - `can_access(required_age: int, user_age: int | None) -> bool` (None = guest → 0)
4. **Service filtering** (`app/services/manga_service.py`):
   - Add `_filter_by_age(manga_list, user_age)` → returns filtered list
   - Add `_check_age_for_manga(manga, user_age)` → raises `HTTPException(403)` if blocked
   - Update `search()`: accept optional `user_age`, filter results
   - Update `list_manga()`: accept optional `user_age`, filter results
   - Update `get_by_id()`: accept optional `user_age`, raise 403 if blocked
5. **Route updates** (`app/api/manga.py`):
   - Add optional `get_current_user_or_none` dependency
   - Pass user age to service methods
6. **Library routes** (`app/api/users.py`): Same pattern
7. **Tests**:
   - Guest (no auth): only `safe` returned
   - 12-year-old: only `safe` returned
   - 16-year-old: `safe` + `suggestive` returned
   - 18-year-old: `safe` + `suggestive` returned
   - Missing `birth_date`: treat as safe-only
   - Invalid/future `birth_date`: treat as safe-only
   - Direct access to restricted manga: 403

## Edge Cases

| Case | Behavior |
|------|----------|
| Guest user (no auth) | safe only |
| birth_date is None | safe only |
| birth_date is in the future | safe only (age = 0) |
| birth_date makes user exactly 16 | suggestive accessible |
| Manga with no contentRating | treat as safe |
| Cache hit for a filtered list | cache is per-key; filtering by age changes the cache key or happens post-cache |
| 18+ content from non-MangaDex source | handled by the same rules if contentRating is stored |

## Risks

| Risk | Mitigation |
|------|------------|
| Cache poisoning — different users get wrong filtered results | Append age tier to cache key or filter after cache hit |
| Performance — age calculation on every request | Age derived from profile, cached per session; computation is O(1) integer math |
| Missing contentRating on historical data | Default to safe on None |
| MangaDex adds new contentRating values | Treat unknown values as safe (conservative); no crash |
