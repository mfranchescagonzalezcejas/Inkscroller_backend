"""SQLite bootstrap and shared connection helper for Phase 5 user/preferences persistence."""

import logging

import aiosqlite

from app.core.config import settings

logger = logging.getLogger(__name__)

# DDL for local persistence tables (keyed by Firebase UID).
_DDL = """
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
    firebase_uid  TEXT  NOT NULL REFERENCES users(firebase_uid),
    manga_id      TEXT  NOT NULL,
    added_at      TEXT  NOT NULL,
    library_status TEXT NOT NULL DEFAULT 'reading',
    updated_at     TEXT,
    PRIMARY KEY (firebase_uid, manga_id)
);
"""


async def _migrate_user_library_table(db: aiosqlite.Connection) -> None:
    """Apply additive migrations for `user_library` when columns are missing."""
    async with db.execute("PRAGMA table_info(user_library)") as cursor:
        rows = await cursor.fetchall()

    columns = {row["name"] for row in rows}

    if "library_status" not in columns:
        await db.execute(
            "ALTER TABLE user_library "
            "ADD COLUMN library_status TEXT NOT NULL DEFAULT 'reading'"
        )

    if "updated_at" not in columns:
        await db.execute("ALTER TABLE user_library ADD COLUMN updated_at TEXT")

    if "title" not in columns:
        await db.execute("ALTER TABLE user_library ADD COLUMN title TEXT")

    if "cover_url" not in columns:
        await db.execute("ALTER TABLE user_library ADD COLUMN cover_url TEXT")

    if "authors" not in columns:
        await db.execute("ALTER TABLE user_library ADD COLUMN authors TEXT NOT NULL DEFAULT '[]'")

    await db.execute(
        "UPDATE user_library "
        "SET library_status = COALESCE(library_status, 'reading'), "
        "updated_at = COALESCE(updated_at, added_at) "
        "WHERE library_status IS NULL OR updated_at IS NULL"
    )


async def init_db(db_path: str | None = None) -> aiosqlite.Connection:
    """Open the SQLite database, apply WAL mode, and create tables if missing.

    Returns the open [aiosqlite.Connection]. The caller is responsible for
    closing it - typically stored in `app.state.db` for the lifespan of the
    FastAPI process.

    Args:
        db_path: Path to the SQLite file. Defaults to ``settings.db_path``.
                 Pass ``":memory:"`` in tests for a hermetic in-memory DB.
    """
    db = await aiosqlite.connect(db_path or settings.db_path)
    db.row_factory = aiosqlite.Row

    # Execute DDL statements individually so WAL pragma runs first.
    for statement in _DDL.strip().split(";"):
        stmt = statement.strip()
        if stmt:
            await db.execute(stmt)

    await _migrate_user_library_table(db)

    await db.commit()
    logger.info("SQLite database ready at %s", settings.db_path)
    return db
