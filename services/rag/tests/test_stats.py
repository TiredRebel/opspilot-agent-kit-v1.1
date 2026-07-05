import pytest
from app import main
from fastapi.testclient import TestClient


async def test_stats_matches_fixture_data(pool):
    await pool.execute(
        """
        INSERT INTO tickets (source, external_ref, body, status, auto_resolved, confidence)
        VALUES
            ('telegram', 'a', 'hi', 'answered', true, 0.9),
            ('telegram', 'b', 'hi', 'needs_human', false, 0.5)
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
    assert body["auto_resolution_rate"] == pytest.approx(0.5)
    assert body["avg_confidence"] == pytest.approx(0.7)
    assert body["total_cost_usd"] == pytest.approx(0.03)
