# Proposal: Accept content_rating query param in manga endpoints

**Change ID:** `fix-195-content-rating-query-param`

## Intent
The frontend sends `content_rating` as query param on `/manga` and `/manga/search` (safe/suggestive/all), but the backend ignores it and always uses the age-based default. This means an 18+ user who sets "Safe + Suggestive" still gets doujinshi/hentai because the backend requests ALL content ratings from MangaDex.

## Scope
### In Scope
- Accept `content_rating` query param in `GET /manga` and `GET /manga/search`
- Add resolution logic that intersects explicit preference with age-allowed ratings
- Update cache keys to include content_rating
- Tests

### Out of Scope
- Frontend changes (already implemented)
- Library endpoints (filtering is on content, not library items)

## Approach
Add optional `content_rating` param to both routes. Create `_resolve_content_ratings()` in MangaService that takes (user_age, content_rating) and returns the MangaDex content ratings to request. When explicit param is provided, intersect with age-allowed ratings so a minor can't bypass age gates via the param.

## Wire Contract
| Frontend value | MangaDex ratings requested |
|---|---|
| `safe` | `safe` |
| `suggestive` | `safe`, `suggestive` |
| `all` | `safe`, `suggestive`, `erotica`, `pornographic` |
| `null`/omitted | age-based default |
