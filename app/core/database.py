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
"""


async def init_db() -> aiosqlite.Connection:
    """Open the SQLite database, apply WAL mode, and create tables if missing.

    Returns the open [aiosqlite.Connection]. The caller is responsible for
    closing it - typically stored in `app.state.db` for the lifespan of the
    FastAPI process.
    """
    db = await aiosqlite.connect(settings.db_path)
    db.row_factory = aiosqlite.Row

    # Execute DDL statements individually so WAL pragma runs first.
    for statement in _DDL.strip().split(";"):
        stmt = statement.strip()
        if stmt:
            await db.execute(stmt)

    await db.commit()
    logger.info("SQLite database ready at %s", settings.db_path)
    return db
