import os


class Settings:
    app_name: str = "Inkscroller API"
    version: str = "0.1.0"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    mangadex_base_url: str = os.getenv("MANGADEX_BASE_URL", "https://api.mangadex.org")
    jikan_base_url: str = os.getenv("JIKAN_BASE_URL", "https://api.jikan.moe/v4")

    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "300"))

    cors_origins: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")


settings = Settings()
