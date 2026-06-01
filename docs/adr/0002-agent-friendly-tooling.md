# ADR 0002: Agent-Friendly Tooling

Status: Accepted.
Date: 2026-06-01.

## Context

The platform will be implemented module by module with coding-agent assistance. Agents need stable commands, generated contracts, and explicit module ownership.

## Decision

Use a root `Makefile`, committed OpenAPI schema, generated TypeScript API client, module README files, `AGENTS.md`, and `docs/work-items/` contracts.

## Consequences

- Agents can run `make agent-check` before handoff.
- Backend API changes must be synchronized with generated frontend client changes.
- UI/UX work must record Claude Design follow-ups in `docs/claude-design/TODO.md`.
