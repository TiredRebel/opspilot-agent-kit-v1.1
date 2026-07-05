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
