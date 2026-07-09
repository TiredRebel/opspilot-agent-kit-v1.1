#!/usr/bin/env python3
"""CLI helper to persist N8N_WEBHOOK_URL in the existing n8n container.

Why this exists: n8n's Telegram Trigger node needs a public URL at activation time
so it can call Telegram setWebhook. That URL is read from the container's
environment (`WEBHOOK_URL` / `N8N_HOST`); if it is missing or wrong, the node
appears broken and the workflow cannot activate (gotcha #50). The existing
`n8n-n8n-1` container was started before this project existed, so its env block
does not include `WEBHOOK_URL`. Re-creating the container risks losing the
encryption key and invalidating credentials; writing the value into
`/home/node/.n8n/.env` inside the container and restarting it is the least
invasive fix.

Reads `WEBHOOK_URL` from `.env` and writes it into the container's env file.
If a tunnel helper (ngrok/cloudflared) is running, the user should set
`WEBHOOK_URL` in `.env` to its public HTTPS URL before running this script.
"""

import subprocess
import sys
from pathlib import Path

ENV_FILE = Path(".env")
CONTAINER_ENV = "/home/node/.n8n/.env"
CONTAINER = "n8n-n8n-1"


def _dotenv_value(path: Path, key: str) -> str | None:
    """Read a single key from a KEY=VALUE file, skipping comments."""
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line[len(key) + 1 :].strip()
    return None


def _container_env_lines() -> list[str]:
    """Return the current contents of n8n's in-container .env, or empty list."""
    result = subprocess.run(
        ["docker", "exec", CONTAINER, "cat", CONTAINER_ENV],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return []
    return result.stdout.splitlines()


def _update_container_env(key: str, value: str) -> None:
    """Replace or append the key=value line in the container's .env file."""
    lines = _container_env_lines()
    prefix = f"{key}="
    new_lines = [line for line in lines if not line.startswith(prefix)]
    new_lines.append(f"{key}={value}")
    payload = "\n".join(new_lines) + "\n"
    # Use a heredoc via sh -c so we do not need to quote the whole file for a single echo.
    subprocess.run(
        [
            "docker",
            "exec",
            CONTAINER,
            "sh",
            "-c",
            f"cat > {CONTAINER_ENV} <<'EOF'\n{payload}EOF\n",
        ],
        check=True,
    )


def main() -> int:
    """Persist WEBHOOK_URL in n8n and restart the container."""
    url = _dotenv_value(ENV_FILE, "WEBHOOK_URL")
    if not url:
        print(
            "WEBHOOK_URL is not set in .env — set it to the public HTTPS URL "
            "(e.g. your ngrok endpoint) and re-run.",
            file=sys.stderr,
        )
        return 1

    if not url.startswith("https://"):
        print(
            f"WARNING: WEBHOOK_URL is '{url}'. Telegram requires HTTPS; "
            "http:// will fail setWebhook.",
            file=sys.stderr,
        )

    try:
        _update_container_env("WEBHOOK_URL", url)
    except subprocess.CalledProcessError as exc:
        print(f"Could not write {CONTAINER_ENV} in {CONTAINER}: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote WEBHOOK_URL={url} to {CONTAINER}:{CONTAINER_ENV}")

    try:
        subprocess.run(["docker", "restart", CONTAINER], check=True)
    except subprocess.CalledProcessError as exc:
        print(f"Could not restart {CONTAINER}: {exc}", file=sys.stderr)
        return 1

    print(f"Restarted {CONTAINER}. Wait ~10s for health, then run `make n8n-sync`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
