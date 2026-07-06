## 1. Baseline

- [x] 1.1 Run `ruff check --select D .` (D rules not yet enabled in config) against the repo to get the real, current list of docstring gaps and any incidental style flags — use this as ground truth instead of the AST-scan estimate from the proposal. **Result:** 104 total flags, but `D100-D104` (presence) rules only fire on public symbols by default — private `_`-helpers are never flagged by ruff's `D` rules, confirming those need to be added manually rather than lint-enforced. Style rules `D205`/`D209`/`D401` also fired 56 times combined on existing/new docstrings — these are excluded from the enabled set per design.md Decision 1 (avoid rewriting already-accepted style).

## 2. Docstrings — services/rag/app/

- [x] 2.1 Add module docstrings to `services/rag/app/__init__.py` and `services/rag/app/settings.py`.
- [x] 2.2 Add docstrings to the missing symbols in `services/rag/app/llm.py` (`LLMResult`, `_cost`, `_log`, `_check_budget`, `_fake_embedding`, `_fake_result`, `_anthropic_client`, `_openai_client`, `_call_openai_embed`, `_is_retryable`, `_complete_gemini`, `_complete_chat`, `complete`).
- [x] 2.3 Add docstrings to the missing symbols in `services/rag/app/main.py` (`lifespan`, `budget_exceeded_handler`, `summarize`).
- [x] 2.4 Add docstrings to the 8 Pydantic model classes in `services/rag/app/schemas.py` (`ClassifyRequest`, `ClassifyResponse`, `QueryRequest`, `QueryResponse`, `IngestResponse`, `SummarizeRequest`, `SummarizeResponse`, `StatsResponse`).

## 3. Docstrings — evals/ and scripts/

- [x] 3.1 Add docstrings to `evals/conftest.py`'s `_use_localhost_database` and the two non-test helpers in `evals/test_classify.py`/`evals/test_grounding.py` (`_load_tickets`, `_chunk_content`) — leave the `test_*` functions themselves undocumented per the test exemption.
- [x] 3.2 Add docstrings to `scripts/ingest.py`'s `main` and `scripts/n8n_sync.py`'s `_client`, `_find_by_name`, `_sync_one`, `main`.

## 4. Lint config

- [x] 4.1 Add the `D` rule family to `[tool.ruff.lint].select` in `pyproject.toml`, plus `ignore`/`per-file-ignores` entries tuned against the real `ruff check --select D` output from task 1.1 (not guessed upfront). **Refinement vs. design.md:** selected the specific presence codes (`D100-D104`) directly rather than the blanket `D` prefix — task 1.1's real output showed `D` also pulls in `D205`/`D209`/`D401` (stylistic) and the `D203`/`D213` ruff auto-resolves with a warning; selecting only the presence codes gets the same enforcement (spec requirement) without an `ignore` list or the extra warning noise.
- [x] 4.2 Add a `per-file-ignores` entry exempting `services/rag/tests/**` and `evals/test_*.py` from the `D` rules.

## 5. Verification

- [x] 5.1 Run `ruff check .` and `ruff format --check .` — both SHALL pass with zero violations. **Result:** both clean on the first try — no reformatting needed for any added docstring.
- [x] 5.2 Run `make test` — 18/18 SHALL still pass (docstring-only changes, no logic touched). **Result:** 18/18 green, no regressions.
- [x] 5.3 Update `PROGRESS.md` and `wiki/log.md` with a session entry noting the docstring audit and the new `D`-rule lint baseline.
