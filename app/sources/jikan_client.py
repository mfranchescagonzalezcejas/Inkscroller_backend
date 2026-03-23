import httpx

from app.core.resilience import with_retry


class JikanClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    @with_retry(max_retries=2, base_delay=1.0)
    async def search_manga(self, title: str):
        response = await self.client.get(
            "/manga",
            params={
                "q": title,
                "limit": 1,
            },
        )
        response.raise_for_status()
        return response.json()
