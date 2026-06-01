SHELL := /bin/bash

PYTHON_VERSION ?= 3.12
UV ?= uv
NPM ?= npm
COMPOSE ?= docker compose
TEST ?=

.PHONY: setup up down test test-backend test-frontend lint lint-backend lint-frontend lint-imports typecheck typecheck-backend typecheck-frontend migrate migration-check seed api-schema api-client check-generated agent-check backend-run frontend-run docker-build frontend-build

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
	$(UV) run python backend/manage.py makemigrations --check --dry-run

seed:
	$(UV) run python backend/manage.py seed_demo

api-schema:
	mkdir -p openapi
	$(UV) run python backend/manage.py spectacular --file openapi/schema.yaml --validate

api-client:
	cd frontend && $(NPM) run api:generate

check-generated: api-schema api-client
	git diff --exit-code openapi/schema.yaml frontend/src/api/generated

frontend-build:
	cd frontend && $(NPM) run build

docker-build:
	$(COMPOSE) build backend frontend

agent-check: lint lint-imports typecheck migration-check test check-generated frontend-build
