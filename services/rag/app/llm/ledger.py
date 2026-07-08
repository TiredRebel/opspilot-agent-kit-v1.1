"""Call accounting for the LLM package: the `Ledger` interface and its asyncpg-backed default.

This module is the package's only database touchpoint. Provider modules never import `app.db`;
they receive a `Ledger` and call `record()` for every attempt. Budget enforcement
(`check_budget()`) runs in the dispatch layer before any non-fake provider call.
"""

import logging
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app import db
from app.llm.base import BudgetExceeded
from app.logging_setup import kv
from app.settings import settings

logger = logging.getLogger("app.llm.ledger")


class Ledger(Protocol):
    """What providers need for accounting — implementable without a database in tests."""

    async def record(
        self,
        ticket_id: str | UUID | None,
        purpose: str,
        provider: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: Decimal,
        latency_ms: int,
        success: bool,
    ) -> None:
        """Record one call attempt's cost/latency/outcome."""
        ...

    async def check_budget(self) -> None:
        """Raise `BudgetExceeded` if today's spend has hit the daily budget."""
        ...


class PgLedger:
    """Default ledger: writes `llm_calls` rows and sums today's spend via asyncpg.

    The pool is resolved through `app.db.get_pool()` inside each call — never cached here —
    because the pool is bound to the event loop that created it (gotcha #12)."""

    async def record(
        self,
        ticket_id: str | UUID | None,
        purpose: str,
        provider: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: Decimal,
        latency_ms: int,
        success: bool,
    ) -> None:
        """Insert one row into `llm_calls` recording this attempt's cost/latency/outcome, and
        emit the matching INFO line — the live view of what the table records durably. This is
        the one spot that sees every attempt for every provider (including failed pre-fallback
        ones), so per-attempt logging lives here, not in provider modules."""
        logger.info(
            kv(
                "llm attempt",
                purpose=purpose,
                provider=provider,
                model=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                success=success,
                ticket_id=ticket_id,
            )
        )
        pool = await db.get_pool()
        await pool.execute(
            """
            INSERT INTO llm_calls
                (ticket_id, purpose, provider, model,
                 tokens_in, tokens_out, cost_usd, latency_ms, success)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            ticket_id,
            purpose,
            provider,
            model,
            tokens_in,
            tokens_out,
            cost_usd,
            latency_ms,
            success,
        )

    async def check_budget(self) -> None:
        """Raise `BudgetExceeded` if today's logged spend has hit `daily_budget_usd`."""
        pool = await db.get_pool()
        spent = await pool.fetchval(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM llm_calls WHERE created_at::date = CURRENT_DATE"
        )
        if float(spent) >= settings.daily_budget_usd:
            raise BudgetExceeded(
                f"daily budget ${settings.daily_budget_usd:.2f} exceeded (spent ${spent}) — "
                f"resets at midnight UTC (spend is summed per created_at::date)"
            )
