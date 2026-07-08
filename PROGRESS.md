# PROGRESS.md — Build board (single source of "what is done")

**Legend:** `[ ]` todo · `[~]` in progress (claimed: agent, date) · `[x]` done (date, agent) · `[HUMAN]` human-only task
**Rule:** claim a task by editing its line to `[~] (agent, YYYY-MM-DD)` in your first commit.

## Phase 0 — Foundation
- [x] P0-1 (Claude, 2026-07-05) docker-compose (postgres/pgvector, rag-api stub) with healthchecks + pinned tags. n8n excluded — existing local instance (localhost:5678) reused instead, see gotcha #1 resolution in wiki/log.md.
- [x] P0-2 (Claude, 2026-07-05) db/init/01_schema.sql per SPEC §3.3 — verified 5 tables + pgvector 0.8.4 on first postgres start.
- [x] P0-3 (Claude, 2026-07-05) Makefile, .env.example, ruff+pytest config, .gitattributes (LF), .gitignore, uv-managed pyproject.toml.
- [x] P0-4 (Claude, 2026-07-05) kb/seed: 10 fake Acme Cloud Suite docs (UA+EN, internally consistent — verified via grep sweep).

## Phase 1 — RAG/LLM service
- [x] P1-1 (Claude, 2026-07-05) llm.py provider layer: claude-haiku-4-5 primary, gpt-5.4-mini fallback on 5xx/timeout/connection errors, fake provider (also cost-logged), budget guardrail (BudgetExceeded → 429), per-attempt cost logging to llm_calls.
- [x] P1-2 (Claude, 2026-07-05) POST /kb/ingest (idempotent re-ingest by title) + scripts/ingest.py (HTTP CLI wrapper for `make seed`); chunk ~500/50 words, embed via text-embedding-3-small, upsert kb_documents/kb_chunks.
- [x] P1-3 (Claude, 2026-07-05) POST /classify — JSON-schema structured output, 1 retry on invalid parse, 422 on second failure. ticket_id is UUID-typed (bad input → clean 422, not a raw 500).
- [x] P1-4 (Claude, 2026-07-05) POST /query — top-5 pgvector cosine search, [source: title#chunk] citations, confidence = 0.5*similarity + 0.5*self_check, gate boundary verified exactly at 0.70/0.699.
- [x] P1-5 (Claude, 2026-07-05) POST /summarize (UA digest text), GET /stats (ticket/cost/latency aggregates).
- [x] P1-6 (Claude, 2026-07-05) 17 L1/L2 tests, all green with LLM_PROVIDER=fake: chunking, classify-schema, confidence boundary, llm-fallback (5xx + 4xx), budget-guardrail, ingest/query roundtrip, idempotency, stats.

## Phase 2 — Intake & auto-answer
- [x] P2-1 [HUMAN] (2026-07-05) Bot created via BotFather (@opspilot_cc_bot) and added to the ops group; TELEGRAM_BOT_TOKEN + TELEGRAM_OPS_CHAT_ID in .env (not committed), both verified live via getMe/getChat.
- [x] P2-2 (Claude, 2026-07-05) WF-1 Intake & Triage — n8n/workflows/wf1_intake_triage.json, imported + activated via n8n REST API (active=true, verified via GET). Telegram Trigger node present but `disabled: true` (no public webhook URL on this n8n instance — gotcha #2/#14); Webhook Trigger (`POST /webhook/opspilot-intake`) is live and is what E2E-tested this phase.
- [x] P2-3 (Claude, 2026-07-05) WF-2 Draft Answer — n8n/workflows/wf2_draft_answer.json, imported + activated. Confidence gate confirmed working end-to-end against the live threshold (0.70, hardcoded literal — n8n's `$env` cannot see this project's `.env`, see gotcha #15).
- [x] P2-4 (Claude, 2026-07-05) Idempotency proven at the workflow level: `scripts/check_intake_idempotency.sh` posts an identical webhook payload twice → exactly one ticket row (on top of the DB-constraint-level proof already in P1's `test_idempotency.py`).
- [x] P2-5 [HUMAN+Claude] (2026-07-06) E2E M1 happy path — n8n's outage (see Blockers, now
  CLOSED) is resolved; Telegram Trigger re-enabled (`updates: ["message","callback_query"]`,
  `disabled` removed) with a live public webhook via ngrok
  (`https://caffeinic-convulsively-barney.ngrok-free.dev`). Live-verified via real ticket
  submissions through the Webhook Trigger path end-to-end into WF-2/WF-3.

## Phase 3 — Human-in-the-loop & SLA
- [x] P3-1 (Claude, 2026-07-06) WF-3 inline keyboard (Approve/Edit/Reject) + callback handling —
  `n8n/workflows/wf3_hitl.json` imported, activated, and **live E2E-verified**: ops message posts
  with all 3 buttons and correct `callback_data`; Approve/Edit/Reject button clicks all correctly
  route through WF-1's callback IF-chain → WF-3's two Switch nodes → the right branch (confirmed via
  n8n execution logs, `lastNodeExecuted` matches expected terminal node in each case). ADR-005's
  single-Telegram-entry-point architecture confirmed working as designed.
- [x] P3-2 (Claude, 2026-07-06) Edit capture (reply-to) — footer format changed from `[ticket:<uuid>]`
  to bracket-free `TICKET-ID:<uuid>` after discovering Telegram's default Markdown parse mode
  silently strips unmatched `[...]` as incomplete link syntax (gotcha #26). **Live-verified**: a real
  Telegram reply (using the native reply gesture, not just quoted text) correctly populates
  `reply_to_message`, `Is Ops Reply` matches (after fixing a type-coercion bug, gotcha #27), the
  ticket-id regex extracts correctly, `Insert Operator Message` succeeds. WF-2's `needs_human`
  branch inserting the `ai_draft` message also confirmed live.
- [x] P3-3 (Claude, 2026-07-06) WF-4 SLA watchdog — imported, activated, **live-verified** against a
  real cron tick: a backdated escalated ticket produced exactly one grouped reminder message in the
  ops chat at the scheduled `:00`/`:15` mark, and `last_reminder_at` was set so the next tick will
  correctly skip it.
- [x] P3-4 [HUMAN+Claude] (2026-07-06) E2E M2–M5 — see Blockers for the one remaining caveat
  (customer-facing send on Approve/Edit-reply/Reject only verified against synthetic webform test
  tickets, not a real Telegram-DM-sourced ticket).

## Phase 4 — Digest & Notion
- [x] P4-1 (Claude, 2026-07-06) `GET /stats` extended with an optional `hours` query param
  (filters all aggregates on `created_at`, no param = unchanged all-time behavior) plus
  `tickets_by_category`/`tickets_by_priority` fields. Tests added (backdated-row exclusion +
  category/priority breakdown); 18/18 L1/L2 tests green.
- [x] P4-2 (Claude, 2026-07-06) `n8n/workflows/wf5_daily_digest.json` — Schedule Trigger (cron
  `0 0 9 * * *`, `settings.timezone: "Europe/Kyiv"`) + a parallel Webhook Trigger
  (`/webhook/opspilot-digest`) for on-demand testing → `GET /stats?hours=24` → `POST /summarize`
  (Ukrainian digest text, confirmed live).
- [x] P4-3 (Claude, 2026-07-06) Same workflow fans out to Telegram (`Send Digest To Ops`, reuses
  `Telegram - OpsPilot`) and Notion (`Append To Notion`, new `Notion - OpsPilot` credential,
  `notionApi` predefined-credential-type auth) — both **live-verified** via the webhook path: a
  real heading (date) + paragraph (digest text) block appended to the live Notion page, and the
  Telegram branch confirmed via execution logs. Found and fixed a real bug: Notion's "append block
  children" endpoint requires **PATCH**, not POST — every reference (my curl tests, the workflow
  node) initially guessed POST; verified against Notion's official API reference after the live
  call failed with a misleadingly-named `invalid_request_url` error (see gotcha #31).
- [ ] P4-4 [HUMAN] E2E M6 — verify the real 09:00 Europe/Kyiv cron fires (not just the webhook
  test path) and do a visual check of the Telegram message + Notion page formatting.

## Phase 5 — Evals & CI
- [x] P5-1 (Claude, 2026-07-06) `evals/tickets.jsonl` — 27 items (subagent-drafted, human/agent-
  reviewed): billing 8, technical 8, account 8, other 3 · priority: urgent 4, high 6, normal 12,
  low 5 · lang: en 16, uk 11 (≥8 required) · 3 `expected_ambiguous` items across distinct
  category pairs (billing/account, technical/billing, technical/account). Content verified
  consistent with real kb/seed facts (pricing, SLA tiers, retention/refund windows, rate limits).
- [x] P5-2 (Claude, 2026-07-06) `evals/test_classify.py` + `evals/test_grounding.py` +
  `evals/conftest.py` built (isolated from `services/rag/tests/` — runs against the real dev DB
  and real ingested KB, not the truncate-safe test DB, since grounding needs real embedded
  chunks). Budget assertion, per-class confusion summary, `@pytest.mark.evals` throughout, all
  wired into `make evals`. **Accuracy target not met with the providers available this
  session** — see Blockers for the full model-comparison writeup (best local result: 0.833 on a
  12B model, accepted as documented rather than continuing to tune, per this phase's stop
  condition). `test_grounding.py` correctly fails under `ollama` (no local embedding model
  matches the required 1536 dims — this is the dimension-guard in `_embed()` working as intended,
  not a test bug) and was not run to a passing state with any provider this session.
- [x] P5-3 (Claude, 2026-07-06) `.github/workflows/ci.yml` — `test` job (push/PR, no secrets:
  postgres service container + ruff + `pytest services/rag/tests`) and `evals` job
  (`workflow_dispatch` only, needs `ANTHROPIC_API_KEY` secret + `make evals`). `Makefile`'s
  `evals` target wired to `uv run pytest evals -m evals -s`. README CI badge added. Not yet
  verified against a real GitHub Actions run (would need a push to validate end-to-end).

### Unplanned addition this phase: multi-provider `llm.py` (Ollama + Gemini)
Requested mid-phase (needed to unblock live evals — neither `ANTHROPIC_API_KEY` nor
`OPENAI_API_KEY` were ever populated in `.env`). `llm_provider` now genuinely selects among
`anthropic` (primary, the only one with an OpenAI fallback chain — unchanged ADR-001 behavior),
`openai`, `gemini` (gemini-2.5-flash + gemini-embedding-001, plain REST via httpx, rate-limit
retry), `ollama` (local, via its OpenAI-compatible endpoint), and `fake`. See wiki/log.md for the
full narrative and wiki/gotchas.md #33–#38 for every non-obvious finding (odd AI-Studio key
format, Gemini's UPPERCASE schema + native dimension control, Gemini's free-tier daily quota,
Ollama `max_tokens` for reasoning models, no 1536-dim local embedding model, and the local-model
accuracy comparison).

## Phase 6 — Deploy & packaging
**Scope decision this session**: real cloud VM provisioning is deferred — current dev setup
(local compose + local n8n + ngrok tunnel) remains the working baseline. This phase produced the
deploy documentation and locally-verifiable artifacts; it does not execute against a live VM.
- [x] P6-1 (Claude, 2026-07-06) `docs/infrastructure.md` — full runbook (provision → clone → .env
  → n8n on the same VM as a separate compose project → `docker compose --profile prod up -d` →
  DNS → Caddy auto-TLS on two subdomains → n8n basic auth/`WEBHOOK_URL` → `make n8n-sync` →
  M7 verification) + GCP↔AWS mapping table. `docker-compose.yml` gained a `caddy` service behind
  `profiles: ["prod"]` (verified: absent from default `docker compose config`, present with
  `--profile prod`) plus a new `caddy/Caddyfile` (two site blocks, not path-based routing).
  Also fixed a real gap from Phase 5: `rag-api`'s environment block never passed through
  `GEMINI_API_KEY`/`OLLAMA_*` — added. **Not executed against a real VM** (see scope decision
  above) — commands are reviewed, not rehearsed.
- [x] P6-2 (Claude, 2026-07-06) `scripts/backup.sh` (pg_dump → gzip → `rclone` upload, cloud-
  agnostic; cron line documented) + `scripts/test_backup_restore.sh`, **run live against a
  scratch database this session** (`opspilot_restore_test`): dump/restore cycle confirmed —
  restored row counts matched the source exactly (`kb_documents=10 kb_chunks=15`). The `rclone`
  upload step itself is documented but not exercised (no cloud remote configured).
- [x] P6-3 (Claude, 2026-07-06) ADR-001 (LLM via service), ADR-002 (confidence gate), ADR-003
  (pgvector), ADR-004 (asyncpg/no-ORM) written; ADR-005 corrected (stale `[ticket:<uuid>]` example
  updated to the actual `TICKET-ID:<uuid>` format used since Phase 3). `wiki/INDEX.md` updated.
- [x] P6-4 (Claude, 2026-07-06) `README.md` replaced — was the agent-kit's own build-instructions
  README; now the project's portfolio README (pitch, Mermaid diagram reused from `docs/SPEC.md`
  §2, 3-command quickstart, CI badge, metrics table placeholders, out-of-scope section, license).
  New `LICENSE` (MIT). Bot handle, demo video link, and real `/stats` metrics remain `[HUMAN]`
  placeholders — need production traffic and the recorded video to fill in.

## Maintenance (OpenSpec-tracked changes)
- [x] `add-ollama-cloud-auth` (Claude, 2026-07-06, archived) — optional `OLLAMA_API_KEY` for the
  `ollama` provider to authenticate directly against `https://ollama.com/v1`. See P5-2 blocker
  entry below and wiki/gotchas.md #41 for the result.
- [x] `add-docstrings-pep8-audit` (Claude, 2026-07-06, archived) — closed all docstring gaps
  found by an AST scan across `services/rag/app/`, `evals/`, and `scripts/`; added `D100-D104`
  (docstring-presence) to ruff's lint config, with tests exempted via `per-file-ignores`.
  `ruff check`/`ruff format --check` clean, `make test` 18/18 green. New spec:
  `openspec/specs/code-documentation-standards/spec.md`.
- [x] `split-llm-provider-package` (Claude, 2026-07-08, archived; merged as PR #5) — replaced the
  627-line `services/rag/app/llm.py` god module with the `app/llm/` package: one module per
  provider under `providers/`, explicit registry dispatch (adding a provider = new module + one
  registry entry), `Ledger` interface isolating the package's only DB touchpoint, façade
  re-exports so `main.py` and callers are unchanged. No behavior change; 19/19 tests green
  (incl. new DB-free provider test), lint clean, live `ollama` `/classify` spot-check passed.
  Delta spec synced into `openspec/specs/llm-provider-layer/spec.md` (3 structural requirements
  added); change archived at `openspec/changes/archive/2026-07-08-split-llm-provider-package/`.
- [x] `add-ticket-events-log` (Claude, 2026-07-08, active — not yet archived) — append-only
  `ticket_events` audit log via `db/init/02_ticket_events.sql`: AFTER triggers on
  `tickets`/`messages` capture ticket.created / classified / status_changed / sla_reminded /
  message.added from both writers (n8n + rag-api) with zero workflow changes; append-only
  enforced in-database; new `GET /tickets/{id}/events`. Schema freeze amended additively
  (ADR-006, `01_schema.sql` untouched); conftest now applies all `db/init/*.sql`. 28/28 tests
  green, lint clean, live smoke against the dev DB passed. New spec capability:
  `ticket-event-log`.

## Blockers / Findings
_(agents append here; format: `- [OPEN|CLOSED] YYYY-MM-DD agent: description`)_
- [CLOSED] 2026-07-05 human: WF-1's "Alert Ops - Urgent" Telegram node's `chatId` set to the real
  ops chat ID directly in the n8n editor (verified via `GET /api/v1/workflows/{id}` — live node now
  shows `-5134402265`, not the placeholder). **Caveat carried forward:** the committed
  `n8n/workflows/wf1_intake_triage.json` still has (and per AGENTS.md must keep)
  `"PLACEHOLDER_OPS_CHAT_ID"` — if `make n8n-sync` is ever re-run to push a future edit to WF-1, the
  `PUT` update will overwrite the whole node's parameters and silently revert `chatId` back to the
  placeholder. Whoever re-syncs WF-1 next must re-apply this same one-time UI edit afterward (see
  gotcha #20).
- [CLOSED] 2026-07-06 Claude: WF-1's Telegram Trigger is re-enabled with a live public webhook
  (ngrok). Was blocked on no public URL (gotcha #2) — resolved once the user's n8n instance had
  `WEBHOOK_URL` configured and came back healthy.
- [CLOSED] 2026-07-06 human+Claude: **n8n outage fully resolved.** Root cause of the Postgres
  auth crash-loop was genuinely a stale password baked into the running `n8n-n8n-1` container's
  environment that no longer matched what `.env`/`psql` had — confirmed by hashing (not just
  length-comparing) the container's actual `DB_POSTGRESDB_PASSWORD` against the expected value,
  which is the only way this was actually caught (see gotcha #29). Fixed via a direct
  `ALTER USER n8n WITH PASSWORD ...` against the live role using the password already loaded in the
  container's memory — no container recreation needed, so the encryption key was not touched again.
  Both `Postgres - OpsPilot` and `Telegram - OpsPilot` credentials from the earlier encryption-key
  rotation *were* confirmed genuinely undecryptable (not a false alarm — WF-1's Telegram Trigger
  activation, the only node type in any of the 4 workflows that actually exercises credential
  decryption at *activation* time rather than execution time, failed with an explicit
  "Credentials could not be decrypted" error) and were recreated fresh via the API. All 4 workflows
  now sync and activate cleanly via `make n8n-sync`.
- [OPEN] 2026-07-05 Claude: `/query`'s embed call doesn't pass `ticket_id` (see
  `services/rag/app/main.py`), so `llm_calls` rows for `purpose='embed'` aren't attributed to a
  ticket. Out of scope for Phase 2 (guardrail: don't touch `services/rag` internals) — minor P1
  follow-up for whoever picks it up.
- [CLOSED] 2026-07-06 Claude: n8n credential setup superseded by the full recreation above; final
  working IDs: `Postgres - OpsPilot` and `Telegram - OpsPilot` (new IDs post-recreation, see n8n's
  own credential list — not committed anywhere, per AGENTS.md).
- [CLOSED] 2026-07-06 Claude: Phase 3 (WF-3, WF-4) imported, activated, and live E2E-verified — see
  P3-1..P3-4 above. The `PLACEHOLDER_OPS_CHAT_ID` fix now covers **6 places** (corrected count — an
  earlier note said 5 and missed one): WF-1's urgent-alert node + "Is Ops Reply" IF condition,
  WF-3's "Send Ops Message" + "Prompt For Correction" + "Escalation Notice To Ops", and WF-4's
  "Send Grouped Reminder". Reminder: per gotcha #20, this is a live-only patch that must be
  reapplied after every future `make n8n-sync` of these 3 workflows (a small helper script pattern
  for this now exists in this session's history — re-derive rather than hand-edit in the UI, to
  keep it reproducible).
- [OPEN] 2026-07-06 Claude: three real bugs were found and fixed only because of this session's live
  E2E pass — none of them were caught by structural JSON/connection-graph validation, which is a
  signal that **structural validation alone is not sufficient sign-off for n8n workflow changes**
  going forward; budget for at least one live execution per new/changed node type before calling a
  workflow phase done:
  1. A literal newline byte embedded in a quoted JS string inside an n8n expression (invalid JS
     syntax, only surfaces at execution time) — gotcha #25.
  2. Telegram's default Markdown parse mode silently stripping the `[ticket:<uuid>]` footer as
     unmatched link syntax, silently breaking the edit-reply regex — gotcha #26. Fixed by switching
     to a bracket-free `TICKET-ID:<uuid>` marker (also applied to the regex in WF-1's
     "Prepare Edit Reply Payload").
  3. A strict-type IF condition comparing Telegram's numeric `chat.id` against a string literal,
     throwing a hard runtime error instead of coercing — gotcha #27.
- [OPEN] 2026-07-06 Claude: the bot's Telegram Group Privacy Mode (default ON) was blocking all
  ordinary group messages/replies from ever reaching n8n's webhook — only commands and
  `callback_query` updates were exempt (gotcha #28). Fixed by the user disabling it via BotFather.
  **Not yet re-verified**: whether this needs to be re-disabled if the bot is ever removed and
  re-added to the ops group (Telegram's own docs are inconsistent on whether privacy-mode changes
  apply retroactively to existing group memberships).
- [OPEN] 2026-07-06 Claude: Approve / Edit-reply / Reject's final customer-facing Telegram send was
  only verified against **synthetic webform-sourced test tickets** (`external_ref` like
  `e2e-approve-test-...`, `source: "webform"`), which have no real Telegram chat to reply to — the
  send correctly fails with "chat not found" in these tests, and (correctly, by design) the ticket
  status/DB update is *not* applied when the customer-facing send fails. The underlying
  chat-id-parsing pattern (`external_ref` split, same as WF-2's already-proven "Reply To Customer"
  node) is unchanged and low-risk, but a fully real E2E (customer DMs the bot → gets escalated →
  operator clicks Approve/Reject or replies with a correction → customer actually receives the
  message) has not yet been run. Do this before considering P3-4 fully closed for a real demo.
- [CLOSED] 2026-07-06 Claude: **`make test`/`pytest` was silently wiping the live dev database**
  (all tickets, KB seed, llm_calls) — `_clean_tables` in `services/rag/tests/conftest.py`
  truncated every app table before/after each test, but tests only rewrote the DB *hostname*
  (`localhost` vs the compose-internal `postgres`), not the database itself, so it was the exact
  same live `opspilot` database used by the running `rag-api`/n8n. This actually happened mid-P4-1:
  running the test suite to verify the `/stats` extension wiped every Phase 2/3 E2E test ticket and
  the ingested KB seed. Fixed by adding a session-scoped autouse fixture
  (`_reset_test_database`) that creates/resets a dedicated `<POSTGRES_DB>_test` database (drop +
  recreate + reapply `db/init/01_schema.sql`) and points `settings.database_url` at it — no new env
  var needed, derived from the existing `POSTGRES_DB`. KB was re-seeded via `scripts/ingest.py`
  after the incident. See gotcha #31.
- [OPEN] 2026-07-06 Claude: Notion's "Append block children" endpoint requires **PATCH**, not POST
  — used POST throughout initial testing (including my own curl reproduction), which fails with a
  misleadingly-named `invalid_request_url` error that doesn't mention the method at all. Fixed in
  `wf5_daily_digest.json`'s "Append To Notion" node. See gotcha #32.
- [OPEN] 2026-07-06 Claude: P4-4's live 09:00 Europe/Kyiv Schedule Trigger tick has not been
  observed yet (only the parallel Webhook Trigger path was used to verify the flow this session,
  since waiting for the real cron wasn't practical mid-build) — the `settings.timezone` field is
  set correctly per the plan's research, but the actual scheduled fire time should be confirmed
  once convenient.
- [OPEN] 2026-07-06 Claude: **P5-2's 0.85 classify-accuracy target was not reached** with any
  provider actually exercised live this session. Root cause: neither `ANTHROPIC_API_KEY` nor
  `OPENAI_API_KEY` were ever populated in `.env` (confirmed empty). Gemini (`gemini-2.5-flash`,
  wired and verified working) hit its free-tier's **daily** quota (20 requests/day — not just the
  5/min limit, which retry-with-backoff already handles) partway through the 27-ticket run,
  which no amount of retrying fixes until the quota resets; the user chose local Ollama over
  enabling billing. Four models compared live on the identical fixture + prompt (Phase 6 revisit
  adds a fourth): `llama3.2:3b` (0.500–0.667, unreliable at the "other" category), `huihui_ai/
  qwen3.5-abliterated:9b` (a reasoning model — slow, and still occasionally failed to produce
  valid JSON within an 8192-token budget), a 12B gemma-coder-tuned GGUF model (**0.833, the
  best of all four** — fast, zero validation failures, perfect on "other" — currently the `.env`
  default), and `minimax-m3:cloud` (Ollama-proxied to its own cloud backend, not local compute —
  gotcha #40; fast and reliable but only **0.750**, worse than the local 12B model). Requested
  `glm-5.2:cloud` specifically was tried first but requires a paid ollama.com subscription (403).
  One prompt clarification was made to `classify.md` (category definitions) per the phase's stop
  condition, tried once, accepted the result rather than continuing to tune indefinitely. Also
  found and fixed a real bug while testing `minimax-m3:cloud`: it wrapped valid JSON in markdown
  code fences despite `strict: true`, which crashed with an unhandled `JSONDecodeError` instead of
  the intended clean retry — `llm.py`'s new `_parse_json()` helper strips fences and returns
  `None` on failure instead of raising, applied to all three structured-output call sites
  (gotcha #39). `test_grounding.py` has not passed with any provider this session: Gemini's quota
  was exhausted before reaching it, and no local Ollama embedding model outputs the required 1536
  dimensions (confirmed: `nomic-embed-text` gives 768) — `/query` correctly raises rather than
  corrupting `kb_chunks`. **To actually close P5-2**: either enable billing on the Gemini key
  (cheap — the whole suite is well under $0.50 even at paid-tier pricing) or obtain a real
  Anthropic/OpenAI key; local models are a viable free `/classify`-only dev option but not
  currently sufficient for a passing `make evals` run. Full comparison and every technical finding
  in wiki/gotchas.md #33–#40.
- [OPEN] 2026-07-06 Claude: **`kimi-k2.7-code:cloud` tried as a fifth model, also does not close
  P5-2's gap** — see `openspec/changes/add-ollama-cloud-auth` (implemented) for the code change
  that made this testable at all: `settings.py`/`llm.py` gained an optional `OLLAMA_API_KEY` that
  routes the `ollama` provider directly to `https://ollama.com/v1`, since the local daemon's
  `:cloud`-model proxying needs a separate paid ollama.com subscription plan that this session's
  account doesn't hold (confirmed via a 403 even after `ollama signin` verified the correct
  account and a full `ollama serve` restart — see wiki/gotchas.md #41). Once wired to a real
  personal API key (pay-per-token product, distinct from the subscription), the call succeeded
  (no 403) but scored only 0.750–0.792 across two runs — worse than the existing local 12B
  default's 0.833. **Also found**: `llm.py`'s cost logging has no pricing entry for `ollama`, so
  this real billed cloud usage logged as `$0.0000` — the `$2` dev-budget invariant currently can't
  see spend on this path. To actually close P5-2: the only untried route left is a real
  Anthropic/OpenAI key (spec already budgets for this, see docs/SPEC.md §4 "$2 dev budget").
- [OPEN] 2026-07-07 Claude: **`gemma4:31b-cloud` tried as a sixth model (openspec change
  `try-gemma4-31b-cloud`), also does not close P5-2's gap.** Via the same `OLLAMA_API_KEY` direct
  cloud-auth path as the prior test — no code change needed, this was a config-value-only test.
  Scored 0.792, reproducible across two runs (unlike `kimi-k2.7-code:cloud`'s run-to-run
  variance), still below both the 0.85 target and the local 12B model's 0.833. Per the decision
  rule in that change's design (update the default only if a candidate strictly beats 0.833),
  `.env`'s `OLLAMA_MODEL` was left unchanged. Four cloud-routed models have now been tried total
  (`minimax-m3:cloud` 0.750, `kimi-k2.7-code:cloud` 0.750–0.792, `gemma4:31b-cloud` 0.792,
  `glm-5.2:cloud` blocked entirely by the subscription gate) — none has beaten the local model.
  The conclusion from the prior entry stands unchanged: the only untried route left is a real
  Anthropic/OpenAI key.
- [OPEN] 2026-07-07 Claude: **Two more cloud models tried on the `llm-optimization` branch,
  neither closes P5-2's gap.** `qwen3.5:397b-cloud` scored 0.792 (same as `gemma4:31b-cloud`) but
  took 22.5 minutes for one 27-item eval run — impractically slow for `/classify`'s synchronous
  path regardless of accuracy. `glm-5.2:cloud` (previously blocked by the subscription gate, gotcha
  #40) became accessible once the account's subscription was reconnected and scored 0.750, tying
  `minimax-m3:cloud` as the worst result of any model tried. Per the same threshold rule as the
  prior entry, `.env`'s `OLLAMA_MODEL` was left unchanged. Five cloud-routed models have now been
  tried total (`minimax-m3:cloud` 0.750, `kimi-k2.7-code:cloud` 0.750–0.792, `gemma4:31b-cloud`
  0.792, `qwen3.5:397b-cloud` 0.792, `glm-5.2:cloud` 0.750) — all cluster in a narrow 0.750–0.792
  band regardless of stated model size, which is itself informative: this looks like a
  task/prompt ceiling for this model family, not a "just try a bigger model" problem. The
  conclusion is unchanged and now well-evidenced: the only untried route to close P5-2 is a real
  Anthropic/OpenAI key.
- [OPEN] 2026-07-06 Claude: Phase 6's real-VM acceptance criteria are explicitly deferred, per
  user decision — "human executes docs/infrastructure.md top-to-bottom," "TESTPLAN M7 passes over
  TLS," and "fresh-clone rehearsal on a clean machine" are all `[ ]` open, not faked as done. When
  a real VM is eventually provisioned: rehearse `docs/infrastructure.md` literally, fix whatever
  step doesn't work as written (it hasn't been run against a real machine yet), then flip these to
  `[x]`.

## Metrics to fill before applying
- Auto-resolution rate: __% · Avg confidence: __ · Avg cost/ticket: $__ · p95 answer latency: __ s · Eval accuracy: __%
