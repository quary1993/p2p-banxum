# platform_core

Purpose: shared primitives, configuration, dates, IDs, file foundations, and platform health checks.

Owned tables/models: none in the bootstrap slice.

Public services/selectors: to be added as foundation primitives are implemented.

API endpoints:

- `GET /api/v1/health/`

Background jobs: none in the bootstrap slice.

Domain events emitted/consumed: none in the bootstrap slice.

Ledger impact: none.

Permission rules: health endpoint is public and exposes no sensitive data.

Important invariants:

- Platform brand and legal operator are configuration values, not hardcoded UI literals.
- Europe/Zurich is the default business timezone.

Common tests and fixtures:

- `backend/apps/platform_core/tests/test_health_api.py`

Non-goals/out-of-scope behavior:

- Financial primitives, settings registry, and file services are Phase 1 work.
