# Phase 6 — Deploy & packaging (Claude Code, with the human alongside for cloud credentials)
# Prerequisite: Phases 0–5 accepted; human E2E M1–M6 all passed.

===== COPY FROM HERE =====
## Objective
Take OpsPilot to a public VM and package the repo for a hiring manager's 5-minute review: docs, ADRs, metrics, and a reproducible README. The audience is a reviewer deciding whether to interview the author.

## Context
Read first: AGENTS.md, docs/SPEC.md §7 (Definition of Done), docs/TESTPLAN.md (M7), PROGRESS.md, wiki/log.md. The human provisions the VM and owns all cloud credentials; you generate every artifact and command they run. Target VM: Hetzner CX22 or GCP e2-small, Ubuntu 24.04, Docker + compose plugin.

## Target State (task IDs P6-1..P6-4)
- P6-1 `docs/infrastructure.md`: step-by-step deploy runbook (provision → clone → .env → compose up → DNS → Caddy TLS → n8n basic auth + WEBHOOK_URL → switch Telegram webhook) + a GCP↔AWS service-mapping table (Compute Engine↔EC2, GCS↔S3, Cloud SQL↔RDS, Secret Manager↔Secrets Manager). Add the caddy service to docker-compose behind a `prod` profile so local dev is unchanged.
- P6-2 `scripts/backup.sh`: nightly pg_dump → gzip → upload to object storage (rclone or gsutil/aws-cli — match the chosen cloud); cron line documented; restore procedure documented and TESTED against a scratch database.
- P6-3 ADRs in docs/decisions/: ADR-001 LLM-calls-via-service (locked earlier — write it up), ADR-002 confidence gate design, ADR-003 pgvector-over-external-vector-DB, ADR-004 asyncpg-no-ORM, plus any ADR-005+ accumulated in log.md.
- P6-4 Final README.md: one-paragraph pitch, architecture diagram (Mermaid from SPEC), quickstart (3 commands), live bot handle placeholder, metrics table populated from GET /stats on production data (human pastes numbers), link placeholders for the demo video, CI badge, out-of-scope section, license.

## Scope
Work only in: docs/, scripts/, README.md, docker-compose.yml (caddy prod profile only). Code and schema are frozen except critical fixes, each requiring a blocker entry first.

## Acceptance Criteria
- [ ] Human executes docs/infrastructure.md top-to-bottom without improvising a single step
- [ ] TESTPLAN M7 passes: /health over TLS, M1 on production, backup object appears, restart-safe
- [ ] All ADRs present; README renders correctly on GitHub with diagram and badge
- [ ] Fresh-clone rehearsal: on a clean machine, `cp .env.example .env && docker compose up -d && make seed` works per README
- [ ] PROGRESS.md fully ticked except [HUMAN] video; final session entry appended

## Stop Conditions
Never handle or request the human's cloud credentials, card data, or account passwords — produce commands for the human to run. Stop before any destructive operation on the VM (document it, let the human run it).
===== COPY TO HERE =====

# Human afterwards: record the 3-minute video (script in the application plan), paste metrics into README, publish the repo, apply.
