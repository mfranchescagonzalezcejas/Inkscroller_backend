import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.core.cache import SimpleCache
from app.core.dependencies import (
    get_chapter_pages_service,
    get_chapter_service,
    get_manga_service,
)
from main import create_app


class FakeMangaService:
    def __init__(self):
        self.received_id = None
        self.search_queries = []
        self.list_calls = []

    async def get_by_id(self, manga_id: str):
        self.received_id = manga_id
        return {
            "id": manga_id,
            "title": "One Piece",
            "authors": [],
            "genres": [],
        }

    async def search(self, query: str):
        self.search_queries.append(query)
        return [
            {
                "id": "search-1",
                "title": f"Result for {query}",
                "authors": [],
                "genres": [],
            }
        ]

    async def list_manga(self, **kwargs):
        self.list_calls.append(kwargs)
        return {"data": [], "total": 0, **kwargs}


class FakeChapterService:
    def __init__(self, chapters=None):
        self.chapters = chapters if chapters is not None else []
        self.calls = []

    async def get_chapters(self, manga_id: str, language: str = "en"):
        self.calls.append({"manga_id": manga_id, "language": language})
        return self.chapters


class FakeChapterPagesService:
    def __init__(self):
        self.received_id = None

    async def get_pages(self, chapter_id: str):
        self.received_id = chapter_id
        return {
            "readable": True,
            "external": False,
            "pages": ["https://cdn.example/page-1.jpg"],
        }


class AppSmokeTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def test_ping_returns_ok(self):
        with TestClient(self.app) as client:
            response = client.get("/ping")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

    def test_lifespan_initializes_shared_resources(self):
        with TestClient(self.app) as client:
            self.assertIsInstance(client.app.state.cache, SimpleCache)
            self.assertEqual(
                str(client.app.state.mangadex_http.base_url),
                "https://api.mangadex.org",
            )
            self.assertEqual(
                str(client.app.state.jikan_http.base_url),
                "https://api.jikan.moe/v4/",
            )

    def test_manga_route_trims_id_before_calling_service(self):
        fake_service = FakeMangaService()
        self.app.dependency_overrides[get_manga_service] = lambda: fake_service

        with TestClient(self.app) as client:
            response = client.get("/manga/%20abc-123%20")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake_service.received_id, "abc-123")
        self.assertEqual(response.json()["id"], "abc-123")

    def test_search_route_uses_overridden_manga_service(self):
        fake_service = FakeMangaService()
        self.app.dependency_overrides[get_manga_service] = lambda: fake_service

        with TestClient(self.app) as client:
            response = client.get("/manga/search?q=berserk")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake_service.search_queries, ["berserk"])
        self.assertEqual(response.json()[0]["id"], "search-1")

    def test_list_manga_route_passes_query_params_to_service(self):
        fake_service = FakeMangaService()
        self.app.dependency_overrides[get_manga_service] = lambda: fake_service

        with TestClient(self.app) as client:
            response = client.get(
                "/manga?limit=10&offset=5&title=monster&status=ongoing&order=latest"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            fake_service.list_calls,
            [
                {
                    "limit": 10,
                    "offset": 5,
                    "title": "monster",
                    "demographic": None,
                    "status": "ongoing",
                    "order": "latest",
                    "genre": None,
                }
            ],
        )

    def test_chapters_route_passes_language_and_returns_items(self):
        fake_service = FakeChapterService(
            chapters=[
                {
                    "id": "chapter-1",
                    "number": "1",
                    "title": "Arrival",
                    "date": datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat(),
                    "scanlation_group": "Team Ink",
                    "readable": True,
                    "external": False,
                    "externalUrl": None,
                }
            ]
        )
        self.app.dependency_overrides[get_chapter_service] = lambda: fake_service

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/manga-77?lang=es")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake_service.calls, [{"manga_id": "manga-77", "language": "es"}])
        self.assertEqual(response.json()[0]["id"], "chapter-1")
        self.assertEqual(response.json()[0]["scanlation_group"], "Team Ink")

    def test_chapters_route_returns_404_when_service_returns_empty(self):
        fake_service = FakeChapterService(chapters=[])
        self.app.dependency_overrides[get_chapter_service] = lambda: fake_service

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/manga-404")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "No chapters found")

    def test_pages_route_trims_chapter_id_before_service_call(self):
        fake_service = FakeChapterPagesService()
        self.app.dependency_overrides[get_chapter_pages_service] = lambda: fake_service

        with TestClient(self.app) as client:
            response = client.get("/chapters/%20chapter-9%20/pages")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake_service.received_id, "chapter-9")
        self.assertEqual(response.json()["readable"], True)


if __name__ == "__main__":
    unittest.main()
