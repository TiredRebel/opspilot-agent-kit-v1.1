.PHONY: up down seed lint test evals backup

up:
	docker compose up -d

down:
	docker compose down

seed:
	uv run scripts/ingest.py

lint:
	uv run ruff format --check .
	uv run ruff check .

test:
	uv run pytest services/rag/tests

evals:
	@echo "make evals: not implemented yet — see P5 (pytest -m evals)"

backup:
	@echo "make backup: not implemented yet — see P6-2 (scripts/backup.sh)"
