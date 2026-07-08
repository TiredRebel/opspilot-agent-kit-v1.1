"""Spec (llm-provider-layer): a provider is unit-testable with a stub Ledger and no database.

No `pool` fixture, no asyncpg — the stub ledger records calls in memory. If any provider code
regressed into importing `app.db` or opening a connection, this test would hang or crash."""

from types import SimpleNamespace

import pytest
from app.llm.providers import openai as openai_provider


# Override conftest's autouse DB fixtures: this module must pass with Postgres down, which is
# the point of the spec scenario ("provider is unit-tested without a database").
@pytest.fixture(scope="session", autouse=True)
def _reset_test_database():
    yield


@pytest.fixture(autouse=True)
def _clean_tables():
    yield


class StubLedger:
    def __init__(self):
        self.records = []

    async def record(self, *args):
        self.records.append(args)

    async def check_budget(self):
        pass


async def test_openai_chat_runs_with_stub_ledger_and_no_database(monkeypatch):
    response = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=7, completion_tokens=3),
        choices=[SimpleNamespace(message=SimpleNamespace(content="stubbed answer"))],
    )

    async def fake_call(*args, **kwargs):
        return response

    monkeypatch.setattr(openai_provider, "_call_openai", fake_call)
    ledger = StubLedger()

    result = await openai_provider.chat(
        "answer", [{"role": "user", "content": "hi"}], None, None, None, ledger
    )

    assert result.provider == "openai"
    assert result.text == "stubbed answer"
    assert result.tokens_in == 7
    assert result.tokens_out == 3
    assert len(ledger.records) == 1
    # (ticket_id, purpose, provider, model, ...) — the row that would have gone to llm_calls.
    assert ledger.records[0][1] == "answer"
    assert ledger.records[0][2] == "openai"
