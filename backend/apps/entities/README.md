# entities

Purpose: borrower legal entities, borrower display profiles, borrower documents, and legal-entity lender records.

Owned tables/models: not implemented in the bootstrap slice.

Public services/selectors: to be defined before Phase 4 work starts.

API endpoints: none yet.

Background jobs: none yet.

Domain events emitted/consumed: entity events will be added with borrower onboarding.

Ledger impact: none directly.

Permission rules: borrowers are admin-created and have no portal accounts.

Important invariants:

- Borrower means the party requesting/repaying the loan; there is no separate Loan Originator party type in v1.
- Borrowers must be KYB/AML-approved before being used in platform transaction workflows.

Non-goals/out-of-scope behavior:

- No borrower self-service portal.
