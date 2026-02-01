import httpx

BASE_URL = "https://api.jikan.moe/v4"


class JikanClient:
    def __init__(self):
        self.client = httpx.AsyncClient(base_url=BASE_URL)

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
