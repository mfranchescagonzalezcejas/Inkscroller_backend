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

    return {
        "id": item.get("id"),
        "title": title,
        "description": description,
        "coverUrl": cover_url,
        "demographic": demographic,
        "status": status,
        # ⬇️ EXTRAS (vacíos, Jikan los rellena)
        "genres": [],
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
