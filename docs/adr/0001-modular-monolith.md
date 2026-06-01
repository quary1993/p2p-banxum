# ADR 0001: Modular Monolith

Status: Accepted.
Date: 2026-06-01.

## Context

BANXUM has tightly coupled financial state across balances, loan funding, claim assignments, repayments, FX, and secondary-market transfers. Launch operations are mostly manual and cost sensitivity is high.

## Decision

Build v1 as a Django modular monolith with strict internal module boundaries, service-layer writes, append-only financial/audit records, OpenAPI-generated frontend clients, and provider adapters.

## Consequences

- One deployable application keeps launch infrastructure simple.
- Module READMEs, services, selectors, and import-boundary checks are required to avoid a tangled codebase.
- Future extraction to separate services remains possible after real traffic or team structure justifies it.
