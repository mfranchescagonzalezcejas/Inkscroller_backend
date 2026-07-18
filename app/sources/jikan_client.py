"""HTTP client for the Jikan v4 REST API with retry support."""

from typing import cast

import httpx
from app.core.resilience import with_retry


class JikanClient:
    """HTTP client for the Jikan v4 REST API (MyAnimeList wrapper) with retry support."""

    def __init__(self, client: httpx.AsyncClient):
        """Initialise with an ``httpx.AsyncClient`` pre-configured with base URL."""
        self.client = client

    @with_retry(max_retries=2, base_delay=1.0)
    async def search_manga(self, title: str) -> dict:
        """Search for a manga by title, returning the first match."""
        response = await self.client.get(
            "/manga",
            params={
                "q": title,
                "limit": 1,
            },
        )
        response.raise_for_status()
        return cast("dict", response.json())

    @with_retry(max_retries=2, base_delay=1.0)
    async def get_manga_by_id(self, mal_id: int) -> dict:
        """Fetch manga details from Jikan v4 by MAL ID (much more precise than search)."""
        response = await self.client.get(f"/manga/{mal_id}")
        response.raise_for_status()
        return cast("dict", response.json())
