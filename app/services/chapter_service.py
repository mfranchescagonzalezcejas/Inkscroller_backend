from datetime import datetime, timezone
from typing import List
from app.sources.mangadex_client import MangaDexClient
from app.core.cache import SimpleCache
from app.services.chapter_mapper import map_mangadex_chapter
from app.services.manga_mapper import COVER_BASE_URL


class ChapterService:
    def __init__(self, client: MangaDexClient, cache: SimpleCache):
        self._client = client
        self._cache = cache

    async def get_chapters(
        self,
        manga_id: str,
        language: str = "en",
    ) -> List[dict]:
        cache_key = f"chapters:{manga_id}:{language}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        payload = await self._client.get_chapters(
            manga_id=manga_id,
            language=language,
        )

        items = payload.get("data", [])
        result = [
            map_mangadex_chapter(item)
            for item in items
            if (
                item.get("attributes", {}).get("pages", 0) > 0
                or item.get("attributes", {}).get("externalUrl") is not None
            )
        ]

        self._cache.set(cache_key, result)
        return result

    async def get_latest_home_chapters(
        self,
        language: str = "en",
        limit: int = 10,
    ) -> List[dict]:
        cache_key = f"chapters:latest:home:v4:{language}:{limit}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        fetch_limit = min(max(limit * 5, 50), 100)
        payload = await self._client.get_latest_chapters(
            language=language,
            limit=fetch_limit,
        )
        chapter_items = payload.get("data", [])

        # Keep only readable/external entries to match reader behavior.
        chapter_items = [
            item
            for item in chapter_items
            if (
                item.get("attributes", {}).get("pages", 0) > 0
                or item.get("attributes", {}).get("externalUrl") is not None
            )
        ]

        # Filter out future-dated chapters from upstream.
        now_utc = datetime.now(timezone.utc)
        chapter_items = [
            item
            for item in chapter_items
            if _chapter_publish_at(item) is None or _chapter_publish_at(item) <= now_utc
        ]

        manga_ids: list[str] = []
        chapter_to_manga: dict[str, str] = {}
        for item in chapter_items:
            chapter_id = item.get("id")
            rels = item.get("relationships", [])
            manga_rel = next((r for r in rels if r.get("type") == "manga"), None)
            manga_id = manga_rel.get("id") if manga_rel else None
            if chapter_id and manga_id:
                chapter_to_manga[chapter_id] = manga_id
                if manga_id not in manga_ids:
                    manga_ids.append(manga_id)

        manga_payload = await self._client.get_manga_list_by_ids(manga_ids)
        manga_items = manga_payload.get("data", [])

        manga_map: dict[str, dict] = {}
        for manga in manga_items:
            manga_id = manga.get("id")
            attributes = manga.get("attributes", {})
            titles = attributes.get("title", {})
            title = titles.get("en") or next(iter(titles.values()), "Unknown")

            cover_file = None
            for rel in manga.get("relationships", []):
                if rel.get("type") == "cover_art":
                    cover_file = rel.get("attributes", {}).get("fileName")
                    break

            cover_url = (
                f"{COVER_BASE_URL}/{manga_id}/{cover_file}.256.jpg"
                if cover_file
                else None
            )

            if manga_id:
                manga_map[manga_id] = {
                    "title": title,
                    "coverUrl": cover_url,
                }

        raw_result: List[dict] = []
        for chapter_item in chapter_items:
            chapter_base = map_mangadex_chapter(chapter_item)
            chapter_id = chapter_base.get("id")
            if not chapter_id:
                continue

            manga_id = chapter_to_manga.get(chapter_id)
            if not manga_id:
                continue

            manga_info = manga_map.get(manga_id)
            if not manga_info:
                continue

            raw_result.append(
                {
                    "chapterId": chapter_id,
                    "mangaId": manga_id,
                    "mangaTitle": manga_info["title"],
                    "mangaCoverUrl": manga_info["coverUrl"],
                    "chapterNumber": chapter_base.get("number"),
                    "chapterTitle": chapter_base.get("title"),
                    "scanlation_group": chapter_base.get("scanlation_group"),
                    "publishAt": chapter_base.get("date"),
                    "readable": chapter_base.get("readable", False),
                    "external": chapter_base.get("external", False),
                }
            )

        # Cap repeated entries per manga to preserve variety in Home feed.
        max_per_manga = 2
        deduped: List[dict] = []
        per_manga_count: dict[str, int] = {}

        for item in raw_result:
            manga_id = item.get("mangaId")
            if not manga_id:
                continue

            current = per_manga_count.get(manga_id, 0)
            if current >= max_per_manga:
                continue

            deduped.append(item)
            per_manga_count[manga_id] = current + 1

            if len(deduped) >= limit:
                break

        self._cache.set(cache_key, deduped)
        return deduped


def _chapter_publish_at(item: dict) -> datetime | None:
    value = item.get("attributes", {}).get("publishAt")
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None
