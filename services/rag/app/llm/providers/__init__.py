"""Provider modules — one per `LLM_PROVIDER` value, registered in `app/llm/registry.py`.

Each module satisfies the `Provider` protocol (`app/llm/base.py`) with module-level `chat()`
and `embed()` coroutines. Raw-call functions (`_call_*`) keep their historical names so test
monkeypatch seams survive the package split unchanged."""
