import httpx
from typing import Any

class MangaDexClient:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def search_manga(self, query: str, limit: int = 5):
        response = await self.client.get(
            "/manga",
            params={
                "title": query,
                "limit": limit,
                "includes[]": ["cover_art"],  # 👈 CLAVE
            },
        )
        response.raise_for_status()
        return response.json()
    async def get_manga(self, manga_id: str):
        response = await self.client.get(
            f"/manga/{manga_id}",
            params={
                "includes[]": ["cover_art"],
            },
        )
        response.raise_for_status()
        return response.json()
    
    async def get_chapters(
        self,
        manga_id: str,
        language: str = "en",
        limit: int = 100,
    ):
        response = await self.client.get(
            "/chapter",
            params={
                "manga": manga_id,
                "translatedLanguage[]": language,
                "order[chapter]": "asc",
                "limit": limit,
            },
        )
        response.raise_for_status()
        return response.json()

    async def get_chapter_pages(self, chapter_id: str) -> dict:
        response = await self.client.get(
            f"/at-home/server/{chapter_id}"
        )
        response.raise_for_status()
        return response.json()

    async def list_manga(
        self,
        limit: int,
        offset: int,
        title: str | None = None,
        demographic: str | None = None,
        status: str | None = None,
        order: str | None = None,
    ):
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "includes[]": ["cover_art"],
        }

        if title:
            params["title"] = title

        if demographic:
            params["publicationDemographic[]"] = demographic

        if status:
            params["status[]"] = status

        if order:
            # Ejemplo: order=latest
            if order == "latest":
                params["order[latestUploadedChapter]"] = "desc"
            elif order == "title":
                params["order[title]"] = "asc"

        response = await self.client.get("/manga", params=params)
        response.raise_for_status()
        return response.json()
