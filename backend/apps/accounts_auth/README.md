# accounts_auth

Purpose: investor accounts, admin accounts, authentication, sessions, account closure, and anonymization.

Owned tables/models: not implemented in the bootstrap slice.

Public services/selectors: to be defined before Phase 2 work starts.

API endpoints: none yet.

Background jobs: none yet.

Domain events emitted/consumed: account and auth events will be added in Phase 2.

Ledger impact: none directly.

Permission rules: this module will own authentication and access gates.

Important invariants:

- Investor login uses magic links plus fresh email codes for sensitive financial actions.
- Admin login uses email/password plus email code.
- Superadmin bootstrap credentials come from environment/deployment configuration.

Non-goals/out-of-scope behavior:

- No borrower portal or borrower login.
