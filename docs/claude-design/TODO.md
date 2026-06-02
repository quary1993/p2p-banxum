# Claude Design TODO

This file captures user-facing UI/UX improvements that should be reviewed by Claude Design. Implementation agents should add entries here when they build or touch public, investor, client-portal, onboarding, marketplace, documents, payments, FX, reporting, or account-settings UI visible to platform users.

Admin console UI/UX is not owned by Claude Design. Admin console screens are implemented and designed by the Codex implementation agent and tracked in `docs/admin-console/TODO.md`.

## Standing Instruction

Claude Design should do a complete user-facing UI/UX pass before launch, covering public pages, registration/login, KYC handoff, investor portal, marketplace, investment flows, balance/FX/withdrawal flows, portfolio, documents, statements, account settings, support/FAQ, and all user-facing notifications or status states.

For user-facing screens, this should include information architecture, navigation, page density, table behavior, forms, confirmations, status/error states, responsive behavior, accessibility, component tokens, and visual consistency across all modules.

Backend/API-only implementation slices do not create a visible UI surface. When a later slice adds a first-version user-facing screen, it should still be treated as implementation-grade UI until Claude Design reviews or redesigns it.

## 2026-06-01: Initial Portal Shell

- Screen or component: root React scaffold shell.
- Current first-version behavior: simple operational shell with top bar, module navigation preview, and status summary.
- Suggested improvement: Claude Design should define the final user-facing/investor information architecture, density, navigation states, responsive behavior, and component tokens before production user-facing portal screens are built out.
- Priority: important.
