"""L3 eval: classification accuracy against evals/tickets.jsonl (docs/TESTPLAN.md).

Accuracy is scored on `category` over non-ambiguous items only — items marked
`expected_ambiguous` are intentionally hard to categorize (a human labeler could reasonably pick
either of two categories), so they're still classified for visibility but excluded from the
pass/fail metric rather than unfairly penalizing the model for genuine ambiguity.
"""

import json
import uuid
from collections import defaultdict
from pathlib import Path

import pytest
from app import main
from fastapi.testclient import TestClient

_FIXTURE_PATH = Path(__file__).resolve().parent / "tickets.jsonl"
_ACCURACY_THRESHOLD = 0.85


def _load_tickets() -> list[dict]:
    """Load the labeled fixture tickets from `tickets.jsonl`, one JSON object per line."""
    with _FIXTURE_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.mark.evals
def test_accuracy():
    tickets = _load_tickets()
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    correct = 0
    scored = 0

    with TestClient(main.app) as client:
        for ticket in tickets:
            response = client.post(
                "/classify",
                json={
                    "ticket_id": str(uuid.uuid4()),
                    "subject": ticket["subject"],
                    "body": ticket["body"],
                },
            )
            assert response.status_code == 200, response.text
            predicted_category = response.json()["category"]
            expected_category = ticket["expected_category"]
            confusion[expected_category][predicted_category] += 1

            if ticket.get("expected_ambiguous"):
                continue
            scored += 1
            if predicted_category == expected_category:
                correct += 1

    accuracy = correct / scored if scored else 0.0

    print(f"\nclassification accuracy: {correct}/{scored} = {accuracy:.3f}")
    print("confusion (expected -> {predicted: count}):")
    for expected in sorted(confusion):
        print(f"  {expected}: {dict(confusion[expected])}")

    assert accuracy >= _ACCURACY_THRESHOLD, (
        f"accuracy {accuracy:.3f} below {_ACCURACY_THRESHOLD} threshold"
    )
