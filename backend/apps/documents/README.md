# documents

Purpose: legal/document templates, generated PDFs, clickwrap acceptance, and secure document access.

Owned tables/models: not implemented in the bootstrap slice.

Public services/selectors: to be defined before Phase 6 work starts.

API endpoints: none yet.

Background jobs: PDF generation jobs will be added later.

Domain events emitted/consumed: document events will be added later.

Ledger impact: none directly.

Permission rules: documents are private and must be authorized per account/admin role.

Important invariants:

- Generated PDFs must be reproducible from stored template/data snapshots.
- Templates use configurable platform/operator variables instead of hardcoded legal names.

Non-goals/out-of-scope behavior:

- No e-signature provider at launch.
