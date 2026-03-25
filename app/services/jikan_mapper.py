from typing import Any


def map_jikan_detail(payload: dict[str, Any]) -> dict[str, Any]:
    manga = payload.get("data", {})

    demographics = manga.get("demographics") or []
    demographic = demographics[0]["name"].lower() if demographics else None

    published = manga.get("published", {}).get("prop", {})

    return {
        "description": manga.get("synopsis"),
        "status": manga.get("status"),
        "score": manga.get("score"),
        "scoredBy": manga.get("scored_by"),
        "rank": manga.get("rank"),
        "popularity": manga.get("popularity"),
        "members": manga.get("members"),
        "favorites": manga.get("favorites"),
        "chapters": manga.get("chapters"),
        "volumes": manga.get("volumes"),
        "authors": [a["name"] for a in manga.get("authors", [])],
        "serialization": (
            manga.get("serializations", [{}])[0].get("name")
            if manga.get("serializations")
            else None
        ),
        "genres": [g["name"].lower() for g in manga.get("genres", [])],
        "demographic": demographic,
        "startYear": published.get("from", {}).get("year"),
        "endYear": published.get("to", {}).get("year"),
    }
