#!/usr/bin/env python3
"""One-shot backfill: enrich user_library rows that have NULL metadata.

Existing rows created before the fix/131 PR don't have enriched MangaDex+Jikan
metadata (score, demographic, malId, genres, chapters, description, status,
etc.). This script iterates every row where ``score IS NULL``, fetches
enriched data via the existing MangaService pipeline, and writes it back.

Usage (from project root, with venv activated):

    source venv/bin/activate
    python -m scripts.backfill_library_metadata

Set BATCH_DELAY (default 0.5s) between requests to avoid upstream rate limits.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

import httpx

from app.core.cache import SimpleCache
from app.core.config import settings
from app.core.database import init_db
from app.services.manga_service import MangaService
from app.sources.jikan_client import JikanClient
from app.sources.mangadex_client import MangaDexClient

logger = logging.getLogger(__name__)

BATCH_DELAY = 0.5  # seconds between manga to avoid rate limiting


def _utc_now() -> str:
    """Return ISO-8601 UTC timestamp."""
    return time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logger.info("Initialising database …")
    db = await init_db()

    rows = await db.fetchall(
        "SELECT manga_id FROM user_library WHERE score IS NULL ORDER BY added_at DESC"
    )
    if not rows:
        logger.info("No rows need backfill — all metadata already populated.")
        await db.close()
        return

    logger.info("Found %d row(s) to backfill.", len(rows))

    async with (
        httpx.AsyncClient(
            base_url=settings.mangadex_base_url,
            timeout=httpx.Timeout(settings.request_timeout_seconds),
        ) as mangadex_http,
        httpx.AsyncClient(
            base_url=settings.jikan_base_url,
            timeout=httpx.Timeout(settings.request_timeout_seconds),
        ) as jikan_http,
    ):
        mangadex = MangaDexClient(mangadex_http)
        jikan = JikanClient(jikan_http)
        cache = SimpleCache(ttl_seconds=3600, maxsize=200)
        manga_service = MangaService(mangadex, jikan, cache)

        for i, row in enumerate(rows):
            manga_id = row["manga_id"]
            logger.info("[%d/%d] Processing %s …", i + 1, len(rows), manga_id)

            try:
                result = await manga_service.get_by_id(manga_id, skip_age_filter=True)
            except Exception:
                logger.exception(
                    "[%d/%d] %s — fetch failed, skipping", i + 1, len(rows), manga_id
                )
                await asyncio.sleep(BATCH_DELAY)
                continue

            if result is None:
                logger.warning(
                    "[%d/%d] %s — not found upstream, skipping",
                    i + 1,
                    len(rows),
                    manga_id,
                )
                await asyncio.sleep(BATCH_DELAY)
                continue

            try:
                await db.execute(
                    """UPDATE user_library SET
                        title = COALESCE(?, title),
                        cover_url = COALESCE(?, cover_url),
                        authors = COALESCE(?, authors),
                        content_rating = COALESCE(?, content_rating),
                        description = COALESCE(?, description),
                        demographic = COALESCE(?, demographic),
                        status = COALESCE(?, status),
                        score = COALESCE(?, score),
                        rank = COALESCE(?, rank),
                        popularity = COALESCE(?, popularity),
                        members = COALESCE(?, members),
                        favorites = COALESCE(?, favorites),
                        serialization = COALESCE(?, serialization),
                        genres = COALESCE(?, genres),
                        chapters = COALESCE(?, chapters),
                        start_year = COALESCE(?, start_year),
                        end_year = COALESCE(?, end_year),
                        mal_id = COALESCE(?, mal_id),
                        updated_at = ?
                    WHERE manga_id = ?""",
                    result.get("title"),
                    result.get("coverUrl"),
                    json.dumps(result.get("authors") or []),
                    result.get("contentRating"),
                    result.get("description"),
                    result.get("demographic"),
                    result.get("status"),
                    result.get("score"),
                    result.get("rank"),
                    result.get("popularity"),
                    result.get("members"),
                    result.get("favorites"),
                    result.get("serialization"),
                    json.dumps(result.get("genres") or []),
                    result.get("chapters"),
                    result.get("startYear"),
                    result.get("endYear"),
                    result.get("malId"),
                    _utc_now(),
                    manga_id,
                )
                await db.commit()
                logger.info(
                    "[%d/%d] %s — enriched successfully", i + 1, len(rows), manga_id
                )
            except Exception:
                logger.exception(
                    "[%d/%d] %s — DB update failed", i + 1, len(rows), manga_id
                )

            if i < len(rows) - 1:
                await asyncio.sleep(BATCH_DELAY)

    await db.close()
    logger.info("Backfill complete.")


if __name__ == "__main__":
    asyncio.run(main())
