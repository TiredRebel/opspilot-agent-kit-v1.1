## Context

`pyproject.toml`'s `[tool.ruff.lint]` currently selects `E, F, I, UP, B` — no `D` (pydocstyle)
rules, so ruff has never enforced docstring presence in this repo. A direct AST scan (not ruff,
since it can't check what isn't selected) found the actual gap:

| Location | Missing module docstrings | Missing function/class docstrings |
|---|---|---|
| `services/rag/app/` | 2 (`__init__.py`, `settings.py`) | 23 (mostly `llm.py`'s private `_`-prefixed helpers, `main.py`'s handlers, `schemas.py`'s Pydantic models) |
| `evals/` | 0 | 5 |
| `scripts/` | 0 | 5 |
| `services/rag/tests/` | not scanned for this change | out of scope — see Non-Goals |

`ruff check .` and `ruff format --check .` both pass cleanly today under the current rule set —
this change is purely additive documentation plus a config change to lock the new bar in.

## Goals / Non-Goals

**Goals:**
- Every module, public function/class, and private (`_`-prefixed) helper in
  `services/rag/app/`, `evals/`, and `scripts/` has a docstring.
- `ruff`'s config enforces this going forward via `D` rules, tuned to the codebase's existing
  docstring style rather than forcing a rewrite of already-good docstrings.
- Zero behavior change — this is documentation and lint config only.

**Non-Goals:**
- Not touching `services/rag/tests/test_*.py` test function bodies — pytest test names are
  already the documentation (`test_confidence_boundary_exactly_070`, etc.); adding docstrings to
  every test would be noise without informational value, consistent with this project's existing
  no-comments-unless-non-obvious convention (`CLAUDE.md`). `ruff`'s per-file-ignores will exempt
  `services/rag/tests/**` and `evals/test_*.py` from the new `D` rules for the same reason (test
  function docstrings restate the test name, not a hidden contract).
- Not adopting full Google/NumPy-style multi-section docstrings project-wide — the codebase's
  existing convention (short one-liners, longer prose only where the "why" is genuinely
  non-obvious, as seen in `llm.py`'s existing docstrings on `_embed`, `_call_ollama`, etc.) is kept
  as the standard; new docstrings match that style rather than introducing a heavier format.
- Not running a full PEP 8 line-by-line manual audit beyond what `ruff format --check`/`ruff
  check` already enforce — `ruff` already covers PEP 8 (line length, import order, etc.) via its
  `E`/`I` rule families; re-deriving that by hand would be redundant with tooling already in CI.
- Not touching `.venv`/vendored code (obviously) or any non-Python file.

## Decisions

**1. Enable `D` rules in `ruff`, but scope via `ignore` to match existing style, not rewrite it.**
Specifically: enable the `D` rule family for presence-checking (`D100`-`D103` module/class/
function/method docstring-missing checks), but add `ignore = ["D203", "D213", ...]` as needed to
avoid ruff fighting the project's already-consistent one-blank-line-after-summary style. Exact
ignore list finalized during implementation by running `ruff check --select D` and reading what it
actually flags stylistically (not just presence) — over-specifying a lint config on paper before
seeing real output tends to guess wrong.

**2. Per-file-ignores for `services/rag/tests/**` and `evals/test_*.py`** to exempt test functions
from `D` entirely (rationale in Non-Goals). `evals/conftest.py` fixtures and `scripts/*.py` are
NOT exempted — they're not tests, they're shared infrastructure/CLI entry points that benefit from
documentation like any other module code.

**3. Docstring content, one line by default.** For simple functions (most private `_helper`s,
Pydantic response/request models in `schemas.py`), a single-line docstring stating what the
function returns or what the model represents is enough — matching e.g. the existing
`_anthropic_client`-style one-liners already in the file for functions that do have docstrings.
Multi-line docstrings are reserved for functions where a hidden constraint or non-obvious behavior
already justified a comment (several already exist in `llm.py`, e.g. `_call_ollama`'s explanation
of `max_tokens=8192`) — those stay as-is, this change doesn't touch them.

## Risks / Trade-offs

- **[Risk]** Enabling `D` rules broadly could flag stylistic issues unrelated to "missing
  docstring" (e.g. `D200`/`D205` formatting nitpicks) across otherwise-fine existing docstrings,
  creating unplanned churn. → **Mitigation**: implementation step explicitly runs `ruff check
  --select D` first to see the *actual* flagged set before deciding the final `ignore` list, rather
  than guessing upfront (see Decision 1).
- **[Risk]** Docstrings added purely to satisfy a lint rule can become restating-the-obvious noise
  (working against this project's own stated no-comments-unless-non-obvious philosophy in
  `CLAUDE.md`). → **Mitigation**: Decision 3 keeps additions to one honest line describing purpose/
  return value, not padded prose — satisfies "every symbol has a docstring" without violating the
  "don't explain WHAT when the name already does" principle for the docstring's *content*.

## Migration Plan

Purely additive — docstrings are added, one new `ruff` rule family is enabled with tuned
`ignore`s. No runtime behavior, API, or schema changes. Rollback is a plain revert if the new `D`
rule set ever proves too noisy in a future PR (unlikely given it's tuned against real output first).

## Open Questions

- Exact `D`-rule `ignore` list is intentionally left to be finalized against real `ruff check
  --select D` output during implementation rather than specified here — see Decision 1.
