"""Tests owed by fix-wf1-telegram-trigger (#14) — docs/TESTPLAN.md M8.

The script lives outside the `app` package, so it is loaded by file path. All docker
interaction is faked; these tests never touch a real container.
"""

import importlib.util
import subprocess
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "set_n8n_webhook_url.py"
_spec = importlib.util.spec_from_file_location("set_n8n_webhook_url", _SCRIPT)
set_webhook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(set_webhook)


class FakeDocker:
    """Stands in for subprocess.run; simulates the container's env file."""

    def __init__(self, existing="", fail_write=False):
        self.existing = existing
        self.fail_write = fail_write
        self.written = None
        self.restarted = False

    def run(self, cmd, **kwargs):
        if cmd[:2] == ["docker", "exec"] and cmd[3:] == ["cat", set_webhook.CONTAINER_ENV]:
            return subprocess.CompletedProcess(cmd, 0, stdout=self.existing, stderr="")
        if cmd[:2] == ["docker", "exec"] and cmd[3] == "sh":
            if self.fail_write:
                raise subprocess.CalledProcessError(1, cmd)
            self.written = cmd[5]
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:2] == ["docker", "restart"]:
            self.restarted = True
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        raise AssertionError(f"unexpected command: {cmd}")


def test_missing_webhook_url_fails_without_touching_docker(monkeypatch, capsys):
    monkeypatch.delenv("WEBHOOK_URL", raising=False)
    fake = FakeDocker()
    monkeypatch.setattr(set_webhook.subprocess, "run", fake.run)

    assert set_webhook.main() == 1
    assert "WEBHOOK_URL is not set" in capsys.readouterr().err
    assert fake.written is None
    assert fake.restarted is False


def test_happy_path_writes_url_and_restarts(monkeypatch):
    monkeypatch.setenv("WEBHOOK_URL", "https://example.ngrok.app")
    fake = FakeDocker(existing="N8N_HOST=localhost\n")
    monkeypatch.setattr(set_webhook.subprocess, "run", fake.run)

    assert set_webhook.main() == 0
    assert "WEBHOOK_URL=https://example.ngrok.app" in fake.written
    assert fake.restarted is True


def test_existing_key_is_replaced_and_other_lines_survive(monkeypatch):
    monkeypatch.setenv("WEBHOOK_URL", "https://new.ngrok.app")
    fake = FakeDocker(existing="WEBHOOK_URL=https://old.ngrok.app\nN8N_HOST=localhost\n")
    monkeypatch.setattr(set_webhook.subprocess, "run", fake.run)

    assert set_webhook.main() == 0
    assert fake.written.count("WEBHOOK_URL=") == 1
    assert "WEBHOOK_URL=https://new.ngrok.app" in fake.written
    assert "https://old.ngrok.app" not in fake.written
    assert "N8N_HOST=localhost" in fake.written


def test_http_url_warns_but_proceeds(monkeypatch, capsys):
    monkeypatch.setenv("WEBHOOK_URL", "http://insecure.example")
    fake = FakeDocker()
    monkeypatch.setattr(set_webhook.subprocess, "run", fake.run)

    assert set_webhook.main() == 0
    assert "Telegram requires HTTPS" in capsys.readouterr().err
    assert fake.restarted is True


def test_container_write_failure_returns_error(monkeypatch, capsys):
    monkeypatch.setenv("WEBHOOK_URL", "https://example.ngrok.app")
    fake = FakeDocker(fail_write=True)
    monkeypatch.setattr(set_webhook.subprocess, "run", fake.run)

    assert set_webhook.main() == 1
    assert "Could not write" in capsys.readouterr().err
    assert fake.restarted is False
