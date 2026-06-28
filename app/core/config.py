import os

from dotenv import load_dotenv

load_dotenv()


DEFAULT_CORS_ORIGINS = (
    "https://inkscroller-app.web.app",
    "https://devdigi.dev",
    "https://www.devdigi.dev",
)
PRODUCTION_LIKE_ENVIRONMENTS = {"production", "prod", "staging", "stage"}


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "on"}


def _runtime_environment() -> str:
    environment_values = [
        os.getenv("ENVIRONMENT"),
        os.getenv("RAILWAY_ENVIRONMENT_NAME"),
        os.getenv("RAILWAY_ENVIRONMENT"),
    ]
    normalized_values = [
        value.strip().lower() for value in environment_values if value and value.strip()
    ]

    for value in normalized_values:
        if value in PRODUCTION_LIKE_ENVIRONMENTS:
            return value

    return normalized_values[0] if normalized_values else "development"


class Settings:
    def __init__(self):
        self.app_name: str = "Inkscroller API"
        self.version: str = "0.1.0"
        self.debug: bool = _parse_bool(os.getenv("DEBUG", "false"))
        self.environment: str = _runtime_environment()

        self.mangadex_base_url: str = os.getenv(
            "MANGADEX_BASE_URL", "https://api.mangadex.org"
        )
        self.jikan_base_url: str = os.getenv("JIKAN_BASE_URL", "https://api.jikan.moe/v4")

        # Feature flags
        self.enable_jikan_enrichment: bool = _parse_bool(
            os.getenv("ENABLE_JIKAN_ENRICHMENT", "true")
        )

        self.cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "300"))

        self.cors_allow_credentials: bool = True
        self.cors_origins: list[str] = _parse_csv(
            os.getenv("CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS))
        )

        # Phase 5 — Firebase Auth Foundation
        self.firebase_project_id: str = os.getenv("FIREBASE_PROJECT_ID", "")

        # ── Database ──────────────────────────────────────────────────
        # SQLite (local dev): set DB_PATH or leave default.
        self.db_path: str = os.getenv("DB_PATH", "./inkscroller.db")

        # PostgreSQL (Railway/local): set CLOUD_SQL_INSTANCE *or* DATABASE_URL.
        #
        # CLOUD_SQL_INSTANCE  — "project:region:instance" connection name.
        #                       Uses Cloud SQL Python Connector + ADC.
        #                       Example: inkscroller-aed59:us-central1:inkscroller-db
        #
        # DATABASE_URL        — Full asyncpg DSN for direct connections (local Docker,
        #                       CI, or manual Cloud SQL proxy).
        #                       Example: set this from your local PostgreSQL DSN.
        self.cloud_sql_instance: str | None = os.getenv("CLOUD_SQL_INSTANCE") or None
        self.database_url: str | None = os.getenv("DATABASE_URL") or None
        self.db_user: str = os.getenv("DB_USER", "inkscroller")
        self.db_pass: str | None = os.getenv("DB_PASS") or None
        self.db_name: str = os.getenv("DB_NAME", "inkscroller")

    def is_production_like(self) -> bool:
        return self.environment in PRODUCTION_LIKE_ENVIRONMENTS

    def validate_cors_configuration(self) -> None:
        if self.is_production_like() and not self.cors_origins:
            raise RuntimeError(
                "Unsafe CORS configuration: CORS_ORIGINS must include at least one "
                "explicit trusted frontend origin in production-like environments."
            )

        if (
            self.cors_allow_credentials
            and self.is_production_like()
            and "*" in self.cors_origins
        ):
            raise RuntimeError(
                "Unsafe CORS configuration: wildcard CORS origins are not allowed "
                "with credentials in production-like environments. Set "
                "CORS_ORIGINS to explicit trusted frontend origins."
            )


settings = Settings()
