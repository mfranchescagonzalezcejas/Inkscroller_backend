from fastapi import FastAPI
from app.api.health import router as health_router
from app.api.manga import router as manga_router
from app.api.chapters import router as chapters_router

app = FastAPI(
    title="Inkscroller API",
    version="0.1.0",
)


app.include_router(health_router)
app.include_router(manga_router)
app.include_router(chapters_router)
