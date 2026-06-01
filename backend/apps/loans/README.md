# loans

Purpose: loan records, collateral, risk rating, schedules, and lifecycle status.

Owned tables/models: not implemented in the bootstrap slice.

Public services/selectors: to be defined before Phase 4 work starts.

API endpoints: none yet.

Background jobs: loan status jobs will be added later.

Domain events emitted/consumed: loan events will be added with product implementation.

Ledger impact: loan closing and disbursement happen through other modules and the ledger.

Permission rules: admins create and publish loans; investors see full data only after required gates.

Important invariants:

- Incomplete loans must not be saved as operational loan records.
- Real-estate-backed is the default collateral posture, but collateral type remains configurable.

Non-goals/out-of-scope behavior:

- Offline credit review is not automated in v1.
