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
# All init files in lexical order — the same set and order the postgres entrypoint applies on a
# fresh volume, so the test schema can't drift from production (ADR-006 additive-only policy).
_DB_INIT_DIR = Path(__file__).resolve().parents[3] / "db" / "init"


def _pg_creds() -> tuple[str, str, str]:
    user = os.environ.get("POSTGRES_USER") or _ENV.get("POSTGRES_USER", "opspilot")
    password = os.environ.get("POSTGRES_PASSWORD") or _ENV.get("POSTGRES_PASSWORD", "changeme")
    port = os.environ.get("POSTGRES_PORT") or _ENV.get("POSTGRES_PORT", "5432")
    return user, password, port


def _test_db_name() -> str:
    dbname = os.environ.get("POSTGRES_DB") or _ENV.get("POSTGRES_DB", "opspilot")
    return f"{dbname}_test"


def _database_url(dbname: str) -> str:
    user, password, port = _pg_creds()
    return f"postgresql://{user}:{password}@localhost:{port}/{dbname}"


def _localhost_database_url() -> str:
    """Tests run against a dedicated `<POSTGRES_DB>_test` database, never the live dev database —
    `_clean_tables` truncates every app table before/after each test, which previously wiped real
    KB seed data and live tickets since tests only rewrote the hostname (Compose maps postgres to
    the internal hostname `postgres`; local pytest runs outside docker, so this also rewrites to
    `localhost`, the published port)."""
    return _database_url(_test_db_name())


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _reset_test_database():
    """Create (or reset) the dedicated test database once per test session, then point
    `settings.database_url` at it so no test ever touches the live dev database."""
    admin_conn = await asyncpg.connect(_database_url("postgres"))
    try:
        test_db = _test_db_name()
        await admin_conn.execute(f'DROP DATABASE IF EXISTS "{test_db}" WITH (FORCE)')
        await admin_conn.execute(f'CREATE DATABASE "{test_db}"')
    finally:
        await admin_conn.close()

    test_conn = await asyncpg.connect(_localhost_database_url())
    try:
        for sql_file in sorted(_DB_INIT_DIR.glob("*.sql")):
            await test_conn.execute(sql_file.read_text(encoding="utf-8"))
    finally:
        await test_conn.close()

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
    tables = "tickets, messages, kb_documents, kb_chunks, llm_calls, ticket_events"
    await pool.execute(f"TRUNCATE {tables} CASCADE")
    yield
    await pool.execute(f"TRUNCATE {tables} CASCADE")
