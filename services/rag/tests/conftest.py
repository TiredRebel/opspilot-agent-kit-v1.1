"""Shared fixtures for L1 (pure/mocked) and L2 (real Postgres) tests.

Test setup/assertions use their own standalone asyncpg connection, kept entirely separate
from `app.db`'s module-level pool — that pool is bound to whichever event loop first creates
it (pytest's own loop for direct `llm.complete()` calls, or `TestClient`'s dedicated
worker-thread loop for HTTP-driven tests), and reusing one loop's pool from another crashes
with "Event loop is closed" / "another operation is in progress". `_reset_app_pool` drops the
app's cached pool before/after every test so it's always recreated fresh, bound to whichever
loop that specific test happens to use.
"""

import os
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from app import db
from app.settings import settings
from dotenv import dotenv_values

_ENV = dotenv_values(Path(__file__).resolve().parents[3] / ".env")


def _localhost_database_url() -> str:
    """Compose maps postgres to the internal hostname `postgres`; local pytest runs outside
    docker, so rewrite it to `localhost` (the published port) for L2 tests."""
    user = os.environ.get("POSTGRES_USER") or _ENV.get("POSTGRES_USER", "opspilot")
    password = os.environ.get("POSTGRES_PASSWORD") or _ENV.get("POSTGRES_PASSWORD", "changeme")
    port = os.environ.get("POSTGRES_PORT") or _ENV.get("POSTGRES_PORT", "5432")
    dbname = os.environ.get("POSTGRES_DB") or _ENV.get("POSTGRES_DB", "opspilot")
    return f"postgresql://{user}:{password}@localhost:{port}/{dbname}"


@pytest.fixture(scope="session", autouse=True)
def _use_localhost_database():
    settings.database_url = _localhost_database_url()


@pytest.fixture(autouse=True)
def _reset_app_pool():
    db._pool = None
    yield
    db._pool = None


@pytest_asyncio.fixture
async def pool():
    """A standalone connection for test setup/assertions — independent of app.db's pool."""
    conn = await asyncpg.connect(_localhost_database_url())
    try:
        yield conn
    finally:
        await conn.close()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables(pool):
    """Keep L2 tests order-independent by truncating app tables before and after each test."""
    tables = "tickets, messages, kb_documents, kb_chunks, llm_calls"
    await pool.execute(f"TRUNCATE {tables} CASCADE")
    yield
    await pool.execute(f"TRUNCATE {tables} CASCADE")
