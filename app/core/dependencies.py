import logging

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.cache import SimpleCache
from app.core.db_adapter import DatabaseAdapter
from app.core.exceptions import AuthError
from app.core.firebase_auth import (
    AuthenticationError,
    FirebaseTokenPayload,
    verify_firebase_token,
)
from app.services.chapter_pages_service import ChapterPagesService
from app.services.chapter_service import ChapterService
from app.services.manga_service import MangaService
from app.services.user_service import UserService
from app.sources.jikan_client import JikanClient
from app.sources.mangadex_client import MangaDexClient

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


def get_shared_cache(request: Request) -> SimpleCache:
    return request.app.state.cache


def get_db(request: Request) -> DatabaseAdapter:
    """Return the shared database adapter stored in ``app.state.db``."""
    return request.app.state.db


def get_user_service(db: DatabaseAdapter = Depends(get_db)) -> UserService:
    """Construct a :class:`UserService` for the current request."""
    return UserService(db)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    user_service: UserService = Depends(get_user_service),
) -> FirebaseTokenPayload:
    """Verify the Bearer token and bootstrap / return the local user.

    Raises :class:`~app.core.exceptions.AuthError` for any authentication
    failure so the registered handler emits a consistent
    ``{"error": "authentication_error", "detail": "..."}`` 401 response.
    """
    if credentials is None:
        raise AuthError("Authentication required.")

    try:
        payload = await verify_firebase_token(credentials.credentials)
    except AuthenticationError as exc:
        raise AuthError(str(exc)) from exc

    # Bootstrap the local user row on first request for this UID.
    await user_service.get_or_create_user(payload)
    return payload


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
