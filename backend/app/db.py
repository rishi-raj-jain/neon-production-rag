from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import get_settings

_pool: AsyncConnectionPool | None = None


async def init_pool() -> None:
    global _pool
    settings = get_settings()
    _pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        kwargs={"row_factory": dict_row},
        open=False,
    )
    await _pool.open()


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialized")
    return _pool


@asynccontextmanager
async def get_conn() -> AsyncIterator:
    pool = get_pool()
    async with pool.connection() as conn:
        yield conn
