# marketplace_primary

Purpose: public marketplace preview, investment orders, funding close, and borrower disbursement workflow.

Owned tables/models: not implemented in the bootstrap slice.

Public services/selectors: to be defined before Phase 7 work starts.

API endpoints: none yet.

Background jobs: none yet.

Domain events emitted/consumed: investment and funding events will be added later.

Ledger impact: all allocations, fees, disbursements, and refunds must post through `ledger` services.

Permission rules: investors need approved KYC, phone verification, terms acceptance, and fresh sensitive-action email code.

Important invariants:

- Pending orders are intent only and do not reserve capacity until committed.
- Balance-funded orders cannot consume lots whose 30-day investment deadline is earlier than the loan funding deadline.

Non-goals/out-of-scope behavior:

- Auto-invest is not in launch scope.
