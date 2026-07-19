"""Map Jikan API response data to internal manga enrichment dict format."""

import html
from typing import Any


def map_jikan_detail(payload: dict[str, Any]) -> dict[str, Any]:
    """Map a Jikan API manga response into the internal enrichment dict format."""
    manga = payload.get("data", {})

    demographics = manga.get("demographics") or []
    demographic = demographics[0]["name"].lower() if demographics else None

    published = manga.get("published", {}).get("prop", {})

    return {
        "description": html.escape(manga.get("synopsis"))
        if manga.get("synopsis")
        else None,
        "status": manga.get("status"),
        "score": manga.get("score"),
        "scoredBy": manga.get("scored_by"),
        "rank": manga.get("rank"),
        "popularity": manga.get("popularity"),
        "members": manga.get("members"),
        "favorites": manga.get("favorites"),
        "chapters": manga.get("chapters"),
        "volumes": manga.get("volumes"),
        "authors": [html.escape(a["name"]) for a in manga.get("authors", [])],
        "serialization": (
            html.escape(manga.get("serializations", [{}])[0].get("name"))
            if manga.get("serializations")
            else None
        ),
        "genres": [html.escape(g["name"].lower()) for g in manga.get("genres", [])],
        "demographic": demographic,
        "startYear": published.get("from", {}).get("year"),
        "endYear": published.get("to", {}).get("year"),
    }
