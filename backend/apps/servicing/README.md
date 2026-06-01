# servicing

Purpose: borrower payment events, repayment application, schedule recalculation, and investor distributions.

Owned tables/models: not implemented in the bootstrap slice.

Public services/selectors: to be defined before Phase 8 work starts.

API endpoints: none yet.

Background jobs: repayment notifications will be added later.

Domain events emitted/consumed: servicing events will be added later.

Ledger impact: every repayment and distribution posts through `ledger` services.

Permission rules: admins record borrower payments and evidence.

Important invariants:

- Payment events may represent partial installments, regular installments, multiple installments, or early repayment.
- Late/default day-counting uses Europe/Zurich calendar days.

Non-goals/out-of-scope behavior:

- Automatic bank repayment matching is not in launch scope.
