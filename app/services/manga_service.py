from __future__ import annotations

import logging
import uuid
import hashlib
import hmac

from app.sources.mangadex_client import MangaDexClient
from app.core.cache import SimpleCache
from app.sources.jikan_client import JikanClient
from app.services.manga_mapper import map_mangadex_manga, apply_statistics
from app.services.jikan_mapper import map_jikan_detail
from app.core.manga_tags import GENRE_TAG_UUIDS
from app.core.config import settings
from app.core.age import can_access_content, can_access_demographic

logger = logging.getLogger(__name__)


class MangaService:
    def __init__(
        self,
        client: MangaDexClient,
        jikan: JikanClient,
        cache: SimpleCache,
        worker_client: MangaDexClient | None = None,
    ) -> None:
        self._client = client
        self._worker_client = worker_client
        self._jikan = jikan
        self._cache = cache
        self._snapshots: dict[str, tuple[str, list[dict]]] = {}

    @staticmethod
    def _matches_demographic(manga: dict, demographics: list[str]) -> bool:
        """Return whether a mapped title belongs to the requested OR-union."""
        return (
            manga.get("demographic") is None and "unspecified" in demographics
        ) or manga.get("demographic") in demographics

    async def _map_and_filter(
        self, items: list[dict], user_age: int | None, skip_statistics: bool = False
    ) -> list[dict]:
        """Map MangaDex items and apply the existing age gates once."""
        result = [map_mangadex_manga(item) for item in items]
        if result and not skip_statistics:
            try:
                statistics = await self._client.get_statistics(
                    [manga["id"] for manga in result]
                )
                for manga in result:
                    apply_statistics(
                        manga, statistics.get("statistics", {}).get(manga["id"], {})
                    )
            except Exception:
                logger.warning("Failed to fetch manga statistics", exc_info=True)
        return self._filter_by_age(result, user_age)

    async def _scan_union(
        self,
        fetches: list,
        demographics: list[str],
        user_age: int | None,
        order: str | None = None,
        max_offset: int = 1000,
    ) -> list[dict]:
        """Build the complete authorized union before exposing its first page.

        Scans up to ``max_offset`` items per fetch to limit upstream requests.
        """
        merged: dict[str, dict] = {}
        for fetch in fetches:
            offset = 0
            while True:
                payload = await fetch(offset)
                raw_items = payload.get("data", []) if isinstance(payload, dict) else []
                mapped = await self._map_and_filter(
                    raw_items, user_age, skip_statistics=True
                )
                for manga in mapped:
                    if (
                        self._matches_demographic(manga, demographics)
                        and manga["id"] not in merged
                    ):
                        merged[manga["id"]] = manga
                offset += len(raw_items)
                if (
                    not raw_items
                    or offset >= payload.get("total", offset)
                    or offset >= max_offset
                ):
                    break
        items = list(merged.values())
        if order:
            _order_fields = {
                "popular": ("popularity", True),
                "rating": ("score", True),
                "title": ("title", False),
                "latest": ("latestUploadedChapter", True),
            }
            entry = _order_fields.get(order)
            if entry:
                key, reverse = entry
                # latestUploadedChapter is a nullable string — use "" not 0
                # to avoid TypeError comparing int vs str in Python 3
                if key == "latestUploadedChapter":
                    items.sort(key=lambda m: m.get(key) or "", reverse=reverse)
                else:
                    items.sort(key=lambda m: m.get(key) or 0, reverse=reverse)
        return items

    @staticmethod
    def _snapshot_cache_key(snapshot_id: str) -> str:
        return f"manga:snapshot:{snapshot_id}"

    def _snapshot_page(
        self, items: list[dict], limit: int, offset: int, fingerprint: str
    ) -> dict:
        """Persist a five-minute snapshot in the shared application cache."""
        snapshot_id = uuid.uuid4().hex
        self._snapshots[snapshot_id] = (fingerprint, items)
        self._cache.set(self._snapshot_cache_key(snapshot_id), (fingerprint, items))
        page = items[offset : offset + limit]
        next_cursor = None
        if offset + len(page) < len(items):
            token = self._cursor_token(snapshot_id, offset + len(page), fingerprint)
            if token:
                next_cursor = token
        return {
            "data": page,
            "limit": limit,
            "offset": offset,
            "total": len(items),
            "has_more": offset + len(page) < len(items),
            "next_cursor": next_cursor,
        }

    @classmethod
    def _cursor_token(cls, snapshot_id: str, offset: int, fingerprint: str) -> str:
        secret = settings.cursor_secret
        if not secret:
            return ""
        payload = f"{snapshot_id}:{offset}:{fingerprint}".encode()
        signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return f"{snapshot_id}:{offset}:{signature}"

    async def _cursor_page(self, cursor: str, limit: int, fingerprint: str) -> dict:
        """Read a verified page from a live snapshot without rescanning upstream."""
        try:
            snapshot_id, raw_offset, signature = cursor.rsplit(":", 2)
            offset = int(raw_offset)
            snapshot = self._cache.get(self._snapshot_cache_key(snapshot_id))
            if not isinstance(snapshot, tuple):
                snapshot = self._snapshots[snapshot_id]
            saved_fingerprint, items = snapshot
        except (KeyError, TypeError, ValueError):
            raise ValueError("Unknown snapshot cursor") from None
        if saved_fingerprint != fingerprint:
            raise ValueError("Snapshot cursor does not match this request")
        expected = self._cursor_token(snapshot_id, offset, fingerprint).rsplit(":", 1)[
            1
        ]
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid snapshot cursor")
        page = items[offset : offset + limit]
        page = await self._fetch_statistics(page)
        next_offset = offset + len(page)
        has_more = next_offset < len(items)
        next_cursor = None
        if has_more:
            token = self._cursor_token(snapshot_id, next_offset, fingerprint)
            if token:
                next_cursor = token
        return {
            "data": page,
            "limit": limit,
            "offset": offset,
            "total": len(items),
            "has_more": has_more,
            "next_cursor": next_cursor,
        }

    @staticmethod
    def _age_allowed_content_ratings(user_age: int | None) -> list[str]:
        """Content ratings the user can access, so we only ask MangaDex for those."""
        if user_age is None or user_age < 16:
            return ["safe"]
        if user_age < 18:
            return ["safe", "suggestive"]
        return ["safe", "suggestive", "erotica", "pornographic"]

    def _filter_by_age(
        self, manga_list: list[dict], user_age: int | None
    ) -> list[dict]:
        """Filter out manga that the user cannot access due to age restrictions.

        Applies two gates:
        1. Demographic: content without publication demographic (doujinshi/self-published)
           is restricted to registered adults (18+).
        2. Content rating: age-gating per content rating (safe/suggestive/erotica/pornographic).
        """
        return [
            m
            for m in manga_list
            if can_access_demographic(m.get("demographic"), user_age)
            and can_access_content(m.get("contentRating"), user_age)
        ]

    @staticmethod
    def _content_rating_to_mangadex(content_rating: str | None) -> list[str]:
        """Map frontend aggregate content_rating to MangaDex content rating values.

        ``None`` and unknown values fall back to ``["safe"]`` — the most
        restrictive option — so the backend never broadens access on an
        unrecognised wire value.
        """
        mapping = {
            "safe": ["safe"],
            "suggestive": ["safe", "suggestive"],
            "all": ["safe", "suggestive", "erotica", "pornographic"],
        }
        return mapping.get(content_rating, ["safe"])

    def _resolve_content_ratings(
        self, user_age: int | None, content_rating: str | None
    ) -> list[str]:
        """Resolve which MangaDex content ratings to request.

        When the caller provides an explicit ``content_rating`` preference,
        use it — but always intersect with the age-allowed set so that
        a minor cannot escalate their access via the query parameter.
        When ``content_rating`` is ``None``, fall back to the age-based
        default.
        """
        age_allowed = self._age_allowed_content_ratings(user_age)

        if content_rating is None:
            return age_allowed

        explicit = self._content_rating_to_mangadex(content_rating)
        return [r for r in explicit if r in age_allowed]

    async def _fetch_statistics(self, items: list[dict]) -> list[dict]:
        """Fetch and merge statistics once for a final merged list."""
        if not items:
            return items
        try:
            manga_ids = [m["id"] for m in items]
            stats = await self._client.get_statistics(manga_ids)
            stats_dict = stats.get("statistics", {})
            for manga in items:
                apply_statistics(manga, stats_dict.get(manga["id"], {}))
        except Exception:
            logger.warning("Failed to fetch statistics for merged list", exc_info=True)
        return items

    async def search(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        user_age: int | None = None,
        content_rating: str | None = None,
        demographic: list[str] | None = None,
        cursor: str | None = None,
    ) -> dict:
        if demographic and "unspecified" in demographic:
            fingerprint = (
                f"search:{query}:{user_age}:{content_rating}:{sorted(demographic)}"
            )
            if cursor is not None:
                return await self._cursor_page(cursor, limit, fingerprint)
            named = [d for d in demographic if d != "unspecified"]
            fetches: list = []
            if named:
                fetches.append(
                    lambda page_offset: self._client.search_manga(
                        query=query,
                        limit=100,
                        offset=page_offset,
                        content_ratings=self._resolve_content_ratings(
                            user_age, content_rating
                        ),
                        demographic=named,
                    )
                )
            worker = self._worker_client or self._client
            fetches.append(
                lambda page_offset: worker.search_manga(
                    query=query,
                    limit=100,
                    offset=page_offset,
                    content_ratings=self._resolve_content_ratings(
                        user_age, content_rating
                    ),
                    demographic=["none"],
                )
            )
            items = await self._scan_union(
                fetches,
                demographic,
                user_age,
            )
            result = self._snapshot_page(items, limit, offset, fingerprint)
            result["data"] = await self._fetch_statistics(result["data"])
            return result
        if cursor is not None:
            raise ValueError("Cursor does not match this request")
        cr_key = content_rating or "default"
        age_key = "none" if user_age is None else str(user_age)
        demo_key = ":".join(sorted(demographic)) if demographic else "none"
        cache_key = (
            f"search:{query}:{limit}:{offset}:age:{age_key}:cr:{cr_key}:demo:{demo_key}"
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        search_kwargs = {
            "query": query,
            "limit": limit,
            "offset": offset,
            "content_ratings": self._resolve_content_ratings(user_age, content_rating),
        }
        if demographic is not None:
            search_kwargs["demographic"] = demographic
        payload = await self._client.search_manga(**search_kwargs)
        items = payload.get("data", []) if isinstance(payload, dict) else []
        total_count = payload.get("total", len(items))
        result = [map_mangadex_manga(item) for item in items]

        # Fetch statistics (ratings/scores) for search results
        if result:
            try:
                manga_ids = [m["id"] for m in result]
                stats_payload = await self._client.get_statistics(manga_ids)
                stats_dict = stats_payload.get("statistics", {})
                for manga in result:
                    manga_stats = stats_dict.get(manga["id"], {})
                    apply_statistics(manga, manga_stats)
            except Exception:
                logger.warning(
                    "Failed to fetch statistics for search results, continuing without ratings",
                    exc_info=True,
                )

        result = self._filter_by_age(result, user_age)

        response = {
            "data": result,
            "limit": limit,
            "offset": offset,
            "total": total_count,
        }

        self._cache.set(cache_key, response)
        return response

    async def list_manga(
        self,
        limit: int = 20,
        offset: int = 0,
        title: str | None = None,
        demographic: list[str] | None = None,
        status: str | None = None,
        order: str | None = None,
        genre: str | None = None,
        user_age: int | None = None,
        content_rating: str | None = None,
        cursor: str | None = None,
    ) -> dict:
        if demographic and "unspecified" in demographic:
            fingerprint = f"list:{title}:{status}:{order}:{genre}:{user_age}:{content_rating}:{sorted(demographic)}"
            if cursor is not None:
                return await self._cursor_page(cursor, limit, fingerprint)
            included_tags = None
            if genre:
                tag_uuid = GENRE_TAG_UUIDS.get(genre.lower())
                if tag_uuid:
                    included_tags = [tag_uuid]
            named = [d for d in demographic if d != "unspecified"]
            fetches: list = []
            if named:
                fetches.append(
                    lambda page_offset: self._client.list_manga(
                        limit=100,
                        offset=page_offset,
                        title=title,
                        demographic=named,
                        status=status,
                        order=order,
                        included_tags=included_tags,
                        content_ratings=self._resolve_content_ratings(
                            user_age, content_rating
                        ),
                    )
                )
            worker = self._worker_client or self._client
            fetches.append(
                lambda page_offset: worker.list_manga(
                    limit=100,
                    offset=page_offset,
                    title=title,
                    demographic=["none"],
                    status=status,
                    order=order,
                    included_tags=included_tags,
                    content_ratings=self._resolve_content_ratings(
                        user_age, content_rating
                    ),
                )
            )
            items = await self._scan_union(
                fetches,
                demographic,
                user_age,
                order=order,
            )
            # ponytail: popular/rating need full stats for correct global sort
            if order in ("popular", "rating"):
                items = await self._fetch_statistics(items)
                key = "popularity" if order == "popular" else "score"
                items.sort(key=lambda m: m.get(key, 0) or 0, reverse=True)
                result = self._snapshot_page(items, limit, offset, fingerprint)
            else:
                result = self._snapshot_page(items, limit, offset, fingerprint)
                result["data"] = await self._fetch_statistics(result["data"])
            return result
        if cursor is not None:
            raise ValueError("Cursor does not match this request")
        cr_key = content_rating or "default"
        age_key = "none" if user_age is None else str(user_age)
        demo_key = ":".join(sorted(demographic)) if demographic else "none"
        cache_key = (
            f"manga:list:{limit}:{offset}:{title}:{demo_key}:"
            f"{status}:{order}:{genre}:age:{age_key}:cr:{cr_key}"
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        # Resolve genre name to MangaDex tag UUID
        included_tags: list[str] | None = None
        if genre:
            tag_uuid = GENRE_TAG_UUIDS.get(genre.lower())
            if tag_uuid:
                included_tags = [tag_uuid]

        payload = await self._client.list_manga(
            limit=limit,
            offset=offset,
            title=title,
            demographic=demographic,
            status=status,
            order=order,
            included_tags=included_tags,
            content_ratings=self._resolve_content_ratings(user_age, content_rating),
        )

        items = payload.get("data", [])

        # Capture upstream total BEFORE filtering so pagination metadata
        # reflects the actual dataset size, not just the current page.
        total_count = payload.get("total", len(items))
        result = [map_mangadex_manga(item) for item in items]

        # Always fetch statistics to get rating for all manga lists
        if result:
            try:
                manga_ids = [m["id"] for m in result]
                stats_payload = await self._client.get_statistics(manga_ids)
                stats_dict = stats_payload.get("statistics", {})

                # Apply statistics to each manga
                for manga in result:
                    manga_stats = stats_dict.get(manga["id"], {})
                    apply_statistics(manga, manga_stats)
            except Exception:
                logger.warning(
                    "Failed to fetch statistics for manga list, continuing without ratings",
                    exc_info=True,
                )

        result = self._filter_by_age(result, user_age)

        response = {
            "data": result,
            "limit": limit,
            "offset": offset,
            "total": total_count,
        }

        self._cache.set(cache_key, response)
        return response

    async def get_by_id(
        self,
        manga_id: str,
        user_age: int | None = None,
        skip_age_filter: bool = False,
    ) -> dict | None:
        cache_key = f"manga:{manga_id}"
        cached = self._cache.get(cache_key)

        if cached is not None:
            # Cache always stores raw (unfiltered) data; re-evaluate access
            # per request so that a prior ``skip_age_filter=True`` call cannot
            # poison the shared cache for age-restricted readers.
            if skip_age_filter:
                return cached
            if user_age is None and cached.get("contentRating") != "safe":
                return None  # guest: only safe content
            if can_access_content(cached.get("contentRating"), user_age):
                return cached
            return None

        payload = await self._client.get_manga(manga_id)
        item = payload.get("data")
        if not item:
            return None

        # Base MangaDex — always cache raw data
        result = map_mangadex_manga(item)

        # 🔥 Enriquecimiento con Jikan (rellenar huecos) — feature flag
        if settings.enable_jikan_enrichment:
            try:
                jikan_payload = await self._jikan.search_manga(result["title"])
                search_data = jikan_payload.get("data", [])
                jikan_data = (
                    map_jikan_detail({"data": search_data[0]}) if search_data else None
                )

                if jikan_data is not None:
                    for key, value in jikan_data.items():
                        # Solo rellenamos si MangaDex no tenía el dato
                        if result.get(key) in (None, [], "") and value not in (
                            None,
                            [],
                            "",
                        ):
                            result[key] = value
            except Exception:
                logger.warning(
                    "Jikan enrichment failed for manga %s, continuing without it",
                    manga_id,
                    exc_info=True,
                )

        self._cache.set(cache_key, result)

        # Age restriction — applied AFTER cache write so the shared cache
        # always holds raw data and access is re-evaluated per request.
        if skip_age_filter:
            return result
        if user_age is None and result.get("contentRating") != "safe":
            return None  # guest: only safe content
        if not can_access_content(result.get("contentRating"), user_age):
            return None
        if not can_access_demographic(result.get("demographic"), user_age):
            return None

        return result
