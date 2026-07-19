from fastapi import FastAPI


def create_hermetic_test_app() -> FastAPI:
    from app.core.rate_limiter import reset_for_tests

    reset_for_tests()
    from main import build_lifespan, create_app

    return create_app(lifespan_context=build_lifespan(db_path=":memory:"))
