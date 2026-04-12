"""Database adapter abstraction for SQLite (local dev) and PostgreSQL (Cloud Run).

Provides a unified async interface so application code (UserService, etc.)
is decoupled from the underlying driver.  Parameter placeholders are always
written as ``?`` in query strings — the PostgreSQL adapter rewrites them to
``$1, $2, ...`` automatically.

Usage
-----
The correct adapter is created by ``database.init_db`` based on the
``DATABASE_URL`` / ``CLOUD_SQL_INSTANCE`` environment variables.  Application
code only ever sees :class:`DatabaseAdapter`.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any


def _to_pg_params(query: str) -> str:
    """Rewrite ``?`` placeholders to positional ``$N`` for asyncpg."""
    idx = 0

    def _replace(_match: re.Match) -> str:  # type: ignore[type-arg]
        nonlocal idx
        idx += 1
        return f"${idx}"

    return re.sub(r"\?", _replace, query)


def _pg_rowcount(status: str) -> int:
    """Parse the rowcount from an asyncpg status string like ``'UPDATE 3'``."""
    try:
        return int(status.split()[-1])
    except (ValueError, IndexError):
        return 0


class DatabaseAdapter(ABC):
    """Minimal async database interface shared by all backend adapters."""

    @abstractmethod
    async def execute(self, query: str, *args: Any) -> int:
        """Execute a DML statement and return the number of affected rows."""

    @abstractmethod
    async def fetchone(self, query: str, *args: Any) -> dict[str, Any] | None:
        """Return the first result row as a dict, or ``None`` if not found."""

    @abstractmethod
    async def fetchall(self, query: str, *args: Any) -> list[dict[str, Any]]:
        """Return all result rows as a list of dicts."""

    @abstractmethod
    async def commit(self) -> None:
        """Commit the current transaction (no-op for auto-commit backends)."""

    @abstractmethod
    async def close(self) -> None:
        """Release the underlying connection / pool."""


# ── SQLite adapter ────────────────────────────────────────────────────────────


class SqliteAdapter(DatabaseAdapter):
    """Wraps an ``aiosqlite.Connection`` for local development and tests."""

    def __init__(self, conn: Any) -> None:  # aiosqlite.Connection
        self._conn = conn

    async def execute(self, query: str, *args: Any) -> int:
        cursor = await self._conn.execute(query, args)
        return cursor.rowcount  # type: ignore[return-value]

    async def fetchone(self, query: str, *args: Any) -> dict[str, Any] | None:
        async with self._conn.execute(query, args) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def fetchall(self, query: str, *args: Any) -> list[dict[str, Any]]:
        async with self._conn.execute(query, args) as cursor:
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def commit(self) -> None:
        await self._conn.commit()

    async def close(self) -> None:
        await self._conn.close()


# ── PostgreSQL adapter ────────────────────────────────────────────────────────


class PostgresAdapter(DatabaseAdapter):
    """Wraps an ``asyncpg.Pool`` for Cloud Run / Cloud SQL production deployments.

    Each call acquires a connection from the pool, executes inside an
    implicit transaction, and releases the connection back to the pool.
    ``commit()`` is a no-op because asyncpg auto-commits single statements.
    """

    def __init__(self, pool: Any) -> None:  # asyncpg.Pool
        self._pool = pool

    async def execute(self, query: str, *args: Any) -> int:
        pg_query = _to_pg_params(query)
        async with self._pool.acquire() as conn:
            result = await conn.execute(pg_query, *args)
        return _pg_rowcount(result)

    async def fetchone(self, query: str, *args: Any) -> dict[str, Any] | None:
        pg_query = _to_pg_params(query)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(pg_query, *args)
        if row is None:
            return None
        return dict(row)

    async def fetchall(self, query: str, *args: Any) -> list[dict[str, Any]]:
        pg_query = _to_pg_params(query)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(pg_query, *args)
        return [dict(row) for row in rows]

    async def commit(self) -> None:
        pass  # asyncpg commits each statement automatically

    async def close(self) -> None:
        await self._pool.close()
