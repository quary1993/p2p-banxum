# reporting

Purpose: accounting exports, tax information statements, regulatory exports, operational reports, and evidence packages.

Owned tables/models: not implemented in the bootstrap slice.

Public services/selectors: to be defined before Phase 12 work starts.

API endpoints: none yet.

Background jobs: report generation and ZIP exports will be added later.

Domain events emitted/consumed: report events will be added later.

Ledger impact: reports read ledger state but do not mutate it.

Permission rules: admin-only unless the report is explicitly investor-facing.

Important invariants:

- Reports derive from the immutable transaction-level ledger where financial.
- Principal flows are separated from income/cost/tax-relevant categories.

Non-goals/out-of-scope behavior:

- Direct Bexio API push is not required at launch.
