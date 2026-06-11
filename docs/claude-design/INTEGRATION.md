# Claude Design Integration Audit

Date: 2026-06-05

This document records how the Claude Design investor UX prototype was integrated into the production frontend.

## Source Material

The received design bundle contained:

- `BANXUM Investor Portal.html`
- `assets/tokens.css`, `assets/components.css`, `assets/app.css`
- `app/*.jsx`
- `app/data.js`
- `DESIGN_PASS_NOTES.md`

The bundle was treated as a UX, IA, state, copy, and visual-system reference, not production code. The Babel-in-browser runtime, React UMD CDN scripts, hash demo router, and `window.BX` mock fixture architecture were not shipped.

The raw prototype files were removed from `docs/claude-design` after integration. The retained source of truth is now this file plus `docs/claude-design/TODO.md`.

## Integrated Files

- `frontend/src/styles.css`
  - Ported the Claude token layer, app shell, component styling, status palette, financial table density, modal/drawer patterns, responsive breakpoints, and mobile sidebar behavior into the real Vite app stylesheet.
  - Removed external font imports from the prototype. The CSS names Public Sans and IBM Plex Mono but falls back to system fonts unless fonts are provided by deployment.

- `frontend/src/investorPortal/types.ts`
  - Added UI-only fixture/support types for profile, deposit instructions, document rows, notifications, and route/account state.

- `frontend/src/investorPortal/fixtures.ts`
  - Replaced `window.BX` prototype fixtures with typed TypeScript fixtures shaped against generated API types from `frontend/src/api/generated/banxumApi.ts`.
  - Fixtures preserve the design scenarios: active account, KYC-pending journey, day-60 freeze, balance lots, inherited FX deadline, public loan preview, full loan detail, portfolio holdings, secondary-market buyer/seller projections, FX history, documents, and recovery split.

- `frontend/src/investorPortal/data.ts`
  - Added the integration adapter that uses generated API hooks for all implemented investor-facing read surfaces.
  - Hooks are self-scoped. No investor/user-id selector is introduced in the frontend.
  - Live backend reads are the default. Local dummy data requires explicit preview mode via `VITE_PREVIEW=true` or the `npm run dev:dummy` script.
  - Preview fixtures are supplied as React Query `placeholderData`, not `initialData`, so they do not become authoritative cached account data in live mode.
  - Production builds fail if `VITE_PREVIEW=true`, and the frontend also has a runtime fail-closed guard for production preview mode.
  - Production builds alias the rich local fixtures to `frontend/src/investorPortal/fixtures.empty.ts`, so dummy names/amounts are not bundled for go-live.

- `frontend/src/investorPortal/format.ts`
  - Added shared formatting helpers for minor-unit money, bps rates, Europe/Zurich dates, and activity metadata categorisation.

- `frontend/src/investorPortal/ui.tsx`
  - Added production React/TypeScript primitives based on the design bundle: icons, buttons, chips, money display, stats, cards, banners, fields, checkboxes, segmented controls, tabs, modals/drawers, review rows, progress, deadline meters, empty states, and bar breakdowns.

- `frontend/src/App.tsx`
  - Replaced the scaffold shell with the integrated user-facing investor experience:
    - public marketplace preview.
    - magic-link login.
    - registration, terms, phone verification, Didit KYC handoff, and KYC status.
    - authenticated portal shell and navigation.
    - dashboard.
    - primary marketplace, loan detail, and investment-intent confirmation.
    - balances, deposit instructions, withdrawal, payout IBAN, ageing buckets, and frozen state.
    - FX quote review and confirmation.
    - portfolio, exposure, activity, orders, and holding detail.
    - secondary-market browse/list/purchase flows with buyer/seller projection separation.
    - documents, acceptance evidence, statements/tax surfaces, settings, and FAQ.

- `frontend/src/App.test.tsx`
  - Updated the smoke test from the old scaffold to the BANXUM public investor preview.

## Backend/API Mapping

Integrated screens use generated hooks for:

- investor dashboard.
- balances and balance lots.
- portfolio and exposure.
- activity.
- primary orders.
- secondary-market investor activity.
- FX history.
- public/marketplace primary loan list and loan detail.
- secondary-market buyer listing browse.

The UI intentionally does not calculate authoritative financial outcomes. Local calculations in confirmation modals are UX previews only and must be replaced with backend mutation responses when mutation endpoints are wired.

## Invariant Audit

The integration was checked against the non-negotiable UX invariants:

- Balance ageing: lots show 30-day investment and 60-day withdrawal deadlines, buckets, FIFO language, and withdrawal-only/overdue states.
- FX ageing: FX proceeds are labelled as inheriting source-lot deadlines; confirmation copy states FX does not reset the 30/60-day clock.
- Day-60 freeze: the frozen state blocks money-moving actions, keeps read-only portfolio/document/account access, and makes usable payout IBAN the primary next action.
- Primary orders: copy states that orders are intents and do not reserve loan capacity until allocated/validated, first-come first-served.
- Secondary-market anonymity: buyer browse/purchase views do not expose seller identity, seller net proceeds, maker fee, document evidence IDs, or admin internals; seller views show seller economics.
- Non-standard secondary listings: non-performing listings show warning/risk acknowledgement in buyer and seller flows.
- Clickwrap: registration, primary investment, FX, and secondary flows show server-versioned document/evidence language and checkbox confirmation.
- Sensitive actions: invest, withdraw, FX, secondary-market list, secondary-market purchase, and payout IBAN update all include fresh email-code confirmation UI states.
- Amounts/timezone: normal money displays two decimals; FX confirmation shows four decimals for target amount/rate context; dates are displayed in Europe/Zurich.
- Brand/operator: user-facing brand is BANXUM; Garanta Finanzgruppe AG appears as legal operator/account/operator disclosure.

## Audit Findings And Corrections

- The prototype KYC copy said or implied that the platform only receives approval status or does not store identity documents. That conflicts with the documented requirement that Garanta retains required compliance evidence and provider references. The integrated KYC handoff now says Didit performs identity capture/verification and Garanta retains required compliance evidence and provider references for audit/regulatory access.

- The prototype used raw HTML, Babel-in-browser, React UMD, hash routing, and `window.BX` fixtures. None of those were shipped. The real implementation uses TypeScript, React 19, generated API hooks, and local typed fixture fallback.

- Frontend audit follow-up, 2026-06-05:
  - Addressed: fixture data is no longer the default. Live API calls are enabled by default; fixture mode requires explicit `VITE_PREVIEW=true` or test mode.
  - Addressed: local dummy review mode is available through `npm run dev:dummy`. The dummy fixtures live in `frontend/src/investorPortal/fixtures.ts` and can be removed with the preview-mode adapter when live endpoints replace every fixture-backed surface.
  - Addressed: normal production bundles no longer include rich dummy fixture strings; production aliases fixture imports to the empty fixture module.
  - Addressed: production builds now fail if `VITE_PREVIEW=true`; production also has a runtime fail-closed guard.
  - Addressed: fixture data uses React Query `placeholderData`, not `initialData`, so live API mode does not treat fake values as fresh cached account data.
  - Addressed: authenticated fixture-backed views show a visible "Preview data" banner stating balances, holdings, activity, FX history, and documents are not real account data.
  - Addressed: live mode no longer displays the fixture investor name/email, fixture documents, fixture deposit instructions, or fixture recovery split as if they were real account data. Missing live projections now show explicit backend-pending states.
  - Addressed: data-backed screens now show retryable server-error states and real empty states instead of indefinite spinners or bare table headers.
  - Addressed: the public preview banner has a mobile layout fix, and public help/FAQ links remain accessible on mobile.
  - Addressed: the UX-state switcher is visible only in explicit fixture preview mode and is hidden from live builds.
  - Addressed: SMS/email confirmation-code helper text that says "Demo: any 6 digits" is now preview-gated and will not appear in live mode.
  - Addressed: the shared HTTP client now sends `X-CSRFToken` from the Django `csrftoken` cookie for unsafe same-origin requests.
  - Addressed: money-input validation uses string parsing by currency minor-unit precision and rejects malformed/over-precision values instead of silently rounding floats.
  - Addressed: money formatting supports currency-specific minor-unit precision.
  - Partially addressed: frontend tests now cover public preview, fixture warning, day-60 frozen state, KYC evidence copy, CSRF behavior, and money parsing/formatting. Broader mutation-flow tests remain deferred until mutation endpoints are live.

- The prototype support email `support@banxum.com` is still used as placeholder user-facing support copy. The real mailbox/domain remains an account/procedural dependency before production.

- Legal/risk copy remains generic placeholder copy. Final advisor-approved documents must be supplied through the documents/template system.

## Verified Locally

Commands run:

- `npm run typecheck`
- `npm run lint`
- `npm run test -- --run`
- `npm run build`

Browser verification against `http://127.0.0.1:5173/`:

- Run in dummy review mode with `npm run dev:dummy` / `VITE_PREVIEW=true`.
- Public preview loads with BANXUM/Garanta branding and no horizontal overflow.
- Public preview renders loan rows from typed dummy data and exposes an "Open dummy portal" review path only in preview mode.
- Registration advances through visible checkbox controls.
- KYC handoff shows corrected Didit/Garanta evidence-retention copy.
- Authenticated dashboard renders balance ageing and Europe/Zurich date context.
- Day-60 freeze state shows frozen financial actions and usable-IBAN next action.
- Mobile viewport renders without horizontal overflow.
- Mobile sidebar opens instantly to `translateX(0)` and is not stuck off-canvas.
- Browser console had no warnings/errors during the verified flows.

## Remaining Dependencies

- Wire live mutation endpoints for:
  - registration submit and Didit redirect/session.
  - sensitive-action email-code issuance/confirmation.
  - primary investment order creation/allocation.
  - withdrawal request.
  - payout IBAN create/update verification.
  - FX quote/execute.
  - secondary-market list/purchase.

- Replace fixture-only surfaces with backend projections where still missing:
  - investor-facing deposit instructions.
  - investor document download URLs/evidence packages.
  - notification list/status.
  - support mailbox/domain values.
  - profile/settings verification summary.
  - recovery/write-off distribution detail on holding detail.

- Before go-live, remove or disable disposable dummy-review code:
  - remove the `dev:dummy` npm script if no longer needed.
  - remove `frontend/src/investorPortal/fixtures.ts` unless retained solely for tests/MSW.
  - remove preview-only review affordances such as "Open dummy portal" and UX-state switching.
  - keep the production fail-closed guard that rejects `VITE_PREVIEW=true`.

- Add production UI states once mutation APIs are live:
  - server-error.
  - validation-error.
  - loading/disabled-submit.
  - cooldown.
  - stale quote/template.
  - success and retry states backed by backend responses.

- Add broader integration tests once live mutations exist:
  - registration submit/Didit redirect failure modes.
  - email-code issue/confirm cooldown and invalid-code states.
  - investment, withdrawal, FX, secondary-market list, and secondary-market purchase server-error states.
  - stale document-template and stale FX quote refresh behavior.

- Perform a final Claude Design polish pass on the integrated app rather than the raw prototype:
  - spacing and typography at all breakpoints.
  - accessibility/keyboard navigation.
  - table density and mobile table alternatives.
  - final legal/risk copy structure after advisor-approved templates exist.
