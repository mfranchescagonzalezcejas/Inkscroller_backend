from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from app.core.dependencies import get_manga_service
from app.models.manga import Manga
from app.services.manga_service import MangaService

router = APIRouter(prefix="/manga", tags=["Manga"])


@router.get("/search", response_model=List[Manga])
async def search_manga(
    q: str = Query(..., min_length=1),
    service: MangaService = Depends(get_manga_service),
):
    return await service.search(q)


@router.get("/{manga_id}", response_model=Manga)
async def get_manga(
    manga_id: str,
    service: MangaService = Depends(get_manga_service),
):
    manga_id = manga_id.strip()
    manga = await service.get_by_id(manga_id)
    if manga is None:
        raise HTTPException(status_code=404, detail="Manga not found")
    return manga


@router.get("")
async def list_manga(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    title: str | None = None,
    demographic: str | None = None,
    status: str | None = None,
    order: str | None = None,
    genre: str | None = None,
    service: MangaService = Depends(get_manga_service),
):
    return await service.list_manga(
        limit=limit,
        offset=offset,
        title=title,
        demographic=demographic,
        status=status,
        order=order,
        genre=genre,
    )
