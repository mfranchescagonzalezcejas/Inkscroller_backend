"""HTTP client for the Jikan v4 REST API with retry support."""

import httpx

from app.core.resilience import with_retry


class JikanClient:
    """HTTP client for the Jikan v4 REST API (MyAnimeList wrapper) with retry support."""

    def __init__(self, client: httpx.AsyncClient):
        """Initialise with an ``httpx.AsyncClient`` pre-configured with base URL."""
        self.client = client

    @with_retry(max_retries=2, base_delay=1.0)
    async def search_manga(self, title: str):
        """Search for a manga by title, returning the first match."""
        response = await self.client.get(
            "/manga",
            params={
                "q": title,
                "limit": 1,
            },
        )
        response.raise_for_status()
        return response.json()
