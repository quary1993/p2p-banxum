# BANXUM Agent Guide

This repository implements BANXUM, a Swiss P2P lending platform operated by Garanta Finanzgruppe AG. Treat the `/plan` folder and `IMPLEMENTATION_PLAN.md` as product requirements unless a newer decision is documented.

## Working Rules

- Read the relevant planning module before editing implementation files.
- Use `IMPLEMENTATION_PLAN.md` and `AGENTS.md` as the engineering source of truth. Do not create persistent audit reports, completed work-item files, or app-local README stubs; merge durable decisions into the canonical docs instead.
- Keep implementation slices narrow and module-owned.
- Put business mutations in services, not in Django model `save()` methods, serializers, views, or signals.
- Financial mutations must be append-only, transaction-safe, and covered by focused tests before handoff.
- Store money as integer minor units plus ISO currency. Use `Decimal` for rates and percentages. Never use floats for financial calculations.
- Use Europe/Zurich for business day-counting and UTC for stored timestamps.
- Generated OpenAPI schema and generated frontend API client files are committed artifacts. Regenerate them through `make api-schema` and `make api-client`.
- Do not manually edit generated files under `frontend/src/api/generated`.
- Do not commit secrets, local environment files, provider credentials, personal data, or production data.

## UI/UX Handoff Rule

When a task touches UI/UX, implement a practical first version that satisfies the documented behavior.

For user-facing/public/investor UI, record design-polish and UX follow-up items for Claude Design in `docs/claude-design/TODO.md`. Claude Design is expected to do a complete user-facing UI/UX pass before launch, covering public pages, onboarding, KYC handoff, investor portal, marketplace, investment flows, balance/FX/withdrawal flows, portfolio, documents, statements, account settings, support, and user-facing notifications/status states.

For admin console UI, do not hand UI/UX work to Claude Design. The admin console is designed and implemented by Codex during implementation, with follow-up items tracked in `docs/admin-console/TODO.md`. Admin screens should be dense, operational, restrained, auditable, and optimized for repeated internal work.

Each UI/UX TODO entry should include:

- Date.
- Screen or component.
- Current first-version behavior.
- Suggested improvement or required admin-console improvement.
- Priority: blocking polish, important, or nice-to-have.

Do not block backend or workflow implementation just because final visual design is pending, but do not leave UI/UX improvement ideas only in chat.

## Commands

- `make setup`: install backend and frontend dependencies.
- `make up`: start local dependency/app stack.
- `make down`: stop local stack.
- `make test`: run backend and frontend tests.
- `make test-backend`: run backend tests.
- `make test-frontend`: run frontend tests.
- `make lint`: run backend and frontend lint.
- `make lint-imports`: enforce backend module import boundaries.
- `make typecheck`: run backend and frontend type checks.
- `make migrate`: apply backend migrations.
- `make seed`: run the local seed command.
- `make bootstrap-superadmin`: synchronize the environment-managed superadmin account from env values.
- `make api-schema`: generate committed OpenAPI schema.
- `make api-client`: generate committed TypeScript API client.
- `make agent-check`: run the standard handoff checks.

## Backend Module Boundaries

- `platform_core`: shared primitives, settings, dates, money, files, IDs, base utilities.
- `accounts_auth`: accounts, authentication, sessions, closure, anonymization.
- `kyc_compliance`: Didit, KYC/KYB status, AML evidence, compliance tasks.
- `entities`: borrower entities and legal-entity lender records.
- `loans`: loan product, collateral, risk, schedules, statuses.
- `marketplace_primary`: primary marketplace, orders, allocations, funding close.
- `ledger`: immutable journal, balances, bank operations, reconciliation.
- `servicing`: borrower payments, repayment allocation, distributions.
- `secondary_market`: holdings, listings, claim transfer settlement.
- `fx`: quote, exchange, sanity checks, external settlement deltas.
- `documents`: templates, generated PDFs, clickwrap evidence, secure access.
- `communications`: SendGrid, notices, retries, marketing consent.
- `reporting`: accounting, tax, regulatory, operational exports.
- `admin_ops`: admin task queues, operational dashboard, SLA tracking.

Cross-module writes should go through public services/selectors. Direct model imports across modules are allowed only while bootstrapping and should be replaced with service boundaries as the module matures.

## Handoff Standard

Before handing off implementation work, run:

```bash
make agent-check
```

`make agent-check` regenerates OpenAPI/client artifacts and fails if tracked generated files drift.

For high-risk financial modules, also run the focused backend test pack for that module, for example:

```bash
make test-backend TEST=backend/apps/ledger/tests
```
