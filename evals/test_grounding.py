"""L3 eval: answer groundedness against real kb/seed content (docs/TESTPLAN.md).

For each question, every cited numeric/factual anchor must actually appear in the content of the
chunks `/query` cited as sources — a deterministic string-anchor check (TESTPLAN's stated
alternative to LLM-as-judge), which is cheaper (no extra paid call) and doesn't depend on the
judge model's own reliability.
"""

import pytest
from app import main
from fastapi.testclient import TestClient

# (question, anchor) pairs — anchors are facts read directly from kb/seed/*.md this session.
_CASES = [
    ("How long is the money-back guarantee?", "14"),  # refund_cancellation_policy_en.md
    ("How long do you keep my data after I cancel my account?", "90"),  # same doc
    ("How much does the Pro plan cost per user per month?", "19"),  # billing_plans_pricing_en.md
    ("What is the API rate limit on the Pro plan?", "600"),  # api_guide_auth_rate_limits_en.md
    ("How long is a password reset link valid for?", "60"),  # troubleshooting_login_2fa_en.md
]


async def _chunk_content(pool, source: str) -> str:
    """Fetch a cited chunk's raw content by its `title#chunk_index` source string."""
    title, _, chunk_index = source.rpartition("#")
    row = await pool.fetchrow(
        """
        SELECT c.content FROM kb_chunks c
        JOIN kb_documents d ON c.document_id = d.id
        WHERE d.title = $1 AND c.chunk_index = $2
        """,
        title,
        int(chunk_index),
    )
    return row["content"] if row else ""


@pytest.mark.evals
@pytest.mark.parametrize("question,anchor", _CASES)
async def test_answer_grounded_in_cited_sources(pool, question, anchor):
    with TestClient(main.app) as client:
        response = client.post("/query", json={"question": question})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["sources"], f"no sources cited for: {question}"

    cited_content = " ".join([await _chunk_content(pool, s) for s in body["sources"]])
    assert anchor in cited_content, (
        f"anchor {anchor!r} not found in cited chunks for {question!r}\n"
        f"sources: {body['sources']}\nanswer: {body['answer']}"
    )
