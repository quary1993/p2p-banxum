# Claude Design TODO

## 2026-10-09: Public Preview Fields, Listing Rule C18 And Lot Labels (QA audit round 2)

- Screen or component: public home carousel, `/projects` cards and `/projects/{loan-id}`; Secondary market "Sell a holding"; My investments loan table.
- Current behavior: the public pages read only the MKT-DEC-002 preview (borrower name, borrower country as a country name, loan type "Direct loan"/"Loan Originator claim" plus "Refinanced", amount, interest, term, status "Open for investment", currency); title and purpose are no longer public. Late or defaulted holdings show a disabled "List" with "Late or in default: cannot be listed"; there is no "Request listing" or "Approval pending". Two lots of one loan count as one loan; each lot row says "invested on <date>" or "bought on <date>", and the table footer says "N loans · M lots".
- Suggested improvement: design a proper country/flag treatment and a loan-type badge for the public cards; consider grouping lots under one loan row with an expandable lot list.
- Priority: nice-to-have.

## 2026-10-09: Public Project Routes And Page Titles

- Screen or component: public project list/detail routes and browser page titles.
- Current behavior: each public project preview uses `/projects/{loan-id}`, survives reload, and returns to `/projects`. Public, authentication, and investor routes update the browser title from the application router, including after sign-out.
- Suggested improvement: add per-project title and description metadata if server rendering or social link previews are introduced.
- Priority: nice-to-have.

## 2026-10-08: Banxum Design Re-skin (User Side)

- Screen or component: all public, sign-in, registration and investor-portal screens. Source: the Banxum prototype (DashLite layout, Archivo, black/white palette) and the Banxum public-site prototype.
- Current behavior: user-side styles live in `frontend/src/banxumSkin.css` (tokens, shell, base components, Overview) and `frontend/src/skin/*.css` (one file per area). Every rule is scoped by the `bxm` class that `UserSkin` sets on `<html>`, so the admin console keeps its own look. Sidebar uses the design names (Overview, Projects > Primary/Secondary market, My investments, Smart Invest, Wallet > Account/FX, Profile & Settings, Documents, Notifications, Help). Header has a user menu, a notifications menu (5 latest, "View all") and an "Open now" line. The primary market has a Cards view (default) and the existing table as List. Investing and the holding detail are pages (`/marketplace/:loanId/invest`, `/portfolio/:holdingId`) instead of dialogs. The new home page is at `/`; the public loan preview moved to `/projects`.
- Suggested improvement:
  - Confirm the company facts that the home page copies from the design: VQF membership, FINOS affiliation, yearly independent audit, CHF 1,100,000 share capital, registered trademark, "not protected by the Swiss deposit insurance", and the 0.25% seller fee wording.
  - Public loan cards follow MKT-DEC-002 (borrower, amount, interest, period, type, status, currency); the design also shows funded %, days left and minimum. Decide if the public preview fields should change.
  - The "Open now" header line shows the open loan that closes last, because the public loan list has no publication date. Add a published-at field if "newest" is wanted.
  - Not built because there is no backend or data: password/2FA/passkey sign-in, language switcher (DE/FR), cookie notice, newsletter form, "Mark all as read", help contact form, loan description/investor count/"new loan vs existing claim" on cards, quick-amount buttons on the invest page, auto-invest without approval, transactions and reports pages.
  - Review the new pages with real (non-fixture) data, long names and empty states.
- Priority: important.

## 2026-10-09: Multi-Select Filters And Smart Invest Criteria

- Screen or component: primary-market filter panel, Smart Invest rule editor and setup wizard (steps 1 and 2), rule summary.
- Current behavior: source, collateral, currency, risk rating, purpose and loan type are multi-select (QA row 37). The filter panel keeps its pill chips as toggles; the rule editor and wizard use square `.check` checkboxes. The combined "Either", "Both", "CHF and EUR", "Anyone" and "Any" options are gone: nothing ticked means no restriction and is labelled ("Any currency", "With or without collateral"). Collateral offers "Any collateral" (every secured loan, including types added later), each collateral type, and "No collateral (unsecured)"; while "Any collateral" is ticked the types show ticked and disabled. The rule editor offers the full rating scale, purpose list and collateral catalog, not only values on today's loans.
- Suggested improvement: the collateral and purpose lists are long on phones (one column of 13 types); consider collapsing the types under "Any collateral" or a "Show types" toggle. Unused `.si-cond-pills` and `.si-wiz-option` rules can be removed from `skin/projects.css` and `styles.css` once no other screen needs them.
- Priority: nice-to-have.

## 2026-09-09: Borrower and Originator Stories

- Screen or component: opportunity calculator, borrower/originator story and separate schedule pages.
- Current behavior: structured rich text and authenticated raster images; direct loans use the borrower's story, LO loans only the originator's story. Selected-public facts remain visible. Investment entry exists on both pages; full schedules retain actual repayments, including prepayments.
- Suggested improvement: final editorial/accessibility review of long stories, empty profiles, long image captions and narrow-screen calculator tables. Preserve confidentiality and label projections as indicative, not guaranteed or received payments.
- Priority: important.

This file is the working brief for Claude Design. Claude Design owns the complete user-facing UI/UX pass for BANXUM before launch. Implementation agents should add entries here whenever they build or touch public, investor, client-portal, onboarding, marketplace, documents, payments, FX, reporting, or account-settings UI visible to platform users.

Admin console UI/UX is not owned by Claude Design. Admin console screens are implemented and designed by the Codex implementation agent and tracked in `docs/admin-console/TODO.md`.

## Ownership Boundary

### 2026-09-09: Archived QA Activity

- Current behavior: Portfolio activity, secondary-market activity and FX history retain pre-reset rows with a small "Before QA reset" label; the archived rows never contribute to current balances or holdings.
- Follow-up: review label wrapping and scanability in the v9 tables on narrow screens. Keep these historical rows distinguishable from the new QA opening balances.
- Priority: nice-to-have.

### 2026-09-07: Funding-Window Eligibility

- Current behavior: single and batch investment previews use each source's remaining holding time; shorter campaigns can use older funds. Balances and FAQ explain potential versus loan-specific eligibility. Fixed day-30 warnings are removed.
- Follow-up: polish the potentially-investable balance label and batch tooltips without implying that all balance can fund every loan; preserve mobile wrapping and keyboard access.
- Priority: nice-to-have.

Claude Design owns:

- Public and unauthenticated user-facing pages.
- Investor registration, login, phone verification, KYC handoff, and account-access states.
- Investor portal IA, navigation, layout, visual system, responsive behavior, and component polish.
- Primary marketplace, loan detail, investment intent, payment instructions, clickwrap, and order-status UX.
- Secondary marketplace browse/list/purchase UX, including risk disclosure and counterparty anonymity.
- Balance, deposit, withdrawal, payout-IBAN, balance-ageing, penalty-mode, and frozen-action UX.
- FX quote, quote-confirmation, exchange history, and limit/error UX.
- Portfolio, exposure, activity, repayment/recovery history, documents, statements, tax-information views, settings, FAQ, support, and notification/status surfaces visible to investors.
- User-facing copy hierarchy, empty states, loading states, validation states, error states, risk warnings, and accessibility.

Claude Design does not own:

- Admin console UI, admin dashboard, admin task queues, compliance review screens, borrower/loan/ledger/reconciliation/admin-reporting screens, or operational admin flows.
- Backend services, financial calculations, ledger rules, regulatory constraints, API contract changes, or database models.
- Legal/regulatory wording approval. Claude may improve UX structure and placeholder copy, but final legal text must remain configurable and advisor-approved.

## Canonical Product Context

- User-facing platform/brand name: BANXUM.
- Legal operator: Garanta Finanzgruppe AG, Switzerland.
- BANXUM must be used for product/platform naming in public pages, investor portal copy, email templates, legal-document titles, generated PDFs/statements, support/FAQ copy, and other user-facing UI where the platform brand is intended.
- Garanta Finanzgruppe AG must be used where the legal operator, contracting party, regulated entity, account holder, VQF/SRO-supervised operating entity, or required legal footer is intended.
- Product brand and legal operator are related but distinct. Do not replace legal-operator references with BANXUM, and do not use Garanta Finanzgruppe AG as the consumer-facing product name unless the context is legal/operator disclosure.
- Platform brand, legal operator, support email, domains, and footer identities must remain configuration/template variables in implementation. Do not hardcode them in reusable templates, document generators, or notification bodies.
- Borrowers are legal entities created and managed by admins. Borrowers do not have a portal and do not log in.
- Direct self-registration is for natural-person lenders only. Legal-entity lenders can exist, but they are created by admins after off-platform onboarding.
- KYC/KYB/AML is handled through Didit/provider workflows plus Garanta compliance evidence. User-facing KYC should be designed as a handoff/status journey, not as an in-platform identity-document collection flow.
- The platform exposes claim/receivable participation in loans. Avoid language that implies a bank deposit, fund unit, savings account, bond exchange, trading venue, guaranteed return, or portfolio-management service.

## Non-Negotiable Domain Rules

These rules must be visible in UX decisions and must not be simplified away:

- Investors can hold platform balances, but every incoming balance lot has regulatory ageing deadlines. Funds must be invested within the 30-day investment window or withdrawn within the 60-day withdrawal window.
- FX conversion does not reset balance ageing. Converted money inherits the source balance deadline. UI must not imply a fresh 30/60-day timer after FX.
- A balance is eligible for investment when it is pledged within its own 30-day investment window. The loan may resolve later under its separately capped funding campaign. Do not incorrectly compare the lot investment deadline with the loan funding deadline.
- If funds reach the 60-day deadline and a usable payout IBAN exists, Garanta may initiate forced withdrawal. If no usable IBAN exists, financial actions are frozen until the investor provides a usable IBAN, and penalty mode may apply according to configurable policy.
- Amounts are stored in minor units. User-facing normal balances and monetary amounts should display two decimals. FX confirmation may display the exchange rate and conversion detail with four decimals where useful; internal precision is higher.
- Supported launch currencies are CHF and EUR, but currency UI should be configurable/extendable.
- Europe/Zurich is the authoritative business timezone for platform day-counts, ageing reminders, late/default status, and user-facing date explanations.
- Primary-market pending investment orders are intents only. They do not reserve loan capacity until funds are allocated/validated in the system.
- First-come, first-served allocation applies when available capacity is limited.
- Loan publication and investment must not expose incomplete borrower optional fields. If an optional borrower field is absent, hide the label and value rather than showing empty, unknown, or not provided.
- Marketplace borrower disclosures must reuse the investor-facing borrower projection from the backend. Do not rebuild hidden/visible document or optional-field logic in frontend code.
- Secondary-market browse and purchase UX must preserve counterparty anonymity. Buyers should not see seller identity, seller net proceeds, maker fee, or internal admin fields. Sellers should not see buyer identity.
- Secondary-market listings for non-performing loans require clear status disclosure and an extra buyer risk acknowledgement.
- Written-off/defaulted/recovery status must be visible next to affected holdings. Do not represent a written-off or defaulted position as a normal live loan just because holding principal still exists.
- Investors may receive repayments, recoveries, secondary-market proceeds, FX proceeds, and withdrawals through platform balance flows. Activity/history must distinguish income/cost items from principal movements.
- Financial actions such as invest, withdraw, FX, secondary-market list, and secondary-market purchase are sensitive. The final UI must support fresh email-code confirmation when the backend integration for that action is wired.

## UX Principles

- Build the actual investor experience, not a marketing landing page. The first authenticated screen should help an investor understand balances, deadlines, investment opportunities, and portfolio state.
- Keep the UI quiet, dense, and financial. Prioritize scanability, tables, compact summaries, clear status chips, exact amounts, and predictable navigation over decorative cards or oversized hero content.
- Use plain English only for v1.
- Avoid promotional return language. Use factual labels such as target interest, scheduled repayment, risk rating, collateral type, current status, days past due, and outstanding principal.
- Separate data that is actionable from data that is historical. A user should quickly understand what they can do now, what is blocked, what needs attention, and what already happened.
- Use progressive disclosure for risk and legal content: show concise summaries near decisions, and provide expandable/detail/download access to full terms and documents.
- Make confirmations explicit for money-moving actions: amount, currency, source balance/deadline impact, fees, expected result, documents accepted, and irreversible/operational caveats.
- All risky statuses need concrete labels and timestamps: KYC pending, KYC manual review, account restricted, phone unverified, balance overdue, withdrawal requested, payment pending validation, loan late, loan defaulted, recovery, final resolution pending, and secondary-market approval required.
- Avoid jargon where it does not help. When domain terms are necessary, define them once in context using compact copy.
- Do not hide regulatory constraints behind friendly language. The 30/60-day balance rule, forced withdrawal requirement, and non-extendable regulatory basis must remain clear.

## User-Facing Information Architecture

Recommended first-pass navigation for authenticated investors:

- Dashboard: account state, balances by currency, ageing alerts, active actions, portfolio summary, recent activity.
- Marketplace: primary-market loans, loan detail, public preview state before login/KYC, investment intent flow.
- Portfolio: holdings, exposure metrics, loan status, repayment/recovery history, public risk notes, secondary-market actions.
- Secondary Market: active listings, non-standard listing warnings, sell/list flow for own holdings, purchase flow.
- Balances: balance lots/deadlines, deposits/payment instructions, withdrawals, payout IBANs, forced-withdrawal/penalty states.
- FX: quote, confirmation, daily limit, fees, history, settlement status copy.
- Documents: accepted terms, investment/secondary-market evidence, account statements, tax-information statements, downloadable packages when implemented.
- Settings: profile, phone verification, bank/payout instructions, marketing consent, support contact, account closure request guidance.

Public/unauthenticated routes should include:

- Public marketplace preview with limited loan fields and clear login/KYC prompts.
- Registration, magic-link login, phone verification, Didit KYC handoff, terms acceptance.
- FAQ/support pages with the support email and concise explanations of balances, investment orders, risks, FX, withdrawals, and secondary market.

## Critical Flow Guidelines

### Registration, Login, And KYC

- Registration accepts natural-person lenders only.
- T&C acceptance happens at registration and must be presented as server-versioned clickwrap, not a generic checkbox detached from document version.
- After registration, route to Didit KYC. If KYC is pending/manual-review/declined, show a clear account state and next step without exposing internal provider payload details.
- Magic-link login should feel simple, but failed/bounced email recovery is handled through support. Do not design self-service password reset for investors.
- Phone verification is required before financial access. Keep phone confirmation lightweight and separate from MFA language.

### Balances, Deposits, And Withdrawals

- Balance views must show per-currency totals and actionable buckets:
  - investable within the 30-day window.
  - withdraw-only because the lot's investment deadline passed.
  - overdue/60-day attention required.
  - penalty-mode/frozen funds.
  - pending withdrawal.
- Each balance lot or grouped bucket should expose enough date context for the investor to understand why an amount is usable or blocked.
- Deposit/payment instructions must make the unique payment reference prominent and explain that matching depends on amount, currency, sender name/IBAN, and reference.
- Withdrawal UX must show destination IBAN, requested amount, currency, expected operational status, and finality caveats.
- Forced withdrawal and missing-IBAN states should be serious but not alarmist. The investor should always know the single next action: provide a usable IBAN.

### Primary Marketplace And Investment

- Public preview before login/KYC should show limited loan data only.
- Full loan detail after financial access should show borrower disclosure, amount, currency, target interest, term, repayment type, collateral type/value/LTV where applicable, risk rating, country, funding progress, deadline, documents, and status.
- Investment intent must communicate that the order is not effective until funds are allocated/validated.
- If only part of an order can be allocated, show the accepted amount, unaccepted amount, and what happens to the excess.
- If deterministic deadline close funds a loan below its original target, show the final subscribed principal and the platform's investor notice in the relevant loan/order/notification surfaces. Do not imply that an admin chose the partial amount.

### Portfolio And Servicing

- Portfolio holdings should separate principal outstanding, interest/recovery received, current loan status, next due date, days past due, repayment type, and secondary-market availability.
- For repayments, show whether the payment was regular, partial, multi-installment, early repayment, or recovery related when available.
- For default/recovery/resolution, show status, public notes, recovery distributions, and any final-resolution reporting context without promising recovery.
- Use current loan status as a first-class visual signal in portfolio tables and holding detail.

### Secondary Market

- Treat secondary market as a bulletin-board claim/participation transfer, not an exchange.
- Listing flow is full-holding only. Do not design partial holding sales.
- Seller price is set as a percentage of current principal balance. UI must show discount/premium clearly.
- Buyer-facing listing detail should show current principal, sale price, discount/premium, accrued interest, taker fee, total cost, loan status, days past due if any, last payment date if available, and public notes.
- Buyer-facing views must not reveal seller identity, seller net proceeds, maker fee, or admin approval internals.
- Seller-facing views may show seller economics, maker fee, net proceeds, listing status, and removal/approval state.
- Non-standard listings need a visible warning and additional acknowledgement before purchase.

### FX

- FX is an auxiliary settlement function. Do not make it feel like trading.
- Launch pairs are CHF/EUR and EUR/CHF. Pair selection should be extendable.
- No minimum exchange amount. Default per-investor daily limit is CHF 100,000 equivalent.
- Quote confirmation should show source amount, target amount, rate, platform fee, expiry/validity, daily-limit impact, and inherited balance deadline impact.
- Background/display quotes may change; confirmed quotes are fixed for the confirmation window. UI should make quote expiry and stale quote refresh clear.
- If a sanity check or provider issue blocks quotes, show a clear unavailable state rather than a suspicious rate.

### Documents, Statements, And Tax Information

- Accepted terms must be viewable later and should show acceptance timestamp, document title/version, transaction context, and downloadable/generated evidence when available.
- Account statements and annual tax-information statements are informational only and not tax advice. This disclaimer must be visible.
- Statements should separate income/cost items from principal and balance movements.
- Do not expose admin-only report controls or full/unredacted admin reporting surfaces to investors. Investor documents must be self-scoped.

## Visual And Interaction Standards

- Use a restrained financial SaaS style: compact tables, consistent spacing, clear hierarchy, and restrained color use.
- Avoid one-note palettes and decorative gradient/orb backgrounds.
- Cards may be used for individual repeated items or compact summaries. Avoid nested cards and marketing-style decorative sections inside the app.
- Use stable table columns, filters, sort states, row actions, pagination or incremental loading where large lists are possible.
- Use icons for common actions where useful, with text labels or tooltips for clarity. Do not replace critical financial labels with icons alone.
- Amounts must align visually, use consistent currency formatting, and avoid wrapping in ways that obscure decimals.
- Date and deadline displays should be consistent and include timezone-sensitive explanations where deadlines matter.
- Every form needs loading, success, validation-error, server-error, cooldown, retry, and stale-data states.
- Every money-moving confirmation needs a review screen before final submit.
- Responsive layouts must work at mobile, tablet, and desktop widths without overlapping text or hidden critical actions.
- Accessibility baseline: keyboard navigation, visible focus states, sufficient contrast, semantic headings, clear form labels, table captions/labels where needed, and screen-reader-friendly status changes.

## API And Implementation Guidance

- Use the generated TypeScript API client from `frontend/src/api/generated/banxumApi.ts` and the shared HTTP client where possible.
- Investor APIs are self-scoped. Do not add user-id selectors or client-supplied investor IDs to investor-facing screens.
- If a backend endpoint is not implemented yet, Claude Design may build UI with MSW mocks or clearly marked local fixtures, but must record the missing endpoint/contract in this file.
- Do not change backend financial calculations or API semantics to fit a design. If a flow feels hard to design, record the UX issue and ask Codex/backend to expose a better projection.
- Keep admin APIs out of user-facing screens.
- Update this file after every design pass with:
  - screen/component touched.
  - current behavior.
  - design decision.
  - remaining backend/API dependency, if any.
  - priority.

## Required Claude Design Deliverables

Before launch, Claude Design should produce or implement:

- Final user-facing route map and navigation model.
- Design tokens for color, typography, spacing, status chips, tables, forms, buttons, alerts, modals, and data cards.
- Responsive layouts for desktop and mobile for all critical flows.
- Investor dashboard, marketplace, balances, portfolio, secondary market, FX, documents, and settings screens.
- Transaction confirmation patterns for invest, withdraw, FX, secondary-market list, and secondary-market purchase.
- Risk/disclosure component patterns for loan risk, default/recovery/resolution, secondary-market warnings, balance-ageing deadlines, and KYC/account restrictions.
- Empty/loading/error/stale/cooldown states.
- Accessibility pass and visual QA screenshots across representative viewports.

## Open Design Work Items

## 2026-06-01: Initial Portal Shell

- Screen or component: root React scaffold shell.
- Current first-version behavior: simple operational shell with top bar, module navigation preview, and status summary.
- Suggested improvement: Claude Design should define the final user-facing/investor information architecture, density, navigation states, responsive behavior, and component tokens before production user-facing portal screens are built out.
- Priority: important.

## 2026-06-02: Investor Balance Ageing And Return-IBAN States

- Screen or component: investor balance dashboard, withdrawal flow, payout-IBAN declaration, ageing reminders, penalty-mode/frozen-action banner.
- Current first-version behavior: no user-facing UI was implemented in this slice; backend APIs now produce balance-ageing reminder events, forced-withdrawal requests, and penalty-mode lot states.
- Suggested improvement: Claude Design should design the investor-facing balance breakdown for investable, withdraw-only, overdue, and penalty-mode funds; reminder messaging hierarchy; the required usable-IBAN declaration/update flow; and a blocking financial-action banner that keeps read-only account access available while clearly explaining the regulatory 60-day limit.
- Priority: important.

## 2026-06-02: Clickwrap Acceptance And Document Downloads

- Screen or component: registration terms display, primary-market investment acceptance, secondary-market purchase/listing acceptance, document evidence/download states.
- Current first-version behavior: no user-facing UI was implemented in this slice; backend APIs now expose current published templates and create immutable acceptance evidence for authenticated transaction contexts.
- Suggested improvement: Claude Design should design the checkbox/clickwrap acceptance presentation, long-form legal text layout, required checkbox hierarchy, stale-template refresh state, accepted-document confirmation state, and user-facing document package/download surfaces for investor portal transactions.
- Priority: important.

## 2026-06-04: Investor Portal API Foundation

- Screen or component: investor dashboard, balances, portfolio, activity timeline, primary-order history, secondary-market own-activity history, and FX history.
- Current first-version behavior: no user-facing UI was implemented in this slice; backend APIs now expose self-scoped data contracts for dashboard summaries, balance ageing buckets/deadlines, payout instructions, holdings, exposure metrics, public loan-note summaries, recent activity, primary orders, secondary-market listings/purchases/sales, and FX quote/exchange history.
- Suggested improvement: Claude Design should do the full investor-portal information architecture and visual pass before production UI implementation, including dashboard hierarchy, balance-ageing warnings, regulatory 60-day deadline language, portfolio/exposure charts, activity table density, empty/error/loading states, responsive behavior, and clear separation between read-only history and money-moving actions.
- Priority: important.

## 2026-06-05: Full User-Facing UX Pass

- Screen or component: all public and investor-facing surfaces.
- Current first-version behavior: Claude Design delivered a standalone high-fidelity reference prototype for the investor experience. That prototype has now been ported into the real Vite/React frontend as a typed first-version investor portal using generated API hooks with local fixture fallback. See `docs/claude-design/INTEGRATION.md`.
- Suggested improvement: Claude Design should now review and polish the integrated app itself, not the deleted standalone prototype. The pass should focus on production-quality spacing, responsive behavior, accessibility, loading/error/cooldown/stale states, and final legal/risk-copy hierarchy across public preview, onboarding/KYC, dashboard, marketplace, investment, balances, withdrawal, FX, portfolio, secondary market, documents, statements, settings, support, and all status/notification states.
- Remaining backend/API dependency: final provider delivery and final production templates/layouts. Registration/KYC redirect, sensitive email-code confirmation, primary investment, withdrawal, live deposit instructions, payout IBAN update, FX quote/execute, secondary-market list/purchase, investor document/statement/tax downloads, and notification delivery status are now wired as first-version live flows.
- Priority: important.

## 2026-06-05: Integrated Investor Portal QA Follow-Up

- Screen or component: integrated investor portal in `frontend/src/App.tsx`, `frontend/src/styles.css`, and `frontend/src/investorPortal/*`.
- Current first-version behavior: app renders public preview, magic-link login, registration/phone/KYC handoff, dashboard, marketplace, loan detail, investment modal, balances/deposit/withdraw/IBAN, FX, portfolio, secondary market, documents, settings, and FAQ. The integration uses generated API hooks and fixture fallback rather than the raw `window.BX` prototype data.
- Design decision: keep the app quiet, dense, and operational. Use BANXUM as brand, Garanta Finanzgruppe AG as legal operator. Preserve counterparty anonymity, balance-ageing deadlines, day-60 freeze copy, server-versioned clickwrap language, and email-code step-up patterns.
- Remaining backend/API dependency: final provider delivery, final legal/tax/reporting templates, and production PDF/CSV layouts. Live mutations and server-projected documents/deposit instructions/notifications are now present as first-version flows.
- Claude Design action: perform a full visual/accessibility pass directly against the integrated Vite app. Check desktop/tablet/mobile; table wrapping; focus states; modal/drawer accessibility; empty/loading/server-error/validation-error/cooldown/stale states; and whether every money-moving confirmation remains understandable without overpromising outcomes.
- Priority: important.

## 2026-06-05: Frontend User-Facing Audit Follow-Up

- Screen or component: investor frontend data adapter, local dummy-data review mode, HTTP client, money inputs/formatting, data-backed state handling, mobile public preview, and critical state tests.
- Current first-version behavior: live API calls are the default. Dummy fixture data requires explicit preview/test mode through `VITE_PREVIEW=true` or `npm run dev:dummy`, cannot be used in production builds, is aliased out of normal production bundles, uses placeholder data rather than initial cached account data, and is visibly labelled in authenticated views. Public and investor data views now show retryable error states and empty states instead of infinite loading or bare table headers.
- Design decision: any fixture-backed authenticated view must carry a clear preview-data warning. The "Open dummy portal" shortcut, UX-state switcher, and "Demo: any 6 digits" code hints are review-only affordances visible only in explicit preview mode. Do not remove or soften the preview warning while fixtures are available.
- Remaining backend/API dependency: final provider delivery, final document/report layouts, profile/settings verification summary, and recovery/default-resolution split detail. Core investor write mutations, deposit instructions, document downloads/evidence packages, and notification list/status now have first-version live API wiring.
- Claude Design action: when polishing the UI, keep the preview warning and fixture/live-data distinction intact. Audit the new retry/error/empty states, the mobile preview-banner layout, and the mobile public help/FAQ access. Do not design fixture states as if they are real account data.
- Priority: important.

## 2026-06-06: Investor Write-Flow Live Wiring

- Screen or component: magic-link login, registration/KYC handoff, withdrawal modal, FX quote/execute, primary investment modal, secondary-market listing modal, and secondary-market purchase modal.
- Current first-version behavior: live mode now uses generated API hooks for magic-link request/consume, natural-person registration, KYC session start/status, sensitive-action email-code request, investor withdrawal request, payout IBAN submission/update, FX quote/execute, primary order/create-clickwrap-allocate, secondary listing create, and secondary purchase. Preview mode keeps clearly marked dummy behavior. Transaction clickwrap uses the current server-published template version and accepts backend-provided checkbox labels rather than hardcoded legal labels.
- Design decision: every money-moving user action must show a review step, server-versioned clickwrap context, explicit email-code request, 6-digit code entry, and a server-error state. Do not make the email-code field look optional in live mode. Do not calculate final financial outcomes in the client; display backend quote/order/listing values where available.
- Remaining backend/API dependency: final legal templates and production PDF/CSV layouts; final provider-backed phone/SMS/SendGrid/Didit/Yahoo flows in deployed environments; final copy for tax and statement disclaimers.
- Claude Design action: run a full production-polish pass on these live mutation flows, including cooldown text after email-code request, stale template/expired quote handling, failed mutation retry/cancel behavior, mobile modal ergonomics, focus management, and clear post-submit states for pending manual operations such as withdrawal.
- Priority: blocking polish.

## 2026-06-06: Investor Payout IBAN Self-Service

- Screen or component: Settings payout accounts card and add/update payout IBAN modal.
- Current first-version behavior: investors can submit an additional CHF/EUR payout IBAN after requesting and entering a `bank_account_change` email code. Live mode posts through `/api/v1/ledger/payout-instructions/`; preview mode shows local success. The submitted instruction does not replace or disable an existing verified deposit-source IBAN. It is clearly labelled pending Garanta verification, is not usable for withdrawals or forced returns until admin verification, and automatically creates a linked finance task for the admin team.
- Design decision: treat payout-account changes as sensitive but operationally pending, not instant. The confirmation copy must say that the 60-day balance deadline is not extended and that Garanta verification is required before the IBAN can be used.
- Remaining backend/API dependency: richer admin review/detail UX for investor-submitted payout instructions, final IBAN verification operating procedure, and production SendGrid delivery of the email-code step.
- Claude Design action: polish the Settings payout-account card and modal, especially mobile form layout and pending-verification status language. Make the distinction explicit between verified source accounts established by deposits and additional accounts awaiting Garanta review; do not imply that requesting another IBAN removes an existing verified payout path.
- Priority: important.

## 2026-06-06: Deposit Instructions, Documents, And Notifications

- Screen or component: Balances deposit modal, Documents screen, Notifications screen, and top-bar notification entry point.
- Current first-version behavior: deposit instructions now load from the backend and display Garanta's configured collection account plus the investor/currency-specific payment reference. Documents now list self-scoped accepted clickwrap evidence plus generated-on-request account statements and annual lender tax-information statements, with PDF/CSV/ZIP download actions where the backend supports them. Notifications now show investor email delivery status and operational notice bodies, while authentication and sensitive-code email bodies are deliberately redacted.
- Design decision: keep these screens operational and evidence-oriented. Deposit copy must not imply instant crediting; it should emphasize bank reconciliation and exact reference matching. Document/tax copy must keep the informational-only/not-tax-advice disclaimer visible. Notification copy must not reveal magic-link URLs or sensitive-action codes in the portal.
- Remaining backend/API dependency: final bank account details in platform settings, final advisor-approved statement/tax templates and PDF/CSV layouts, and production provider delivery/status data.
- Claude Design action: polish the density and hierarchy of the deposit-instruction modal, download action grouping, document type filters, checksum/evidence hints, notification status chips, and mobile table/card behavior. Confirm that users can distinguish generated-on-request files from immutable accepted evidence.
- Priority: important.

## 2026-06-23: Generated Legal Evidence PDFs

- Screen or component: registration acceptance, primary-market investment modal, Documents screen, and accepted-document confirmation states.
- Current first-version behavior: registration can use the imported lender user agreement template, and primary-market investments can use the imported project investment confirmation / claim assignment agreement template. Accepted evidence is rendered on demand as a BANXUM/Garanta PDF with a cover page, table of contents, source-of-truth notice, accepted checkbox, and transaction-specific data populated by the server. Accepted legal terms and transaction-agreement PDFs are no longer emailed by default; users access historical accepted versions from the Documents screen.
- Design decision: treat these PDFs as legal evidence packages, not marketing collateral. The UI should make clear which document was accepted, which transaction it belongs to, when it was accepted, and where the generated PDF/CSV can be downloaded later.
- Remaining backend/API dependency: final counsel-approved template text, final production PDF layout decision, and any later post-close assignment artifact if legal requires a final holding ID after funding close.
- Claude Design action: polish user-facing copy and layout around "terms unavailable", stale-template refresh, accepted-document success, and Documents-screen grouping for historical accepted versions and per-order investment confirmations. Do not design an email-with-attachment expectation for legal terms.
- Priority: important.

## 2026-06-30: Public And Portal FAQ

- Screen or component: logged-out FAQ/How-it-works page and signed-in Help & FAQ screen.
- Current first-version behavior: FAQ content is now a shared React component rendered from a public-safe route (`/faq` or public navigation) and inside the authenticated investor shell. Logged-out visitors no longer hit investor portal gating or authenticated data calls when opening FAQ.
- Design decision: keep FAQ educational and compliance-aware rather than promotional. It explains the P2P model, onboarding/KYC, balance ageing, investment orders, repayments, secondary-market anonymity, FX deadline inheritance, documents, support, and risk warnings without implying guaranteed liquidity or returns.
- Suggested improvement: Claude Design should polish the public FAQ hierarchy, mobile accordion spacing, quick navigation between sections, and whether the public FAQ should include visual diagrams for money flow and 30/60-day ageing rules.
- Priority: important.

## 2026-07-04: FX Market-Closed Availability State

- Screen or component: investor Currency Exchange screen and quote error states.
- Current first-version behavior: live-mode FX now displays a proactive weekend-closed banner and disables quote entry/button on Zurich weekends. Backend quote errors distinguish weekend closure, configured FX market holiday closure, and ordinary temporary provider staleness/malformed provider responses.
- Design decision: closed-market FX should feel like a clear operational unavailability state, not a failed trade. Copy must explain that BANXUM cannot issue executable quotes when live FX market rates are not published, while keeping exchange history readable.
- Suggested improvement: Claude Design should polish the weekend/holiday banner placement, mobile spacing, disabled-form affordance, and whether the exchange form should collapse into a read-only explanatory panel during market closures.
- Priority: important.

## 2026-07-04: Borrower Disclosure On Loan Detail

- Screen or component: authenticated marketplace loan detail, Overview and Documents tabs.
- Current first-version behavior: loan detail now renders the backend-projected borrower disclosure. Legal business name is always public; business classification, registered address, and contact info appear only when Garanta marks that field public for the specific borrower. Internal ownership, bank-account details, KYB/AML observations, and financial-risk notes are not returned to the investor UI. Borrower documents shown in the Documents tab come only from investor-visible, clean-scanned borrower files in the backend disclosure projection.
- Design decision: do not duplicate disclosure visibility rules in the frontend. Hide absent optional fields completely; do not show "unknown" or empty labels. Keep borrower disclosure factual and operational, not promotional.
- Suggested improvement: Claude Design should polish the borrower disclosure section for scanability, especially long address/contact text, financial-metric alignment, document-list hierarchy, and mobile layout inside the loan detail tabs.
- Priority: important.

## 2026-07-08: Refinanced Loan Badge

- Screen or component: public loan preview header, marketplace listing rows, authenticated loan detail header, portfolio holdings rows, and holding detail drawer.
- Current first-version behavior: loans with `is_refinancing: true` show a small monospace `tag` badge - "Refinanced loan" in headers/drawers and a shorter "Refinanced" variant inline next to the loan title in marketplace and holdings table rows. The badge is purely informational and reuses the existing `.tag` styling used for currency/purpose tags.
- Design decision: refinancing is provenance information, not a risk warning. The badge must stay visually neutral (no warn/bad tone) and must not crowd out status, rating, or currency chips.
- Suggested improvement: Claude Design should decide whether the badge deserves a distinct visual treatment from generic currency/purpose tags (for example an outline accent), review truncation/wrapping of the title-plus-tag combination in narrow table cells on mobile, and consider a tooltip or one-line explainer for first-time investors who do not know what a refinanced loan is.
- Priority: nice-to-have.

## 2026-07-08: Original Loan Section On Refinanced Loan Detail

- Screen or component: authenticated marketplace loan detail, Overview tab (`OriginalLoanSection`).
- Current first-version behavior: for refinancing loans, the Overview tab renders an "Original loan" card below the purpose/borrower-disclosure card showing original principal, original interest rate (bps rendered as %), original term, original repayment type, original interest-only period where applicable, original loan start date, and a read-only "Original loan repayment schedule" table (#, due date, principal, interest, total, outstanding after, and a green "Paid" chip on installments settled before publication). The table ends with a bold, separated totals row for the additive amount columns and paid count; the running outstanding-after column is intentionally not summed. Copy states the schedule is informational, shows the loan being refinanced, and that investors fund the new loan whose terms are shown above; the financed amount can be lower than the remaining outstanding of the original schedule.
- Design decision: never present the original schedule as the payment plan investors will receive. Keep the informational disclaimer adjacent to the table, and hide the whole section (not empty labels) when the loan is not a refinancing loan or optional original fields are absent.
- Suggested improvement: Claude Design should polish long-schedule ergonomics (24+ rows): consider collapsing paid installments behind a "show paid installments" toggle or scroll container, sticky table header, a compact paid/remaining summary line above the table, mobile horizontal-scroll behavior for the seven-column table, and whether the section belongs on Overview or a dedicated tab once real refinancing volume exists.
- Priority: important.

## 2026-07-27: Portfolio Holding Detail And Repayment Schedule

- Screen or component: Portfolio Holdings table and holding-detail modal.
- Current first-version behavior: selecting a holding opens a large centered modal instead of a narrow side drawer. It retains holding-level invested, outstanding, interest-received, rate, status, and public-risk-note information. Two tabs separate the investor-specific outstanding principal/interest projection from the authoritative whole-loan schedule, which also shows amounts already paid. Both schedule tables end with a bold, separated totals row; the projection totals principal, interest, and expected payments, while the whole-loan schedule totals contractual, paid, and outstanding amounts.
- Design decision: the investor tab is projected server-side by applying the servicing module's exact largest-remainder distribution algorithm sequentially to all current active holdings. The whole-loan tab remains explicitly labelled as borrower obligations. Both can change after holding transfers, repayments in advance, recoveries, or schedule revisions; the frontend must never derive, prorate, or re-amortize either schedule itself.
- Suggested improvement: Claude Design should review long-schedule ergonomics, sticky headers, paid/upcoming filtering, mobile horizontal scrolling, and whether a later API should add an investor-specific expected-distribution projection alongside the authoritative whole-loan schedule.
- Priority: important.

## 2026-07-27: Secondary-Market Review And Step-Up Flow

- Screen or component: secondary-market buyer listing detail, seller listing modal, and Portfolio-to-secondary-market navigation.
- Current first-version behavior: seller listing is a two-step, large-modal flow. Step one reviews the holding, borrower, rate/term, LTV, pricing, fees, seller proceeds, listed-claim projection, whole-loan schedule, and current seller terms. Only after the seller confirms that data does step two send and request entry of the fresh email code before publishing or submitting for approval. Buyer detail now shows buyer-safe loan context and both schedules without seller identity or seller economics; opening it does not send a code, and the buyer explicitly requests one only when ready to purchase. The Portfolio action opens the Secondary Market directly on `Sell a holding`.
- Design decision: preserve counterparty anonymity and backend-projected schedules. Step-up authorization is deliberately late in the flow so an exploratory buyer receives no unsolicited code and a seller does not authorize data that is still being edited. Seller acceptance evidence and the listing mutation are created only at final submission.
- Suggested improvement: review long-schedule ergonomics inside transaction modals, sticky headers, mobile table scrolling, visual step progression, focus placement when moving to verification, and the hierarchy between loan risk information and transaction pricing. Do not collapse the schedule review into client-side calculations or expose seller-side fields to buyers.
- Priority: important.

## 2026-08-03: Investor Brandbook Reskin

- Screen or component: public preview, onboarding/authentication, investor shell, dashboard, marketplace, portfolio, balances, FX, secondary market, documents, notifications, settings, FAQ, forms, tables, status surfaces, and dialogs. The internal admin console remains visually isolated from this layer.
- Current first-version behavior: the existing production flows now use the `website_redesign` visual language without changing routes, API calls, mutations, data projections, or account-state behavior. The reskin applies the ivory/card/hairline palette, Instrument Sans financial figures, Newsreader editorial asides, carbon binding actions, green add-money/profit semantics, red risk/destructive semantics, pill actions and modes, lighter tables, quieter cards, and tighter responsive layouts. The marketplace retains its live-data filters and expanded detail while matching the redesign's company/rate/term/LTV/capacity/deadline hierarchy.
- Design decision: keep the existing sidebar information architecture and every established workflow. Carbon is the default command color; green is reserved for adding money, positive value, and future active investing-rule state; red is reserved for risk, lateness, penalties, and destructive action. Investor/public styles stay scoped to `.app`, `.public`, and `.auth-wrap` so they cannot restyle the operations-focused admin console.
- Suggested improvement: continue the page-by-page redesign only by adapting existing backend projections and workflows. Verify every future screen at desktop, 768px tablet, and 390px mobile; keep wide financial tables contained rather than creating page-level overflow; and preserve the focused/detailed marketplace modes as fields are added.
- Priority: important.

## 2026-07-27: Consolidated Secondary-Market Listing Management

- Screen or component: Secondary Market `Sell a holding` and `Secondary market activity` tabs, plus Portfolio Holdings status.
- Current first-version behavior: each sellable holding row now shows whether it is unlisted, actively listed, or awaiting approval. An open listing replaces the create action with `Edit` and `Cancel`; editing reprices the same listing through a fresh terms-acceptance and email-code flow, while cancellation removes the listing without changing the holding. Portfolio rows and holding detail show the same listing status. The former `My listings` tab is replaced by a unified activity table covering listing creation/edits, cancellations, purchases, and sales; sales and purchases are selected by default, with filters for listing lifecycle entries.
- Design decision: the holding is the primary management context, so investors should not have to reconcile a separate listing table with their portfolio. Listing edits are labelled as listing activity and share the `Listings and edits` filter; they are not presented as money movements. Edit/cancel controls remain unavailable in read-only impersonation and frozen account states.
- Suggested improvement: Claude Design should review action density on narrow screens, status-chip terminology, keyboard/focus behavior across edit and cancellation modals, filter discoverability, and whether activity rows need a compact detail expansion for historical pricing. Preserve the distinction between listing lifecycle entries and completed sale/purchase cash movements.
- Priority: important.

## 2026-07-27: Servicing-Ready Status And Automatic Listing Repricing

- Screen or component: Portfolio holding detail, full-loan schedules, Secondary Market listing/buy views, activity, and repayment-credit notifications.
- Current first-version behavior: `Funded` now means funding closed but borrower payout still pending; the loan becomes `Active` only after the borrower disbursement succeeds. Funded holdings remain visible, but their secondary-market action is disabled with an explicit post-disbursement availability hint. Investor full-loan schedules show immutable historical regular and advance payments followed by the latest outstanding schedule, while investor holding projections remain future-only. Every unsold open secondary listing is automatically recalculated after repayment, recovery, or servicing-status change from the latest holding/loan state while preserving the seller's premium/discount percentage. Repayment-credit notices mention this recalculation only when that investor's listing remains active. If the loan becomes late/defaulted, the listing status tooltip explains that it is hidden pending Garanta reapproval.
- Design decision: do not present a funded-but-undisbursed loan as servicing-active, do not derive historical schedule rows or listing economics in the client, and do not imply that the seller's absolute listing price is fixed after principal changes. The durable seller instruction is the premium/discount percentage (`price_bps`).
- Suggested improvement: clarify `Funded - awaiting borrower payout` versus `Active` in status tooltips; visually distinguish historical payment rows from projected rows; add an unobtrusive “Repriced after repayment” activity/detail treatment; and make the preserved premium/discount explicit in active-listing summaries without exposing internal recalculation metadata.
- Priority: important.

## 2026-08-03: Marketplace Redesign And Brand-System Adoption

- Screen or component: authenticated investor shell brand lockup and primary Marketplace route.
- Current behavior: the investor frontend self-hosts the `Instrument Sans` and `Newsreader` variable fonts and uses the BANXUM redesign palette through the production token layer. The Marketplace page uses the approved editorial heading and account-aware supporting copy, displays the configured minimum investment, labels the selected currency balance as available to invest, and exposes the authoritative Smart Invest state. Marketplace structured filters can be saved as the investor's one active rule and route to the Smart Invest page; search text, sorting, and focused/detailed view are not persisted. Focused rows follow the redesign's Company, Yield, Term, Collateral margin, Available to invest, and Availability order. Search, filter/sort controls, the Detailed secondary row, loan status/rating/currency/refinancing provenance, funding progress, and all existing investment flows remain intact.
- Design decision: `website_redesign/` is a visual/IA reference, not executable production code. Smart Invest is a server-owned discovery and first-publication alert rule, never an automated investment mandate. The setup wizard has five steps only: collateral, currency, optional minimum yield, optional maximum term, and review. The design-reference repayment/reinvestment and originator-concentration questions are intentionally excluded because the product neither auto-invests nor enforces a concentration cap. Fabricated 30/60-day capacity forecasts remain excluded; financial eligibility and investment actions continue through the ordinary server-enforced flow.
- Remaining backend/API dependency: none for the one-rule Smart Invest foundation, matching projection, transactional match alert, Marketplace save action, or dashboard widget. The marketplace preview still omits some authenticated detail fields; add them only through backend investor projections after product/compliance approval, never by copying disclosure logic or financial calculations into the frontend.
- Suggested improvement: continue the redesign route by route while retaining the current menu and data contracts. Recheck the opportunity desk with production-scale row counts, add backend pagination before the list becomes large, and conduct a final keyboard/screen-reader pass after the remaining investor screens adopt the new tokens.
- Priority: important.

## 2026-08-06: Smart Invest Rule And Setup Wizard

- Screen or component: Smart Invest menu route, five-step setup wizard, manual criteria editor, Marketplace `Save Smart Filters` action, dashboard match widget, and active/inactive rule state.
- Current behavior: an eligible investor can activate one server-owned rule from structured Marketplace criteria, review current matching opportunities, adjust it, or deactivate and clear it. Smart Invest is a peer navigation item immediately after Investment Opportunities, not an indented child. The wizard asks only about collateral, CHF/EUR scope, optional minimum yield, optional maximum term, and review. It has no repayment/reinvestment preference and no originator-concentration step. A newly published match creates one transactional alert per investor/loan pair; it never reserves funds or places an order. The redesigned dashboard shows currency-separated invested principal, schedule-backed upcoming payments, received interest, idle balances, required actions, and the current Smart Invest rule/matches without combining currencies or fabricating reinvestment. Clicking a matching loan on either surface opens the same opportunity sheet and ordinary reviewed investment flow. Superadmin read-only impersonation can view but cannot change the rule.
- Design decision: preserve the v9 editorial hierarchy and rule-state treatment while keeping every financial action explicit. Keep Smart Invest adjacent to Investment Opportunities as a separate first-class route. Dashboard values must remain server-projected and currency-separated. Do not reintroduce the design-artifact concentration, repayment, or reinvestment questions unless a later product decision introduces an enforceable portfolio-policy model.
- Suggested improvement: perform a final production-data visual pass for long Loan Originator names, zero-match and many-match states, keyboard focus inside the wizard, and small mobile viewports. Keep risk wording visibly adjacent to matching results.
- Priority: important.

## 2026-08-03: CHF/EUR Currency Exchange Redesign

- Screen or component: investor Currency & FX route, conversion preview, executable-quote handoff, balances, availability notices, and exchange history.
- Current behavior: the page now follows the `website_redesign/fx.html` composition while retaining BANXUM's existing CHF/EUR-only launch scope and audited execution flow. A large converter shows source and target currencies, source balance, target proceeds, platform fee, and the effective rate net of fees. The effective rate is centered in the conversion action band and Convert sits in that same row; the reference design's EUR-only lending explanation and incoming-payment conversion row are intentionally omitted. A compact right rail shows CHF/EUR balances and the material FX controls. History remains a real self-scoped backend projection and now presents Date, Converted, Rate net of fees, and Received rather than fabricating provider/reference fields BANXUM does not store.
- Design decision: live amount previews are computed by a non-persistent backend endpoint using the same provider freshness/sanity validation, configured fee, exact minor-unit rounding, and daily-limit logic as executable quote issuance. The browser never fetches or calculates a provider rate. Previewing creates no legal or append-only quote evidence; Convert requests a fresh 60-second executable quote and then enters the existing terms/email-code confirmation flow. CHF/EUR are the only currencies shown. Weekend, configured holiday, and temporary-provider-unavailable states remain explicit and fail closed while balances/history stay readable.
- Remaining backend/API dependency: none for the implemented CHF/EUR conversion and history screen. Yahoo availability and approved provider terms remain operational go-live dependencies. Future currencies, richer provider provenance in history, or a persistent indicative-rate feed require explicit backend contracts and must not be inferred in the client.
- Suggested improvement: validate rate/fee legibility with production-sized history, review the converter's keyboard and screen-reader announcement order, and keep the mobile source/target relationship clear without replacing exact amounts with decorative charts.
- Priority: important.

## 2026-08-04: Portfolio Redesign And Data-Grounded Risk Widgets

- Screen or component: investor Portfolio route, My loans table, earnings calendar, portfolio-spread, collateral-spread, and borrower-default panels.
- Current behavior: the Portfolio route now follows the redesign while retaining the live self-scoped holdings, Activity, and Orders projections. All money remains integer-minor-unit data rendered with the shared currency-aware formatter. The portfolio-spread widget uses current concentration, purpose, disclosed LTV, collateral type, and current late/defaulted exposure; it does not infer a historical on-time-payment ratio from schedule-event rows. Collateral classification uses the loan's explicit collateral type, while weighted LTV includes only secured holdings with a disclosed LTV. Default-interest figures come from each loan's configured annual `default_penalty_interest_bps`; zero means not configured. Recovery copy shows the universal non-overridable order of Garanta legal costs/recovery fee, penalty/default interest, contractual interest, then principal; loan terms may change amounts due but cannot move principal ahead of another due tier. Collateral values can change and recovery timing is not guaranteed.
- Design decision: preserve the redesign's four-widget composition without presenting reference-prototype assumptions as live financial or legal terms. Do not add fixed daily penalty rates, fixed court timelines, guaranteed collateral outcomes, or client-derived payment-performance history. Where the API cannot prove a metric, use a narrower current-state metric or add an authoritative backend projection first.
- Remaining backend/API dependency: a historical payment-performance score and project-specific recovery-duration estimate require canonical servicing/reporting projections and approved disclosure semantics before they can appear. The current implementation deliberately omits both.
- Suggested improvement: review dense expanded-panel copy and chart labels with legal/compliance, test long borrower and collateral labels, and retain the no-page-overflow behavior at 390px, 768px, and desktop widths.
- Priority: important.

## 2026-08-04: Portfolio Tabs, Tables, And Empty States

- Screen or component: investor Portfolio route, `My loans`, `Activity`, and `Orders` tabs, primary-order information tooltip, portfolio insights, and no-data states.
- Current behavior: `Activity` and `Orders` now use the same unframed, strong-rule financial-table language as Marketplace and `My loans`, while preserving all existing dates, references, categories, amounts, identifiers, allocation values, and status explanations. The four portfolio-insight widgets sit below the selected tab and remain available when switching between populated or empty Activity/Orders views. They are hidden only when the selected currency has no active holdings, because calendar, concentration, collateral, and default metrics would otherwise be misleading. Empty holdings and orders provide direct Marketplace/Orders actions. The former full-width primary-order notice is now an accessible hover/focus/tap tooltip next to the Orders tab.
- Design decision: tab selection changes the transaction dataset, not the investor's underlying portfolio insight. Currency selection therefore remains available on every tab and controls the persistent holdings-derived widgets. Wide Activity and Orders tables scroll only inside their own container; the focused `My loans` table has no desktop/tablet overflow and enables contained horizontal scrolling only at narrow widths where its columns cannot fit.
- Remaining backend/API dependency: none for this behavior. Server-side pagination will be required before Activity or Orders histories become large enough that returning the complete self-scoped dataset affects response or rendering performance.
- Suggested improvement: keep this header-rule, restrained-row, tabular-number treatment as the baseline while redesigning the remaining investor tables page by page. Test unusually long loan titles, localized status labels, and high-volume histories before launch; do not solve long histories by shrinking text below the established table scale.
- Priority: important.

## 2026-08-04: Portfolio Insight Grid And Compact Order References

- Screen or component: Portfolio insight widgets and the `Orders` table identifier columns.
- Current behavior: the four holdings-derived widgets form two equal-width cards per row when the content area can support them. Opening either card places its full detail panel across the entire width immediately below that two-card row. At 860px and below, each widget expands to the available tab/content width and its detail follows the selected card directly. Orders use a numbered compact reference (`#1`, `#2`, and a shortened identifier) plus an unframed copy icon; the loan column uses the bold loan title plus an equivalent icon. Hover/focus text and accessible names preserve `Copy order ID` and `Copy loan ID`, while the complete identifiers remain out of the visual hierarchy.
- Design decision: insight cards should scan as a balanced two-column dashboard on wide screens without making their expanded analysis compete for half-width space. On narrow screens, legibility takes priority over retaining two columns. Copy controls are utilities rather than primary actions, so they have no border, pill, padding, or visible label in dense tables.
- Remaining backend/API dependency: none. Compact references are presentation-only and always copy the authoritative complete backend ID.
- Suggested improvement: validate widget heights with production-scale labels and translated copy, and consider a shared icon-only utility tooltip primitive if the same compact identifier pattern is adopted across more investor tables.
- Priority: important.

## 2026-08-04: Secondary-Market Redesign And Authoritative Buyer Economics

- Screen or component: Secondary Market `For sale now`, `Sell a holding`, and `Secondary market activity` tabs, buyer listing table, seller summary, and buyer detail modal.
- Current behavior: the route now follows the redesign's editorial hierarchy and three-tab navigation while preserving the existing anonymous browse, full-holding listing/edit/cancel, filtered activity, terms, risk acknowledgement, schedules, and sensitive-action flows. Buyer rows show server-owned outstanding principal, transfer asking price, premium/discount, remaining unpaid installments, and total buyer cost. Loading, error, empty, frozen, and read-only states remain distinct; frozen/read-only viewers can inspect buyer-safe listing detail but cannot request a code or purchase.
- Design decision: do not estimate an investor's effective annual return in the browser. Actual yield depends on purchase price, accrued interest, fees, repayment type, timing, future servicing changes, and the complete cash-flow schedule. Until an approved backend yield projection exists, the table uses authoritative buyer total cost and the premium/discount explainer remains qualitative. Seller availability copy distinguishes immediately listable, non-performing approval-required, and funded-awaiting-disbursement holdings.
- Remaining backend/API dependency: an effective annual buyer-yield or IRR column requires a canonical server-side calculation, definition, rounding policy, disclosures, and tests for every repayment type. It must not be restored as a client-side approximation.
- Suggested improvement: review long mixed-currency listing tables, compact activity filters, and buyer-detail schedule density at production scale. Preserve contained horizontal scrolling on narrow screens and keep seller identity/economics out of every buyer projection.
- Priority: important.

## 2026-08-04: Investor Data-Table System Pass

- Screen or component: public loan preview, Dashboard opportunities, Balances lots, Portfolio Activity and Orders, Secondary Market browse/sell/activity, Documents, FX history, and loan/investment schedules.
- Current behavior: investor-facing datasets now share the redesign's open financial-table grammar: a strong top rule, restrained uppercase headers, consistent row rhythm, tabular right-aligned amounts, subtle separators and hover feedback, compact utility actions, and horizontal scrolling contained within the table rather than the page. Marketplace, Portfolio My loans, FX history, and secondary buyer listings retain their domain-specific responsive compositions; legacy card frames were removed from public/dashboard loans, balance lots, seller holdings, secondary activity, and document history. Schedule tables retain their detail/modal containers and totals rows. Filtered Documents now shows a deliberate empty state instead of a header-only table.
- Design decision: visual consistency does not mean forcing every dataset into identical columns or mobile behavior. Operational schedules remain denser than browse tables; marketplace and secondary buyer rows retain their information hierarchy; admin-console tables remain intentionally separate and work-focused. Wide financial datasets scroll internally at narrow widths rather than shrinking money, statuses, or legal references below the established type scale.
- Remaining backend/API dependency: high-volume Activity, Orders, Documents, and balance-lot datasets need server-side pagination before production volume makes full self-scoped responses expensive. No client-side truncation was introduced in this pass.
- Suggested improvement: validate long translated labels, large histories, mixed currencies, and screen-reader table navigation with production-scale fixtures. Consider stacked mobile rows only for the highest-frequency user workflows after usability testing; retain native table semantics for schedules and audit-like histories.
- Priority: important.

## 2026-08-04: Navigation, Add Funds, And Select Controls

- Screen or component: investor sidebar, sticky header, Add Funds bank-transfer modal, registration, Marketplace filters, payout controls, QA state switcher, and admin select inputs.
- Current behavior: the primary navigation now uses `Investment Opportunities` and `My Portfolio`; Notifications remains available from the persistent header bell and no longer consumes a duplicate sidebar row. `Add Funds` is the single action label on Dashboard and Balances, and a persistent green header action opens the existing self-scoped bank-transfer instructions with an explicit CHF/EUR selector. On mobile, balances collapse while Add Funds stays beside the notification control. Sidebar labels remain single-line at the supported 320px minimum viewport. Native select elements retain platform/mobile accessibility while sharing one deliberate surface, chevron, hover, focus, and disabled treatment across investor, onboarding, and admin interfaces.
- Design decision: technical and regulatory nouns such as deposit reconciliation and deposit protection remain unchanged where they describe actual concepts; only the user command is normalized to `Add Funds`. The Notifications route and history screen remain intact even though its sidebar link was removed. The header action reuses the canonical deposit-instruction projection and does not introduce a second funding workflow or any client-side bank-account logic.
- Remaining backend/API dependency: none for these shell and control changes. Available funding currencies continue to come from the backend instruction projection.
- Suggested improvement: validate unusually long translated navigation labels before localization and confirm native option-menu rendering on the supported iOS, Android, Windows, and macOS browser matrix.
- Priority: important.

## 2026-09-07: Loan Originator Subscription Opportunities And Holdings

- Screen or component: Investment Opportunities common table/detail, finite
  subscription review, funding-close exception states, My Portfolio holding detail, activity, documents,
  and secondary-market buyer detail.
- Current behavior: direct BANXUM loans and Loan Originator claims share the primary
  opportunity table. The common rate column is `Yield`; an originator row carries a
  Loan Originator badge/name and opens a product-aware detail with anonymized
  borrower disclosure, underlying coupon, nominal participating yield, separate
  interest/penalty participation, minimum investment, funding deadline, maturity,
  current outstanding/sellable principal, and post-boundary cash flows. Current
  subscriptions reserve balance at par after clickwrap/email-code confirmation.
  Successful close creates holdings and immutable post-boundary entitlements in the
  same transaction. The boundary installment belongs entirely to the LO and its
  actual bank receipt is recorded separately. Portfolio and
  activity identify activated originator claims and show investor cash-flow projections.
  Performing originator holdings may be resold at par or a discount, not a premium.
- Design decision: never present the underlying coupon as a promised investor IRR,
  never imply returns are guaranteed, and never expose private final-borrower legal
  name unless explicitly published per loan by an admin, originator settlement status,
  or internal import references. Explain that no
  investor interest accrues during funding or on the boundary installment; one unit
  of cash buys one unit of principal at activation; later interest and penalty rights
  use separate declared participation. Failed close preserves the reservation and
  alerts operations; cancellation restores the original balance-lot amounts and
  ageing dates. No originator recourse/buyback exists.
- Remaining backend/API dependency: non-performing originator-claim resale is
  intentionally blocked until an approved impaired-accrual/default-entitlement
  pricing projection exists. Do not design around or bypass that v1 boundary.
- Suggested improvement: run final mobile/tablet usability and accessibility review
  with long originator names, mixed currencies, near-deadline rounds, close-failure
  and legacy upgrade exceptions, empty projections, and cancellation/refund copy. The
  review should preserve the existing marketplace table hierarchy rather than
  introducing a separate marketplace.
- Priority: important.

## 2026-08-04: Loan-Originator Retention Disclosure

- Screen or component: originator-claim marketplace detail, investment terms, and portfolio holding detail.
- Current behavior: a positive server-owned retention percentage is disclosed as the minimum share of current outstanding principal retained by the named Loan Originator. The holding view states only that the retained claim is not offered to investors; it does not infer historical cash flows, loss parity, recourse, or recovery outcomes in the browser. A zero value is intentionally omitted.
- Design decision: describe the mechanism factually as an ownership/availability floor, not as protection or a guarantee. All retained and sellable amounts are calculated by the backend with ceiling rounding in minor units. Investor screens consume only the percentage and authoritative schedules supplied by the API.
- Remaining backend/API dependency: none for the current disclosure. Any future comparison of originator and investor realized losses or recoveries requires a dedicated server projection and approved legal wording.
- Suggested improvement: validate the disclosure with legal/compliance and test 0%, fractional percentages, 99.99%, long originator names, and narrow screens without promoting the retention percentage into an implied credit rating.
- Priority: important.

## 2026-10-09: Session Expiry, Blocked Accounts, Logo Home Link

- Screen or component: investor log-in screen, expired-link screen, portal "Account access" page, site/sign-in/registration logos.
- Current behavior: sessions end 2 hours after login; the next API call returns the investor to Log in with a "Your session has expired" notice (kept until a new link is requested). A restricted, locked or closed account with an open session sees an "Account access" page with the status and support address instead of portal screens; a valid link of a restricted or locked account shows "Your account is restricted/locked" with a Contact support button. The expired-link screen keeps its email field while typing and sends only on Enter or the button. Every logo outside the portal links to the Overview when an investor is signed in and to the home page otherwise.
- Suggested improvement: decide whether to warn shortly before the 2-hour limit (the API does not expose the expiry time yet), and review the Account access page copy with compliance for each status.
- Priority: nice-to-have.

## 2026-10-09: KYC Verification Under Review

- Screen or component: investor Verification page (KYC status) and registration KYC step.
- Current behavior: a case that waits for an admin decision (decline, manual review, AML hit, provider re-check) shows "Verification under review" with "Your verification is under review. We will contact you." and no start button; the API refuses a new session with the same text (409). AML hits read as manual review in the investor API. The start button returns only after an admin requests re-verification.
- Suggested improvement: keep the copy non-revealing (never name sanctions, PEP or adverse media); consider a restart action on the "Waiting for verification result" state when the Didit session has expired, and a timeline step label for "under review".
- Priority: nice-to-have.

## 2026-10-09: Secondary Buy Modal Price Lock

- Screen or component: secondary-market Buy modal ("For sale now" > Buy).
- Current behavior: the review rows (principal, sale price, accrued interest, taker fee, total cost) come from the freshly loaded listing detail, and the purchase sends those reviewed values. If the price changed before confirm (seller edit, repayment repricing, or a new day's accrued interest), the server rejects the purchase with nothing charged; the modal shows a "Price changed" banner, reloads the new price, unticks the terms checkbox and keeps the entered email code so the buyer can review and confirm again.
- Suggested improvement: highlight which rows changed (old vs new total) and consider a short note that accrued interest grows daily, so a review left open overnight must be refreshed.
- Priority: nice-to-have.

## 2026-10-09: Notification Centre Content

- Screen or component: investor Notifications page and header bell.
- Current behavior: only real notices are listed (sign-in links and confirmation codes are left out and never counted as unread). Each row shows the notice time (when the event happened, platform clock) and a short label such as Deposit, Withdrawal, Funding, Loan status or Balance reminder. New notices cover deposits, withdrawals, forced returns, penalty mode, payout IBANs, currency exchange, primary orders, funding close/cancel, order release and Late/Defaulted loans; each opens its balance, FX, portfolio or holding page.
- Suggested improvement: filter chips by label, group same-day balance reminders of different currencies, and a calmer layout for long bodies (the full email body is shown today).
- Priority: nice-to-have.

## 2026-10-09: Login Links, Repeated Registration, Phone Correction

- Screen or component: login-link and registration emails, registration step 2 ("Verify your phone").
- Current behavior: login emails link to `/login#token=...`; the portal removes the token from the address bar before any request. A registration for an address that already has an account gets the same "Magic link sent" screen; the owner gets an email that says the account already exists (with a sign-in link for investors). Nothing stored changes. On the phone step, "Send SMS" uses the number typed at registration; until the phone is verified, this corrects a wrong stored number. The page does not show the stored number when it differs.
- Suggested improvement: show the stored number (masked) on the phone step with an explicit "Change number" control, and review the "account already exists" email copy.
- Priority: nice-to-have.

## 2026-10-09: Withdrawal Review, Forced Returns and Penalties in Activity

- Screen or component: Withdraw modal (Review step) and the My investments > Activity table.
- Current behavior: the Review step shows the destination IBAN and account name before the email code. Activity lists each day-60 penalty charge ("Penalty charged: balance past the 60-day limit", tag "penalty") and labels forced returns "Forced return to your bank account" (tag "forced return"); a cancelled one reads "Forced return cancelled". Payee names come from the verified payout IBAN.
- Suggested improvement: link a forced-return or penalty line to a short explanation of the 60-day rule and the payout IBAN used; group daily penalty lines per lot when there are many.
- Priority: important.

## 2026-10-09: Completed Holdings, Holding Page States, Borrower Document Download

- Screen or component: My investments (new "Completed" tab), holding page, loan page "Documents" card.
- Current behavior: repaid, sold and closed holdings are listed under My investments > Completed with the result (Repaid, Sold, Written off), invested amount and interest received; Open goes to the holding page. The holding page counts borrower installments (not payment rows), shows "Matures <date>" for Loan Originator claims, and a loan in default opens on the overdue payment; its future installments read "Not expected". Each borrower document on a loan page has a Download button; a refused download shows the reason under the list.
- Suggested improvement: add a final summary for completed holdings (total received, return, end date) and filters by result; decide the wording for future installments of a defaulted loan with compliance.
- Priority: important.

## 2026-10-09: Invest Results, Seller Pricing, Own Listings

- Screen or component: invest page result step, Smart Invest batch review, loan quick-view sheet, listing form, "For sale now".
- Current behavior: the invest result shows what the server did: "Order placed" (reserved), "Order partly placed" (only part of the amount was left) or "Order not placed" (less than the minimum was left; red banner, nothing moved). A new amount or Back to the amount step needs the terms ticked again. The batch review needs the same risk acknowledgement as a single investment. The listing form shows the server's transfer price, accrued interest, maker fee and net proceeds for a sale today. Your own listing shows a grey "Your listing" pill instead of Buy and opens a view without terms or code. Amount fields keep the decimal comma and accept ' ’ and spaces.
- Suggested improvement: design the partly placed / not placed states (icon, next step such as "Find another loan"), show the accrued-interest growth per day on the listing form, and style "Your listing" rows (badge, muted row) at phone width.
- Priority: nice-to-have.

## 2026-10-09: Frozen Account Banner, Account Page, Phone Tables, Dialogs

- Screen or component: investor shell banner (day-60 penalty mode), Account page (payout IBANs, pending withdrawals), phone tables (Account lots, Activity, Orders, Documents, Smart Invest matches), all dialogs, FX confirmation.
- Current behavior: the frozen state comes from the balances API; one red banner on every page says what is frozen, the daily penalty, and to add a payout IBAN (button opens the IBAN dialog); Invest, FX, secondary trades and Add Funds are blocked with the reason. IBANs show Verified / Pending verification; pending withdrawals list forced returns with a "Forced return" chip. Below 640 px tables become stacked label/value rows. Dialogs take focus, keep Tab inside, give focus back, and ignore Escape while a money action runs. The FX confirmation counts the quote down and offers "Refresh quote". Unknown addresses show a "Page not found" page.
- Suggested improvement: design the stacked phone rows (spacing, which fields lead), a compact variant of the frozen banner after the first visit, the empty-IBAN state of the Withdraw dialog, and the 404 page artwork. Portfolio widget cards are still whole-card buttons (long accessible names) and some pages jump heading levels (Banner titles are h4).
- Priority: important.
