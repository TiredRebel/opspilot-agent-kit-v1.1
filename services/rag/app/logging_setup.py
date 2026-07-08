"""Structured logging for the RAG service — stdlib only, single-line key=value records.

Named `logging_setup` (not `logging`) so it can't shadow the stdlib module inside the package.
Only the `app` logger namespace is configured; uvicorn's own loggers are untouched
(`propagate = False` keeps app records off the root logger, so uvicorn/root handlers can't
double-print them)."""

import logging
import sys

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def setup_logging(level: str = "INFO") -> None:
    """Configure the `app` logger namespace. Idempotent — the FastAPI lifespan runs once per
    process in production but once per TestClient context in tests, so a second call only
    re-applies the level instead of stacking duplicate handlers."""
    logger = logging.getLogger("app")
    logger.setLevel(level.upper())
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_FORMAT))
        logger.addHandler(handler)
        logger.propagate = False


def kv(msg: str, **keys) -> str:
    """Render `msg` plus `key=value` pairs for structured, greppable log lines. None-valued
    keys are omitted (e.g. a missing ticket_id) rather than printed as `key=None`."""
    parts = [msg] + [f"{key}={value}" for key, value in keys.items() if value is not None]
    return " ".join(parts)
