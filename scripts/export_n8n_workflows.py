#!/usr/bin/env python3
"""CLI entrypoint for a manual, on-demand export of OpsPilot's 7 live n8n workflows into
`workflows-n8n/`, redacted back to the same PLACEHOLDER_* values used in the committed
`n8n/workflows/*.json` (which never get the real live-patched values — see wiki/gotchas.md #20).
Redaction is path-diff-based against the committed files, not a hardcoded secret list: nodes are
matched by name (robust to a node being added/removed live), everything else is walked
structurally. Not part of CI/`make` — run manually when a fresh snapshot is wanted."""

import json
import re
import sys
from pathlib import Path

from n8n_sync import IMPORT_FIELDS, WORKFLOWS_DIR, _client, _find_by_name

EXPORT_DIR = Path(__file__).resolve().parent.parent / "workflows-n8n"

WORKFLOW_FILES = {
    "WF-1 Intake & Triage": "wf1_intake_triage.json",
    "WF-2 Draft Answer": "wf2_draft_answer.json",
    "WF-3 Human-in-the-loop": "wf3_hitl.json",
    "WF-4 SLA Watchdog": "wf4_sla_watchdog.json",
    "WF-5 Daily Digest": "wf5_daily_digest.json",
    "WF-6 Outbound Delivery": "wf6_delivery.json",
    "WF-7 Event Publisher": "wf7_event_publisher.json",
}

_PLACEHOLDER_RE = re.compile(r"PLACEHOLDER_\w+|\w+_PLACEHOLDER")


def _has_placeholder(value: object) -> bool:
    """True if a committed value contains one of this project's PLACEHOLDER_* redaction tokens
    — a substring search, not a whole-string match, since some placeholders sit inside a larger
    template string (e.g. a Notion URL: `.../blocks/PLACEHOLDER_NOTION_PAGE_ID/children`)."""
    return isinstance(value, str) and bool(_PLACEHOLDER_RE.search(value))


def _redact(committed: object, live: object) -> object:
    """Return `live` with any leaf overwritten by the committed placeholder at that same path."""
    if _has_placeholder(committed):
        return committed
    if isinstance(committed, dict) and isinstance(live, dict):
        return {k: (_redact(committed[k], v) if k in committed else v) for k, v in live.items()}
    if isinstance(committed, list) and isinstance(live, list) and len(committed) == len(live):
        return [_redact(c, v) for c, v in zip(committed, live, strict=True)]
    return live


def _redact_nodes(committed_nodes: list[dict], live_nodes: list[dict]) -> list[dict]:
    """Redact each live node against its committed counterpart matched by node `name`, not
    list index — a node added/removed live shouldn't break redaction for the nodes that still
    match, unlike a naive index-aligned list diff."""
    by_name = {n["name"]: n for n in committed_nodes}
    return [
        _redact(by_name[node["name"]], node) if node.get("name") in by_name else node
        for node in live_nodes
    ]


def _null_credential_ids(nodes: list[dict]) -> None:
    """Null every node's credential `.id` in place — instance-specific, n8n re-matches by name."""
    for node in nodes:
        for cred in node.get("credentials", {}).values():
            if isinstance(cred, dict) and "id" in cred:
                cred["id"] = None


def _strip_webhook_ids(nodes: list[dict]) -> None:
    """Remove n8n's auto-assigned `webhookId` (present on live Webhook/Telegram-trigger nodes,
    absent from every committed file) — instance-specific registration noise, same category as
    credential IDs, not something a fresh import should carry over."""
    for node in nodes:
        node.pop("webhookId", None)


def _diff(committed: object, live: object, path: str = "root") -> list[str]:
    """Recursively collect human-readable differences between the committed and final export."""
    diffs: list[str] = []
    if isinstance(committed, dict) and isinstance(live, dict):
        for key in sorted(set(committed) | set(live)):
            if key not in live:
                diffs.append(f"{path}.{key}: present in committed, missing in export")
            elif key not in committed:
                diffs.append(f"{path}.{key}: present in export, missing in committed")
            else:
                diffs.extend(_diff(committed[key], live[key], f"{path}.{key}"))
    elif isinstance(committed, list) and isinstance(live, list):
        if len(committed) != len(live):
            diffs.append(f"{path}: length differs (committed={len(committed)}, export={len(live)})")
        else:
            for i, (c, v) in enumerate(zip(committed, live, strict=True)):
                diffs.extend(_diff(c, v, f"{path}[{i}]"))
    elif committed != live:
        diffs.append(f"{path}: committed={committed!r} export={live!r}")
    return diffs


def main() -> int:
    """Export the 7 OpsPilot workflows from the live n8n instance, redacted and diff-reported."""
    EXPORT_DIR.mkdir(exist_ok=True)
    with _client() as client:
        for name, filename in WORKFLOW_FILES.items():
            workflow = _find_by_name(client, name)
            if workflow is None:
                print(f"Workflow not found on live instance: {name!r}", file=sys.stderr)
                return 1

            committed = json.loads((WORKFLOWS_DIR / filename).read_text(encoding="utf-8"))
            live = {k: v for k, v in workflow.items() if k in IMPORT_FIELDS}

            redacted = dict(live)
            redacted["nodes"] = _redact_nodes(committed["nodes"], live["nodes"])
            redacted["connections"] = _redact(committed["connections"], live["connections"])
            redacted["settings"] = _redact(committed["settings"], live["settings"])
            _null_credential_ids(redacted["nodes"])
            _strip_webhook_ids(redacted["nodes"])

            (EXPORT_DIR / filename).write_text(
                json.dumps(redacted, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            print(f"{filename}: exported to {EXPORT_DIR / filename}")

            diffs = _diff(committed, redacted)
            if diffs:
                print(f"  {len(diffs)} difference(s) vs n8n/workflows/{filename}:")
                for d in diffs:
                    print(f"    {d}")
            else:
                print("  no differences vs committed n8n/workflows/ file")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
