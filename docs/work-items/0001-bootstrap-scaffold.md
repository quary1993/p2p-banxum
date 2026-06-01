# Work Item 0001: Bootstrap Scaffold

Status: implemented.

## Goal

Create the initial agent-ready implementation foundation for BANXUM.

## Business Context

Before domain workflows are implemented, the repository needs predictable commands, backend/frontend shells, OpenAPI generation, module boundaries, CI, and local infrastructure.

## Write Scope

- Root tooling files.
- `backend/`
- `frontend/`
- `.github/workflows/`
- `docs/`
- `docker-compose.yml`

## Acceptance Criteria

- Backend health endpoint works.
- Frontend shell renders.
- OpenAPI schema and generated client are reproducible.
- `make agent-check` passes locally.
- Claude Design UI/UX follow-up rule is documented.

## Non-Goals

- No financial, KYC, account, or loan domain models yet.
- No production provider integrations yet.
