# OpsPilot — Master Test Plan

Every task ID in `PROGRESS.md` maps to at least one check below. Agents keep this file current:
new feature ⇒ new/updated test entry.

---

## Test levels

| Level | What | How | Who | LLM |
|---|---|---|---|---|
| **L1 Unit** | chunking, schema validation, confidence math, cost calculation, budget guardrail | `pytest` in `services/rag/tests/` | agent, every session | `fake` provider only |
| **L2 Integration** | endpoints against real Postgres/pgvector; ingest→query round trip | `pytest` with compose services up (`make test`) | agent | `fake` provider only |
| **L3 Evals** | classification accuracy + answer groundedness on labeled set | `make evals` (`pytest -m evals`) | agent (CI) + human review of failures | live cheap models, budget-capped |
| **L4 Manual E2E** | full Telegram flows incl. inline buttons | scripts M1–M6 below | **HUMAN** | live |
| **L5 Deploy smoke** | production VM health | script M7 | human + agent (curl checks) | live |

## L1/L2 — required automated tests

- `test_chunking.py` — ~500-token chunks, 50 overlap, no empty chunks, stable ordering.
- `test_classify_schema.py` — valid JSON passes; invalid JSON triggers exactly one retry; second failure → 422 + logged `success=false`.
- `test_confidence.py` — blend formula; gate at exactly 0.70 (boundary: 0.70 auto-sends, 0.699 escalates).
- `test_llm_fallback.py` — primary 5xx/timeout → fallback called once → both attempts in `llm_calls`.
- `test_budget_guardrail.py` — spend over daily cap → HTTP 429, no provider call made.
- `test_ingest_query_roundtrip.py` (L2) — ingest seed doc → query known fact → answer cites correct source.
- `test_idempotency.py` (L2) — duplicate `{source, external_ref}` insert does not create a second ticket.
- `test_stats.py` (L2) — `/stats` aggregates match fixture data.
- `test_set_webhook.py` — missing `WEBHOOK_URL` env var fails fast without touching docker;
  `_update_container_env` replaces an existing `WEBHOOK_URL=` line instead of appending a
  duplicate and preserves unrelated lines; `http://` URL warns but proceeds; docker write
  failure → exit 1, no restart (docker calls mocked). Owed by `fix-wf1-telegram-trigger` #14.

## L3 — eval harness

- Fixture: `evals/tickets.jsonl`, 25–30 items: `{subject, body, expected_category, expected_priority, lang}`;
  ≥ 8 Ukrainian, ≥ 3 deliberately ambiguous (expected to land below the confidence gate).
- `test_classify.py::test_accuracy` — accuracy ≥ **0.85** on category; report per-class confusion in output.
- `test_grounding.py` — for 5 KB questions: every factual claim in the answer appears in the cited chunks
  (LLM-as-judge with the self-check prompt, or string-anchor checks for numeric facts).
- Budget assertion: total eval run cost (sum of `llm_calls.cost_usd` for the run) < $0.50.

## L4 — manual E2E scripts (HUMAN executes; agent prepares fixtures)

**M1 Happy path.** Send the bot a question answered verbatim in `kb/seed` (e.g., billing FAQ).
*Expect:* auto-reply < 15 s with correct content; ticket `answered`, `auto_resolved=true`; ≥ 3 rows in `llm_calls` (embed, answer, self_check).

**M2 Ambiguous → Approve.** Send a vague question ("something is wrong with my account").
*Expect:* no auto-reply; ops channel receives draft + confidence < 0.70 + buttons; tapping ✅ sends the draft to the customer; status `answered`.

**M3 Edit capture.** Repeat M2, tap ✏️, reply with corrected text.
*Expect:* customer receives the corrected version; `messages` contains both `ai_draft` and `operator` rows.

**M4 Reject.** Repeat M2, tap ❌.
*Expect:* status `escalated`; escalation notification posted; customer receives a holding message.

**M5 SLA reminder.** Set a `needs_human` ticket's `updated_at` 3 h back (SQL); wait for the next cron tick.
*Expect:* exactly one grouped reminder; `last_reminder_at` set; no repeat on the following tick.

**M6 Digest.** Trigger WF-5 manually.
*Expect:* digest in ops channel + appended to the Notion page; numbers match `GET /stats`; includes USD spend.

**M8 Webhook persistence (WF-1 Telegram Trigger).** Set `WEBHOOK_URL` in `.env` to the public
HTTPS URL, run `make n8n-set-webhook`, wait for the `n8n-n8n-1` restart.
*Expect:* WF-1 activates without the "webhook URL missing" error; Telegram `getWebhookInfo`
returns the URL from `.env`; stored n8n credentials still decrypt (no key rotation).
This is the runtime verification left pending by #14 — code review flagged that stock n8n
images may not source `/home/node/.n8n/.env` (gotcha #50); if activation fails, reopen the finding.

## L5 — deploy smoke (M7)

1. `curl https://<domain>/health` → 200 with DB ok. 2. M1 against production. 3. TLS valid; n8n UI behind auth.
4. Trigger `backup.sh` → dump appears in object storage. 5. `docker compose restart` → all services healthy, data intact.

## Traceability — Definition of Done → tests

| DoD item | Verified by |
|---|---|
| Bot answers KB question < 15 s | M1 |
| Ambiguous → Approve/Edit flow | M2, M3, M4 |
| Digest to Telegram + Notion with spend | M6 |
| Evals ≥ 85%, CI green | L3 + CI badge |
| Deployed, TLS, backups | M7 |
| WF-1 Telegram Trigger activates with persisted `WEBHOOK_URL` | M8 + `test_set_webhook.py` |
| Stranger reproduces locally | fresh-clone rehearsal before applying |
