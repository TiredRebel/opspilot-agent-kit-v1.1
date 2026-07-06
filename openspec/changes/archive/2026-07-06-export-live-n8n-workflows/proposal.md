## Why

`n8n/workflows/*.json` is this project's committed source-of-truth, but it deliberately contains
`PLACEHOLDER_*` tokens instead of real values (ops chat ID, Notion page ID, cross-workflow ID
references — per AGENTS.md and wiki/gotchas.md #20), because those real values get live-patched
directly in the n8n UI/API and never round-trip back into the committed JSON. That means the
committed files, imported as-is into a fresh n8n instance, would **not work out of the box** —
a new user would hit the same "Send Ops Message" / "Is Ops Reply" / Notion-append failures this
project already hit and fixed live, with no record of what value to substitute. A user-requested
`workflows-n8n/` folder, freshly exported from the live instance and safely re-scrubbed, gives a
verified, current snapshot of the 5 real OpsPilot workflows as they actually run today — useful for
backup, portability, or reviewing drift between the committed JSON and the live-patched reality.

## What Changes

- New `scripts/export_n8n_workflows.py` — fetches the 5 OpsPilot workflows (by name: `WF-1 Intake &
  Triage`, `WF-2 Draft Answer`, `WF-3 Human-in-the-loop`, `WF-4 SLA Watchdog`, `WF-5 Daily Digest`)
  from the live n8n instance via its REST API (reusing the `_client()`/`_find_by_name()` pattern
  already in `scripts/n8n_sync.py`), **not** the other 8 unrelated workflows that happen to live on
  the same shared n8n instance (gotcha #1 — this project reuses an existing local install).
- Each fetched workflow is reduced to the same importable shape already used by
  `n8n/workflows/*.json` (`name`, `nodes`, `connections`, `settings` — matches
  `scripts/n8n_sync.py`'s `IMPORT_FIELDS`), then **redacted** by diffing against the committed
  file with the same name: wherever the committed JSON has a `PLACEHOLDER_*`/`*_PLACEHOLDER` token
  at a given path, the live value at that same path is overwritten back to that placeholder,
  wherever the committed file has `credentials.<key>.id: null`, the live value is nulled the same
  way. This needs no hardcoded secret values — it only needs to know *where* the existing
  placeholders already are.
- New `workflows-n8n/` folder at the repo root containing the 5 redacted files
  (`wf1_intake_triage.json` .. `wf5_daily_digest.json`, same names as `n8n/workflows/`), each
  diffed against its `n8n/workflows/` counterpart post-redaction so any *remaining* difference is
  a real, reviewable drift between committed and live (not a leftover secret).
- **No changes** to `n8n/workflows/*.json` themselves, `scripts/n8n_sync.py`, or any running
  workflow — this is a read-only export.

## Capabilities

### New Capabilities
- `n8n-workflow-export`: defines how OpsPilot's live n8n workflows get exported to a clean,
  secret-scrubbed, re-importable JSON snapshot.

### Modified Capabilities
(none)

## Impact

- **Code**: new `scripts/export_n8n_workflows.py` only. No existing script/service code changes.
- **New artifact**: `workflows-n8n/*.json` (5 files), committed to git — safe to commit because
  every path that had a real secret in the committed `n8n/workflows/` counterpart is re-scrubbed
  before writing.
- **Requires**: a reachable live n8n instance with `N8N_API_URL`/`N8N_API_KEY` set (same
  requirement as `make n8n-sync`) — this is a manual, on-demand export, not part of CI or `make`
  by default (no scheduled drift risk to manage).
- **Downstream**: none — existing workflows, sync script, and tests are unaffected.
