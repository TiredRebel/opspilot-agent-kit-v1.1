"""Shared fixtures for L3 eval tests (`make evals` / `pytest -m evals`).

Unlike `services/rag/tests/` (isolated `<POSTGRES_DB>_test` database, `fake` provider — see
wiki/gotchas.md #31), evals run against the **real** dev database and its real ingested KB
(`make seed`), using a real cheap LLM provider, so groundedness checks have real embedded chunks
to retrieve against. Never truncates any table.
"""

import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from app import db
from app.settings import settings
from dotenv import dotenv_values

_ENV = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
_BUDGET_USD = Decimal("0.50")


def _localhost_database_url() -> str:
    """Compose maps postgres to the internal hostname `postgres`; local pytest runs outside
    docker, so rewrite it to `localhost` (the published port) — same trick as gotcha #11, but
    against the real dev database (no `_test` suffix): evals need the actual ingested KB."""
    user = os.environ.get("POSTGRES_USER") or _ENV.get("POSTGRES_USER", "opspilot")
    password = os.environ.get("POSTGRES_PASSWORD") or _ENV.get("POSTGRES_PASSWORD", "changeme")
    port = os.environ.get("POSTGRES_PORT") or _ENV.get("POSTGRES_PORT", "5432")
    dbname = os.environ.get("POSTGRES_DB") or _ENV.get("POSTGRES_DB", "opspilot")
    return f"postgresql://{user}:{password}@localhost:{port}/{dbname}"


@pytest.fixture(scope="session", autouse=True)
def _use_localhost_database():
    """Point the app's settings at the localhost-rewritten dev database for the whole session."""
    settings.database_url = _localhost_database_url()


@pytest.fixture(autouse=True)
def _non_fake_provider(monkeypatch):
    """Evals must exercise a real classifier/answerer, not the deterministic fake provider.
    Defaults to ollama (local, no rate limit/quota) — gemini's free tier caps at 20
    generateContent calls/day (gotcha #35), too low for this suite's ~37 calls. Override
    EVALS_LLM_PROVIDER to run against a different real provider."""
    monkeypatch.setattr(settings, "llm_provider", os.environ.get("EVALS_LLM_PROVIDER", "ollama"))


@pytest.fixture(autouse=True)
def _reset_app_pool():
    """Same event-loop hazard as gotcha #12 — app.db's pool is bound to whichever loop first
    creates it; TestClient's worker-thread loop differs from pytest's own."""
    db._pool = None
    yield
    db._pool = None


@pytest_asyncio.fixture
async def pool():
    """A standalone connection for assertions/lookups — independent of app.db's pool."""
    conn = await asyncpg.connect(_localhost_database_url())
    try:
        yield conn
    finally:
        await conn.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _budget_assertion():
    """Caps this eval run's total spend at $0.50 (docs/TESTPLAN.md), scoped to llm_calls rows
    created from this fixture's setup onward so pre-existing dev-DB activity isn't counted."""
    conn = await asyncpg.connect(_localhost_database_url())
    start = datetime.now(UTC)
    try:
        yield
        spent = await conn.fetchval(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM llm_calls WHERE created_at >= $1", start
        )
        print(f"\neval run cost: ${spent:.4f} (budget: ${_BUDGET_USD})")
        assert spent < _BUDGET_USD, f"eval run cost ${spent:.4f} exceeded ${_BUDGET_USD} budget"
    finally:
        await conn.close()
