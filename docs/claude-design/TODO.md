# Claude Design TODO

This file is the working brief for Claude Design. Claude Design owns the complete user-facing UI/UX pass for BANXUM before launch. Implementation agents should add entries here whenever they build or touch public, investor, client-portal, onboarding, marketplace, documents, payments, FX, reporting, or account-settings UI visible to platform users.

Admin console UI/UX is not owned by Claude Design. Admin console screens are implemented and designed by the Codex implementation agent and tracked in `docs/admin-console/TODO.md`.

## Ownership Boundary

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
- If a balance cannot be invested because its remaining window is too short for a loan funding deadline, the UI must explain that the amount is withdraw-only for that purpose.
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
  - withdraw-only because investment deadline passed or loan funding deadline would exceed the remaining window.
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
- If loan amount is lowered after committed investments, show the admin's investor message/reason in the relevant loan/order/notification surfaces.

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
- Current first-version behavior: investors can submit a CHF/EUR payout IBAN after requesting and entering a `bank_account_change` email code. Live mode posts through `/api/v1/ledger/payout-instructions/`; preview mode shows local success. The submitted instruction replaces the previous active instruction but is clearly labelled pending Garanta verification and is not usable for withdrawals or forced returns until admin verifies it.
- Design decision: treat payout-account changes as sensitive but operationally pending, not instant. The confirmation copy must say that the 60-day balance deadline is not extended and that Garanta verification is required before the IBAN can be used.
- Remaining backend/API dependency: richer admin review/detail UX for investor-submitted payout instructions, final IBAN verification operating procedure, and production SendGrid delivery of the email-code step.
- Claude Design action: polish the Settings payout-account card and modal, especially mobile form layout, pending-verification status language, and the warning that replacing the active payout instruction may temporarily leave the investor without a usable verified payout path.
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
