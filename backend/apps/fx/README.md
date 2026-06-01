# fx

Purpose: FX rate polling, executable quotes, sanity checks, exchange execution, and external settlement deltas.

Owned tables/models: not implemented in the bootstrap slice.

Public services/selectors: to be defined before Phase 9 work starts.

API endpoints: none yet.

Background jobs: display-rate polling and daily delta reporting will be added later.

Domain events emitted/consumed: FX events will be added later.

Ledger impact: exchanges, FX fees, and realized surplus/deficit post through `ledger`.

Permission rules: investors need a fresh sensitive-action email code before execution.

Important invariants:

- FX is auxiliary settlement, not trading/speculation.
- FX conversion does not reset balance ageing.
- Launch limit is CHF 100,000 per investor per day or equivalent.

Non-goals/out-of-scope behavior:

- No unhedged exposure alerts at launch.
