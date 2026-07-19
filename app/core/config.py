"""Application configuration loaded from environment variables."""

import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()


DEFAULT_CORS_ORIGINS = (
    "https://inkscroller-app.web.app",
    "https://devdigi.dev",
    "https://www.devdigi.dev",
)
PRODUCTION_LIKE_ENVIRONMENTS = {"production", "prod", "staging", "stage"}


def _parse_csv(value: str) -> list[str]:
    """Split a comma-separated string into a trimmed list, skipping empty items."""
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_bool(value: str) -> bool:
    """Parse common truthy string representations to a boolean."""
    return value.lower() in {"1", "true", "yes", "on"}


def _runtime_environment() -> str:
    """Detect the runtime environment from ENVIRONMENT / RAILWAY_ENVIRONMENT_NAME / RAILWAY_ENVIRONMENT."""
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
    """Application settings loaded from environment variables with sensible defaults."""

    def __init__(self) -> None:
        """Load all settings from environment variables, falling back to defaults."""
        self.app_name: str = "Inkscroller API"
        self.app_description: str = (
            "Backend API for InkScroller, a full-stack manga reading platform. "
            "Proxies and enriches data from MangaDex (catalogue, chapters, pages) "
            "and Jikan/MyAnimeList (metadata enrichment). "
            "Features Firebase authentication, age-gated content access, "
            "user preferences, personal manga libraries, and demographic filtering."
        )
        self.version: str = "1.0.0"
        self.environment: str = _runtime_environment()
        raw_debug = _parse_bool(os.getenv("DEBUG", "false"))
        self.debug: bool = (
            raw_debug and self.environment not in PRODUCTION_LIKE_ENVIRONMENTS
        )

        self.mangadex_base_url: str = os.getenv(
            "MANGADEX_BASE_URL", "https://api.mangadex.org"
        )
        self.mangadex_worker_url: str = os.getenv("MANGADEX_WORKER_URL", "")
        self.jikan_base_url: str = os.getenv(
            "JIKAN_BASE_URL", "https://api.jikan.moe/v4"
        )

        # Feature flags
        self.enable_jikan_enrichment: bool = _parse_bool(
            os.getenv("ENABLE_JIKAN_ENRICHMENT", "true")
        )

        self.cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "300"))
        self.readyz_timeout_seconds: int = max(1, int(os.getenv("READYZ_TIMEOUT", "5")))

        # Request resource limits
        self.request_timeout_seconds: int = int(
            os.getenv("REQUEST_TIMEOUT_SECONDS", "30")
        )
        self.max_request_body_mb: int = int(os.getenv("MAX_REQUEST_BODY_MB", "5"))

        self.cors_allow_credentials: bool = True
        self.cors_origins: list[str] = _parse_csv(
            os.getenv("CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS))
        )

        # Phase 5 — Firebase Auth Foundation
        self.firebase_project_id: str = os.getenv("FIREBASE_PROJECT_ID", "")
        self.mangadex_contact: str = os.getenv("MANGADEX_CONTACT", "")

        # ── Cursor signing key ────────────────────────────────────────
        self.cursor_secret: str = os.getenv("CURSOR_SECRET", "")
        if not self.cursor_secret:
            logger.info(
                "CURSOR_SECRET not set — cursor-based pagination is disabled. "
                "Set CURSOR_SECRET to enable tamper-proof cursor tokens."
            )

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
        """Check whether the current environment is production-like (prod/staging)."""
        return self.environment in PRODUCTION_LIKE_ENVIRONMENTS

    def validate_cors_configuration(self) -> None:
        """Raise ``RuntimeError`` if the CORS config is unsafe for production-like environments."""
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
