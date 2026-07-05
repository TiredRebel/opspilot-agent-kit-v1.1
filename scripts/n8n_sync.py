#!/usr/bin/env python3
"""CLI entrypoint for `make n8n-sync` — imports/updates + activates n8n/workflows/*.json via
n8n's Public REST API. WF-2 is synced first so its real n8n-assigned workflow ID can be patched
into WF-1's Execute Workflow node (the committed JSON carries a placeholder — the real ID isn't
known until n8n creates the workflow)."""

import json
import os
import sys
from pathlib import Path

import httpx

WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / "n8n" / "workflows"
IMPORT_FIELDS = {"name", "nodes", "connections", "settings"}


def _client() -> httpx.Client:
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
    full = json.loads(raw_text)
    body = {key: full[key] for key in IMPORT_FIELDS}

    existing = _find_by_name(client, body["name"])
    if existing:
        response = client.put(f"/workflows/{existing['id']}", json=body)
    else:
        response = client.post("/workflows", json=body)
    response.raise_for_status()
    workflow = response.json()

    try:
        activate_response = client.post(f"/workflows/{workflow['id']}/activate")
        activate_response.raise_for_status()
        active = activate_response.json()["active"]
        detail = None
    except httpx.HTTPStatusError as exc:
        active = False
        detail = exc.response.json().get("message", exc.response.text)

    return {"name": workflow["name"], "id": workflow["id"], "active": active, "detail": detail}


def main() -> int:
    wf2_path = WORKFLOWS_DIR / "wf2_draft_answer.json"
    wf1_path = WORKFLOWS_DIR / "wf1_intake_triage.json"

    with _client() as client:
        wf2_result = _sync_one(client, wf2_path.read_text(encoding="utf-8"))
        print(wf2_result)

        wf1_raw = wf1_path.read_text(encoding="utf-8")
        wf1_raw = wf1_raw.replace("WF2_WORKFLOW_ID_PLACEHOLDER", wf2_result["id"])
        wf1_result = _sync_one(client, wf1_raw)
        print(wf1_result)

    if not (wf1_result["active"] and wf2_result["active"]):
        print("One or more workflows failed to activate.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
