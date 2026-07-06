.PHONY: up down seed n8n-sync lint test evals backup

up:
	docker compose up -d

down:
	docker compose down

seed:
	uv run scripts/ingest.py

n8n-sync:
	set -a; . ./.env; set +a; uv run scripts/n8n_sync.py

lint:
	uv run ruff format --check .
	uv run ruff check .

test:
	uv run pytest services/rag/tests

evals:
	uv run pytest evals -m evals -s

backup:
	@echo "make backup: not implemented yet — see P6-2 (scripts/backup.sh)"
