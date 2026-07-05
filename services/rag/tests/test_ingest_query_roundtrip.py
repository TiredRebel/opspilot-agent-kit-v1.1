import pytest
from app import main
from fastapi.testclient import TestClient


@pytest.fixture
def seed_dir(tmp_path):
    doc = tmp_path / "billing_faq.md"
    doc.write_text(
        "# Billing FAQ\n\nThe Starter plan costs nine dollars per user per month.",
        encoding="utf-8",
    )
    return tmp_path


def test_ingest_then_query_cites_the_ingested_source(seed_dir, pool):
    with TestClient(main.app) as client:
        ingest_response = client.post("/kb/ingest", params={"seed_dir": str(seed_dir)})
        assert ingest_response.status_code == 200
        assert ingest_response.json() == {"documents": 1, "chunks": 1}

        query_response = client.post(
            "/query", json={"question": "How much does the Starter plan cost?"}
        )

    assert query_response.status_code == 200
    body = query_response.json()
    assert body["sources"] == ["billing_faq#0"]
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["answer"]


def test_reingest_is_idempotent(seed_dir):
    with TestClient(main.app) as client:
        first = client.post("/kb/ingest", params={"seed_dir": str(seed_dir)})
        second = client.post("/kb/ingest", params={"seed_dir": str(seed_dir)})

    assert first.json() == {"documents": 1, "chunks": 1}
    assert second.json() == {"documents": 1, "chunks": 1}
