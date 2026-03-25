from fastapi import Request

from app.core.cache import SimpleCache
from app.services.chapter_pages_service import ChapterPagesService
from app.services.chapter_service import ChapterService
from app.services.manga_service import MangaService
from app.sources.jikan_client import JikanClient
from app.sources.mangadex_client import MangaDexClient


def get_shared_cache(request: Request) -> SimpleCache:
    return request.app.state.cache


def get_manga_service(request: Request) -> MangaService:
    return MangaService(
        client=MangaDexClient(request.app.state.mangadex_http),
        jikan=JikanClient(request.app.state.jikan_http),
        cache=get_shared_cache(request),
    )


def get_chapter_service(request: Request) -> ChapterService:
    return ChapterService(
        client=MangaDexClient(request.app.state.mangadex_http),
        cache=get_shared_cache(request),
    )


def get_chapter_pages_service(request: Request) -> ChapterPagesService:
    return ChapterPagesService(
        client=MangaDexClient(request.app.state.mangadex_http),
        cache=get_shared_cache(request),
    )
