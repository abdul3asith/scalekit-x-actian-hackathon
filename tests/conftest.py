"""Shared fixtures. The DB fixture skips (rather than fails) when Postgres
isn't reachable, so the unit tests still run anywhere."""

import pytest
import pytest_asyncio

from app.data.db import close_pool, connection, open_pool


@pytest_asyncio.fixture
async def db_conn():
    try:
        await open_pool()
        async with connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
            yield conn
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Postgres not available: {exc}")
    finally:
        await close_pool()
