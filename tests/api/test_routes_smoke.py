import unittest
from datetime import UTC, datetime
from importlib.util import find_spec
from unittest.mock import AsyncMock, MagicMock, patch

if find_spec("fastapi") is None:
    raise unittest.SkipTest("fastapi is not installed")

from app.core import database
from app.core.cache import SimpleCache
from app.core.config import settings
from app.core.dependencies import (
    get_chapter_pages_service,
    get_chapter_service,
    get_manga_service,
    get_tag_service,
    get_user_age,
    get_user_language,
)
from app.services.manga_service import MangaService
from app.services.tag_service import TagService
from app.sources.mangadex_client import MangaDexClient
from fastapi.testclient import TestClient
from tests.api.helpers import create_hermetic_test_app


class FakeMangaService:
    def __init__(self):
        self.received_id = None
        self.search_queries = []
        self.list_calls = []

    async def get_by_id(
        self, manga_id: str, user_age=None, skip_age_filter=False, language=None
    ):
        self.received_id = manga_id
        return {
            "id": manga_id,
            "title": "One Piece",
            "authors": [],
            "genres": [],
        }

    async def search(self, query: str, **kwargs):
        self.search_queries.append(query)
        return {
            "data": [
                {
                    "id": "search-1",
                    "title": f"Result for {query}",
                    "authors": [],
                    "genres": [],
                }
            ],
            "total": 1,
            "limit": kwargs.get("limit", 10),
            "offset": kwargs.get("offset", 0),
        }

    async def list_manga(self, **kwargs):
        self.list_calls.append(kwargs)
        return {"data": [], "total": 0, **kwargs}


class FakeChapterService:
    def __init__(self, chapters=None):
        self.chapters = chapters if chapters is not None else []
        self.calls = []
        self._chapter_manga_map = {}

    async def get_manga_id_for_chapter(self, chapter_id: str) -> str | None:
        return self._chapter_manga_map.get(chapter_id)

    async def get_chapters(self, manga_id: str, language: str | None = "en"):
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
        self.app = create_hermetic_test_app()
        self._secret_patcher = patch.object(
            settings, "cursor_secret", "test-secret-for-cursors"
        )
        self._secret_patcher.start()

    def tearDown(self):
        self._secret_patcher.stop()
        self.app.dependency_overrides.clear()

    def test_ping_returns_ok(self):
        with TestClient(self.app) as client:
            response = client.get("/ping")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

    def test_ready_returns_ok_when_db_is_healthy(self):
        with TestClient(self.app) as client:
            response = client.get("/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ready": True, "database": "ok"})

    def test_ready_returns_503_on_db_timeout(self):
        """Simulate a DB timeout to verify the 503 path returns a stable response."""
        from unittest.mock import patch

        with TestClient(self.app) as client:
            db = client.app.state.db
            with patch.object(db, "fetchone", side_effect=TimeoutError()):
                response = client.get("/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"ready": False, "database": "timeout"})

    def test_ready_returns_503_on_db_error(self):
        """Simulate a DB error to verify the 503 path does not leak exception details."""
        from unittest.mock import patch

        with TestClient(self.app) as client:
            db = client.app.state.db
            with patch.object(
                db, "fetchone", side_effect=Exception("internal db error")
            ):
                response = client.get("/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"ready": False, "database": "error"})

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

    def test_tags_uses_shared_mangadex_client(self):
        mangadex_http = MagicMock()
        response = MagicMock()
        response.json.return_value = {
            "data": [
                {
                    "id": "tag-1",
                    "attributes": {"name": {"en": "Action"}, "group": "genre"},
                }
            ]
        }
        mangadex_http.get = AsyncMock(return_value=response)

        with TestClient(self.app) as client:
            cache = client.app.state.cache
            client.app.state.mangadex_http = mangadex_http
            self.app.dependency_overrides[get_tag_service] = lambda: TagService(
                MangaDexClient(mangadex_http), cache
            )
            route_response = client.get("/manga/tags")

        self.assertEqual(route_response.status_code, 200)
        mangadex_http.get.assert_awaited_once_with("/manga/tag")
        self.assertEqual(
            route_response.json()["genres"],
            [{"id": "tag-1", "name": "Action"}],
        )

    def test_test_lifespan_ignores_configured_database_settings(self):
        original_database_url = settings.database_url
        original_cloud_sql_instance = settings.cloud_sql_instance
        settings.database_url = "postgresql://prod.example/inkscroller"
        settings.cloud_sql_instance = "prod-project:region:instance"

        try:
            with patch(
                "app.core.database._init_postgres",
                new_callable=AsyncMock,
                side_effect=AssertionError("test lifespan used configured database"),
            ) as init_postgres:
                with patch(
                    "app.core.database._init_sqlite",
                    new=AsyncMock(wraps=database._init_sqlite),
                ) as init_sqlite:
                    with TestClient(self.app) as client:
                        response = client.get("/ping")

            self.assertEqual(response.status_code, 200)
            init_sqlite.assert_awaited_once_with(":memory:")
            init_postgres.assert_not_awaited()
        finally:
            settings.database_url = original_database_url
            settings.cloud_sql_instance = original_cloud_sql_instance

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
        self.assertEqual(response.json()["data"][0]["id"], "search-1")

    def test_search_route_passes_limit_offset(self):
        fake_service = FakeMangaService()
        self.app.dependency_overrides[get_manga_service] = lambda: fake_service

        with TestClient(self.app) as client:
            response = client.get("/manga/search?q=berserk&limit=5&offset=10")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["limit"], 5)
        self.assertEqual(body["offset"], 10)
        self.assertEqual(body["total"], 1)

    def test_capabilities_advertise_cursor_null_union_contract(self):
        with TestClient(self.app) as client:
            response = client.get("/manga/capabilities")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "demographic_filter": {
                    "contract_version": 1,
                    "null_union": True,
                    "pagination": "cursor-v1",
                }
            },
        )

    def test_unknown_demographic_is_rejected_before_service(self):
        fake_service = FakeMangaService()
        self.app.dependency_overrides[get_manga_service] = lambda: fake_service

        with TestClient(self.app) as client:
            response = client.get("/manga?demographic=unknown")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(fake_service.list_calls, [])

    def test_guest_unspecified_passes_validation_to_service(self):
        fake_service = FakeMangaService()
        self.app.dependency_overrides[get_manga_service] = lambda: fake_service
        self.app.dependency_overrides[get_user_age] = lambda: None

        with TestClient(self.app) as client:
            response = client.get("/manga?demographic=unspecified")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(fake_service.list_calls), 1)

    def test_search_forwards_repeated_demographics(self):
        fake_service = FakeMangaService()
        self.app.dependency_overrides[get_manga_service] = lambda: fake_service
        self.app.dependency_overrides[get_user_age] = lambda: 18

        with TestClient(self.app) as client:
            response = client.get(
                "/manga/search?q=berserk&demographic=seinen&demographic=unspecified"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            fake_service.search_queries,
            ["berserk"],
        )

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
                    "user_age": None,
                    "content_rating": None,
                    "cursor": None,
                }
            ],
        )

    def test_list_cursor_conflict_returns_409(self):
        class ExpiredCursorService(FakeMangaService):
            async def list_manga(self, **kwargs):
                raise ValueError("Expired snapshot cursor")

        self.app.dependency_overrides[get_manga_service] = ExpiredCursorService
        self.app.dependency_overrides[get_user_age] = lambda: 18
        with TestClient(self.app, raise_server_exceptions=False) as client:
            response = client.get("/manga?demographic=unspecified&cursor=expired")

        self.assertEqual(response.status_code, 409)

    def test_cursor_continues_across_real_dependency_instances(self):
        client = MagicMock()
        client.list_manga = AsyncMock(
            return_value={
                "data": [
                    {
                        "id": "first",
                        "attributes": {
                            "title": {"en": "First"},
                            "publicationDemographic": None,
                            "contentRating": "safe",
                            "tags": [],
                        },
                        "relationships": [],
                    },
                    {
                        "id": "second",
                        "attributes": {
                            "title": {"en": "Second"},
                            "publicationDemographic": None,
                            "contentRating": "safe",
                            "tags": [],
                        },
                        "relationships": [],
                    },
                ],
                "total": 2,
            }
        )
        client.get_statistics = AsyncMock(return_value={"statistics": {}})
        self.app.dependency_overrides[get_manga_service] = lambda: MangaService(
            client, MagicMock(), self.app.state.cache
        )
        self.app.dependency_overrides[get_user_age] = lambda: 18

        with TestClient(self.app) as client_app:
            first = client_app.get("/manga?limit=1&demographic=unspecified")
            second = client_app.get(
                f"/manga?limit=1&demographic=unspecified&cursor={first.json()['next_cursor']}"
            )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["data"][0]["id"], "second")
        self.assertEqual(client.list_manga.await_count, 1)

    def test_chapters_route_passes_language_and_returns_items(self):
        fake_service = FakeChapterService(
            chapters=[
                {
                    "id": "chapter-1",
                    "number": "1",
                    "title": "Arrival",
                    "date": datetime(2024, 1, 1, tzinfo=UTC).isoformat(),
                    "scanlation_group": "Team Ink",
                    "language": "es",
                    "readable": True,
                    "external": False,
                    "externalUrl": None,
                }
            ]
        )
        fake_manga = FakeMangaService()
        self.app.dependency_overrides[get_chapter_service] = lambda: fake_service
        self.app.dependency_overrides[get_manga_service] = lambda: fake_manga
        self.app.dependency_overrides[get_user_age] = lambda: None
        self.app.dependency_overrides[get_user_language] = lambda: "es"

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/manga-77?lang=es")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            fake_service.calls, [{"manga_id": "manga-77", "language": "es"}]
        )
        self.assertEqual(response.json()[0]["id"], "chapter-1")
        self.assertEqual(response.json()[0]["scanlation_group"], "Team Ink")
        self.assertEqual(response.json()[0]["language"], "es")

    def test_chapters_route_returns_200_when_service_returns_empty(self):
        fake_service = FakeChapterService(chapters=[])
        fake_manga = FakeMangaService()
        self.app.dependency_overrides[get_chapter_service] = lambda: fake_service
        self.app.dependency_overrides[get_manga_service] = lambda: fake_manga
        self.app.dependency_overrides[get_user_age] = lambda: None
        self.app.dependency_overrides[get_user_language] = lambda: "es"

        with TestClient(self.app) as client:
            response = client.get("/chapters/manga/manga-404")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_pages_route_trims_chapter_id_before_service_call(self):
        fake_pages = FakeChapterPagesService()
        fake_manga = FakeMangaService()
        fake_chapter = FakeChapterService()
        # Chapter maps to a known manga so age-gate passes
        fake_chapter._chapter_manga_map["chapter-9"] = "safe-1"
        self.app.dependency_overrides[get_chapter_pages_service] = lambda: fake_pages
        self.app.dependency_overrides[get_manga_service] = lambda: fake_manga
        self.app.dependency_overrides[get_chapter_service] = lambda: fake_chapter
        self.app.dependency_overrides[get_user_age] = lambda: None

        with TestClient(self.app) as client:
            response = client.get("/chapters/%20chapter-9%20/pages")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(fake_pages.received_id, "chapter-9")
        self.assertEqual(response.json()["readable"], True)


if __name__ == "__main__":
    unittest.main()
