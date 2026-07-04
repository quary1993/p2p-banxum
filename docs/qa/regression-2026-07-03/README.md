# Full Regression Test — 2026-07-03/04

Full end-to-end regression of the BANXUM platform against the specs in `/plan`
and `/docs`, run on **staging** (`staging.nxnarena.com`) using **QA development
mode** (simulated time travel over 61 business days), plus browser E2E at
desktop (1440×900) and mobile (390×844) viewports. Production was not touched;
staging was restored to its pre-test snapshot afterwards (verified).

## What was run

1. **Spec extraction** — all 21 modules in `/plan` plus `/docs` TODOs were
   distilled into a prioritized user-story matrix (`spec-test-matrix.md`).
2. **Local gate** — `make agent-check` (lint, imports, mypy/tsc, migrations,
   pytest/vitest, schema/client sync, production build).
3. **Staging lifecycle simulation** (`staging-lifecycle-driver.py`,
   `results.jsonl` — **133 checks, all passing** after checker corrections):
   - Borrower + loan fixtures with validation negatives (missing fields,
     principal <1,000 / >1,000,000,000, funding deadline >60d).
   - Two investors registered through the **real pipeline**: registration →
     magic-link login → server-side gating (403 before phone+KYC) → live Didit
     session via the provider API → **HMAC-signed webhook** approval → gate
     unlock. (Phone verification flag set directly in DB — see Blockers.)
   - Deposits with `BX-CHF-…` references; balance lots created with exact
     Zurich-midnight 30/60-day deadlines.
   - Orders: below-minimum & over-capacity rejected; wrong email code rejected;
     unallocated orders reserve no capacity; no cancel endpoint; investor
     sessions blocked from admin APIs.
   - **Partial close** (L1: 50k of 100k → principal lowered, schedule
     regenerated to exactly 50,000.00) and **full close** (L2), holdings +
     escrow movement, disbursement enforcing the 2% success-fee withholding
     (full-principal payout rejected).
   - **Time travel** (+61 days total, ~7,600 scheduled-job runs, 0 failures):
     - installment due → borrower repayment recorded → pro-rata distribution
       (4,395.79 = exact annuity) credited as a fresh lot with new 30/60 clocks;
     - day-5 **late** and day-16 **defaulted** transitions on the unpaid loan;
     - balance-ageing reminder ladder (25/46/53/58/59/60) — 6 emails;
     - day-30 withdraw-only enforcement with explicit error;
     - day-60: forced-withdrawal queue for the investor with a verified IBAN,
       **penalty mode** for the one without (1%/day: exactly 200.00 CHF over
       2 Zurich days on the 10,000 overdue remainder);
     - **secondary market**: performing listing sold directly — every economic
       field verified by hand (price 46,941.30 @ 2% premium, maker fee 117.35,
       taker fee 352.06, accrued interest 151.30 over 12 days to the seller,
       seller net 46,975.25, buyer total 47,444.66; half-up, fees exclude
       accrued interest); defaulted-loan listing required admin approval +
       disclosure + extra buyer acknowledgement, and paid **0 accrued
       interest** (contractual interest cut off at default);
     - self-declared IBAN via email code, withdrawal, admin finalization;
     - reports (balance ageing, reconciliation, default exposure, FX activity,
       audit log) generated in full-detail CSV;
     - **reconciliation identity holds to the cent**: cash 36,714.75 =
       investor liability 24,525.34 + Garanta success fees 1,400.00 + platform
       fees/penalties 789.41 + withdrawal payable 10,000.00; the lot subledger
       equals the GL liability exactly;
     - complete audit trail for every lifecycle action.
   - **Users module**: admin directory; read-only impersonation (admin session
     + signed header) reads investor data, mutations blocked, impersonating an
     admin rejected.
   - **QA revert** restored the exact pre-test snapshot (verified twice).
4. **Browser E2E** (`browser-e2e.mjs`) — investor + admin consoles, all nav
   screens, desktop + mobile: **0 console errors, 0 failed API calls**;
   42 annotated screenshots reviewed by a 4-agent visual panel.
5. **FX**: unsupported pair and the CHF 100,000/day cap rejected correctly.
   Quote/execute could not be exercised because the run fell on a **Zurich
   Saturday** — the sanity guard correctly **fails closed** on stale weekend
   rates (spec behavior). Unit suite covers execution; re-run
   `drive.py fxsmoke` on a weekday for live confirmation.

## Bugs found and fixed in this pass

| # | Severity | Area | Bug | Fix |
|---|----------|------|-----|-----|
| 1 | P0 (build) | backend tests | Date time-bombs: hardcoded deposit `value_date=2026-06-02` made 18 marketplace tests fail from Jul 3; documents tests would follow Jul 20 | relative dates (`business_date(now)`) in fixtures |
| 2 | P1 policy | ledger | Withdrawal requests accepted **any** destination IBAN — spec requires Garanta-verified accounts only (an unverified self-declared IBAN received a 49k withdrawal in the simulation) | `request_investor_withdrawal` now requires an active, verified-usable payout instruction matching the IBAN + currency; new regression test |
| 3 | P1 | investor portal | Dashboard "Interest received (lifetime distributions)" dropped interest earned on holdings later sold/repaid (showed 0.00 after a secondary sale) | lifetime summary now aggregates over all holdings ever held; regression test added |
| 4 | P1 | emails/notifications | User-facing bodies leaked raw internals: "2000000 minor units CHF", ISO timestamps | new `format_amount_minor` (Swiss format, e.g. `CHF 46'941.30`) used across servicing/secondary-market/ledger emails; deadline dates now Zurich business dates |
| 5 | P1 | investor UI | Settings screen not wired to live data (placeholder strings as profile values, verification chips hardcoded to "backend required", "Phone backend required" label) | bound to live profile/KYC/phone data |
| 6 | P1 | investor UI (mobile) | Portfolio/documents/FX/activity tables clipped at 390px with no scroll affordance | scrollable table wrappers |
| 7 | P1 | admin UI | Desktop dashboard currency table clipped (FX UNSETTLED unreadable); mobile Users/Loans/Templates toolbars overflow with unusable buttons | layout/stacking + scrollable wrappers |
| 8 | P2 | admin UI | Raw minor-units KPI (`COMMITTED 7000000`), name+UUID concatenation, audit column clipping, `Qa` heading, users-table column widths | formatted/fixed |
| 9 | P2 | investor UI | FX history empty state missing; raw snake_case activity references; "1 active holdings" pluralization | fixed |
| 10 | P2 | emails | Seller "sale completed" email reused the buyer topic `…purchase_confirmation` | new `email.secondary_market_sale_confirmation` topic |

Checker-side false alarms (app was correct): committed-capacity expectation,
distribution lot source-type name, seller-proceeds source-type name, defaulted
listing status literal, audit-window flooding, impersonation header usage —
all recorded as superseded entries in `results.jsonl`.

## Healthy errors (by design — not bugs)

- **FX fails closed on weekends/holidays** with explicit user-facing closure
  copy. Weekends show a proactive "FX unavailable on weekends" banner in the
  investor FX screen; configured holidays return a market-holiday quote error.
  Ordinary stale/malformed provider data returns a temporary FX-rate
  availability message with support escalation copy. QA time travel can still
  trigger the temporary-provider path because simulated clock ≫ provider
  timestamp breaks the 300s freshness window.
- **KYC decline non-overridable** for direct manual approval (reopen→approve
  path is the false-positive route; user-confirmed policy).
- Empty marketplace after funding close ("No loans available") — loans leave
  the public list when funded.
- QA-mode date-sourcing artifacts: model `created_at` uses the real clock while
  business dates use the simulated clock, so activity/document dates can look
  "before" value dates during time travel. Coincide in production.
- Admin date inputs default to the real browser date, not the QA clock —
  QA-harness artifact only.

## Blocked — needs user input

1. ~~**Twilio trial account** (error 21608)~~ **RESOLVED 2026-07-04**: the
   account is upgraded (`type: Full`, verified via the Twilio API), so SMS
   phone verification can now reach arbitrary numbers. The regression run
   itself set `phone_verified_at` directly in the staging DB — that remains
   the right technique for *automated* runs (no SMS receiver), but a manual
   registration with a real phone is now expected to work end-to-end.
2. **FX live execution E2E** — re-run on a weekday (Zurich market day):
   `BANXUM_DIDIT_WEBHOOK_SECRET=… uv run --with requests staging-lifecycle-driver.py fxsmoke`.
3. **Spec divergence to ratify**: `plan/06` says "no impersonation feature";
   the platform now ships an audited, read-only, superadmin-gated
   impersonation (cannot target admins, mutations blocked). Recommend updating
   the plan text to match the implemented (safer) design.

## Artifacts

- `spec-test-matrix.md` — consolidated user-story/invariant matrix from /plan
- `staging-lifecycle-driver.py` — replayable staged API driver (QA-mode aware)
- `browser-e2e.mjs` — CDP browser sweep (session-cookie injection, nav walk,
  console/API-error capture, screenshots)
- `results.jsonl` — all 133 recorded checks with details
