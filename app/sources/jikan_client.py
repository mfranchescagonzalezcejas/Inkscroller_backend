import httpx


class JikanClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

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
