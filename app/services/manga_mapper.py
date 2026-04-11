from __future__ import annotations
from typing import Any

COVER_BASE_URL = "https://uploads.mangadex.org/covers"


def map_mangadex_manga(item: dict[str, Any]) -> dict[str, Any]:
    attributes = item.get("attributes", {})
    relationships = item.get("relationships", [])

    # Title
    titles = attributes.get("title", {})
    title = titles.get("en") or next(iter(titles.values()), "Unknown")

    # Description (base, Jikan la mejorará)
    descriptions = attributes.get("description", {})
    description = descriptions.get("en")

    # Demographic
    demographic = attributes.get("publicationDemographic")

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
        "description": description,
        "coverUrl": cover_url,
        "demographic": demographic,
        "status": status,
        "genres": genre_names,
        # ⬇️ Statistics (filled by get_statistics in service)
        "score": None,
        "rank": None,
        "popularity": None,
        "members": None,
        "favorites": None,
        "authors": [],
        "serialization": None,
        "chapters": None,
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
