from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.health import router as health_router
from app.api.manga import router as manga_router
from app.api.chapters import router as chapters_router
from app.api.pages import router as pages_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers

app = FastAPI(
    title="Inkscroller API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(health_router)
app.include_router(manga_router)
app.include_router(chapters_router)
app.include_router(pages_router)
