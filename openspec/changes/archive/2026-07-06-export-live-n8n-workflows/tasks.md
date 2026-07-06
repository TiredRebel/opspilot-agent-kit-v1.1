## 1. Script

- [x] 1.1 Create `scripts/export_n8n_workflows.py`: import `_client` from `scripts/n8n_sync.py`, define the 5 target workflow names, and fetch each by name (reuse or adapt `_find_by_name`). **Note:** the list endpoint (`_find_by_name`'s `GET /workflows`) already returns full `nodes`/`connections`/`settings` per workflow — no separate `GET /workflows/{id}` call needed.
- [x] 1.2 Reduce each fetched workflow to `{name, nodes, connections, settings}` (reuse `IMPORT_FIELDS` from `scripts/n8n_sync.py`).
- [x] 1.3 Implement path-diff redaction: load the matching `n8n/workflows/*.json` file, recursively walk both structures in parallel, and wherever the committed value at a path matches `PLACEHOLDER_.*` or `.*_PLACEHOLDER`, overwrite the live value at that path with the committed placeholder string. **Refinements found live:** (1) the top-level `nodes` list is matched by node `name`, not list index — robust to a node being added/removed live; (2) the placeholder check had to become a substring search, not a whole-string match — WF-5's Notion URL embeds `PLACEHOLDER_NOTION_PAGE_ID` inside a larger string (`https://api.notion.com/v1/blocks/PLACEHOLDER_NOTION_PAGE_ID/children`), and the first version of the script missed it, leaking the real Notion page ID into the first export attempt (caught by task 2.2's grep before anything was committed).
- [x] 1.4 Unconditionally null every `nodes[*].credentials.*.id` in the exported output.
- [x] 1.5 After redaction, diff the result against the committed counterpart and print any remaining differences to stdout (do not fail the script on a diff). **Refinement:** also strip `webhookId` (n8n's auto-assigned per-node registration UUID, absent from every committed file) — same instance-specific-noise category as credential IDs, not just diff-report it forever.
- [x] 1.6 Write each redacted workflow to `workflows-n8n/<same-filename-as-n8n/workflows/>`.

## 2. Run and verify

- [x] 2.1 Run the script against the live instance; confirm exactly 5 files are written to `workflows-n8n/` with the same names as `n8n/workflows/`. **Result:** all 5 written (17/12/22/5/6 nodes respectively, matching the committed files' node counts).
- [x] 2.2 Manually inspect each output file for any remaining real secret value (grep for the known real ops chat ID / Notion page ID patterns) — confirm none leak through before this is committed. **Result:** first run leaked the real Notion page ID (see 1.3 note) — caught here, fixed, re-ran clean. Second run: zero matches for either real secret value; placeholder counts per file match `n8n/workflows/` exactly (4/1/3/1/2).
- [x] 2.3 Review the printed drift summary from 1.5 — note anything genuinely surprising in the session log (task 3.1), don't silently ignore it. **Result:** one real (benign) drift found — WF-1's live `settings.binaryMode: "separate"` isn't in the committed file (an n8n default/setting added since WF-1 was last committed, not a secret). All other 4 workflows show zero diff after redaction.
- [x] 2.4 Confirm each output file is valid JSON and matches the `{name, nodes, connections, settings}` shape (no leftover instance metadata). **Result:** confirmed for all 5 files.

## 3. Documentation

- [x] 3.1 Add a `wiki/log.md` session entry noting the new `workflows-n8n/` folder, that it's a manual/on-demand export (not auto-synced), and whatever drift (if any) task 2.3 surfaced.
- [x] 3.2 Update `wiki/map.md`'s component matrix with a row (or note under the existing n8n workflow rows) pointing at `workflows-n8n/` and `scripts/export_n8n_workflows.py`.
