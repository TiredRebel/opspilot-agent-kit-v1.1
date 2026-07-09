# Infrastructure — deploy runbook

**Status: not yet executed against a live VM.** This is the forward-looking runbook for when a
real cloud VM is provisioned. Today's working setup is local Docker Compose + the developer's own
local n8n instance + an ngrok tunnel for the Telegram webhook (see `wiki/gotchas.md` #1, #2). Every
step below is written to be run verbatim by a human with no improvisation, per this phase's
acceptance criteria — but it hasn't been rehearsed against a real machine yet. Treat commands here
as reviewed-but-unverified until someone actually runs them top to bottom.

## 1. Provision the VM

**Hetzner CX22** (recommended — cheapest reasonable fit, ~€4/mo, 2 vCPU / 4GB RAM / 40GB disk,
enough for postgres + rag-api + caddy on one box):

1. Create the server: Ubuntu 24.04 LTS, CX22, your SSH key attached at creation.
2. `ssh root@<server-ip>`
3. Create a non-root user and add it to the `docker` group once Docker is installed (step below)
   — don't run the stack as root long-term.

### GCP ↔ AWS service mapping (reference — this runbook doesn't use either cloud managed service)

| Purpose | GCP | AWS |
|---|---|---|
| VM | Compute Engine (e2-small) | EC2 (t3.small) |
| Object storage (backups) | Cloud Storage (GCS) | S3 |
| Managed Postgres | Cloud SQL | RDS |
| Secrets | Secret Manager | Secrets Manager |
| DNS | Cloud DNS | Route 53 |

This project runs its own Postgres in a container rather than a managed database (ADR-003 —
pgvector needs to live next to it anyway), so "managed Postgres" here is informational, not a step
you need to follow.

## 2. Install Docker + the compose plugin

```bash
curl -fsSL https://get.docker.com | sh
usermod -aG docker "$USER"
# log out and back in for the group change to take effect
docker compose version   # confirm the compose plugin is present (bundled with modern Docker)
```

## 3. Clone the repo and configure `.env`

```bash
git clone https://github.com/TiredRebel/opspilot-agent-kit-v1.1.git opspilot
cd opspilot
cp .env.example .env
```

Edit `.env` with real values: `POSTGRES_PASSWORD` (pick a real one, don't ship `changeme`),
`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`/`GEMINI_API_KEY` (whichever provider(s) you're actually
using — `LLM_PROVIDER` selects the active one, see `services/rag/app/llm.py`), `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_OPS_CHAT_ID`, `NOTION_API_KEY`, `NOTION_PAGE_ID`. Never commit this file (`.gitignore`
already excludes it).

## 4. Set up n8n on this same VM

This repo's own `docker-compose.yml` intentionally does **not** run n8n (`wiki/gotchas.md` #1) —
in dev that's because an instance already existed on the developer's machine; in production, n8n
still needs to run somewhere, so it runs as its own, separate compose project on this same VM,
proxied by Caddy on its own subdomain (step 6).

```bash
mkdir ~/n8n && cd ~/n8n
cat > docker-compose.yml <<'YAML'
services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - n8n_pgdata:/var/lib/postgresql/data

  n8n:
    image: n8nio/n8n:latest
    restart: unless-stopped
    # Runs as the image's own default non-root "node" user (do NOT override to user: "0:0" —
    # that was the exact bug that rotated this project's encryption key mid-build and made every
    # existing credential undecryptable: root looks for /root/.n8n, but the persistent volume is
    # mounted at /home/node/.n8n. See wiki/gotchas.md #21.)
    environment:
      DB_TYPE: postgresdb
      DB_POSTGRESDB_HOST: postgres
      DB_POSTGRESDB_USER: ${POSTGRES_USER}
      DB_POSTGRESDB_PASSWORD: ${POSTGRES_PASSWORD}
      DB_POSTGRESDB_DATABASE: ${POSTGRES_DB}
      N8N_HOST: ops.example.com
      WEBHOOK_URL: https://ops.example.com/
      N8N_BASIC_AUTH_ACTIVE: "true"
      N8N_BASIC_AUTH_USER: ${N8N_BASIC_AUTH_USER}
      N8N_BASIC_AUTH_PASSWORD: ${N8N_BASIC_AUTH_PASSWORD}
      GENERIC_TIMEZONE: Europe/Kyiv
    ports:
      - "5678:5678"
    volumes:
      - n8n_storage:/home/node/.n8n
    depends_on:
      - postgres

volumes:
  n8n_pgdata:
  n8n_storage:
YAML

cat > .env <<'ENV'
POSTGRES_USER=n8n
POSTGRES_PASSWORD=<pick a real password>
POSTGRES_DB=n8n
N8N_BASIC_AUTH_USER=<pick a username>
N8N_BASIC_AUTH_PASSWORD=<pick a real password>
ENV

docker compose up -d
```

Replace `ops.example.com` with your real subdomain (also used in the Caddyfile, step 6). Once
n8n is up, create an API key (Settings → API) for `make n8n-sync`, and recreate the `Postgres -
OpsPilot` / `Telegram - OpsPilot` / `Notion - OpsPilot` credentials via the n8n UI (or scripted —
see `scripts/n8n_sync.py`'s history for the credential-creation pattern) since this is a fresh
instance with nothing imported yet.

## 5. Bring up this project's own stack

```bash
cd ~/opspilot
docker compose --profile prod up -d
make seed
```

`--profile prod` additionally starts `caddy` (absent by default — see `docker-compose.yml`); local
dev machines never need this flag.

## 6. DNS + Caddy TLS

Point two A records at the VM's IP: `api.<your-domain>` and `ops.<your-domain>`. Edit
`caddy/Caddyfile`, replacing `api.example.com`/`ops.example.com` with your real subdomains, then:

```bash
docker compose --profile prod up -d --force-recreate caddy
docker compose --profile prod logs -f caddy   # watch for "certificate obtained successfully"
```

Caddy requests and renews Let's Encrypt certs automatically for both site blocks — no certbot, no
renewal cron.

## 7. Point the Telegram webhook at production

Set `N8N_API_URL` in this project's `.env` to `https://ops.<your-domain>`, then:

```bash
set -a; . ./.env; set +a
uv run scripts/n8n_sync.py
```

This imports/activates all 7 workflows on the production n8n instance. WF-1's Telegram Trigger
node registers its own webhook with Telegram on activation, using n8n's `WEBHOOK_URL` (set in step
4) — no separate "switch the webhook" step is needed; it happens as a side effect of activating
WF-1 against an n8n instance that already has the right `WEBHOOK_URL` configured.

If the production VM's public URL ever changes (e.g. moving domains, re-pointing a tunnel), update
`WEBHOOK_URL` in the n8n compose environment, restart the n8n container, and re-run
`make n8n-sync`.

## 8. Verify (docs/TESTPLAN.md § L5 — M7)

```bash
curl https://api.<your-domain>/health          # 200, {"status":"ok","db":true}
# M1: message the production bot a KB question, confirm auto-reply < 15s
# Confirm TLS: browser padlock on both subdomains, or `curl -v` and check the cert issuer
# n8n UI at https://ops.<your-domain> prompts for basic auth
./scripts/backup.sh                             # confirm a dump lands in the configured rclone remote
docker compose --profile prod restart           # confirm all services come back healthy, data intact
```

## Known gaps (see PROGRESS.md)

- This runbook has not been executed against a real VM this session — commands are reviewed, not
  rehearsed. Treat step numbers/exact flags as best-effort until a real run confirms them.
- `scripts/backup.sh`'s `rclone` upload step needs a configured remote (`rclone config`) that
  isn't set up anywhere yet — the pg_dump/gzip/restore portions are tested locally against a
  scratch database (see the script's own header comment), the upload/download portions are not.
