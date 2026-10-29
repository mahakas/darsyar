.PHONY: help lock up down restart logs ps health migrate revision seed-admin seed-plans test test-db coverage eval lint typecheck fmt dev-backend dev-frontend shell-db shell-backend clean smoke

help:
	@printf '%s\n' 'Darsyar v4 targets: lock up down restart logs ps health migrate revision seed-admin seed-plans test test-db coverage eval lint typecheck fmt dev-backend dev-frontend shell-db shell-backend clean smoke'

# Phase 0: generate genuine lockfiles from configured registries; never hand-write them.
lock:
	cd backend && uv lock && uv sync --locked --extra dev
	cd frontend && npm install --package-lock-only
	cd frontend && npm ci

up:
	docker compose up --build -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps -a

health:
	@docker compose ps -a --format json | python scripts/check_compose_health.py

migrate:
	docker compose run --rm migrate

revision:
	@test -n "$(message)" || (echo 'Usage: make revision message=add_table_name' && exit 2)
	cd backend && uv run --locked alembic revision --autogenerate -m "$(message)"

seed-admin:
	cd backend && uv run --locked python -m app.scripts.seed_admin

seed-plans:
	@echo 'BLOCKED: plan seed is implemented after approved pricing/accounting design.'; exit 2

test:
	cd backend && uv run --locked --extra dev pytest -q

test-db:
	python scripts/run_test_db.py

coverage:
	cd backend && uv run --locked --extra dev pytest --cov=app --cov-report=term-missing --cov-fail-under=70

eval:
	@echo 'BLOCKED: golden dataset and RAG implementation are phase 4/5 deliverables; do not fabricate scores.'; exit 2

lint:
	cd backend && uv run --locked --extra dev ruff check .
	cd frontend && npm run lint

typecheck:
	cd backend && uv run --locked --extra dev mypy app
	cd frontend && npm run typecheck

fmt:
	cd backend && uv run --locked --extra dev ruff format .
	cd frontend && npm run lint -- --fix

dev-backend:
	cd backend && uv run --locked uvicorn app.main:app --reload

dev-frontend:
	cd frontend && npm run dev

shell-db:
	docker compose exec postgres sh -ec 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

shell-backend:
	docker compose exec api sh

smoke:
	uv run --directory backend --locked python ../scripts/smoke_test.py

clean:
	docker compose down --remove-orphans
