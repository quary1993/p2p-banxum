# Claude Design TODO

This file captures UI/UX improvements that should be reviewed by Claude Design. Implementation agents should add entries whenever they build or touch UI/UX.

## Standing Instruction

Claude Design should do a complete product-wide UI/UX pass before launch, covering both investor and admin portals end to end. This should include information architecture, navigation, page density, table behavior, forms, confirmations, status/error states, responsive behavior, accessibility, component tokens, and visual consistency across all modules.

Backend/API-only implementation slices do not create a visible UI surface. When a later slice adds a first-version screen, it should still be treated as implementation-grade UI until Claude Design reviews or redesigns it.

## 2026-06-01: Initial Portal Shell

- Screen or component: root React scaffold shell.
- Current first-version behavior: simple operational shell with top bar, module navigation preview, and status summary.
- Suggested improvement: Claude Design should define the final admin/investor information architecture, density, navigation states, responsive behavior, and component tokens before production portal screens are built out.
- Priority: important.

## 2026-06-02: Admin Authentication Foundation

- Screen or component: admin login, admin email-code confirmation, and superadmin admin-user creation screens.
- Current first-version behavior: no UI was implemented in this slice; only backend API, OpenAPI schema, generated TypeScript client, and tests exist.
- Suggested improvement: when the admin portal UI is implemented, Claude Design should design or redesign the full admin authentication journey, including password entry, email-code confirmation, locked/error states, resend/cooldown messaging, first superadmin bootstrap guidance, regular-admin creation form, and audit-friendly operational copy.
- Priority: important.

## 2026-06-02: KYC Manual Review And Account Controls

- Screen or component: KYC manual-review queue, KYC case decision panel, account restrict/lock/close/reactivate controls.
- Current first-version behavior: no UI was implemented in this slice; only backend API, OpenAPI schema, generated TypeScript client, append-only evidence models, and tests exist.
- Suggested improvement: Claude Design should design or redesign the full admin compliance workflow, including queue filters, risk/status badges, provider-reference display, evidence summaries, decision forms, non-overridable sanctions/decline messaging, re-verification flow, account-control confirmation dialogs, closure clean-account confirmation copy, audit trail display, and clear distinction between Didit provider review and Garanta internal review.
- Priority: important.
