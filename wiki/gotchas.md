# Gotchas (numbered, append-only)

1. **n8n port collision — RESOLVED at P0-1.** An n8n container already runs on this machine
   (`n8n-n8n-1`, default 5678). Decision: **reuse it** — this project's `docker-compose.yml` does
   NOT run n8n at all; `.env.example` points `N8N_API_URL=http://localhost:5678` at the existing
   instance. Its sidecar `n8n-postgres-1` is not published to the host, so it never collides with
   this project's own Postgres on 5432. Never run two n8n instances on one port.
2. **Telegram Trigger needs a public webhook URL.** Local dev: use a cloudflared quick tunnel (or
   n8n's dev tunnel) and set WEBHOOK_URL for n8n; on the VM the real domain replaces it. Do not try
   long-polling hacks.
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
