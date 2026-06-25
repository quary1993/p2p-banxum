# Admin Console UI/UX TODO

This file captures admin console UI/UX work owned by the Codex implementation agent. Claude Design is not responsible for admin console design or redesign; Claude Design should focus on user-facing/public/investor UX.

## Standing Instruction

Admin console screens should be implemented as complete operational UI by Codex during the relevant implementation slices. The admin console should be dense, clear, restrained, auditable, and optimized for repeated operational work rather than marketing-style presentation.

When an implementation slice builds or touches admin console UI, record follow-up items here. Do not move admin console UI/UX work to `docs/claude-design/TODO.md`.

Each entry should include:

- Date.
- Screen or component.
- Current first-version behavior.
- Required admin-console improvement.
- Priority: blocking polish, important, or nice-to-have.

## 2026-06-01: Initial Admin Shell

- Screen or component: admin portal shell, layout, navigation, dashboard entry points.
- Current first-version behavior: simple root React scaffold shell with top bar, module navigation preview, and status summary.
- Required admin-console improvement: Codex should implement the final admin information architecture, dense navigation, dashboard/task entry point, responsive operational layout, component tokens, table/form states, and consistent admin status language as admin screens are built.
- Priority: important.

## 2026-06-02: Admin Authentication Foundation

- Screen or component: admin login, admin email-code confirmation, and superadmin admin-user creation screens.
- Current first-version behavior: no UI was implemented in this slice; only backend API, OpenAPI schema, generated TypeScript client, and tests exist.
- Required admin-console improvement: Codex should implement the full admin authentication journey, including password entry, email-code confirmation, locked/error states, resend/cooldown messaging, first superadmin bootstrap guidance, regular-admin creation form, and audit-friendly operational copy.
- Priority: important.

## 2026-06-02: KYC Manual Review And Account Controls

- Screen or component: KYC manual-review queue, KYC case decision panel, account restrict/lock/close/reactivate controls.
- Current first-version behavior: no UI was implemented in this slice; only backend API, OpenAPI schema, generated TypeScript client, append-only evidence models, and tests exist.
- Required admin-console improvement: Codex should implement the full admin compliance workflow, including queue filters, risk/status badges, provider-reference display, evidence summaries, decision forms, non-overridable sanctions/decline messaging, re-verification flow, account-control confirmation dialogs, closure clean-account confirmation copy, audit trail display, and clear distinction between Didit provider review and Garanta internal review.
- Priority: important.

## 2026-06-02: Admin Operations Task Queue

- Screen or component: admin task queue, task detail, task event history, audit-log search.
- Current first-version behavior: no UI was implemented in this slice; only backend API, OpenAPI schema, generated TypeScript client, append-only task-event evidence, and tests exist.
- Required admin-console improvement: Codex should implement the admin operational task workflow, including dashboard entry point, filters, saved views, SLA/due-date states, priority indicators, assignment controls, related-object links, empty states, task completion/cancellation copy, task event history display, and audit-log search ergonomics.
- Priority: important.

## 2026-06-02: Borrower Entity Foundation

- Screen or component: borrower list, borrower detail, KYB/compliance status controls, borrower document panel, investor-disclosure preview.
- Current first-version behavior: no UI was implemented in this slice; only backend API, OpenAPI schema, generated TypeScript client, borrower/document/event models, append-only borrower event evidence, and tests exist.
- Required admin-console improvement: Codex should implement the admin borrower workflow, including dense borrower search/filter table, create/edit forms, KYB status confirmation copy, compliance-hold indicators, optional financial disclosure inputs with currency/minor-unit formatting, operational fields, document linking/upload states, clean-scan visibility states, investor-disclosure preview, and borrower event history.
- Priority: important.

## 2026-06-02: Ledger Balance Ageing Operations

- Screen or component: investor payout-instruction management, balance-ageing scan, forced-withdrawal queue, penalty-mode review.
- Current first-version behavior: no UI was implemented in this slice; only backend API, OpenAPI schema, generated TypeScript client, payout-instruction model, ageing scan service, forced-withdrawal request generation, penalty-mode transition evidence, and tests exist.
- Required admin-console improvement: Codex should implement operational screens for registering verified payout IBANs, reviewing active payout instructions by investor/currency, running or inspecting balance-ageing scans, seeing due reminders, identifying forced-withdrawal requests, reviewing lots moved into penalty mode because no usable IBAN exists, and linking each item to ledger evidence/audit events.
- Priority: important.

## 2026-06-02: Document Templates And Clickwrap Evidence

- Screen or component: superadmin document-template/version editor, template publication workflow, clickwrap evidence viewer.
- Current first-version behavior: no UI was implemented in this slice; only backend API, OpenAPI schema, generated TypeScript client, immutable template versions, publication service, current-template lookup, clickwrap acceptance evidence, append-only guards, and tests exist.
- Required admin-console improvement: Codex should implement the superadmin template editor and publication flow, including category/key/language selection, body editor, checkbox-label editor, variable-scope helper panel, placeholder validation errors, legal-review reference fields, version history, current-published marker, acceptance evidence search, and links from transaction/admin workflows to accepted document evidence.
- Priority: important.

## 2026-06-05: Daily Operations Dashboard API

- Screen or component: admin daily operations dashboard.
- Current first-version behavior: backend-only dashboard API is available at `/api/v1/admin-ops/dashboard/`; it returns summary counters, currency-level operational buckets, and short queues for tasks, KYC review, bank-operation exceptions, withdrawals, balance ageing, funding loans, servicing due items, risk loans, secondary-market approvals, unsettled FX, failed email outbox messages, and reconciliation breaks.
- Required admin-console improvement: Codex should implement the full dashboard screen using this API, including dense KPI cards, currency bucket table, queue tabs, severity/status badges, due/overdue states, drill-through links to the owning operational screen, refresh controls, empty/error/loading states, and a compact responsive layout suitable for daily finance/compliance operations.
- Priority: important.

## 2026-06-05: Admin Shell And Daily Operations Dashboard

- Screen or component: `/admin` console shell, admin login entry, daily operations dashboard, queue detail drawer, currency operations table.
- Current first-version behavior: implemented a Codex-owned admin console route using the generated admin dashboard API. In preview/test mode it uses isolated dummy admin operations data; in live mode it fetches `/api/v1/admin-ops/dashboard/`. The shell includes dense left navigation, top status bar, KPI cards, queue selector, queue table with status/priority/due indicators, item detail drawer with metadata, refresh/error/loading/empty states, and currency-level operation summaries. Admin email/password plus email-code login UI is present and uses the generated admin auth mutations outside preview mode.
- Required admin-console improvement: implement module-specific drill-through workflows from each queue item, including task detail/update, KYC manual decision forms, bank-operation reconciliation screens, withdrawal finalization, ageing scan review, loan close/servicing/risk note actions, secondary-market approval, FX settlement declaration, failed-email handling, reconciliation snapshot investigation, audit timeline display, and permission-specific controls for superadmin-only surfaces. Add explicit admin role/permission labels when the backend exposes finer-grained roles.
- Priority: important.

## 2026-06-05: Admin Operations Task Queue UI

- Screen or component: `/admin` Tasks navigation item, operational task table, task filters, create-task modal, task detail/update drawer, task event history.
- Current first-version behavior: implemented the task queue with generated admin task list/create/patch/event APIs in live mode and isolated local preview updates in dummy mode. Admins can filter by status, priority, type and text; create internal tasks; inspect task metadata; update title/type/status/priority/due date/notes/completion note; use quick status actions; and view append-only task lifecycle events returned by the backend. Preview/test mode includes dummy tasks and event history without backend calls.
- Required admin-console improvement: add assignment controls once admin-user search/listing is exposed, richer saved task views, SLA color rules based on backend-provided current time, related-object deep links to each owning module screen, event metadata expansion, and bulk task operations if operations volume requires it.
- Priority: important.

## 2026-06-05: Admin Module Completion First Version

- Screen or component: `/admin` Compliance, Finance ops, Loans, Reports, and Superadmin settings navigation items.
- Current first-version behavior: implemented module-owned operational panels using the generated backend API client. Compliance shows the KYC manual-review queue, AML decision form, and account-access controls. Finance ops includes lender deposit declaration, payout IBAN registration, balance lookup, ageing scan, reconciliation snapshot, withdrawal finalize/cancel, borrower disbursement, FX delta/realized reports, and FX external settlement declaration. Loans includes borrower and loan tables, borrower creation, loan draft creation, publish/close funding/release order actions, servicing repayment/status/risk-note/recovery actions, and secondary-market approval/reject/remove forms. Reports includes report generation and audit-event search. Superadmin settings includes document template version listing, template create/publish, admin-user creation, and account-access controls. Preview mode uses dummy data and local action confirmations; live mode posts only through generated API hooks.
- Required admin-console improvement: replace ID-only action inputs with deep links and prefilled module context from dashboard/task rows once backend list/detail APIs expose the needed records. Add admin-user search/listing for assignment and access controls; evidence-file upload widgets for payment/servicing actions once storage endpoints are exposed; document acceptance evidence search; borrower document linking and investor-disclosure preview panels; report download helpers for base64 CSV/PDF/ZIP responses; richer validation for integer minor-unit fields; and permission labels if Garanta later adds more granular compliance/finance roles beyond admin/superadmin.
- Priority: important.

## 2026-06-05: Admin Console Audit Follow-Ups

- Screen or component: admin data tables on Compliance, Loans, Reports and other dense module screens.
- Current first-version behavior: added CSS containment so cards inside admin grids can shrink and wide tables scroll within their own table wrapper instead of causing page-level horizontal overflow on narrow screens.
- Required admin-console improvement: before launch, run a dedicated mobile/tablet pass for the admin console and decide whether the densest tables should remain horizontal-scroll tables or become stacked row cards below the mobile breakpoint. Admin is desktop-primary, so this is not blocking once page-level overflow is contained.
- Priority: nice-to-have.

- Screen or component: `/admin` route access UX.
- Current first-version behavior: live `/admin` renders the admin login flow, and all admin data/actions are backend-enforced through admin-only endpoints. There is no separate frontend role redirect because the SPA does not yet have a current-user role/session bootstrap endpoint for pre-routing.
- Required admin-console improvement: when a current-user/session endpoint exposes account type and admin status, add a route guard that redirects non-admin authenticated users away from `/admin` and shows a concise unauthorized state. This is defense-in-depth and UX polish, not the security boundary.
- Priority: nice-to-have.

- Screen or component: high-impact admin mutations, including admin-user creation, document-template publication, borrower disbursement, recovery, and FX settlement declaration.
- Current first-version behavior: forms are backend-gated, CSRF-safe, idempotent, and audited, but they submit directly from the form.
- Required admin-console improvement: add dedicated confirmation dialogs with operation summaries and typed confirmation phrases for irreversible, cash-moving, or legal-evidence mutations. Use module-specific copy rather than native browser confirm dialogs.
- Priority: important.

## 2026-06-05: Admin Console Drill-Through And Evidence Operations

- Screen or component: Compliance manual-review queue, Loans/Borrowers operations, primary-market and servicing actions.
- Current first-version behavior: KYC, borrower, and loan tables now support row selection and pass selected context into related action forms. Selected borrower/loan/case context is shown in compact context bars. Funding close, order balance release, recovery, secondary-market approval/rejection/removal, and template publication now use dedicated confirmation dialogs with operation summaries before submission.
- Required admin-console improvement: continue replacing ID-only inputs with backend-backed search/select controls once list/detail endpoints expose the required records, especially investor/user search, withdrawal request list/detail, primary-order list/detail, secondary listing search, and stored-file/evidence selection.
- Priority: important.

- Screen or component: Reports panel.
- Current first-version behavior: live generated report responses now expose artifact metadata, checksum, manifest, content preview, and a download button that handles plain-text and base64 CSV/PDF/ZIP responses. Preview mode still avoids generating dummy report artifacts.
- Required admin-console improvement: add saved report presets, report history browsing, object-storage artifact links once report persistence is implemented, and clearer superadmin-only labels for restricted KYC/audit/tax/full-export reports.
- Priority: important.

- Screen or component: high-impact cash-moving/legal-evidence forms.
- Current first-version behavior: confirmation dialogs cover several high-impact direct actions, but form-submit actions such as borrower disbursement, lender deposit declaration, withdrawal finalization/cancellation, FX settlement declaration, recovery fee/cost variants, admin-user creation, and account closure still rely on form review plus backend validation.
- Required admin-console improvement: extend the confirmation-dialog pattern to every irreversible, cash-moving, account-access, or legal-evidence mutation, preferably with backend-provided operation summaries where available.
- Priority: important.

## 2026-06-06: Reconciliation Break Task Sync

- Screen or component: admin daily dashboard reconciliation-breaks queue and operational task queue.
- Current first-version behavior: added a backend/API sync action that scans reconciliation snapshots with non-zero reconciliation differences, account-sign anomalies, or investor balance lot-vs-liability integrity breaks and creates idempotent `payment_reconciliation` admin tasks. The admin dashboard shows a `Create tasks` action when the reconciliation-breaks queue is selected; live mode posts to the generated sync endpoint and preview mode shows local explanatory feedback.
- Required admin-console improvement: add drill-through from each reconciliation-break task to the underlying snapshot, show the snapshot's detailed sign/investor-integrity metadata in a structured investigation panel, allow admins to mark the break as explained/corrected with evidence references, and add backend-backed saved views for unresolved reconciliation exceptions.
- Priority: important.

## 2026-06-06: Primary Campaign Cancellation Action

- Screen or component: Loans panel, primary-market loan detail/actions for published campaigns.
- Current first-version behavior: the Loans panel exposes manual funding cancellation and campaign-expiry scan actions through generated API hooks. Manual cancellation requires a reason, includes an investor message field, and uses a danger confirmation dialog that explains balance-reservation release and immutable evidence. The expiry scan can evaluate the selected loan or all expired published campaigns by as-of date and calls the backend cancellation primitive. Selected loan context shows status, funding deadline, committed principal, and total principal.
- Required admin-console improvement: replace the current selected-loan-only context with a dedicated published-campaign detail drawer showing pending/allocated order counts, projected released principal, affected investor/order rows, and direct links to cancellation evidence, released order events, restored balance lots, and loan audit events. Add clearer post-action summaries from the cancellation/scan response, especially when multiple campaigns are cancelled or skipped.
- Priority: important.

## 2026-06-06: Final Loss-Recognition Admin UX

- Screen or component: Loans panel, servicing/risk actions.
- Current first-version behavior: the backend exposes a strict final default loss-recognition endpoint for defaulted loans. It closes all remaining active holdings, records immutable per-investor loss lines, and moves the loan to written_off. The Loans panel still exposes the day-to-day servicing status, risk-note, and recovery-payment workflows; final loss recognition is not presented as a casual generic write-off action.
- Required admin-console improvement: if this workflow is exposed in the admin console, design it as a separate advisor-approved final-resolution flow with a clear policy checklist, investor impact summary, component-loss review, evidence reference, and explicit confirmation. It must not look like an ordinary edit/remove/write-off button.
- Priority: blocking polish.

## 2026-06-16: Admin Entity CRUD Tables

- Screen or component: Loans, Borrowers, Document templates, and Superadmin user-account directory.
- Current first-version behavior: added backend-searchable, dense entity tables with search/filter controls in the table header, a create action in the header, and row-level action columns. Borrowers and loans open edit modals backed by the existing PATCH endpoints. Document templates expose create-version and publish-version actions while preserving immutable version history. User accounts are searchable through the admin lookup endpoint and route status changes through the audited account-access workflow.
- Required admin-console improvement: add true detail drawers for each entity with event history, related documents/evidence, and linked operational queues. Physical remove/delete remains intentionally unsupported for borrowers, loans, template versions, and users because these are audit/evidence entities; future "remove" semantics must be explicit domain transitions such as loan cancellation, listing removal, account closure, or template supersession.
- Priority: important.

## 2026-06-23: Admin Manual And Launch Operations Update

- Screen or component: admin manual, Finance Ops deposit instructions, Superadmin document-template operations, Reports/document downloads.
- Current first-version behavior: the admin manual source now documents the current CHF/EUR collector accounts, the verified CHF QR-bill behavior, the generated lender user agreement and project investment confirmation PDFs, and the current CRUD/search/autocomplete admin flows. `docs/runbooks/go-live-checklist.md` now centralizes go-live, admin operations, provider validation, and before-real-money test checklists.
- Required admin-console improvement: keep the manual in sync after future changes to collection accounts, provider behavior, generated document delivery, or admin CRUD flows. Add screenshots/figures for any new detail drawers, object-storage artifact links, or final loss-recognition UI if those are introduced.
- Priority: important.

## 2026-06-25: Users Module And Read-Only Impersonation

- Screen or component: `/admin` Users module, account access controls, superadmin read-only investor view.
- Current first-version behavior: added a dedicated Users navigation item with backend-side search, filters, pagination, row-level account-access controls, admin-user creation, and a superadmin-only read-only view action for non-admin users. The read-only view opens the existing investor portal with a short-lived signed impersonation token, displays a support/audit banner, disables visible investor mutation entry points, and leaves the real authenticated session as the superadmin. Investor-portal read/download endpoints scope data to the selected investor while generated documents/reports are audit-attributed to the superadmin.
- Required admin-console improvement: update the visual admin manual screenshots and workflow chapters so user account actions are taught from the Users module rather than Superadmin Settings or Compliance. Add a future impersonation-audit drawer showing recent `admin.readonly_impersonation_started`, `document.artifact_rendered`, and report-generation audit events for the selected user, visible only to superadmins.
- Priority: important.

## 2026-06-25: QA Development Mode

- Screen or component: `/admin` QA mode section.
- Current first-version behavior: added a superadmin-only QA panel backed by guarded platform-core APIs. In non-production environments with `QA_DEV_MODE_ALLOWED=true`, superadmins can enable QA mode, capture a database snapshot, advance the simulated platform clock by whole days, replay daily scheduled jobs for crossed Europe/Zurich business dates, inspect the last replay result, and revert the database to the entry snapshot. The backend rejects QA mode in production regardless of UI state. Revert restores database state and may sign the operator out; file/object storage and external provider side effects are not rolled back.
- Required admin-console improvement: after QA has been exercised on staging, add a small history/diff drawer for recent QA advances, including failed scheduled-job summaries and links to the generated scheduled-job run evidence. Add a staging-only visual banner across the admin shell while QA mode is enabled so operators cannot miss that time is simulated.
- Priority: important.

## 2026-06-25: User Accepted-Document History

- Screen or component: `/admin` Users module, row-level Documents modal.
- Current first-version behavior: admins can open a selected user's accepted-document history from the Users table. The modal lists historical clickwrap acceptances with human-readable identifiers, template titles, accepted timestamps, context labels, and content-hash prefixes. PDF/CSV artifacts are generated on demand through admin-scoped endpoints, and the rendered artifact is audited to the admin actor rather than the user. Legal terms and transaction-agreement PDFs are not emailed by default.
- Required admin-console improvement: update the admin manual screenshots/workflows to include the Users document-history action. Add a future evidence drawer with recent `DocumentRenderedArtifact` rows, full checksum/manifest display, and links from related orders/listings/loans back to the accepted document.
- Priority: important.
