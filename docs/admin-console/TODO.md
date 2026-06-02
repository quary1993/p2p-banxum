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
