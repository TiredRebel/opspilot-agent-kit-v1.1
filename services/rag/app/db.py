import asyncpg

from app.settings import settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Lazily create the module-level asyncpg pool (no ORM — ADR-004)."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(settings.database_url)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def check_db() -> bool:
    """Liveness check used by GET /health."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True
    except Exception:
        return False
