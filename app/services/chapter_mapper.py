"""Map raw MangaDex chapter API items to internal dict format."""

import html
from datetime import datetime
from typing import Any, cast


def map_mangadex_chapter(item: dict[str, Any]) -> dict[str, Any]:
    """Map a raw MangaDex chapter item to the internal chapter dict format."""
    attr = item.get("attributes", {})

    pages = attr.get("pages", 0)
    external_url = attr.get("externalUrl")

    date = None
    if attr.get("publishAt"):
        date = datetime.fromisoformat(attr["publishAt"].replace("Z", "+00:00"))

    return {
        "id": item.get("id"),
        "number": attr.get("chapter"),
        "title": html.escape(attr.get("title")) if attr.get("title") else None,
        "date": date,
        "scanlation_group": _extract_scanlation_group_name(item),
        "language": attr.get("translatedLanguage", ""),
        # 🔑 LO IMPORTANTE
        "readable": pages > 0,
        "external": external_url is not None,
        "externalUrl": external_url,
    }


def _extract_scanlation_group_name(item: dict[str, Any]) -> str | None:
    """Extract the scanlation group name from a raw MangaDex chapter item's relationships."""
    relationships = item.get("relationships", [])
    for relationship in relationships:
        if relationship.get("type") != "scanlation_group":
            continue

        attributes = relationship.get("attributes", {})
        name = attributes.get("name") if isinstance(attributes, dict) else None
        if name:
            return html.escape(name)

        fallback_id = relationship.get("id")
        if fallback_id:
            return cast("str", fallback_id)

    return None
