# secondary_market

Purpose: investor holdings, full-holding listings, buyer purchases, maker/taker fees, and claim transfer evidence.

Owned tables/models: not implemented in the bootstrap slice.

Public services/selectors: to be defined before Phase 10 work starts.

API endpoints: none yet.

Background jobs: none yet.

Domain events emitted/consumed: listing and transfer events will be added later.

Ledger impact: buyer cost, seller proceeds, fees, and accrued interest settlement post through `ledger`.

Permission rules: non-performing holdings require admin approval and extra buyer acknowledgement before listing/purchase.

Important invariants:

- A listing transfers an entire holding, not a fraction of a holding.
- The secondary market is a bulletin-board transfer mechanism, not a regulated trading venue.

Non-goals/out-of-scope behavior:

- No partial transfer of a single holding.
