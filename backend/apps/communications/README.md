# communications

Purpose: SendGrid transactional email, notices, delivery retries, full sent-content archive, and marketing consent.

Owned tables/models: not implemented in the bootstrap slice.

Public services/selectors: to be defined before Phase 6 work starts.

API endpoints: none yet.

Background jobs: email outbox processing will be added later.

Domain events emitted/consumed: communication events will be added later.

Ledger impact: none directly.

Permission rules: transactional emails are mandatory; marketing consent is optional.

Important invariants:

- Failed transactional emails create admin-visible notices after retries.
- Templates expose variable scopes and examples for superadmin editing.

Non-goals/out-of-scope behavior:

- SMS is only for phone verification at launch.
