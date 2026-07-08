## ADDED Requirements

### Requirement: Ollama provider default model SHALL be justified by an eval comparison
The `OLLAMA_MODEL` default configured in `.env`/`.env.example` SHALL be the option with the best
recorded `evals/test_classify.py` accuracy among models actually tested, with that comparison
documented in `wiki/gotchas.md`.

#### Scenario: A new candidate model is tested
- **WHEN** a new Ollama model (local or cloud) is evaluated against `evals/test_classify.py`
- **THEN** the result (accuracy, and confusion summary if available) SHALL be recorded in
  `wiki/gotchas.md`'s model-comparison entries, regardless of whether it becomes the new default

#### Scenario: A tested candidate beats the current default
- **WHEN** a newly tested model's accuracy exceeds the current `OLLAMA_MODEL` default's recorded
  accuracy
- **THEN** `.env`'s `OLLAMA_MODEL` SHALL be updated to the new candidate, and `PROGRESS.md`'s
  P5-2 entry SHALL reflect the new baseline

#### Scenario: A tested candidate does not beat the current default
- **WHEN** a newly tested model's accuracy is equal to or worse than the current default's
  recorded accuracy
- **THEN** the current default SHALL remain unchanged, and the result SHALL still be recorded as
  a negative data point (per the first scenario) rather than left undocumented
