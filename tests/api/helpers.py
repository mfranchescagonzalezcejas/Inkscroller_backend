from fastapi import FastAPI

from main import build_lifespan, create_app


def create_hermetic_test_app() -> FastAPI:
    return create_app(lifespan_context=build_lifespan(db_path=":memory:"))
