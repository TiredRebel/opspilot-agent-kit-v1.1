# log.md — chronological record (append-only)

Entry prefix convention (parseable): `## [YYYY-MM-DD HH:MM] <op> | <agent> | <title>`
where `<op>` ∈ `build | ingest | review | lint | query`.
Last N entries: `grep "^## \[" wiki/log.md | tail -5`

## [2026-07-05 11:00] build | kit-generator (Claude, chat) | Agent kit authored (pre-P0)
- Completed: AGENTS.md, CLAUDE.md, SPEC, TESTPLAN, prompts P0–P6 + R1/R2, wiki, PROGRESS
- Decisions: ADR-001 pre-locked (LLM calls only via FastAPI service); ADR-004 pre-locked (asyncpg, no ORM)
- Gotchas added: #1–#7 seeded from the owner's known environment
- Handoff / next: run prompts/P0_foundation.md in Claude Code (plan mode) from a fresh git repo

## [2026-07-05 12:00] ingest | kit-generator (Claude, chat) | karpathy LLM Wiki pattern adopted (v1.1)
- Source: gist.github.com/karpathy/442a6bf555914893e9891c11519de94f (read-only reference, not vendored)
- Changes: log.md prefix convention; INDEX.md → content catalog; map.md added as the zero-hop project map;
  R3 wiki-lint prompt added; AGENTS.md gained the "Wiki schema" section (page-creation heuristic, file-back rule)
- Deliberate deviation: single dense map page instead of per-entity pages — for a small greppable codebase,
  entity-page sprawl measured worse than one map page (see README → memory system notes)
- Handoff / next: unchanged — start with prompts/P0_foundation.md

## [2026-07-05 19:00] build | Claude Code | Phase 0 — Foundation (P0-1..P0-4)
- Completed: P0-1 docker-compose.yml (postgres pgvector/pgvector:pg16 + rag-api only), P0-2
  db/init/01_schema.sql (verbatim from SPEC §3.3), P0-3 Makefile/.env.example/pyproject.toml
  (uv-managed) + .gitattributes/.gitignore, P0-4 kb/seed (10 fake "Acme Cloud Suite" docs, UA+EN)
- Files touched: docker-compose.yml, db/init/01_schema.sql, Makefile, .env.example, pyproject.toml,
  uv.lock, .gitattributes, .gitignore, services/rag/{Dockerfile,app/*,tests/test_health.py},
  kb/seed/*.md (10 files), PROGRESS.md, wiki/map.md, wiki/gotchas.md
- Decisions: git repo initialized this session (was not a repo before); n8n port collision (gotcha
  #1) resolved by reusing the existing local n8n instance on :5678 rather than running a second one
  — no n8n service in this project's compose at all
- Gotchas added: #8 (port 8000 often taken on this machine, rag-api moved to 8010), #9 (`make` not
  installed in the Windows Git-Bash toolchain — verified via `uv run ruff/pytest` + `docker compose`
  directly instead); gotcha #1 updated to record its resolution
- Verified: `docker compose up -d` → both services healthy; `\dt` shows 5 tables; pgvector 0.8.4;
  `curl :8010/health` → 200 `{"status":"ok","db":true}`; `uv run ruff format --check .` and
  `uv run ruff check .` clean; `uv run pytest services/rag/tests` → 2 passed; kb/seed facts
  cross-checked via grep for contradictions — none found
- Handoff / next: Phase 1 (prompts/P1_rag_service.md) builds the real llm.py provider layer and
  /kb/ingest, /classify, /query, /summarize, /stats endpoints on top of this stub

## [2026-07-05 20:30] build | Claude Code | Phase 1 — RAG/LLM service (P1-1..P1-6)
- Completed: P1-1 app/llm.py (claude-haiku-4-5 primary, gpt-5.4-mini fallback on 5xx/timeout/
  connection errors, fake provider, daily budget guardrail, per-attempt llm_calls logging incl.
  fake calls), P1-2 POST /kb/ingest + scripts/ingest.py, P1-3 POST /classify (schema + 1 retry),
  P1-4 POST /query (top-5 pgvector + confidence gate), P1-5 POST /summarize + GET /stats, P1-6
  17 L1/L2 tests (all green, LLM_PROVIDER=fake)
- Files touched: services/rag/app/{llm,retrieval,schemas,main,settings}.py, services/rag/prompts/
  {classify,answer,self_check,digest}.md, services/rag/tests/{conftest,test_chunking,
  test_confidence,test_classify_schema,test_llm_fallback,test_budget_guardrail,
  test_ingest_query_roundtrip,test_idempotency,test_stats}.py, scripts/ingest.py, Dockerfile,
  docker-compose.yml, pyproject.toml, Makefile (seed target), PROGRESS.md, wiki/map.md,
  wiki/gotchas.md
- Decisions: model IDs verified live (not guessed) — Anthropic via the bundled claude-api skill
  (claude-haiku-4-5, $1/$5 per 1M), OpenAI via WebFetch of developers.openai.com
  (gpt-5.4-mini, $0.75/$4.50 per 1M; text-embedding-3-small unchanged, Context7 was
  quota-exhausted); kb/seed mounted read-only into rag-api rather than baked into the image;
  scripts/ingest.py is an HTTP client against the running service, not a direct DB script (host
  vs. container DATABASE_URL hostname mismatch); citations in /query are computed in code from
  top-k retrieval, not parsed out of LLM text, since the fake provider can't produce them
- Gotchas added: #10 (kb/ bind mount + KB_SEED_DIR), #11 (tests rewrite DATABASE_URL to
  localhost), #12 (app.db pool is loop-bound — pytest vs TestClient loops corrupt it if shared),
  #13 (llm_calls.ticket_id is UUID — type it as uuid.UUID at the API boundary, not str)
- Verified: `uv run ruff format --check .` / `ruff check .` clean; `uv run pytest
  services/rag/tests` → 17 passed; rebuilt rag-api via `docker compose up -d --build`; `make seed`
  (uv run scripts/ingest.py) → 10 docs / 15 chunks against the real kb/seed; manually curled
  /classify (valid UUID → 200, bad UUID → clean 422), /query (cited sources, confidence in
  [0,1]), /summarize (correct UTF-8 Ukrainian text — an earlier mangled-looking curl pipe was a
  terminal decoding artifact, not an app bug), /stats (reflects logged llm_calls)
- Handoff / next: Phase 2 (prompts/P2_intake_autoanswer.md) — n8n WF-1 Intake & Triage and WF-2
  Draft Answer, calling this service's /classify and /query over HTTP; P2-1 (BotFather bot
  creation) is [HUMAN]-only

## [2026-07-05 21:15] build | Claude Code | Phase 2 — Intake & auto-answer (P2-1..P2-4)
- Completed: P2-1 finished (bot added to ops group, TELEGRAM_OPS_CHAT_ID confirmed via getUpdates/
  getChat); P2-2 wf1_intake_triage.json (Telegram Trigger [disabled] + Webhook Trigger → normalize →
  Postgres INSERT ON CONFLICT DO NOTHING → IF-is-new → /classify → Postgres UPDATE → IF-urgent →
  ops alert → Execute Workflow WF-2); P2-3 wf2_draft_answer.json (Execute Workflow Trigger →
  Postgres SELECT → /query → IF confidence>=0.70 → reply to customer (Telegram, if
  source=='telegram') + mark answered vs. mark needs_human); P2-4 idempotency proven live via
  scripts/check_intake_idempotency.sh (duplicate webhook delivery → still exactly one ticket)
- Files touched: n8n/workflows/{wf1_intake_triage,wf2_draft_answer}.json, scripts/{n8n_sync.py,
  check_intake_idempotency.sh}, Makefile (n8n-sync target), PROGRESS.md, wiki/map.md,
  wiki/gotchas.md
- Decisions: node JSON shapes researched via 2 parallel Explore agents (n8n source +
  docs.n8n.io + one live example) then cross-verified empirically against the actual running
  instance (n8n v2.18.7, Public API v1.1.1) rather than trusted blind — this caught two real gaps
  the research didn't have confirmed: Execute Workflow Trigger's real "accept all data" shape
  (`inputSource: "passthrough"`, not the guessed `workflowInputs` object) and n8n's stricter
  activation-time credential validation (vs. creation-time, which is permissive). Ticket identity
  for Telegram-sourced tickets encoded as `external_ref = "{chat_id}:{message_id}"` (no schema
  change) so WF-2 can parse the reply channel back out. CONFIDENCE_THRESHOLD (0.70) and the RAG
  service URL (`http://host.docker.internal:8010`) are literals in the JSON, not `$env`
  expressions — n8n's `$env` can't see this project's `.env` (gotcha #15)
- Course-correction during credential setup (see PROGRESS.md Blockers for full detail): a
  scripted attempt to create the Postgres n8n credential via API was correctly blocked by the auto
  mode classifier (the approved plan said this was a manual UI step) — paused and got explicit
  user authorization before proceeding. Also found 3 ambiguous/duplicate Telegram credentials on
  the instance (none named as requested) — user identified which one was for @opspilot_cc_bot,
  renamed it via PATCH /credentials/{id} rather than embedding its ID in committed JSON, keeping
  the "reference credentials by name only" rule intact. Separately, `.env` was edited outside this
  session (DB password changed with a typo mismatch between POSTGRES_PASSWORD/DATABASE_URL, and
  CONFIDENCE_THRESHOLD dropped to 0.40) — flagged to the user rather than silently adapting; user
  chose to actually apply the new DB password (fixed the typo, ran `ALTER USER` on the live
  container, recreated rag-api) and revert the threshold to the SPEC default
- Gotchas added: #14 (n8n container is on a separate Docker network — use host.docker.internal),
  #15 ($env doesn't see our .env), #16 (activation validation stricter than creation), #17
  (placeholder-then-human-relink pattern for values that are secret-shaped but can't be $env), #18
  (Execute Workflow Trigger's real passthrough shape), #19 (Postgres credential API's sshTunnel
  quirk); gotcha #2 updated with confirmation + the disabled:true workaround
- Verified: both workflows `active: true` via GET /api/v1/workflows/{id}; POST
  /webhook/opspilot-intake with a seeded-KB question → ticket reached needs_human at
  confidence=0.46 (fake-provider embeddings aren't semantically meaningful, so the low score is
  expected — the gate logic itself, including the previously-unconfirmed numeric "gte" operator,
  is proven correct by this routing); llm_calls has classify/answer/self_check rows for that
  ticket; scripts/check_intake_idempotency.sh passes; `grep` of all committed files for the bot
  token, n8n API key, and real chat ID found nothing
- Handoff / next: Phase 3 (prompts/P3_hitl_sla.md) — WF-3 inline keyboard replaces the "WF-3
  Placeholder" NoOp in wf2_draft_answer.json; P2-5 (human E2E M1 with live Telegram) still needs a
  tunnel — see PROGRESS.md Blockers

## [2026-07-05 21:30] build | human | Closed ops-alert chatId placeholder blocker
- Completed: human set WF-1's "Alert Ops - Urgent" node's `chatId` to the real ops chat ID
  directly in the n8n editor; verified live via `GET /api/v1/workflows/{id}` (`-5134402265`, not
  the placeholder)
- Decisions: committed `n8n/workflows/wf1_intake_triage.json` intentionally still has
  `"PLACEHOLDER_OPS_CHAT_ID"` (must stay that way per AGENTS.md) — this live/committed divergence
  means a future `make n8n-sync` of WF-1 will silently revert this fix; documented as gotcha #20
  and flagged in PROGRESS.md Blockers rather than solved with reconciliation logic
- Gotchas added: #20 (re-sync overwrites human-patched literals)
- Handoff / next: unchanged — Phase 3 next; whoever next edits/re-syncs WF-1 must re-apply this
  chatId fix afterward

## [2026-07-06 00:20] build | human+Claude | n8n instance down — paused, not fixed
- Attempted: set up an ngrok tunnel for P2-5 (Telegram E2E), applied `WEBHOOK_URL` to n8n's
  separate `/home/mcgun/n8n/docker-compose.yml` project (its own `.env`, not this repo's) and
  recreated the `n8n` container to pick it up
- Found: recreating that container exposed two pre-existing bugs in the user's own n8n setup, not
  this repo — (a) `user: "0:0"` (root) vs. the `n8n_storage` volume mounted at `/home/node/.n8n`
  means root writes encryption-key state to unmounted `/root/.n8n` instead, so any recreate
  silently rotates the encryption key (no backup existed — every credential on this n8n instance is
  now undecryptable and needs recreating); (b) n8n's own Postgres sidecar auth kept failing even
  after the user confirmed via direct `psql` that the current `.env` password works — root cause:
  a stale `POSTGRES_NON_ROOT_PASSWORD` already exported somewhere in the WSL environment shadows
  `.env` for any `docker compose` invocation (shell env beats `.env` file in compose's precedence);
  explicit `unset` in the invoking shell didn't clear it either, meaning the source is more
  persistent (`/etc/environment`, WSLENV passthrough, or similar) — needs the user's own terminal,
  not a remote relay, to track down
- Decisions: paused rather than kept guessing at someone else's infra from a lossy remote bridge.
  This blocks nothing in our own repo — Phase 2's acceptance criteria already passed via the
  Webhook Trigger path (gotcha #2's `disabled:true` workaround). Proceeding to Phase 3; n8n-specific
  Phase 3 tasks (WF-3/WF-4 import+activate+E2E) will be authored now and verified once n8n is back
- Gotchas added: #21 (recreating the pre-existing n8n container is risky — root/volume-path
  mismatch rotates the encryption key; env-var shadowing can silently defeat a `.env` password fix)
- Handoff / next: once n8n is healthy again, recreate the `Postgres - OpsPilot` and
  `Telegram - OpsPilot` credentials (same steps as P2's close-out), re-run `make n8n-sync` for
  WF-1/WF-2, re-apply the ops-alert `chatId` fix (gotcha #20), then attempt P2-5's live Telegram E2E

## [2026-07-06 00:45] build | Claude Code | Phase 3 — HITL & SLA (P3-1..P3-3, authored not verified)
- Completed: edited `wf1_intake_triage.json` (Telegram Trigger re-enabled, `updates:["message",
  "callback_query"]`, new IF-chain router for callback_query / ops-chat-reply / plain-message),
  edited `wf2_draft_answer.json` (needs_human branch now inserts the `ai_draft` message — a real
  gap found this session — and calls WF-3 instead of a NoOp), authored `wf3_hitl.json` (Switch on
  `mode` then on `action`; no trigger of its own — pure Execute-Workflow sub-workflow) and
  `wf4_sla_watchdog.json` (cron `*/15`, grouped reminder + per-ticket `last_reminder_at`); wrote
  `docs/decisions/ADR-005-single-telegram-entry-point.md`; extended `scripts/n8n_sync.py` to sync
  all 4 workflows in dependency order (WF-3, WF-4 first — no deps; then WF-2 — needs WF-3's id;
  then WF-1 — needs both)
- Files touched: `n8n/workflows/{wf1_intake_triage,wf2_draft_answer}.json` (edited),
  `n8n/workflows/{wf3_hitl,wf4_sla_watchdog}.json` (new), `docs/decisions/ADR-005-*.md` (new),
  `scripts/n8n_sync.py`, `PROGRESS.md`, `wiki/map.md`, `wiki/gotchas.md`
- Decisions: **ADR-005** — Telegram allows exactly one webhook per bot token, so WF-3 cannot have
  its own Telegram Trigger without silently breaking WF-1's customer-intake webhook registration on
  activation (no error anywhere — just "customer messages stop arriving" at some later point).
  Consolidated on WF-1's existing trigger as the sole entry point; WF-3 is purely
  Execute-Workflow-invoked. Reply→ticket mapping for edit-capture (P3-2) uses a `[ticket:<uuid>]`
  footer in the draft text rather than n8n workflow static data — no key-management/concurrency
  concerns, fully inspectable by a human reading the chat, no schema change
- Research: 2 rounds of Explore-agent research this phase, both reading n8n source directly
  (`Telegram.node.ts`, `Switch.node.ts`, `TelegramApi.credentials.ts`, `ScheduleTrigger.node.ts`,
  `ExecuteWorkflowTrigger.node.ts`) rather than trusting docs.n8n.io prose (consistently thin on
  exact JSON shapes across both P2 and P3). Corrected two things Phase 2's research had gotten
  wrong/unconfirmed: the inline-keyboard shape's actual array/object nesting (`rows` array →
  singular `row` → `buttons` array, not the reverse), and confirmed `resource:"callback",
  operation:"answerQuery"` is a native Telegram-node operation (no raw-HTTP/credential-token
  workaround needed, which also wouldn't have worked — `$credentials` isn't exposed to expressions)
- Verification status: **JSON authored and structurally validated only** (`python -m json.tool` +
  a scripted connection-graph check for broken links/orphan/duplicate nodes across all 4 files) —
  n8n itself has been down since the outage recorded in the previous entry, so import, activation,
  and any live E2E behavior (button taps, callback answering, SLA cron timing) are **unverified**.
  Treat P3-1..P3-3 as "written, reviewed, not yet proven" until n8n is back up.
- Gotchas added: #22 (Schedule Trigger cron is 6 fields incl. seconds, not standard 5), #23 (one
  webhook per bot token constrains workflow design, not just deployment), #24 (don't guess
  IF/Switch operator type/operation pairs for existence checks — wrong ones fail silently at
  runtime, not at import; use the boolean-coercion idiom instead)
- Handoff / next: once n8n is healthy (see previous entry's blockers), recreate both credentials,
  `make n8n-sync` (now handles all 4 files), then fix the 5 remaining `PLACEHOLDER_OPS_CHAT_ID`
  spots (WF-1's "Is Ops Reply" IF + urgent-alert node, WF-3's 2 ops-message nodes, WF-4's reminder
  node) before attempting P3-4's E2E (M2–M5)

## [2026-07-06 01:15] build | human+Claude | n8n outage resolved + Phase 3 live E2E (P2-5, P3-1..P3-4)
- Completed: root-caused and fixed the n8n Postgres auth crash-loop; recreated both n8n credentials;
  synced and activated all 4 workflows; found and fixed 3 real bugs surfaced only by live execution;
  fixed the bot's Group Privacy Mode blocking group replies; live-verified P2-5 and P3-1..P3-4 end
  to end via real Telegram interactions (button taps, native reply gesture) and a real SLA cron tick
- Root cause of the crash-loop: the *running* `n8n-n8n-1` container's `DB_POSTGRESDB_PASSWORD` had
  silently diverged from `.env`'s current value — same length (10 chars, coincidence), different
  actual bytes, confirmed only by hashing both values (never printing either) rather than trusting a
  length check (gotcha #29). Fixed via a direct `ALTER USER n8n WITH PASSWORD ...` against the live
  Postgres role using the password already loaded in the container's own memory — deliberately chose
  this over recreating the container, since recreation is what caused the original encryption-key
  rotation (gotcha #21) and would have risked repeating it
- Both `Postgres - OpsPilot` and `Telegram - OpsPilot` credentials were confirmed genuinely
  undecryptable post-rotation (not a false alarm): of all 4 workflows, only WF-1's Telegram Trigger
  actually exercises credential decryption *at activation time* (registering the webhook needs the
  bot token) — WF-2/WF-3/WF-4's triggers (Execute Workflow Trigger, Schedule Trigger) don't touch
  credentials until actual execution, so their clean activations were never proof the credentials
  were healthy. Recreated both fresh via the API once this was understood; all 4 workflows then
  synced and activated cleanly
- Three bugs found and fixed, none caught by structural JSON/connection-graph validation — all three
  only surfaced once real executions ran:
  1. A literal newline byte (not an escaped `\n`) inside a quoted JS string in WF-3's "Send Ops
     Message" `text` expression — invalid JavaScript, surfaced as "invalid syntax" deep in a
     Telegram-node stack trace (gotcha #25)
  2. The `[ticket:<uuid>]` footer was being silently stripped by Telegram's default Markdown parse
     mode (interpreted as an incomplete `[text](url)` link) — broke the edit-reply regex silently,
     no error anywhere (gotcha #26). Fixed by switching to a bracket-free `TICKET-ID:<uuid>` marker
     in both WF-3's footer-builder and WF-1's regex
  3. WF-1's "Is Ops Reply" IF condition compared Telegram's numeric `chat.id` against a string
     literal under `typeValidation: "strict"`, throwing a hard runtime type error instead of
     coercing (gotcha #27) — fixed by wrapping the leftValue in `String(...)`
- The bot's Telegram Group Privacy Mode (default ON) was blocking all ordinary group messages and
  replies from ever reaching n8n's webhook — only commands and `callback_query` updates were
  exempt, which is exactly why button clicks always worked reliably in testing but plain replies
  produced zero executions with no error anywhere (gotcha #28). Diagnosed by testing a `/test`
  command (always exempt) and confirming it *did* trigger an execution while plain text/replies
  didn't; fixed by the user disabling Group Privacy via BotFather
- Live E2E verified: ticket→`needs_human` routing (confidence 0.45 under the fake provider, correct
  gate behavior); ops message posts with all 3 buttons and correct `callback_data`; Approve/Edit/
  Reject button clicks all route to the correct branch (confirmed via `lastNodeExecuted` in n8n's
  execution API); a real Telegram reply (native reply gesture, not just quoted text — an earlier
  attempt using literal text without the reply gesture produced no `reply_to_message` at all) is
  correctly captured, ticket-id extracted, operator message inserted; SLA watchdog fired on its real
  15-minute cron tick, produced exactly one grouped reminder for a backdated ticket, and set
  `last_reminder_at` so the next tick will correctly skip it
- Caveat carried forward: Approve/Edit-reply/Reject's *customer-facing* send was only exercised
  against synthetic webform-sourced test tickets (no real Telegram chat to reply to) — the send
  correctly fails "chat not found" and the DB update is correctly skipped when it does (by design),
  but a fully real customer-DM-sourced E2E hasn't been run yet. Flagged in PROGRESS.md Blockers
- Gotchas added: #25 (raw newline in a JS expression string), #26 (Telegram Markdown strips
  unmatched brackets), #27 (strict-mode IF doesn't coerce number→string), #28 (Group Privacy Mode
  blocks ordinary group messages, not callbacks), #29 (compare container env values by hash, not
  just length), #30 (rapid reactivation hits Telegram's own rate limit, not a real config error)
- Handoff / next: run a fully real E2E (customer DMs the bot → escalates → operator
  approves/edits/rejects → customer actually receives the reply) before treating P3-4 as closed for
  a live demo. Otherwise Phase 3 is done — Phase 4 (digest + Notion) is next per PROGRESS.md

## [2026-07-06 01:45] build | Claude Code | Phase 4 — Digest & Notion (P4-1..P4-3)
- Completed: P4-1 extended `GET /stats` with an optional `hours` query param (all aggregates scope
  to `created_at >= now() - N hours`; no param = unchanged all-time behavior) plus
  `tickets_by_category`/`tickets_by_priority` fields; P4-2/P4-3 authored and **live E2E-verified**
  `n8n/workflows/wf5_daily_digest.json` (Schedule Trigger 09:00 Europe/Kyiv + a parallel Webhook
  Trigger for on-demand testing → `/stats?hours=24` → `/summarize` → fan out to Telegram + Notion)
- Files touched: `services/rag/app/{main,schemas}.py`, `services/rag/tests/{conftest,test_stats}.py`,
  `n8n/workflows/wf5_daily_digest.json` (new), `scripts/n8n_sync.py`, `.env` (NOTION_API_KEY,
  NOTION_PAGE_ID — human-provided, never committed), `PROGRESS.md`, `wiki/map.md`, `wiki/gotchas.md`
- Decisions: extended `/stats` rather than duplicating aggregation SQL in an n8n Postgres node (per
  the phase prompt's explicit preference) — new `hours` param is opt-in so the existing all-time
  behavior and its test stay unchanged. Added a parallel Webhook Trigger alongside the Schedule
  Trigger (mirrors WF-1's existing dual-trigger pattern) specifically so the whole flow could be
  self-tested via curl during the build rather than waiting for the real 09:00 cron tick.
  "Append To Notion" uses `authentication: "predefinedCredentialType"` +
  `nodeCredentialType: "notionApi"` (confirmed shape by reading `HttpRequestV3.node.ts`) rather than
  a generic header-auth credential, so n8n handles the Notion auth header the same way its own
  dedicated Notion node would, while still using a plain HTTP Request node per the phase prompt
- **Incident, found and fixed mid-P4-1**: running `uv run pytest` to verify the `/stats` extension
  silently truncated the *live dev database* — all Phase 2/3 E2E test tickets and the entire
  ingested KB seed were wiped. Root cause: `_clean_tables` in `conftest.py` truncates every app
  table before/after each test, but the old `_localhost_database_url()` only rewrote the DB
  *hostname* for running pytest outside Docker (gotcha #11), not the database name — so tests ran
  directly against the same live `opspilot` database the running `rag-api`/n8n use. Fixed (user
  explicitly asked for the fix, not just a re-seed workaround) with a session-scoped autouse
  fixture that creates/resets a dedicated `<POSTGRES_DB>_test` database, reapplies
  `db/init/01_schema.sql` fresh each session, and points `settings.database_url` at it — derived
  from the existing `POSTGRES_DB`/`POSTGRES_USER`, no new env var. Re-seeded the KB via
  `scripts/ingest.py` afterward. See gotcha #31.
- **Bug found and fixed**: Notion's "Append block children" endpoint requires HTTP `PATCH`, not
  `POST` — used POST throughout initial testing (including a plain `curl -X POST` reproduction,
  which ruled out an n8n-specific bug before I even opened Notion's docs) and got a misleadingly-
  named `"code":"invalid_request_url"` error that says nothing about the method. Confirmed the
  correct verb via Notion's official API reference and fixed the workflow node. See gotcha #32.
- Verified live end-to-end via the Webhook Trigger path (`POST /webhook/opspilot-digest`): response
  showed both a `heading_2` block (today's date) and a `paragraph` block (the fake provider's
  Ukrainian digest text) successfully appended to the real Notion page, and the parallel Telegram
  branch's execution ran successfully (confirmed via n8n's execution API — `status: success`,
  `Send Digest To Ops` present in `runData`)
- Gotchas added: #31 (tests must use an isolated database, not just a rewritten hostname — a
  shared-DB test suite can and did silently wipe live data), #32 (Notion's block-append endpoint is
  PATCH, not POST — a misleading error message masked this)
- Handoff / next: P4-4 (human E2E M6) — confirm the real 09:00 Europe/Kyiv Schedule Trigger tick
  fires on its own (only the webhook test path was exercised this session) and do a visual check of
  the Telegram message + Notion page formatting. Otherwise Phase 4 is done — Phase 5 (evals + CI) is
  next per PROGRESS.md

## [2026-07-06 07:30] build | Claude Code | Phase 5 — Evals & CI + multi-provider llm.py (P5-1..P5-3)
- Completed on the new `Phase-5` branch: P5-1 `evals/tickets.jsonl` (27 items, subagent-drafted
  per the phase prompt's own instruction, reviewed for distribution/quality); P5-2
  `evals/{conftest,test_classify,test_grounding}.py`; P5-3 `.github/workflows/ci.yml` +
  `Makefile`'s `evals` target + README CI badge. Unplanned mid-phase addition: `llm.py` restructured
  to genuinely support multiple providers (`anthropic`/`openai`/`gemini`/`ollama`/`fake`), needed
  to unblock live evals once it turned out `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` were both empty
- Files touched: `evals/{conftest,test_classify,test_grounding,tickets.jsonl}.py`,
  `.github/workflows/ci.yml`, `Makefile`, `README.md`, `services/rag/app/{llm,settings}.py`,
  `services/rag/prompts/classify.md`, `.env`/`.env.example`, `pyproject.toml` (moved `httpx` from
  dev to main deps — `llm.py`'s Gemini calls need it at runtime, not just in tests/scripts),
  `docs/SPEC.md` §3.1, `PROGRESS.md`, `wiki/map.md`, `wiki/gotchas.md`
- Decisions: `evals/conftest.py` deliberately does NOT reuse `services/rag/tests/conftest.py`'s
  isolated-test-database pattern (gotcha #31) — grounding checks need the real ingested KB, so it
  points at the actual dev database and never truncates. `_complete_openai_compatible()` extracted
  as a shared response-parser for OpenAI and Ollama (both return identically-shaped
  ChatCompletion objects via Ollama's OpenAI-compatible endpoint), avoiding duplicated parsing
  logic. Only `anthropic` mode keeps a fallback chain (unchanged from ADR-001); `openai`,
  `gemini`, `ollama` each run standalone by design — a genuine 4-way fallback graph was judged
  unnecessary complexity for what these are actually used for (dev/eval alternatives, not a
  production reliability chain)
- Research, all verified live rather than guessed (established pattern this session): Gemini's
  `generateContent`/`embedContent` REST shapes, its UPPERCASE-type structured-output schema
  format, its native `outputDimensionality` parameter (confirmed hitting exactly 1536 dims,
  matching the frozen schema — gotcha #5), real per-1M-token pricing from Google's own pricing
  page, and — critically — an unusual `AQ.`-prefixed key from AI Studio that still worked despite
  not matching the commonly-documented `AIzaSy...` format (gotcha #33)
- Incident + fix, found mid-P5-1: running `pytest` to verify the `/stats` P4-1 extension silently
  wiped the live dev database (all Phase 2/3 test tickets, the ingested KB) — `_clean_tables` in
  `services/rag/tests/conftest.py` truncated the same database the running services actually use,
  since the old fixture only ever rewrote the DB hostname (gotcha #11), not the database name.
  User asked for a real fix, not just a re-seed: added a session-scoped fixture that creates/
  resets a dedicated `<POSTGRES_DB>_test` database and reapplies `db/init/01_schema.sql` fresh
  each session — no new env var, derived from the existing `POSTGRES_DB`. See gotcha #31 (from
  the prior Phase 4 entry; this session's incident is what actually triggered the fix)
- Gemini quota discovery: initially hit what looked like a simple 5 req/min rate limit (retry-
  with-backoff added, parsing the exact wait from the 429 body since there's no `Retry-After`
  header); after ~23 minutes of retries the *real* constraint surfaced — a separate 20
  requests/*day* quota (`quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier`), which no
  amount of backoff fixes short of waiting a full day. This project's eval suite needs ~37 chat
  calls, comfortably exceeding that. User chose local Ollama over enabling billing
- Local-model comparison (all against the identical fixture + prompt, live): `llama3.2:3b` — fast,
  reliable, 0.500→0.667 accuracy after one prompt clarification (still over-predicts `account`);
  `huihui_ai/qwen3.5-abliterated:9b` — a visible-reasoning "thinking" model, slow (~60-100s/call),
  needed an explicit generous `max_tokens` (8192, up from none) since its reasoning trace could
  exceed Ollama's implicit default and truncate the final JSON (gotcha #36), but still
  occasionally failed to converge even with that budget; a 12B gemma-coder-tuned GGUF model —
  fast, zero validation failures, **0.833 accuracy**, the closest of the three but still under
  the 0.85 bar. Per the phase's explicit stop condition (one prompt adjustment, one rerun, then
  stop and document rather than keep tuning), accepted 0.833 as the recorded result rather than
  continuing to iterate against a live accuracy target
- `test_grounding.py` has not passed with any provider this session — blocked by the same Gemini
  quota exhaustion, and independently by no local Ollama embedding model matching the schema's
  frozen 1536 dimensions (`nomic-embed-text` gives 768, confirmed live) — `_embed()`'s dimension
  guard correctly raised rather than writing a corrupted vector, exactly as designed
- Comment-audit pass done per explicit request: added missing module/function docstrings and
  WHY-comments across `llm.py`, `main.py`, `db.py`, `schemas.py`, `settings.py`, `n8n_sync.py`;
  left `db/init/01_schema.sql` untouched (explicitly frozen per every phase prompt's guardrail,
  even for comment-only changes)
- Gotchas added: #33 (AI Studio key format varies, verify don't assume), #34 (Gemini schema is
  UPPERCASE + native dimension control), #35 (Gemini free tier has a daily quota, not just
  per-minute — corrected mid-session after initially under-diagnosing it), #36 (reasoning models
  need generous max_tokens), #37 (no 1536-dim local embedding model exists), #38 (local model
  accuracy/reliability comparison for structured classification)
- Handoff / next: to actually pass `make evals` (P5-2's literal acceptance criterion), either
  enable billing on the existing Gemini key or obtain a real Anthropic/OpenAI key — local models
  remain a valid free option for `/classify`-only dev/testing but aren't sufficient alone. CI
  workflow exists but hasn't been exercised against a real GitHub Actions run yet. README badge,
  Makefile, and PROGRESS.md are otherwise complete for this phase

## [2026-07-06 10:15] build | Claude Code | Phase 6 — Deploy & packaging (P6-1..P6-4)
- Completed on new `Phase-6` branch: P6-1 `docs/infrastructure.md` (full runbook) +
  `docker-compose.yml`'s `caddy` service behind `profiles: ["prod"]` + `caddy/Caddyfile`; P6-2
  `scripts/backup.sh` + `scripts/test_backup_restore.sh` (run live against a scratch DB); P6-3
  four new ADRs + one correction to ADR-005; P6-4 `README.md` replaced with the project's own
  portfolio README + new `LICENSE` (MIT)
- Files touched: `docs/infrastructure.md` (new), `docker-compose.yml`, `caddy/Caddyfile` (new),
  `scripts/{backup.sh,test_backup_restore.sh}` (new), `docs/decisions/ADR-{001,002,003,004}-*.md`
  (new), `docs/decisions/ADR-005-*.md` (corrected), `wiki/INDEX.md`, `README.md`, `LICENSE` (new),
  `services/rag/app/llm.py` (markdown-fence JSON parsing fix), `.env`, `PROGRESS.md`, `wiki/map.md`
- Decisions: real cloud VM provisioning explicitly **deferred** this session (user's call) — the
  runbook is written as accurate forward-looking documentation but not rehearsed against a live
  machine; `PROGRESS.md`'s acceptance criteria for the real-VM/TLS/DNS parts are left `[ ]` open
  rather than checked off unearned. Caddy chosen over nginx (automatic HTTPS, fewer moving parts
  to document/maintain) after the user asked to reconsider FastAPI-self-hosted-routing and nginx
  as alternatives — FastAPI/uvicorn can terminate TLS itself but doesn't solve routing to n8n
  (a separate process this repo doesn't control) and loses automatic cert renewal either way.
  Two subdomains (not path-based routing on one domain) for n8n vs. rag-api, since n8n's UI/API
  path space is broad and version-dependent — a future n8n upgrade adding new top-level routes
  could silently collide with a path-based rule. `rclone` (not gsutil/aws-cli) for backups, since
  the cloud choice itself is deferred — doesn't hard-couple the script to one provider
- Verified live rather than assumed: `docker compose config` (default) excludes `caddy`;
  `docker compose --profile prod config` includes it — profile gating works as designed and local
  dev is genuinely unaffected. The dump→gzip→restore cycle actually run against a scratch
  `opspilot_restore_test` database — restored row counts matched the source exactly
  (`kb_documents=10 kb_chunks=15`); the `rclone` upload step itself is documented but not
  exercised (no cloud remote configured, consistent with deferring real cloud infra)
- Mid-phase revisit of Phase 5's still-open accuracy gap (user asked to try `glm-5.2:cloud` for
  Ollama and fold any fixes into this work): `glm-5.2:cloud` requires a paid ollama.com
  subscription (a plain 403, not a missing-model error) — inaccessible with the current account.
  Substituted `minimax-m3:cloud` (also Ollama-cloud-routed, confirmed free-tier accessible) and
  reran the full classify eval: **0.750, worse than the already-tested local 12B model's 0.833**
  — concrete evidence that "cloud-routed" and "presumably bigger" don't automatically mean more
  accurate for this specific structured-classification task (gotcha #38 updated with this data
  point; gotcha #40 documents the `:cloud` accessibility discovery). `.env`'s `OLLAMA_MODEL`
  reverted to the 12B model as the best-tested option
- Bug found and fixed during that revisit: `minimax-m3:cloud` wrapped its valid JSON answer in
  markdown code fences despite `response_format: {type: json_schema, strict: true}` — "strict"
  mode is evidently not equally strict across every provider. The original
  `json.loads(text)` would raise an unhandled `JSONDecodeError` instead of the intended clean
  retry/422 path. Fixed with a shared `_parse_json()` helper (strips a leading/trailing fence,
  returns `None` rather than raising on anything unparseable) applied at all three
  structured-output call sites — Anthropic, the OpenAI-compatible path shared by OpenAI/Ollama,
  and Gemini, since any of them could in principle do this (gotcha #39)
- Also fixed a real gap from Phase 5 while touching `docker-compose.yml`: `rag-api`'s environment
  block never passed through `GEMINI_API_KEY`/`OLLAMA_*` — the containerized service literally
  couldn't have used those providers despite `llm.py` supporting them since Phase 5
- Gotchas added: #39 (a provider can wrap JSON in markdown fences even under `strict: true` —
  parse defensively), #40 (Ollama's `:cloud` models proxy to ollama.com, some need a paid
  subscription, check each one rather than assuming); #38 updated with the `minimax-m3:cloud`
  data point
- Handoff / next: when a real VM is provisioned, rehearse `docs/infrastructure.md` literally end
  to end and fix whatever doesn't work as written (it's reviewed, not tested) — that's the
  remaining work for P6-1/P6-4's real-VM acceptance criteria. P5-2's accuracy gap is unchanged in
  substance (still needs a real paid-tier or Anthropic/OpenAI-key provider to actually clear
  0.85) but now has a more complete comparison across four models

## [2026-07-06 14:00] build | Claude Code | Ollama cloud API-key auth + docstring/PEP-8 audit (OpenSpec: add-ollama-cloud-auth, add-docstrings-pep8-audit)
- P5-2 revisit via OpenSpec change `add-ollama-cloud-auth` (archived): added optional
  `OLLAMA_API_KEY` setting so the `ollama` provider can authenticate directly against
  `https://ollama.com/v1` instead of only the local daemon. Motivated by a live-confirmed
  distinction — the local daemon's proxying of `:cloud` models needs a separate paid ollama.com
  subscription plan (403 even after `ollama signin` confirmed the right account and a full
  `ollama serve` restart), while a personal API key works immediately against the direct cloud
  endpoint (pay-per-token, a different product). Tested against `kimi-k2.7-code:cloud`: auth path
  confirmed working, but accuracy came back 0.750–0.792 across two runs — still below the local
  12B model's 0.833, so P5-2's 0.85 target remains open. Also found: `llm.py`'s cost logging has
  no pricing entry for `ollama`, so this real billed cloud usage logged as $0.0000 — the `$2`
  dev-budget invariant can't currently see spend on this path (gotcha #41)
- Separate OpenSpec change `add-docstrings-pep8-audit` (archived): an AST scan found 23
  functions/classes + 2 modules missing docstrings in `services/rag/app/`, plus 9 more in
  `evals/`/`scripts/` — `ruff check`/`ruff format --check` passed cleanly throughout because the
  configured rule set never checked for docstrings. Closed all of them (one-line docstrings for
  simple functions/Pydantic models, matching the codebase's existing concise style — no rewriting
  of already-good multi-paragraph docstrings). Added `D100-D104` (docstring-presence only, not
  the full stylistic `D` family) to `pyproject.toml`'s ruff `select`, with `services/rag/tests/**`
  and `evals/test_*.py` exempted via `per-file-ignores` since test names are already the
  documentation. `ruff check .`/`ruff format --check .` both clean, `make test` 18/18 green
- Files touched: `services/rag/app/{__init__,settings,llm,main,schemas}.py`,
  `evals/{conftest,test_classify,test_grounding}.py`, `scripts/{ingest,n8n_sync}.py`,
  `pyproject.toml`, `.env.example`, `openspec/specs/llm-provider-layer/spec.md` (new),
  `openspec/specs/code-documentation-standards/spec.md` (new), `PROGRESS.md`, `wiki/gotchas.md`,
  `wiki/map.md`
- Handoff / next: P5-2 still needs a real Anthropic/OpenAI key (already budgeted in
  `docs/SPEC.md` §4) to actually reach 0.85 — every free/cheap-cloud route tried so far
  (Gemini quota, `minimax-m3:cloud`, `glm-5.2:cloud`, `kimi-k2.7-code:cloud`) has come up short
  or blocked

## [2026-07-06 15:30] build | Claude Code | Live n8n workflow export (OpenSpec: export-live-n8n-workflows)
- User-requested: a `workflows-n8n/` folder with the 5 OpsPilot workflows exported fresh from the
  live n8n instance, redacted, and genuinely ready to import — motivated by `n8n/workflows/*.json`
  deliberately containing `PLACEHOLDER_*` tokens that never get the real live-patched values
  (gotcha #20), so those committed files alone wouldn't import cleanly on a fresh instance.
- Scoped to just the 5 OpsPilot workflows out of 13 total on the shared instance (gotcha #1 — this
  project reuses an existing local n8n install); the other 8 are unrelated personal automations
  and were explicitly excluded per user decision.
- New `scripts/export_n8n_workflows.py`: fetches each of the 5 by name (n8n's `/workflows` list
  endpoint already returns full `nodes`/`connections`/`settings`, no extra per-ID call needed),
  reduces to the same `{name, nodes, connections, settings}` shape as `n8n/workflows/*.json`
  (reusing `n8n_sync.py`'s `IMPORT_FIELDS`), then redacts by diffing against the committed file:
  nodes matched by `name` (not list index, so an added/removed live node doesn't break redaction
  for the rest), any committed value *containing* a `PLACEHOLDER_*`/`*_PLACEHOLDER` substring
  wins over the live value at that path, credential `.id` and `webhookId` are always stripped
  (instance-specific, non-portable). Ends with a structural diff against the committed file,
  printed but non-fatal, so any real drift is visible rather than silently swallowed or silently
  committed.
- **Real bug caught during this session, before anything was committed**: the first version's
  placeholder check required an exact whole-string match, which missed WF-5's Notion URL
  (`.../blocks/PLACEHOLDER_NOTION_PAGE_ID/children` — the token is embedded in a larger string,
  not the whole value) and leaked the real Notion page ID into the first export attempt. Caught by
  the manual secret-grep verification step (not the diff step, which doesn't know what's a
  secret) before the file was ever committed; fixed by switching to a substring search and letting
  the *whole* committed string win at that leaf, then re-ran clean (zero real-secret matches,
  placeholder counts matching `n8n/workflows/` exactly: 4/1/3/1/2 per file)
- Real (benign) drift found by the diff step: WF-1's live `settings.binaryMode: "separate"` isn't
  present in the committed file — an n8n default/setting added sometime after WF-1 was last
  committed, not a secret, not otherwise acted on this session
- Files touched: `scripts/export_n8n_workflows.py` (new), `workflows-n8n/*.json` (new, 5 files),
  `wiki/map.md`
- Handoff / next: this is a manual, on-demand snapshot tool — not wired into CI/`make`, so
  `workflows-n8n/` will go stale if `n8n/workflows/` or the live instance changes and this script
  isn't re-run. No automation currently keeps it fresh by design (see design.md non-goals).

## [2026-07-08 10:20] build | Claude Code | llm.py split into app/llm/ package (OpenSpec: split-llm-provider-package)
- Completed: `services/rag/app/llm.py` (627 lines, top god node in the knowledge graph) replaced by
  the `app/llm/` package — `base.py` (LLMResult/Purpose/BudgetExceeded/Provider protocol/EMBED_DIM
  + shared dim-check), `pricing.py`, `prompts.py`, `ledger.py` (`Ledger` interface + asyncpg
  `PgLedger` — the package's only DB touchpoint), `providers/{anthropic,openai,gemini,ollama,fake}.py`
  (+ `_openai_compat.py` shared parser), `registry.py` (explicit PROVIDERS dict replaces both
  `if provider ==` dispatch chains), `__init__.py` façade re-exporting the public four.
- No behavior change: ADR-001 anthropic→openai fallback ordering (log failed attempt → re-raise if
  non-retryable → fall back) moved verbatim; budget check still precedes every non-fake call; fake
  short-circuit still skips the budget check; `main.py` untouched (façade imports only).
- Edge-case tightening (only intentional deviation): unknown `LLM_PROVIDER` + embed purpose now
  raises the same `ValueError` as chat did, instead of silently using the OpenAI embed path.
- Tests: patch targets moved to `app.llm.providers.<name>._call_*` (assertions unchanged); new
  `test_provider_no_db.py` proves a provider runs against a stub Ledger with Postgres unreachable
  (conftest's autouse DB fixtures overridden locally). 19/19 green; ruff format+check clean.
- Live spot-check: `LLM_PROVIDER=ollama` `/classify` roundtrip against the local daemon (12B gemma
  model) returned valid structured output and wrote the expected `llm_calls` row (cost $0, unlisted
  local model — same as before).
- Files touched: `services/rag/app/llm/**` (new, 12 files), `services/rag/app/llm.py` (deleted),
  `services/rag/tests/{test_llm_fallback,test_budget_guardrail}.py` (patch paths),
  `services/rag/tests/test_provider_no_db.py` (new), `wiki/map.md`, `PROGRESS.md`.
- Handoff / next: the `Ledger` seam is the intended hook for a future `ticket_events`/event-emission
  change; archive the OpenSpec change once reviewed (`/opsx:archive`).

## [2026-07-08 11:15] build | Claude Code | Append-only ticket_events audit log (OpenSpec: add-ticket-events-log)
- Completed: `db/init/02_ticket_events.sql` — `ticket_events` table (id, seq identity, ticket_id
  FK, type, payload jsonb, created_at) + `(ticket_id, created_at, seq)` index, populated by AFTER
  triggers on `tickets` (ticket.created / ticket.classified / ticket.status_changed `{from,to}` /
  ticket.sla_reminded) and `messages` (message.added with role + message id). Trigger-based so
  BOTH writers (n8n's ~10 raw-SQL postgres nodes and the rag-api) are captured with zero workflow
  JSON changes. Append-only enforced by a raising BEFORE UPDATE/DELETE trigger (REVOKE wouldn't
  bind — both writers connect as the table owner); TRUNCATE deliberately allowed for tests.
- Schema freeze amended, not broken (ADR-006): `01_schema.sql` byte-for-byte unchanged; policy is
  now "existing tables frozen; additive-only via numbered `db/init/NN_*.sql` + one ADR each".
  Applied to the dev DB via `docker exec -i ... psql < db/init/02_ticket_events.sql`, run twice to
  prove idempotency (IF NOT EXISTS / OR REPLACE / DROP TRIGGER IF EXISTS throughout).
- New endpoint `GET /tickets/{ticket_id}/events` (ordered `(created_at, seq)`, 404 unknown, 422
  malformed UUID); `TicketEvent`/`TicketEventsResponse` models in schemas.py. asyncpg returns
  jsonb as text — parsed with json.loads at the endpoint.
- `seq` exists because same-transaction events share `created_at` (now() is transaction time) —
  confirmed live in the smoke test: classified + status_changed landed with identical timestamps
  and only seq ordered them.
- Tests: conftest now applies ALL `db/init/*.sql` in lexical order (was hardcoded 01_schema.sql —
  the test DB would otherwise silently diverge from fresh-volume schemas) and truncates
  ticket_events; `evals/conftest.py` needed NO change (tasks.md 2.2's premise was wrong — it
  applies no schema, it runs against the real dev DB). New `test_ticket_events.py`: 9 L2 tests
  (5 capture types, append-only UPDATE+DELETE rejection, ordered endpoint response, 404, 422).
  28/28 green, ruff clean.
- Live smoke: psql-inserted ticket (n8n's write path) + triage/status updates produced 3 events;
  endpoint returned them in order against the dev DB. Note: smoke ticket `smoke-events-1` stays in
  the dev DB — its events can't be deleted (append-only + FK), which is the feature working.
- Files touched: `db/init/02_ticket_events.sql` (new), `services/rag/app/{main,schemas}.py`,
  `services/rag/tests/{conftest.py,test_ticket_events.py}`,
  `docs/decisions/ADR-006-additive-schema-changes.md` (new), `wiki/map.md` (invariant #2 reworded,
  new component row, ADR list), `PROGRESS.md`.
- Handoff / next: intent-level events (draft.approved vs edited) and any pg_notify/queue consumers
  are explicitly deferred to the service-owns-ticket-writes change; `type` is TEXT so those arrive
  without DDL. Deployed instances need the one-off psql apply (same command as above).

## [2026-07-08 12:15] build | Claude Code | Structured logging + meaningful messages (OpenSpec: add-structured-logging)
- Completed: `app/logging_setup.py` (stdlib-only; `setup_logging()` configures the `app` logger
  namespace — stderr handler, single-line format, propagate=False so uvicorn/root can't
  double-print; `kv()` helper renders key=value suffixes, None keys omitted). `LOG_LEVEL` setting
  (+ `.env.example`, compose `${LOG_LEVEL:-INFO}`), wired in the lifespan startup.
- Per-LLM-attempt INFO line lives in `PgLedger.record()` — the one spot that sees every attempt
  for every provider (incl. failed pre-fallback anthropic ones); zero provider-module edits for
  it. WARNING (exception class named) in `providers/anthropic.py` when a retryable error triggers
  the ADR-001 fallback. Live-verified with ollama: the line carries purpose/provider/model/
  tokens/cost/latency/success/ticket_id.
- Meaningful messages: classify 422 detail now names missing fields + provider + model + attempt
  count (WARNING logged too); `_parse_score` logs the raw self-check text before scoring 0.0;
  `check_db` returns `(ok, error_class)` and logs the traceback — `/health` body gains `error`
  when down; BudgetExceeded says it resets at midnight UTC; unknown `LLM_PROVIDER` lists valid
  options derived from `sorted(registry.PROVIDERS)` (can't drift); `n8n_sync.py` prints
  `<name>: imported, activated` per workflow, raw response only on failure.
- One deliberate behavior change: `/query` with zero retrieved chunks no longer drafts from an
  empty context — short-circuits before the answer/self_check LLM calls (they could only
  hallucinate, and cost two calls), returns sentinel answer + sources=[] + confidence 0.0. The
  WF-2 gate (0.0 < 0.70 → needs_human) routes it to a human unchanged. Live-verified against the
  empty test DB.
- Tests: new `test_observability.py` (5 tests: empty-KB short-circuit incl. llm_calls purposes
  check, classify 422 detail, health error class, per-attempt INFO record, unknown-provider
  message). `test_health.py` stubs updated for the `(ok, error)` tuple (the only pre-existing
  test this change touches). 33/33 green, ruff clean.
- Gotcha found while testing: pytest's caplog attaches at the ROOT logger, so a propagate=False
  logger is invisible to it — and attaching caplog.handler to the `app` logger directly captures
  records TWICE if setup_logging() hasn't run yet in that process (once via the logger handler,
  once via propagation, since propagate is still True pre-setup). Fix: the test fixture calls the
  idempotent setup_logging() first, then attaches caplog.handler. Also: em dashes in log messages
  render as `�` in Windows consoles — log messages stick to ASCII punctuation.
- Files touched: `services/rag/app/{logging_setup.py(new),main.py,db.py,settings.py}`,
  `app/llm/{__init__.py,ledger.py,providers/anthropic.py}`, `scripts/n8n_sync.py`,
  `services/rag/tests/{test_observability.py(new),test_health.py}`, `.env.example`,
  `docker-compose.yml`, `wiki/map.md`, `PROGRESS.md`.
- Handoff / next: request-ID middleware and log shipping deferred until >1 service or >1 log
  consumer. Remaining review items: service-owned ticket writes (intent-level events), job queue
  for the long /query path.

## [2026-07-08 13:00] build | Claude Code | Archived try-gemma4-31b-cloud + spec sync (PR #11)
- Completed: OpenSpec change `try-gemma4-31b-cloud` closed out — delta spec synced into
  `openspec/specs/llm-provider-layer/spec.md` (new requirement: the `OLLAMA_MODEL` default SHALL
  be justified by a recorded eval comparison, 3 scenarios covering record/beat/lose outcomes),
  change moved to `openspec/changes/archive/2026-07-08-try-gemma4-31b-cloud/`. Squash-merged as
  PR #11.
- Files touched: `openspec/specs/llm-provider-layer/spec.md`, `openspec/changes/**` (move),
  `PROGRESS.md` (Maintenance entry + P5-2 blocker cross-ref).
- Decisions: none new — the eval result itself (0.792, default unchanged) was recorded 2026-07-07.
- Gotchas added: none.
- Branch cleanup: all 6 stale local+remote branches from PRs #5–#10 deleted (verified merged via
  `gh pr list` first — squash merges defeat `git branch --merged`); only `master` remains.
- Handoff / next: no active OpenSpec changes. Open items unchanged: P4-4 (live 09:00 Kyiv cron),
  P5-2 (needs a real Anthropic/OpenAI key), Phase 6 real-VM rehearsal.

## [2026-07-08 16:15] build | Claude Code | RabbitMQ async messaging (add-rabbitmq-messaging)
- Completed / Partial: OpenSpec change `add-rabbitmq-messaging` implemented and validated;
  ADR-007 written. WF-1/WF-2 intake buffering, WF-2/WF-3→WF-6 outbound delivery with retry/DLQ,
  and pg_notify→WF-7→`opspilot.events` ticket fan-out all wired in JSON. Still open: live E2E
  verification of the new workflows (no access to the user's n8n editor/credentials), lint/test
  run, PR/merge/archive.
- Files touched: `docker-compose.yml`, `.env.example`, `Makefile`, `scripts/rabbitmq_topology.py`,
  `db/init/03_event_notify.sql`, `n8n/workflows/{wf1_intake_triage,wf2_draft_answer,wf3_hitl,
  wf6_delivery,wf7_event_publisher}.json`, `scripts/{n8n_sync.py,export_n8n_workflows.py}`,
  `docs/decisions/ADR-007-rabbitmq-async-messaging.md`, `openspec/changes/add-rabbitmq-messaging/`,
  `PROGRESS.md`, `wiki/map.md`.
- Decisions: ADR-007 (RabbitMQ, n8n-native consumers, consumer-managed retry counter because n8n's
  RabbitMQ trigger nacks with `requeue=true`, pg_notify for fan-out with `ticket_events` as source
  of truth). User-approved deviation from frozen `docs/SPEC.md` v1.0: WF-1→WF-2 no longer direct
  `Execute Workflow`; customer sends no longer inline.
- Gotchas added: none yet — record discovered traps after live E2E (e.g. n8n RabbitMQ trigger ack
  mode, host-port reachability from an external n8n instance).
- Handoff / next: run `make lint && make test`; do live E2E against local n8n (create `RabbitMQ -
  OpsPilot` credential, sync all 7 workflows, test webform→draft queue→WF-2, delivery retry/DLQ,
  event topic publishes); then PR, squash-merge, archive change, sync specs.

## [2026-07-09 15:00] build | Claude Code | RabbitMQ messaging live E2E + close-out (add-rabbitmq-messaging)
- Completed: reverted an unauthorized-direction detour found uncommitted in the tree (a Python
  worker service under `services/worker/` duplicating WF-2's logic — contradicted ADR-007's
  "n8n-native consumers, no new worker tier" decision and never ran; user confirmed n8n-native).
  Deleted the worker, its compose service, `aio-pika`/`python-telegram-bot` deps, stray
  `wiki/*.new*.md` files, and `scripts/patch_rabbitmq_workflows.py`.
- Fixed two real execution-time bugs no structural validation caught (gotchas #47/#48): RabbitMQ
  publish nodes needed `typeVersion: 1.1` (not 1.2) + explicit `"operation": "sendMessage"`;
  live-workflow PUTs must filter `settings` to the API's allowed keys. WF-1's committed publish
  node also converted from a management-HTTP-API workaround back to the native `rabbitmq` node.
- Live E2E all green: webform intake → `q.draft_answer` → WF-2 fires (ticket classified, gate →
  needs_human, WF-3 posts to ops); delivery retry/DLQ proven with a bogus chat_id (5 retries at
  ~30s spacing observed on `q.outbound_delivery.retry`, then exactly ONE parked DLQ message with
  `attempts: 5` + ops alert); event fan-out proven via a probe queue bound `#` to
  `opspilot.events` (ticket.created / ticket.classified / ticket.status_changed ×2 /
  message.added, all keyed by event type). `scripts/n8n_sync.py` imports all 7; export
  round-trips clean (only live position/binaryMode noise).
- Ops-chat-id live re-patch applied post-sync to WF-1/3/4/6 (now 7 spots — gotcha #49).
- Files touched: `n8n/workflows/*.json` (7), `scripts/{n8n_sync,export_n8n_workflows}.py`,
  `db/init/03_event_notify.sql`, `docker-compose.yml`, `Makefile`, `.env.example`,
  `scripts/rabbitmq_topology.py`, ADR-007, `openspec/changes/add-rabbitmq-messaging/`,
  `workflows-n8n/*` (re-export), `PROGRESS.md`, `wiki/{map,gotchas}.md`, `README.md`.
- Tests: `ruff` clean, 33/33 pytest green. `openspec validate add-rabbitmq-messaging` passes.
- Handoff / next: PR + squash-merge, archive change, sync `async-messaging` +
  `n8n-workflow-export` delta specs into `openspec/specs/`.
