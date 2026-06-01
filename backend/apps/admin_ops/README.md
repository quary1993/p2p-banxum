# admin_ops

Purpose: admin dashboard, task queues, SLA fields, audit search, and operational workflow entry points.

Owned tables/models: not implemented in the bootstrap slice.

Public services/selectors: to be defined before Phase 3 work starts.

API endpoints: none yet.

Background jobs: task generation jobs will be added later.

Domain events emitted/consumed: admin task events will be added later.

Ledger impact: admin operation screens may call ledger services but must not write ledger records directly.

Permission rules: superadmin handles parametrization; admin handles operational workflows.

Important invariants:

- No launch workflow requires two sets of eyes, but records should be future-ready for approval fields.

Non-goals/out-of-scope behavior:

- No sophisticated case-management system at launch.
