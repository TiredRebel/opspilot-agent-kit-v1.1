#!/usr/bin/env python3
"""CLI entrypoint for `make n8n-sync` — imports/updates + activates n8n/workflows/*.json via
n8n's Public REST API. Synced in dependency order so each workflow's real n8n-assigned ID can be
patched into whichever other committed JSON references it as a placeholder (the real ID isn't
known until n8n creates the workflow): WF-3, WF-4, and WF-5 have no dependencies; WF-2 references
WF-3; WF-1 references both WF-2 and WF-3."""

import json
import os
import sys
from pathlib import Path

import httpx

WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / "n8n" / "workflows"
IMPORT_FIELDS = {"name", "nodes", "connections", "settings"}


def _client() -> httpx.Client:
    """Build an httpx client authenticated against n8n's Public REST API."""
    base_url = os.environ.get("N8N_API_URL", "http://localhost:5678")
    api_key = os.environ.get("N8N_API_KEY")
    if not api_key:
        print("N8N_API_KEY is not set — export it or run via `make n8n-sync`.", file=sys.stderr)
        raise SystemExit(1)
    return httpx.Client(
        base_url=f"{base_url}/api/v1",
        headers={"X-N8N-API-KEY": api_key, "Content-Type": "application/json"},
        timeout=30,
    )


def _find_by_name(client: httpx.Client, name: str) -> dict | None:
    """Page through n8n's /workflows list to find an existing workflow by exact name."""
    cursor = None
    while True:
        params = {"limit": 250}
        if cursor:
            params["cursor"] = cursor
        response = client.get("/workflows", params=params)
        response.raise_for_status()
        payload = response.json()
        for workflow in payload.get("data", []):
            if workflow.get("name") == name:
                return workflow
        cursor = payload.get("nextCursor")
        if not cursor:
            return None


def _sync_one(client: httpx.Client, raw_text: str) -> dict:
    """Create-or-update one workflow from its JSON text, then attempt to activate it."""
    full = json.loads(raw_text)
    body = {key: full[key] for key in IMPORT_FIELDS}

    existing = _find_by_name(client, body["name"])
    if existing:
        response = client.put(f"/workflows/{existing['id']}", json=body)
    else:
        response = client.post("/workflows", json=body)
    response.raise_for_status()
    workflow = response.json()

    # Creation/update succeeds even with unresolved credentials or a bad trigger config —
    # activation is where n8n actually validates those (wiki/gotchas.md #16). Catching this
    # per-workflow (rather than letting it crash the whole sync) keeps partial progress visible:
    # a workflow that's created-but-inactive still shows up in the printed result below.
    try:
        activate_response = client.post(f"/workflows/{workflow['id']}/activate")
        activate_response.raise_for_status()
        active = activate_response.json()["active"]
        detail = None
    except httpx.HTTPStatusError as exc:
        active = False
        detail = exc.response.json().get("message", exc.response.text)

    return {"name": workflow["name"], "id": workflow["id"], "active": active, "detail": detail}


def _report(result: dict) -> None:
    """One human-readable line per workflow; the raw n8n response detail only on failure."""
    if result["active"]:
        print(f"{result['name']}: imported, activated")
    else:
        print(
            f"{result['name']}: imported, ACTIVATION FAILED — {result['detail']}", file=sys.stderr
        )


def main() -> int:
    """Sync all 5 workflows in dependency order, patching placeholder IDs as they're created."""
    with _client() as client:
        wf3_result = _sync_one(
            client, (WORKFLOWS_DIR / "wf3_hitl.json").read_text(encoding="utf-8")
        )
        _report(wf3_result)

        wf4_result = _sync_one(
            client, (WORKFLOWS_DIR / "wf4_sla_watchdog.json").read_text(encoding="utf-8")
        )
        _report(wf4_result)

        wf5_result = _sync_one(
            client, (WORKFLOWS_DIR / "wf5_daily_digest.json").read_text(encoding="utf-8")
        )
        _report(wf5_result)

        wf2_raw = (WORKFLOWS_DIR / "wf2_draft_answer.json").read_text(encoding="utf-8")
        wf2_raw = wf2_raw.replace("WF3_WORKFLOW_ID_PLACEHOLDER", wf3_result["id"])
        wf2_result = _sync_one(client, wf2_raw)
        _report(wf2_result)

        wf1_raw = (WORKFLOWS_DIR / "wf1_intake_triage.json").read_text(encoding="utf-8")
        wf1_raw = wf1_raw.replace("WF2_WORKFLOW_ID_PLACEHOLDER", wf2_result["id"])
        wf1_raw = wf1_raw.replace("WF3_WORKFLOW_ID_PLACEHOLDER", wf3_result["id"])
        wf1_result = _sync_one(client, wf1_raw)
        _report(wf1_result)

    results = [wf1_result, wf2_result, wf3_result, wf4_result, wf5_result]
    if not all(r["active"] for r in results):
        print("One or more workflows failed to activate.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
