"""Async PostgreSQL connection pool (psycopg 3)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import settings

_pool: AsyncConnectionPool | None = None


def get_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            conninfo=settings.database_url,
            open=False,
            kwargs={"row_factory": dict_row, "autocommit": True},
        )
    return _pool


async def open_pool() -> None:
    await get_pool().open()


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def connection() -> AsyncIterator:
    """Yield a pooled connection (autocommit; each statement is its own txn)."""
    async with get_pool().connection() as conn:
        yield conn
