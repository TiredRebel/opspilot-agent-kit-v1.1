#!/usr/bin/env python3
"""CLI entrypoint for `make seed` — triggers POST /kb/ingest on the running rag-api service."""

import os
import sys

import httpx


def main() -> int:
    """POST /kb/ingest on the running rag-api and print the resulting document/chunk counts."""
    port = os.environ.get("RAG_API_PORT", "8010")
    url = f"http://localhost:{port}/kb/ingest"
    try:
        response = httpx.post(url, timeout=120)
    except httpx.ConnectError:
        print(f"Could not reach {url} — is `docker compose up -d` running?", file=sys.stderr)
        return 1
    response.raise_for_status()
    print(response.json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
