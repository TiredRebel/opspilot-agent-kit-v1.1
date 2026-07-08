"""Module-level asyncpg connection pool (no ORM — ADR-004)."""

import logging

import asyncpg

from app.settings import settings

logger = logging.getLogger("app.db")

# A pool is bound to the asyncio event loop that created it; reusing it from a different loop
# raises "Event loop is closed" / "another operation is in progress" (see wiki/gotchas.md #12).
# Kept as a bare module global (not request-scoped) since the app only ever runs on one loop in
# production — tests are the exception, and reset this to None between runs for that reason.
_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Create the pool on first use and cache it for the lifetime of the current event loop."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(settings.database_url)
    return _pool


async def close_pool() -> None:
    """Called from the FastAPI lifespan shutdown hook so the pool doesn't leak connections."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def check_db() -> tuple[bool, str | None]:
    """Liveness check used by GET /health. Returns `(ok, error_class_name)` — the exception
    class gives /health's body a specific reason instead of a bare `db: false`, and the full
    traceback goes to the log rather than being swallowed."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True, None
    except Exception as exc:
        logger.exception("database health check failed")
        return False, type(exc).__name__
