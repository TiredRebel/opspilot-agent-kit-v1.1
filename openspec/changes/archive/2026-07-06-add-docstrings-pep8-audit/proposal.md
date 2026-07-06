## Why

An audit of the project's Python files found real gaps: `ruff check`/`ruff format --check` both
pass cleanly today (the configured rule set — `E, F, I, UP, B` — has no docstring rules enabled),
but a direct AST scan found **23 functions/classes and 2 modules** missing docstrings across
`services/rag/app/`, plus 9 more across `evals/` and `scripts/`. Nothing currently enforces
docstring presence or checks against the fuller PEP 257/PEP 8 docstring conventions, so this has
drifted silently. This is a documentation-completeness pass, not a bug fix — done now while the
codebase is small enough (21 non-test files) to close the gap in one pass rather than let it grow.

## What Changes

- Add module-level docstrings to the 2 files missing one (`services/rag/app/__init__.py`,
  `services/rag/app/settings.py`).
- Add docstrings to the 23 functions/classes in `services/rag/app/` currently missing one
  (concentrated in `llm.py`, `main.py`, `schemas.py`) — one-line docstrings for simple
  functions/Pydantic models, fuller ones only where a function's contract isn't obvious from its
  signature and existing inline comments.
- Add docstrings to the 9 functions missing one in `evals/` and `scripts/`.
- Add `D` (pydocstyle) rules to `ruff`'s lint config, scoped to enforce presence going forward
  without relitigating existing docstring *style* choices already in the codebase (e.g. the
  existing multi-paragraph docstrings in `llm.py` stay as-is).
- Confirm `ruff check .` and `ruff format --check .` both still pass after the new rule is added
  and gaps are closed (they already pass on the current rule set — this locks in the new bar).
- **No behavior changes** — this is docstrings and lint config only, no logic edits.

## Capabilities

### New Capabilities
- `code-documentation-standards`: defines which Python files/symbols in this repo require
  docstrings and what `ruff` enforces for it going forward.

### Modified Capabilities
(none — no existing product-behavior specs change)

## Impact

- **Code**: docstring additions only, across `services/rag/app/{__init__,settings,llm,main,
  schemas}.py`, `evals/{conftest,test_classify,test_grounding}.py`,
  `scripts/{ingest,n8n_sync}.py`. No changes to `services/rag/tests/` (test functions are exempt —
  see design.md).
- **Config**: `pyproject.toml`'s `[tool.ruff.lint]` `select` list gains `D` rules (scoped further
  via `ignore`/per-file-ignores to avoid churn on already-acceptable docstring styles).
- **CI**: `.github/workflows/ci.yml`'s existing `ruff check` step in the `test` job will now also
  catch missing docstrings on future changes — no new CI step needed, this rides the existing one.
- **Downstream**: none — no API/behavior contracts change.
