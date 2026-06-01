# ledger

Purpose: immutable journal, investor balances, balance lots, bank operations, reconciliation, fees, and statements.

Owned tables/models: not implemented in the bootstrap slice.

Public services/selectors: to be defined before Phase 5 work starts.

API endpoints: none yet.

Background jobs: balance ageing, reminders, forced withdrawal, and penalty jobs will be added later.

Domain events emitted/consumed: financial events will be added later.

Ledger impact: this module owns ledger writes and must expose service APIs for other modules.

Permission rules: financial state changes require audited admin or investor action context.

Important invariants:

- Ledger entries are immutable; corrections use reversal or compensating entries.
- Day-60 penalty mechanics are env/deployment-configurable and capped at remaining overdue source balance.
- FX does not reset ageing or restore investment eligibility.

Non-goals/out-of-scope behavior:

- No automated bank feed at launch.
