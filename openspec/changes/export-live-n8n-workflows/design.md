## Context

Live n8n instance (`localhost:5678`, reused per gotcha #1) currently holds 13 workflows; only 5
are OpsPilot's:

| Committed file | Live workflow name | Live ID |
|---|---|---|
| `wf1_intake_triage.json` | WF-1 Intake & Triage | `yJPNRtejO63lWoXt` |
| `wf2_draft_answer.json` | WF-2 Draft Answer | `0ExVh6IQrIGJsmOW` |
| `wf3_hitl.json` | WF-3 Human-in-the-loop | `X3xeprbfavtk14oX` |
| `wf4_sla_watchdog.json` | WF-4 SLA Watchdog | `8AsnOqN1OqLCowHr` |
| `wf5_daily_digest.json` | WF-5 Daily Digest | `5F5H4me3wASKJMBh` |

The other 8 (`Daily Telegram Morning Message`, `Daily Telegram 9:30 AM`, 4 copies of `OKF Starter —
Compile Documents to OKF Bundle`, `My workflow`, `My workflow 2`) are unrelated personal
automations on the same shared instance — explicitly out of scope (per user decision this
session).

Known real-vs-placeholder deltas already documented (PROGRESS.md Blockers, wiki/gotchas.md #20):
6 `chatId`/condition spots across WF-1/WF-3/WF-4/WF-5 real ops-chat-ID; 1 Notion page ID in WF-5's
"Append To Notion" URL; 2 cross-workflow ID references in WF-1/WF-2 (`WF2_WORKFLOW_ID_PLACEHOLDER`,
`WF3_WORKFLOW_ID_PLACEHOLDER`) that `scripts/n8n_sync.py` patches at sync time. Credential blocks
in the committed files always have `"id": null` (matched by `"name"` on import instead).

## Goals / Non-Goals

**Goals:**
- Produce `workflows-n8n/{wf1_intake_triage,wf2_draft_answer,wf3_hitl,wf4_sla_watchdog,
  wf5_daily_digest}.json`, each a clean, re-importable export of the live workflow (same shape as
  `n8n/workflows/*.json`: `name`, `nodes`, `connections`, `settings` only).
- Redact every path that's a placeholder in the matching `n8n/workflows/*.json` file back to that
  same placeholder value in the export — without the script needing to hardcode what the real
  secret values are.
- Make it obvious if there's a *structural* difference between committed and live beyond the known
  placeholder spots (real drift worth a human look), vs. just the expected placeholder deltas.

**Non-Goals:**
- Not exporting the other 8 unrelated workflows on the shared instance.
- Not modifying `n8n/workflows/*.json`, `scripts/n8n_sync.py`, or anything live in n8n — purely a
  read-only export script.
- Not adding this to CI, `make`, or any scheduled job — it's a manual, on-demand snapshot tool; the
  user runs it when they want a fresh one.
- Not attempting perfect byte-for-byte reproduction of `n8n/workflows/*.json` — legitimate drift
  (e.g. a live-only UI tweak never ported back) should surface as a real diff, not be silently
  hidden.

## Decisions

**1. Redaction is path-diff-based, not value-based.** The script does NOT hardcode the real ops
chat ID or Notion page ID anywhere (it shouldn't need to know them). Instead, for each of the 5
workflows it recursively walks both the committed JSON and the freshly fetched live JSON in
parallel. At every leaf position where the committed value is a string matching
`^PLACEHOLDER_.*` or `.*_PLACEHOLDER$`, the live JSON's value at that same path is overwritten
with the committed placeholder string. This is robust as long as the two structures align at those
specific paths (they should — same node, same parameter key, just a different literal value) and
naturally generalizes to "whatever the committed convention already decided needs redacting,"
rather than a maintained list of secret literals that could drift or leak.

**2. Credential IDs are always nulled, unconditionally.** Every `nodes[*].credentials.*.id` in the
live export is set to `null` regardless of what the committed file has there (it's always `null`
in the committed files already) — credential IDs are n8n-instance-specific internal identifiers,
not portable, and n8n re-matches by `credentials.*.name` on import anyway.

**3. Export uses the same `IMPORT_FIELDS` reduction as `scripts/n8n_sync.py`.** The raw
`GET /workflows/{id}` response includes instance metadata (`id`, `active`, `createdAt`,
`updatedAt`, `versionId`, `tags`, `staticData`, `pinData`, `meta`) that isn't part of an importable
workflow definition and isn't present in the committed files either — reduce to
`{name, nodes, connections, settings}` for consistency with the existing convention, using the
same field set already defined in `scripts/n8n_sync.py` (imported, not redefined, to avoid two
sources of truth for "what counts as an importable workflow").

**4. After redaction, diff each new file against its `n8n/workflows/` counterpart and print a
summary** (not fail the script) — this is the human-visible signal for "is there real drift here
beyond the known placeholder spots." Any remaining difference after redaction is either legitimate
drift (a live-only fix never ported back to the committed file) or a redaction path this script
didn't anticipate; either way it's worth a look, not something to silently swallow.

**5. Script location: `scripts/export_n8n_workflows.py`, reusing `scripts/n8n_sync.py`'s
`_client()` helper** (import it rather than duplicating the auth/base-URL logic) — same
`N8N_API_URL`/`N8N_API_KEY` env vars, same failure mode (clear stderr message) if unset.

## Risks / Trade-offs

- **[Risk]** Path-diff redaction depends on committed and live JSON having the same shape at
  placeholder paths. If a node was restructured live (not just a value changed), the path might
  not line up, and redaction could miss a value or throw on an unexpected shape. → **Mitigation**:
  Decision 4's diff-after-redact step surfaces this immediately — an unredacted secret would show
  up as an unexpected diff against the committed file, which the script prints for human review
  rather than committing blind.
- **[Risk]** A future live-only edit could introduce a *new* secret-shaped value that isn't at any
  currently-known placeholder path (e.g. a brand new node with a hardcoded ID). → **Mitigation**:
  explicitly a known limitation, stated in the script's own docstring/output — this tool catches
  drift at *already-identified* placeholder locations, it is not a general secret scanner. The
  diff-summary output (Decision 4) is the human checkpoint for catching this class of miss.
- **[Risk]** Committing `workflows-n8n/` risks becoming a second, silently-stale copy if never
  re-run. → **Mitigation**: explicitly a manual/on-demand tool (Non-Goals) with no automation
  promising freshness — the wiki/log.md entry for this change will say plainly that this is a
  point-in-time export, not a continuously-synced one.

## Migration Plan

New folder + new script only — no changes to existing behavior. Nothing to roll back beyond
deleting the new files if this turns out not to be useful.

## Open Questions

- None blocking.
