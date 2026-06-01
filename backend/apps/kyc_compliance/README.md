# kyc_compliance

Purpose: Didit sessions, KYC/KYB status, AML flags, manual review, and regulatory evidence exports.

Owned tables/models: not implemented in the bootstrap slice.

Public services/selectors: to be defined before Phase 2 work starts.

API endpoints: none yet.

Background jobs: Didit follow-up jobs will be added in Phase 2.

Domain events emitted/consumed: KYC/KYB events will be added in Phase 2.

Ledger impact: none directly.

Permission rules: financial activity is blocked until the relevant KYC/KYB/AML gate is approved.

Important invariants:

- Provider webhooks must be authenticated, idempotent, and audit logged.
- KYC/KYB/AML evidence must remain in Garanta-controlled Swiss storage where legally and technically possible.

Non-goals/out-of-scope behavior:

- No legal-entity self-service KYB flow at launch.
