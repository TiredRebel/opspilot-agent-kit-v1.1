# Gotchas (numbered, append-only)

1. **n8n port collision.** An n8n container already runs on this machine (default 5678). The kit's
   compose must either reuse it (point N8N_API_URL at it) or map the new instance to **5679**. Decide
   at P0-1 and record in log.md. Never run two instances on one port.
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
