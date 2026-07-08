"""Prompt loading for the RAG service — prompts live in version-controlled files."""

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Prompts are version-controlled files, never inline strings (AGENTS.md)."""
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
