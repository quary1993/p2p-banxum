SHELL := /bin/bash

PYTHON_VERSION ?= 3.12
UV ?= uv
NPM ?= npm
COMPOSE ?= docker compose
TEST ?=
MIGRATION_CHECK_DATABASE_URL ?= sqlite:///:memory:
POSTGRES_TEST_DATABASE_URL ?= postgres://banxum:banxum@localhost:5432/banxum
POSTGRES_HARDENING_TEST ?= backend/apps/platform_core/tests/test_postgres_hardening.py

.PHONY: setup up down test test-backend test-backend-postgres test-postgres-hardening test-ledger test-frontend lint lint-backend lint-frontend lint-imports typecheck typecheck-backend typecheck-frontend migrate migration-check migration-check-postgres seed bootstrap-superadmin api-schema api-client check-generated check-scheduled-jobs agent-check backend-run frontend-run docker-build frontend-build

setup:
	$(UV) sync --python $(PYTHON_VERSION) --group dev
	cd frontend && $(NPM) install

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

backend-run:
	$(UV) run python backend/manage.py runserver 0.0.0.0:8000

frontend-run:
	cd frontend && $(NPM) run dev -- --host 0.0.0.0

test: test-backend test-frontend

test-backend:
	$(UV) run pytest $(if $(TEST),$(TEST),backend)

test-backend-postgres:
	DATABASE_URL="$(POSTGRES_TEST_DATABASE_URL)" $(UV) run pytest $(if $(TEST),$(TEST),backend)

test-postgres-hardening:
	DATABASE_URL="$(POSTGRES_TEST_DATABASE_URL)" $(UV) run pytest $(POSTGRES_HARDENING_TEST)

test-ledger:
	$(UV) run pytest backend/apps/ledger/tests

test-frontend:
	cd frontend && $(NPM) run test -- --run

lint: lint-backend lint-frontend

lint-backend:
	$(UV) run ruff check backend

lint-frontend:
	cd frontend && $(NPM) run lint

lint-imports:
	$(UV) run lint-imports

typecheck: typecheck-backend typecheck-frontend

typecheck-backend:
	$(UV) run mypy backend

typecheck-frontend:
	cd frontend && $(NPM) run typecheck

migrate:
	$(UV) run python backend/manage.py migrate

migration-check:
	DATABASE_URL="$(MIGRATION_CHECK_DATABASE_URL)" $(UV) run python backend/manage.py makemigrations --check --dry-run

migration-check-postgres:
	DATABASE_URL="$(POSTGRES_TEST_DATABASE_URL)" $(UV) run python backend/manage.py makemigrations --check --dry-run

seed:
	$(UV) run python backend/manage.py seed_demo

bootstrap-superadmin:
	$(UV) run python backend/manage.py bootstrap_superadmin

check-scheduled-jobs:
	$(UV) run python backend/manage.py check_scheduled_jobs

api-schema:
	mkdir -p openapi
	$(UV) run python backend/manage.py spectacular --file openapi/schema.yaml --validate

api-client:
	cd frontend && $(NPM) run api:generate

check-generated:
	@before=$$(mktemp); after=$$(mktemp); \
	trap 'rm -f "$$before" "$$after"' EXIT; \
	git diff --no-ext-diff HEAD -- openapi/schema.yaml frontend/src/api/generated > "$$before"; \
	$(MAKE) api-schema; \
	$(MAKE) api-client; \
	git diff --no-ext-diff HEAD -- openapi/schema.yaml frontend/src/api/generated > "$$after"; \
	diff -u "$$before" "$$after"

frontend-build:
	cd frontend && $(NPM) run build

docker-build:
	$(COMPOSE) build backend frontend

agent-check: lint lint-imports typecheck migration-check test check-generated frontend-build
