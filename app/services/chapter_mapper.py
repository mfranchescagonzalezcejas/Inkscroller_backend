from datetime import datetime
from typing import Any

def map_mangadex_chapter(item: dict[str, Any]) -> dict[str, Any]:
    attr = item.get("attributes", {})

    pages = attr.get("pages", 0)
    external_url = attr.get("externalUrl")

    date = None
    if attr.get("publishAt"):
        date = datetime.fromisoformat(
            attr["publishAt"].replace("Z", "+00:00")
        )

    return {
        "id": item.get("id"),
        "number": attr.get("chapter"),
        "title": attr.get("title"),
        "date": date,

        # 🔑 LO IMPORTANTE
        "readable": pages > 0,
        "external": external_url is not None,
        "externalUrl": external_url,
    }
