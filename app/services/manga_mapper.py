"""Map raw MangaDex manga API items to internal dict format and apply statistics."""

from __future__ import annotations

from typing import Any

COVER_BASE_URL = "https://uploads.mangadex.org/covers"


def map_mangadex_manga(
    item: dict[str, Any],
    language: str | None = None,
) -> dict[str, Any]:
    """Map a raw MangaDex API item to a standardised manga dict.

    Extracts title, description, demographic, status, cover URL, content
    rating, and genre tags. Statistics fields are left as ``None`` and
    filled later by :func:`apply_statistics`.

    When ``language`` is provided, resolves title and description in that
    language, falling back to ``en`` then to the first available value.
    """
    attributes = item.get("attributes", {})
    relationships = item.get("relationships", [])

    # Title (language-aware: requested → en → first available)
    titles = attributes.get("title", {})
    title = (
        titles.get(language)
        or titles.get("en")
        or next(iter(titles.values()), "Unknown")
    )

    # Description (language-aware: requested → en → None)
    descriptions = attributes.get("description", {})
    description = descriptions.get(language) or descriptions.get("en")

    # Demographic
    demographic = attributes.get("publicationDemographic")
    if demographic == "none":
        demographic = None

    # Latest upload
    latest_uploaded_chapter = attributes.get("latestUploadedChapter")

    # Status
    status = attributes.get("status")

    # Cover
    cover_file = None
    for rel in relationships:
        if rel.get("type") == "cover_art":
            cover_file = rel.get("attributes", {}).get("fileName")
            break

    cover_url = (
        f"{COVER_BASE_URL}/{item['id']}/{cover_file}.256.jpg" if cover_file else None
    )

    # MAL ID from MangaDex links (used by Jikan enrichment)
    links = attributes.get("links") or {}
    mal_id = links.get("mal")
    if mal_id is not None:
        try:
            mal_id = int(mal_id)
        except (ValueError, TypeError):
            mal_id = None

    # Content rating
    content_rating = attributes.get("contentRating")

    # Available translated languages (from GET /manga/{id})
    available_translated_languages = (
        attributes.get("availableTranslatedLanguages") or []
    )

    # Type mapping from originalLanguage
    _ORIGINAL_LANGUAGE_TO_TYPE = {
        "ja": "manga",
        "ko": "manhwa",
        "zh": "manhua",
    }
    original_language = attributes.get("originalLanguage")
    manga_type = (
        _ORIGINAL_LANGUAGE_TO_TYPE.get(original_language) if original_language else None
    )

    # Tags - extract genre names from attributes
    tags = attributes.get("tags", [])
    genre_names = [
        tag.get("attributes", {}).get("name", {}).get("en", "")
        for tag in tags
        if tag.get("attributes", {}).get("group") == "genre"
    ]

    return {
        "id": item.get("id"),
        "title": title,
        "type": manga_type,
        "description": description,
        "coverUrl": cover_url,
        "demographic": demographic,
        "latestUploadedChapter": latest_uploaded_chapter,
        "status": status,
        "contentRating": content_rating,
        "availableTranslatedLanguages": available_translated_languages,
        "genres": genre_names,
        "malId": mal_id,
        # ponytail: chapters always None from MangaDex, Jikan enrichment fills it
        "chapters": None,
        # ⬇️ Statistics (filled by get_statistics in service)
        "score": None,
        "rank": None,
        "popularity": None,
        "members": None,
        "favorites": None,
        "authors": [],
        "serialization": None,
        "startYear": None,
        "endYear": None,
    }


def apply_statistics(manga: dict[str, Any], stats: dict[str, Any]) -> dict[str, Any]:
    """Apply statistics (rating, follows) to a manga dict."""
    if not stats:
        return manga

    rating = stats.get("rating", {})
    follows = stats.get("follows", 0)

    # Update with actual values from MangaDex
    manga["score"] = rating.get("bayesian") or rating.get("average")
    manga["popularity"] = follows
    manga["favorites"] = follows  # Same value, keeping for compatibility

    return manga
