"""Database bootstrap — returns a DatabaseAdapter for SQLite or PostgreSQL.

Local development (no DATABASE_URL / CLOUD_SQL_INSTANCE set):
    Uses aiosqlite with a local SQLite file (default: ./inkscroller.db).
    Pass ``":memory:"`` to get a hermetic in-memory DB for tests.

Cloud Run production (CLOUD_SQL_INSTANCE or DATABASE_URL set):
    Uses asyncpg via the Cloud SQL Python Connector.
    Authentication is handled automatically by Workload Identity on Cloud Run.
    For local testing against Cloud SQL, set DATABASE_URL directly.
"""

from __future__ import annotations

import logging

from app.core.config import settings
from app.core.db_adapter import DatabaseAdapter, PostgresAdapter, SqliteAdapter

logger = logging.getLogger(__name__)

# ── DDL ───────────────────────────────────────────────────────────────────────

_SQLITE_DDL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
    firebase_uid  TEXT    PRIMARY KEY,
    email         TEXT    NOT NULL,
    display_name  TEXT,
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS reading_preferences (
    firebase_uid         TEXT    PRIMARY KEY REFERENCES users(firebase_uid),
    default_reader_mode  TEXT    NOT NULL DEFAULT 'vertical',
    default_language     TEXT    NOT NULL DEFAULT 'en',
    updated_at           TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS user_library (
    firebase_uid   TEXT  NOT NULL REFERENCES users(firebase_uid),
    manga_id       TEXT  NOT NULL,
    added_at       TEXT  NOT NULL,
    library_status TEXT  NOT NULL DEFAULT 'reading',
    updated_at     TEXT,
    title          TEXT,
    cover_url      TEXT,
    authors        TEXT  NOT NULL DEFAULT '[]',
    PRIMARY KEY (firebase_uid, manga_id)
);
"""

_POSTGRES_DDL = """
CREATE TABLE IF NOT EXISTS users (
    firebase_uid  TEXT    PRIMARY KEY,
    email         TEXT    NOT NULL,
    display_name  TEXT,
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS reading_preferences (
    firebase_uid         TEXT    PRIMARY KEY REFERENCES users(firebase_uid),
    default_reader_mode  TEXT    NOT NULL DEFAULT 'vertical',
    default_language     TEXT    NOT NULL DEFAULT 'en',
    updated_at           TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS user_library (
    firebase_uid   TEXT  NOT NULL REFERENCES users(firebase_uid),
    manga_id       TEXT  NOT NULL,
    added_at       TEXT  NOT NULL,
    library_status TEXT  NOT NULL DEFAULT 'reading',
    updated_at     TEXT,
    title          TEXT,
    cover_url      TEXT,
    authors        TEXT  NOT NULL DEFAULT '[]',
    PRIMARY KEY (firebase_uid, manga_id)
);
"""


# ── SQLite bootstrap ──────────────────────────────────────────────────────────


async def _init_sqlite(db_path: str) -> DatabaseAdapter:
    import aiosqlite

    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row

    for stmt in _SQLITE_DDL.strip().split(";"):
        s = stmt.strip()
        if s:
            await conn.execute(s)

    await _migrate_sqlite_columns(conn)
    await conn.commit()

    logger.info("SQLite database ready at %s", db_path)
    return SqliteAdapter(conn)


async def _migrate_sqlite_columns(conn: object) -> None:
    """Add columns introduced after the initial schema (additive migrations)."""
    import aiosqlite

    assert isinstance(conn, aiosqlite.Connection)

    async with conn.execute("PRAGMA table_info(user_library)") as cursor:
        rows = await cursor.fetchall()
    columns = {row["name"] for row in rows}

    migrations = [
        (
            "library_status",
            "ALTER TABLE user_library ADD COLUMN library_status TEXT NOT NULL DEFAULT 'reading'",
        ),
        ("updated_at", "ALTER TABLE user_library ADD COLUMN updated_at TEXT"),
        ("title", "ALTER TABLE user_library ADD COLUMN title TEXT"),
        ("cover_url", "ALTER TABLE user_library ADD COLUMN cover_url TEXT"),
        (
            "authors",
            "ALTER TABLE user_library ADD COLUMN authors TEXT NOT NULL DEFAULT '[]'",
        ),
    ]
    for col, ddl in migrations:
        if col not in columns:
            await conn.execute(ddl)

    await conn.execute(
        "UPDATE user_library "
        "SET library_status = COALESCE(library_status, 'reading'), "
        "    updated_at = COALESCE(updated_at, added_at) "
        "WHERE library_status IS NULL OR updated_at IS NULL"
    )


# ── PostgreSQL bootstrap ──────────────────────────────────────────────────────


async def _init_postgres() -> DatabaseAdapter:
    """Connect to Cloud SQL via the Cloud SQL Python Connector or a direct DATABASE_URL."""
    import asyncpg  # type: ignore[import]

    if settings.cloud_sql_instance:
        # Cloud Run path: Workload Identity, no password needed in env.
        from google.cloud.sql.connector import Connector  # type: ignore[import]

        connector = Connector()

        async def _getconn(*_args, **_kwargs) -> object:
            return await connector.connect_async(
                settings.cloud_sql_instance,
                "asyncpg",
                user=settings.db_user,
                password=settings.db_pass or None,
                db=settings.db_name,
            )

        pool = await asyncpg.create_pool(connect=_getconn, min_size=1, max_size=10)
        logger.info(
            "PostgreSQL pool ready via Cloud SQL connector (%s)",
            settings.cloud_sql_instance,
        )
    else:
        # Direct DATABASE_URL — useful for local Docker Compose or CI.
        pool = await asyncpg.create_pool(
            dsn=settings.database_url, min_size=1, max_size=10
        )
        logger.info("PostgreSQL pool ready via DATABASE_URL")

    # Apply DDL (idempotent CREATE TABLE IF NOT EXISTS).
    async with pool.acquire() as conn:
        async with conn.transaction():
            for stmt in _POSTGRES_DDL.strip().split(";"):
                s = stmt.strip()
                if s:
                    await conn.execute(s)

    return PostgresAdapter(pool)


# ── Public factory ────────────────────────────────────────────────────────────


async def init_db(db_path: str | None = None) -> DatabaseAdapter:
    """Return the appropriate DatabaseAdapter for the current environment.

    - ``db_path`` overrides ``settings.db_path`` and is only used for SQLite.
      Pass ``":memory:"`` in tests for a hermetic in-memory database.
    - When ``CLOUD_SQL_INSTANCE`` or ``DATABASE_URL`` is set, the PostgreSQL
      adapter is returned and ``db_path`` is ignored.
    """
    if settings.cloud_sql_instance or settings.database_url:
        return await _init_postgres()

    return await _init_sqlite(db_path or settings.db_path)
