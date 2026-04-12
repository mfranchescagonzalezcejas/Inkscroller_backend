import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    app_name: str = "Inkscroller API"
    version: str = "0.1.0"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    mangadex_base_url: str = os.getenv("MANGADEX_BASE_URL", "https://api.mangadex.org")
    jikan_base_url: str = os.getenv("JIKAN_BASE_URL", "https://api.jikan.moe/v4")

    # Feature flags
    enable_jikan_enrichment: bool = (
        os.getenv("ENABLE_JIKAN_ENRICHMENT", "true").lower() == "true"
    )

    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "300"))

    cors_origins: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")

    # Phase 5 — Firebase Auth Foundation
    firebase_project_id: str = os.getenv("FIREBASE_PROJECT_ID", "")

    # ── Database ──────────────────────────────────────────────────
    # SQLite (local dev): set DB_PATH or leave default.
    db_path: str = os.getenv("DB_PATH", "./inkscroller.db")

    # PostgreSQL (Cloud Run): set CLOUD_SQL_INSTANCE *or* DATABASE_URL.
    #
    # CLOUD_SQL_INSTANCE  — "project:region:instance" connection name.
    #                       Uses Cloud SQL Python Connector + Workload Identity.
    #                       Example: inkscroller-aed59:us-central1:inkscroller-db
    #
    # DATABASE_URL        — Full asyncpg DSN for direct connections (local Docker,
    #                       CI, or manual Cloud SQL proxy).
    #                       Example: postgresql://user:pass@localhost:5432/inkscroller
    cloud_sql_instance: str | None = os.getenv("CLOUD_SQL_INSTANCE") or None
    database_url: str | None = os.getenv("DATABASE_URL") or None
    db_user: str = os.getenv("DB_USER", "inkscroller")
    db_pass: str | None = os.getenv("DB_PASS") or None
    db_name: str = os.getenv("DB_NAME", "inkscroller")


settings = Settings()
