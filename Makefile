.PHONY: install dev test lint migrate seed db-up db-down down logs api-run

## ── Backend (apps/api) ──────────────────────────────────────────
install:
	cd apps/api && uv venv && uv pip install -e ".[dev]"

dev:
	cd apps/api && uv run uvicorn app.main:app --reload --port 8000

test:
	cd apps/api && uv run pytest -v

lint:
	cd apps/api && uv run ruff check .

typecheck:
	cd apps/api && uv run mypy app

migrate:
	cd apps/api && uv run alembic upgrade head

seed:
	cd apps/api && uv run python -m app.db.seed

## ── Infra (docker compose) ──────────────────────────────────────
db-up:
	docker compose up -d db redis minio

db-down:
	docker compose down

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f api
