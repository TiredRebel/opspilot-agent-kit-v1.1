# Gotchas (numbered, append-only)

1. **n8n port collision — RESOLVED at P0-1.** An n8n container already runs on this machine
   (`n8n-n8n-1`, default 5678). Decision: **reuse it** — this project's `docker-compose.yml` does
   NOT run n8n at all; `.env.example` points `N8N_API_URL=http://localhost:5678` at the existing
   instance. Its sidecar `n8n-postgres-1` is not published to the host, so it never collides with
   this project's own Postgres on 5432. Never run two n8n instances on one port.
2. **Telegram Trigger needs a public webhook URL — CONFIRMED at P2-2.** This n8n instance has no
   `N8N_HOST`/`N8N_EDITOR_BASE_URL`/`WEBHOOK_URL` configured (never needed one before — its only
   prior Telegram workflow used a Schedule Trigger + plain send, not an incoming trigger). Telegram's
   `setWebhook` call fails on activation with a vague "Bad Request" and **blocks the whole
   workflow** from activating, not just that node. Workaround until a tunnel/domain exists: set
   `"disabled": true` on the Telegram Trigger node in `wf1_intake_triage.json` — the Webhook Trigger
   path activates and runs fine independently. Re-enable in the n8n UI once a real public URL exists
   (cloudflared tunnel locally, or the real domain on the VM at P6). Do not try long-polling hacks.
3. **WSL2 networking.** Docker services bind inside WSL2; localhost forwarding usually works from
   Windows, but tunnels and n8n WEBHOOK_URL must reference the externally reachable URL, not localhost.
4. **pgvector image.** Use `pgvector/pgvector:pg16`. HNSW indexes require pgvector ≥ 0.5 — verify with
   `SELECT extversion FROM pg_extension WHERE extname='vector';`.
5. **Embedding dimensions are load-bearing.** `text-embedding-3-small` = 1536 dims = `vector(1536)` in
   the schema. Changing the embedding model requires a schema change + ADR — don't.
6. **n8n public API.** Import/activate workflows via REST: enable the API, create an API key in the n8n
   UI (Settings → API), store as N8N_API_KEY. Workflow JSON `credentials` blocks must be re-linked by
   the human in the UI once — exported JSON must NOT contain credential secrets.
7. **Windows line endings.** Enforce LF via .gitattributes at P0-3; CRLF in shell scripts breaks
   containers silently.
8. **Port 8000 is often taken on this machine** (an unrelated Windows service binds it — not a
   Docker container). `rag-api`'s compose mapping failed with "port not available" until
   `RAG_API_PORT` was moved to **8010** in both `.env` and `.env.example`. Check `netstat -ano | grep :<port>`
   before assuming a default port is free.
9. **`make` is not installed in the Windows Git-Bash toolchain Claude Code runs in.** Verify P0/P1
   deliverables by running the underlying commands directly (`uv run ruff ...`, `uv run pytest ...`,
   `docker compose ...`) instead of `make <target>` during agent sessions on this machine. The
   Makefile itself is still correct and will work on Linux/the deploy VM/CI.
10. **`kb/seed/` is not in the rag-api Docker image — it's a bind mount.** The Dockerfile only
    `COPY`s `services/rag/app` and `services/rag/prompts`; `docker-compose.yml` mounts
    `./kb:/app/kb:ro` on the `rag-api` service and sets `KB_SEED_DIR=/app/kb/seed` there.
    `settings.kb_seed_dir` defaults to the relative `kb/seed` (works for `uv run` from the repo root
    and for L2 pytest fixtures) — that default only resolves correctly in Docker because compose
    overrides it. Also: `scripts/ingest.py` does **not** touch the DB directly — it just POSTs to the
    running `rag-api`'s `/kb/ingest`, because `DATABASE_URL` in `.env` uses the container-internal
    hostname `postgres`, which doesn't resolve from a host-run script.
11. **Local pytest runs outside Docker, so `DATABASE_URL`'s `postgres` hostname doesn't resolve.**
    `services/rag/tests/conftest.py` rewrites `settings.database_url` to `localhost:$POSTGRES_PORT`
    for the whole test session. Don't "fix" this by changing `.env`'s `DATABASE_URL` — that value is
    correct for the compose network; the test override is intentionally test-only.
12. **`app.db`'s pool is a module-level singleton bound to whichever event loop creates it —
    mixing pytest's own loop with `TestClient`'s dedicated worker-thread loop corrupts it**
    (`RuntimeError: Event loop is closed` / `another operation is in progress`). Test fixtures must
    (a) use their own standalone `asyncpg.connect()` for setup/assertions — never `db.get_pool()` —
    and (b) reset `db._pool = None` before/after every test so the app always recreates its pool
    fresh, bound to whatever loop that specific test happens to run on. See
    `services/rag/tests/conftest.py`'s `_reset_app_pool` / `pool` fixtures.
13. **`llm_calls.ticket_id` is a `UUID` column.** A `ClassifyRequest`/`QueryRequest.ticket_id` typed as
    plain `str` lets a non-UUID value reach asyncpg and crash with an unhandled 500
    (`asyncpg.exceptions.DataError`) instead of a clean 422. Both fields are typed `uuid.UUID` in
    `app/schemas.py` so pydantic rejects bad input at the API boundary.
14. **n8n's container is on a separate Docker network from this project's compose stack** (gotcha
    #1 — it's reused, not part of our compose). HTTP Request nodes calling the RAG service must use
    `http://host.docker.internal:8010/...` — `localhost` from inside the n8n container resolves to
    the n8n container itself, and a compose-network hostname like `rag-api` doesn't exist on n8n's
    network at all. Verified working: `docker exec n8n-n8n-1 curl http://host.docker.internal:8010/health`.
    Same reasoning applies to the Postgres credential's `host` field in the n8n UI/API
    (`host.docker.internal`, not `postgres` or `localhost`).
15. **n8n's `$env` does NOT expose this project's `.env`.** This n8n instance is a separate,
    pre-existing container with its own environment — `{{$env.CONFIDENCE_THRESHOLD}}` or
    `{{$env.TELEGRAM_OPS_CHAT_ID}}` silently evaluate to empty rather than erroring. All config
    values referenced in hand-authored workflow JSON must be literals. This creates a real tension
    with "never commit secrets/real chat IDs" (below).
16. **n8n activation validation is stricter than creation.** `POST /workflows` happily creates a
    workflow with unresolved placeholder credentials (`{"id": null, "name": "..."}`) — but
    `POST /workflows/{id}/activate` hard-rejects with a 400 listing every node with an unresolved
    credential, or an "out of date"/misconfigured trigger node. You cannot activate until every
    credential name in the JSON has a real, matching credential (by exact name + type) already on
    the instance. `scripts/n8n_sync.py` surfaces this as a non-fatal per-workflow `active: false` +
    `detail` message rather than crashing, so partial progress (created-but-inactive) is still visible.
17. **Real chat IDs can't be committed, but n8n can't read `.env` either (see #15) — resolution
    pattern.** For config that's genuinely secret-shaped (a real Telegram chat ID) but must be a
    literal because `$env` doesn't work: commit an obvious placeholder string (e.g.
    `"PLACEHOLDER_OPS_CHAT_ID"`) and have a human replace it once in the n8n editor after import —
    the same one-time-relink pattern already used for credentials. Track these in `PROGRESS.md`
    Blockers so they don't get lost.
18. **`n8n-nodes-base.executeWorkflowTrigger`'s "accept all data" mode is `parameters: {"inputSource":
    "passthrough"}`** — not an empty `{}`, and not a `workflowInputs` object (that shape is for the
    *calling* Execute Workflow node's resourceMapper, a different parameter on a different node).
    Confirmed by reading the node source directly (`ExecuteWorkflowTrigger.node.ts` +
    `utils/workflowInputsResourceMapping/constants.ts`) after empirically testing wrong guesses
    against the live instance and hitting "Missing or invalid required parameters: workflowInputs" /
    "Could not find property option".
19. **n8n's `POST /api/v1/credentials` for a Postgres credential needs `"sshTunnel": false` in
    `data`, but NOT the other `ssh*` fields** (`sshHost`, `sshUser`, etc.) — including them alongside
    `sshTunnel: false` fails validation ("is of prohibited type [object Object]"); omitting
    `sshTunnel` entirely fails validation too ("requires property sshAuthenticateWith" etc). Minimal
    working `data`: `{host, database, user, password, port, ssl, allowUnauthorizedCerts,
    maxConnections, sshTunnel: false}`.
20. **A placeholder-then-human-relink value (gotcha #17) only stays fixed until the next
    `make n8n-sync` of that workflow.** `scripts/n8n_sync.py` does a full `PUT` on every re-sync,
    which overwrites *all* node parameters from the committed JSON — including reverting any
    literal a human has since patched live in the n8n editor (e.g. WF-1's ops-alert `chatId`, fixed
    2026-07-05) back to its committed placeholder. There's no reconciliation between "live value a
    human intentionally changed" and "committed placeholder" — deliberately not built, to avoid
    committing the real value just to make the sync idempotent. Whoever re-syncs a workflow with a
    known placeholder must re-apply the same one-time UI edit afterward; check `PROGRESS.md`
    Blockers for the current list before assuming a re-sync is side-effect-free.
21. **Recreating the pre-existing `n8n` container is risky — it's not this project's compose, and
    has at least two latent bugs of its own** (`/home/mcgun/n8n/docker-compose.yml`, a separate
    project). (a) It runs as `user: "0:0"` (root) but mounts its persistent volume at
    `/home/node/.n8n` — root looks for config/encryption-key state at `/root/.n8n` instead, so
    **any container recreation silently generates a new encryption key**, breaking decryption of
    every existing credential (no warning, no error — just quietly-broken credentials afterward).
    (b) Its `.env` file's `POSTGRES_NON_ROOT_PASSWORD` can be shadowed by a **stale value already
    exported somewhere in the WSL environment** (docker-compose precedence: shell env > `.env`
    file) — editing `.env` and even `--force-recreate`-ing the container silently keeps using the
    old password. Before recreating this container for any reason (new env var, restart, etc.),
    warn the user explicitly that credentials will need re-creation, and if DB auth fails
    post-recreate despite a correct `.env`, suspect environment-variable shadowing before assuming
    the password itself is wrong — check with `[ -n "${VAR+x}" ]`, don't just re-edit `.env` again.
22. **n8n's Schedule Trigger cron format has 6 fields, not the standard Unix 5** —
    `[Second] [Minute] [Hour] [Day of Month] [Month] [Day of Week]` (confirmed from
    `ScheduleTrigger.node.ts`). "Every 15 minutes" (`*/15 * * * *` in standard cron) is
    `"0 */15 * * * *"` here — a leading seconds field of `0`, not `*/15 * * * *` copy-pasted as-is
    (which n8n would parse with an off-by-one field shift). Shape: `{"rule": {"interval": [{"field":
    "cronExpression", "expression": "0 */15 * * * *"}]}}`.
23. **A single Telegram bot can have only one registered webhook URL — this constrains n8n workflow
    design, not just deployment.** Two separate Telegram Trigger nodes in two different workflows
    for the *same bot credential* will silently fight over the webhook registration on activation
    (last one activated wins, with no error surfaced anywhere). See ADR-005 — the fix is one
    Telegram Trigger total, with in-workflow routing (IF chain on `callback_query` presence /
    `reply_to_message` + chat-id) fanning out to sub-workflows via Execute Workflow, rather than
    giving each conceptual flow (intake vs. HITL callbacks) its own trigger.
24. **When hand-authoring n8n IF/Switch filter conditions for "does this field exist," don't reach
    for `{"type": "object", "operation": "notEmpty"}` without confirming that combination is valid
    for this n8n version.** An invalid operator/type pair doesn't fail at import or activation (it's
    stored as opaque JSON) — it silently misbehaves at actual execution time, which is a much worse
    failure mode to debug than an upfront rejection. The safer, more standard idiom: coerce to a
    boolean in the expression itself and check that
    (`leftValue: "={{ !!$json.someField }}"`, `operator: {"type": "boolean", "operation": "true"}`).
25. **A literal newline byte inside a quoted JS string in an n8n expression is invalid JavaScript —
    and this only surfaces at execution time, never at import/activation.** Writing
    `"text": "={{ 'foo' + '\n\n' + 'bar' }}"` in the committed JSON (where `\n` is JSON's own escape,
    producing a real newline character once parsed) embeds a raw line break inside a single-quoted
    JS string literal, which is a syntax error the moment the expression actually runs
    ("invalid syntax", surfaced deep in a Telegram/Code node's stack trace, not at the workflow
    JSON level). Fix: double-escape in the JSON source (`\\n`) so the parsed JS source text still
    contains the two literal characters `\` and `n`, which JS then correctly interprets as an
    escaped newline inside the string.
26. **Telegram's default Markdown parse mode silently strips unmatched `[...]` as incomplete link
    syntax.** A message text built as `'...' + '[ticket:' + id + ']'` renders with the brackets
    (and sometimes surrounding text) removed, because Telegram's legacy Markdown parser interprets
    `[text]` as the start of a `[text](url)` link and drops the bracket characters when no `(url)`
    follows. This silently breaks anything downstream that regex-parses the message text back out
    (e.g. an edit-reply ticket-id extractor) — the workflow won't error, it'll just never match.
    Avoid embedding structured markers in Markdown-parsed Telegram text with square brackets; use a
    bracket-free plain-text marker instead (e.g. `TICKET-ID:<uuid>` + a matching
    `/TICKET-ID:([0-9a-fA-F-]+)/` regex), which is immune to parse-mode reinterpretation regardless
    of what `parse_mode` ends up being.
27. **n8n's IF node with `typeValidation: "strict"` and operator `type: "string"` does NOT
    auto-coerce a number value — it throws a hard runtime error instead of silently failing or
    coercing.** Comparing Telegram's `$json.message.chat.id` (always a JSON number) against a
    string literal rightValue under strict validation fails with
    `Wrong type: '-123456' is a number but was expecting a string [condition 0, item 0]`. This is a
    different, more severe failure mode than gotcha #24 (which is about a *type/operation pair*
    being invalid) — here the pairing is valid, but the *value's runtime type* doesn't match what
    strict mode expects. Fix: coerce explicitly in the expression, e.g.
    `leftValue: "={{ String($json.message.chat.id) }}"`, rather than relying on implicit coercion.
28. **Telegram bots have Group Privacy Mode ON by default, which silently blocks n8n's Telegram
    Trigger from ever receiving ordinary group messages or replies — only commands (`/foo`) and
    `callback_query` updates (inline keyboard button presses) get through.** This is *not* a
    webhook-registration problem — `getWebhookInfo` will correctly show `"message"` in
    `allowed_updates`, and `pending_update_count` stays at 0 (Telegram isn't even attempting
    delivery, so there's nothing queued or retried). The telltale symptom: button clicks reliably
    produce n8n executions, but plain text messages and replies produce *zero* executions at all,
    with no error anywhere. Any workflow design relying on capturing free-text operator replies in
    a group (e.g. an edit-reply-capture flow) requires Privacy Mode disabled via BotFather:
    `/mybots` → select the bot → **Bot Settings** → **Group Privacy** → **Turn off**. This is a
    one-time human action outside any repo/API — record it as done, since it isn't discoverable
    from the workflow JSON itself.
29. **A running container's baked-in env var can silently diverge from what's in `.env` on disk,
    even without any recreation — checking only the *length* of a value is not enough to catch
    this.** During an extended n8n Postgres-auth crash-loop debugging session, the container's
    `DB_POSTGRESDB_PASSWORD` matched the expected value's length (10 chars) by coincidence, which
    briefly looked like proof the value matched. It didn't — a `sha256sum` comparison of the
    container's actual env value against the expected literal (never printing either value)
    revealed a real mismatch. When diagnosing "the same credential works manually but not from
    inside the container," compare the actual byte-for-byte value (via a hash, to avoid printing
    secrets), not just its length.
30. **Reactivating a Telegram-Trigger workflow repeatedly in quick succession hits Telegram's own
    rate limit on `setWebhook`-adjacent calls** — n8n's `/workflows/{id}/activate` starts failing
    with `"The service is receiving too many requests from you"` (a plain 400, easy to mistake for
    a real config problem). This is expected after several `make n8n-sync` + live-patch cycles done
    back-to-back (each PUT+activate re-registers the webhook). Just wait ~10–30s and retry; no
    config change needed.
31. **`services/rag/tests/conftest.py`'s `_clean_tables` fixture truncates every app table before
    and after each test — and until this session, that ran against the same live dev database the
    running `rag-api`/n8n actually use, not an isolated test database.** The old
    `_localhost_database_url()` only rewrote the DB *hostname* (`postgres` → `localhost`, for
    running pytest outside Docker — see gotcha #11) while keeping the exact same `POSTGRES_DB`.
    Running `make test`/`pytest` therefore silently wiped all live tickets and the ingested KB seed
    — this actually happened once, discovered only because `/stats` came back empty right
    afterward. Fixed with a session-scoped autouse fixture that creates (or drops+recreates) a
    dedicated `<POSTGRES_DB>_test` database, reapplies `db/init/01_schema.sql` fresh, and points
    `settings.database_url` at *that* — no new env var needed, derived from the existing
    `POSTGRES_DB`/`POSTGRES_USER`. If you ever see `/stats` or `/kb/ingest` looking unexpectedly
    empty right after running tests, re-seed (`uv run scripts/ingest.py`) rather than assuming data
    corruption.
32. **Notion's "Append block children" endpoint (`/v1/blocks/{id}/children`) requires HTTP
    `PATCH`, not `POST`.** Using POST returns a 400 with `"code":"invalid_request_url"` and
    message `"Invalid request URL."` — a genuinely misleading error, since it doesn't mention the
    method at all and the exact same URL works fine for `GET` (list children). Confirmed by
    reproducing the failure with plain `curl -X POST` (ruling out an n8n-specific bug) before
    checking Notion's official API reference, which documents `PATCH` for this route. Also: an
    n8n integration must have "insert content" capability granted (separate from just having the
    target page shared with it via **`...`** → Connections) for this to succeed at all.
33. **A key copied from Google AI Studio doesn't always look like `AIzaSy...`** — one obtained
    this session started with `AQ.` instead, and still worked correctly against
    `generativelanguage.googleapis.com` (confirmed via a live `GET /v1beta/models` call). Don't
    assume a key is invalid, wrong-service, or mistyped just because its prefix doesn't match the
    most commonly-documented format — verify against the actual API before asking the user to
    re-check where they copied it from.
34. **Gemini's structured-output schema is a JSON-Schema subset with UPPERCASE type names
    (`"OBJECT"`, `"STRING"`) and no `additionalProperties` support** — passing a normal
    lowercase JSON-Schema dict (like `CLASSIFY_SCHEMA` in `schemas.py`) is silently rejected or
    misbehaves. `llm.py`'s `_to_gemini_schema()` converts rather than hand-maintaining a second
    schema per shape. Separately, `gemini-embedding-001` defaults to 3072-dim output, not the
    1536 this project's schema is frozen at (gotcha #5) — but the model supports requesting a
    smaller dimension natively via `outputDimensionality` in the request body (it's
    Matryoshka-trained, so truncation is a supported, intended use case, not a hack); confirmed
    live rather than assumed.
35. **Google's Gemini API free tier has both a per-minute rate limit (as low as 5 req/min for
    `gemini-2.5-flash`) AND a much more restrictive per-*day* quota (confirmed live: 20
    requests/day, `quotaId: "GenerateRequestsPerDayPerProjectPerModel-FreeTier"`) — retrying
    with backoff only helps for the former.** The 429 body's `error.message` names the exact wait
    in plain text ("Please retry in 36.6s") rather than a `Retry-After` header, and
    `llm.py`'s `_post_gemini_with_retry()` parses and honors it — but once the *daily* quota is
    exhausted, every retry gets a fresh 429 with a new short wait, creating the illusion that
    backing off a bit longer would eventually succeed when it actually won't until the daily
    quota resets. Diagnose which one you've hit by re-requesting immediately after a supposed
    wait and reading `error.details[].quotaId` in the JSON body, not just the top-level message.
    This project's `evals/tickets.jsonl` needs ~37 chat calls total (27 classify + ~10 for
    grounding's answer/self-check pairs) — comfortably past the free daily cap for a single day,
    which is why `evals/conftest.py` defaults to `ollama` instead (gotcha #38 covers the
    accuracy tradeoff that comes with it).
36. **A "thinking"/reasoning-style local Ollama model needs a generous explicit `max_tokens`, not
    the 1024 used for Anthropic/OpenAI in `llm.py`.** `huihui_ai/qwen3.5-abliterated:9b` emits an
    internal reasoning trace (often 1000+ tokens, returned separately in a `reasoning` field
    alongside `content`) before the actual JSON answer — with too small a token budget the
    response gets cut off mid-reasoning and `content` is empty or truncated, which fails JSON
    parsing but looks like a schema-compliance problem rather than a token-budget one. `_call_
    ollama` now passes `max_tokens=8192` to leave room for both the reasoning trace and the final
    answer. If evaluating a different local model, check whether it does the same kind of visible
    "thinking" before answering, and size `max_tokens` accordingly.
37. **No dedicated Ollama embedding model commonly outputs exactly 1536 dimensions** — the
    obvious default, `nomic-embed-text`, outputs 768 (confirmed live). Unlike Gemini's
    Matryoshka-trained embedding model (gotcha #34), Ollama has no native way to request a
    smaller output dimension, so there's no equivalent fix short of finding (or fine-tuning) a
    model that happens to match, or padding/projecting the vector (not implemented — would
    silently degrade retrieval quality in a way that's hard to detect later). `_embed()` raises a
    clear error on a dimension mismatch rather than writing a corrupted row, so this fails loudly
    at ingest/query time rather than silently. Practically: `ollama` mode currently only works for
    chat-only endpoints (`/classify`); `/query`'s embed step needs `anthropic`, `openai`, or
    `gemini` until a matching local embedding model is found.
38. **Local Ollama model choice swings `/classify` accuracy dramatically — from clearly failing
    to close-to-passing — with no code change, only a config value.** Compared live against the
    same 27-item eval fixture and the same (once-clarified) `classify.md` prompt:
    - `llama3.2:3b`: fast (~2s/call), reliable, but only 0.500–0.667 accuracy — consistently
      over-predicts `account` for anything it's unsure about, including all 3 `other`-category
      tickets in one run.
    - `huihui_ai/qwen3.5-abliterated:9b`: a visible-reasoning "thinking" model (gotcha #36) —
      slow (~60-100s/call) and, even with an 8192-token budget, still occasionally failed to
      converge to valid JSON within budget on some tickets after 15+ minutes of otherwise-successful
      calls. Not recommended for this task despite being a larger model, given the reliability cost.
    - A 12B gemma-based coder-tuned model: fast (~5s/call, no reasoning trace), reliable (zero
      validation failures), and scored 0.833 — close to but just under this project's 0.85 bar,
      with `other` at a perfect 3/3 (unlike llama3.2:3b's 0/3). **The strongest of all four models
      tried, including the cloud-routed one below** — currently the default in `.env`.
    - `minimax-m3:cloud` (routed through Ollama's own cloud backend, not running locally at all —
      see gotcha #40): fast (~3s/call, cloud-side compute), reliable, but scored only 0.750 —
      *worse* than the local 12B model despite presumably being a much larger model. Concretely
      confirms the lesson below isn't just about local-vs-cloud or model size in the abstract.
    None of these reached the 0.85 threshold `docs/TESTPLAN.md` requires; only a "real" cloud
    provider (Anthropic, OpenAI, or Gemini past its free-tier quota — gotcha #35) reliably clears
    it. Lesson: don't assume "bigger model" or "reasoning model" or "cloud-routed" automatically
    means more accurate or more reliable for a specific structured-output task — test the actual
    task, not just general capability or spec sheet, and weight reliability (does it ever fail to
    produce valid JSON at all) alongside raw accuracy.
39. **A model can wrap valid JSON in markdown code fences (` ```json ... ``` `) even when given
    an explicit `response_format: json_schema` with `strict: true`** — seen live with
    `minimax-m3:cloud` via Ollama's OpenAI-compatible endpoint. "Strict" structured-output mode is
    evidently not equally strict across every provider/model. The original parsing
    (`json.loads(text)` directly) would raise an unhandled `JSONDecodeError` on this, crashing the
    request instead of the intended clean retry/422 path. Fixed with a shared `_parse_json()`
    helper in `llm.py` that strips a leading/trailing fence (with or without a `json` language
    tag) before parsing, and catches `JSONDecodeError` to return `None` rather than raising —
    used at all three structured-output call sites (Anthropic, the OpenAI-compatible path shared
    by OpenAI/Ollama, and Gemini), since any of them could in principle do this.
40. **Ollama can transparently proxy to *cloud-hosted* models it doesn't run itself** — model
    names ending `:cloud` (visible in `ollama list`/`/api/tags`) route through
    `https://ollama.com` using the local Ollama installation's own account, not local compute at
    all. Some require a paid ollama.com subscription (`glm-5.2:cloud`, `minimax-m2.7:cloud`,
    `kimi-k2.7-code:cloud` all returned `"this model requires a subscription"` — a plain 403, not
    a model-not-found error) while others are accessible on the free tier (`minimax-m3:cloud`
    worked without any subscription). Don't assume every `:cloud`-suffixed model behind the same
    Ollama server is equally accessible — check each one; a 403 with that exact message means
    "needs a paid plan," not "misconfigured" or "model doesn't exist."
