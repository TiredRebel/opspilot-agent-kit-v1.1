import pytest
from app import main
from fastapi.testclient import TestClient


async def test_stats_matches_fixture_data(pool):
    await pool.execute(
        """
        INSERT INTO tickets
            (source, external_ref, body, status, category, priority, auto_resolved, confidence)
        VALUES
            ('telegram', 'a', 'hi', 'answered', 'billing', 'normal', true, 0.9),
            ('telegram', 'b', 'hi', 'needs_human', 'technical', 'high', false, 0.5)
        """
    )
    await pool.execute(
        """
        INSERT INTO llm_calls
            (purpose, provider, model, tokens_in, tokens_out, cost_usd, latency_ms, success)
        VALUES
            ('classify', 'anthropic', 'claude-haiku-4-5', 10, 10, 0.01, 100, true),
            ('answer', 'anthropic', 'claude-haiku-4-5', 10, 10, 0.02, 200, true)
        """
    )

    with TestClient(main.app) as client:
        response = client.get("/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["tickets_by_status"] == {"answered": 1, "needs_human": 1}
    assert body["tickets_by_category"] == {"billing": 1, "technical": 1}
    assert body["tickets_by_priority"] == {"normal": 1, "high": 1}
    assert body["auto_resolution_rate"] == pytest.approx(0.5)
    assert body["avg_confidence"] == pytest.approx(0.7)
    assert body["total_cost_usd"] == pytest.approx(0.03)


async def test_stats_hours_filter_excludes_old_rows(pool):
    await pool.execute(
        """
        INSERT INTO tickets (source, external_ref, body, status, category, priority, created_at)
        VALUES
            ('telegram', 'old', 'hi', 'answered', 'billing', 'low', now() - interval '3 days'),
            ('telegram', 'recent', 'hi', 'answered', 'technical', 'high', now())
        """
    )
    await pool.execute(
        """
        INSERT INTO llm_calls
            (purpose, provider, model, tokens_in, tokens_out, cost_usd, latency_ms, success,
             created_at)
        VALUES
            ('answer', 'anthropic', 'claude-haiku-4-5', 10, 10, 0.05, 100, true,
             now() - interval '3 days'),
            ('answer', 'anthropic', 'claude-haiku-4-5', 10, 10, 0.02, 200, true, now())
        """
    )

    with TestClient(main.app) as client:
        filtered = client.get("/stats", params={"hours": 24}).json()
        unfiltered = client.get("/stats").json()

    assert filtered["tickets_by_status"] == {"answered": 1}
    assert filtered["tickets_by_category"] == {"technical": 1}
    assert filtered["tickets_by_priority"] == {"high": 1}
    assert filtered["total_cost_usd"] == pytest.approx(0.02)

    assert unfiltered["tickets_by_status"] == {"answered": 2}
    assert unfiltered["total_cost_usd"] == pytest.approx(0.07)
