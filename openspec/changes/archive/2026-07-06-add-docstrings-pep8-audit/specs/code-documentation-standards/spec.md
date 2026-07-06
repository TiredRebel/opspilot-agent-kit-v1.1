## ADDED Requirements

### Requirement: Application and script modules SHALL have docstrings
Every Python module under `services/rag/app/`, `evals/`, and `scripts/` SHALL have a module-level
docstring, except `services/rag/tests/` and `evals/test_*.py` test modules (see the test-code
exemption requirement below).

#### Scenario: A module is missing a docstring
- **WHEN** a file under `services/rag/app/`, `evals/`, or `scripts/` (excluding test modules) has
  no module-level docstring
- **THEN** `ruff check .` SHALL report a `D100`-family violation for that file

### Requirement: Public and private functions/classes SHALL have docstrings
Every function, async function, and class defined in `services/rag/app/`, `evals/` (excluding test
functions), and `scripts/` SHALL have a docstring — including private (`_`-prefixed) helpers.

#### Scenario: A function or class is missing a docstring
- **WHEN** a function, async function, or class in an in-scope module has no docstring
- **THEN** `ruff check .` SHALL report a `D101`/`D102`/`D103`-family violation for it

#### Scenario: A docstring exists but is redundant boilerplate
- **WHEN** a docstring is added solely to satisfy the lint rule
- **THEN** it SHALL be a single accurate line describing purpose or return value, matching the
  concise style already used elsewhere in the codebase, not multi-paragraph filler

### Requirement: Test code is exempt from mandatory docstrings
Test functions in `services/rag/tests/**` and `evals/test_*.py` SHALL be exempt from the
docstring-presence rule, since descriptive test names already serve as documentation.

#### Scenario: A test function has no docstring
- **WHEN** a function in `services/rag/tests/**` or `evals/test_*.py` has no docstring
- **THEN** `ruff check .` SHALL NOT report a docstring-missing violation for it (covered by a
  `per-file-ignores` entry in `pyproject.toml`)

### Requirement: ruff SHALL enforce docstring presence going forward
`pyproject.toml`'s `[tool.ruff.lint]` configuration SHALL include the pydocstyle (`D`) rule family
for docstring-presence checks, tuned with an `ignore`/`per-file-ignores` list so it does not flag
the codebase's existing accepted docstring style as non-compliant.

#### Scenario: CI runs ruff after this change
- **WHEN** `make lint` (or CI's `ruff check`/`ruff format --check` step) runs against the
  repository after this change is applied
- **THEN** it SHALL pass with zero violations, and any future PR that omits a required docstring
  SHALL fail this same check
