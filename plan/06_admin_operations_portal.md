# Admin and Operations Portal

Status: Draft. Updated with operating-model, identity/KYC evidence storage, marketplace, servicing, recovery allocation, document, Bexio finance exports, bank reconciliation, reporting, communication, and admin-auth decisions on 2026-06-01.

## Purpose

Define the internal portal used by Garanta staff to operate onboarding, borrowers, loans, marketplace listings, payments exceptions, servicing, compliance/admin tasks, documents, reporting, and support.

## Scope

- User and entity search.
- Compliance/admin task queues and filtered task queries.
- Legal-entity lender creation and off-platform KYC/AML evidence management.
- Manual legal-entity lender investment entry from the lender database.
- Borrower entity creation and off-platform KYB/AML evidence management.
- Borrower and complete loan record review.
- Offline credit result recording.
- Loan listing creation and approval.
- Marketplace monitoring.
- Investment order validation and oversubscription handling.
- Payment and ledger operations.
- Secondary-market operations.
- Servicing exception handling.
- Document templates and files.
- Support notes and internal comments.
- Audit logs and operational reports.

## Internal Personas

Launch role levels:

- Superadmin.
- Admin.

Functional personas that may map into those role levels:

- Operations analyst.
- Compliance analyst.
- Compliance manager / MLRO.
- Credit analyst.
- Credit approver.
- Finance user.
- Finance manager.
- Customer support.
- System administrator.
- Auditor/read-only user, future only; launch auditor/regulator handling uses admin-generated export packages.

## Launch Role Model

### Superadmin

Superadmin owns parametrization and configuration-level administration.

Examples:

- Configure loan product parameters.
- Configure common product settings exposed in the UI, including purpose options, collateral options, repayment type availability/defaults, fee defaults, and broad sanity-check limits where implemented.
- Configure platform settings, using configuration/template variables for platform brand name, legal operator name, support email, domains, and document footer identities rather than hardcoded template text.
- Configure eligibility and limit parameters.
- Configure document/template parameters where exposed through admin tooling. Reusable legal/document template changes require versioning and audit and are superadmin-owned.
- Configure fee, repayment, disclosure, and workflow parameters where exposed through admin tooling.
- Deeper product parameters may remain deployment/configuration controlled in the first version.
- Create and manage admin accounts.
- Reset admin passwords.
- Configure Garanta collection account/IBAN details where exposed in the platform.

Superadmin is not the default role for day-to-day operations. The initial superadmin account is configured through environment variables at deploy time. Superadmin credentials and superadmin account removal are managed through environment/deployment configuration, not through the database UI. Because parametrization changes can materially affect regulated workflows, the platform should support audit logs, reason codes, and future configurable maker-checker approval for sensitive configuration changes. Maker-checker and admin step-up authentication are disabled at launch.

### Admin

Admin owns operational execution.

Examples:

- Create and manage borrower entities.
- Create and manage legal-entity lender records after off-platform onboarding.
- Manually add legal-entity lender investments in loans from the lender database.
- Create and manage loan records.
- Review and approve loans.
- Decide onboarding exceptions.
- Publish and manage operational loan/listing workflows where policy permits.
- Confirm payments.
- Declare bank operations, including lender deposits, lender withdrawals, borrower loan disbursements, borrower repayments, Garanta out, Garanta in, and external FX settlement.
- Query investor balance ageing and deadline exposures.
- Query net currency-exchange deltas by day or period.
- Review ledger-bank reconciliation differences by currency.
- Generate accrued Garanta revenue reports for arbitrary periods.
- Handle payment and reconciliation exceptions.
- Manage borrower and lender operational tasks, notes, and evidence.
- Upload, review, and manage operational documents.
- Upload and manage off-platform KYC/KYB/AML evidence.
- Perform other day-to-day actions needed to run the platform.

Admin actions remain subject to workflow rules, reason codes, and audit logging. Maker-checker controls should be configurable for future use but disabled at launch.

## Core Views

- Work queue dashboard.
- User profile.
- Entity profile.
- Legal-entity lender profile.
- Borrower entity profile.
- KYC/KYB status.
- KYC/KYB evidence and manual AML review workspace.
- KYC/KYB evidence export workspace.
- Compliance/admin task detail.
- Loan record detail.
- Offline credit/result evidence area, if needed later.
- Loan listing editor.
- Investment/order book monitor.
- Manual legal-entity lender investment entry.
- Oversubscription/refund task queue.
- Payment reconciliation queue.
- Bank operation declaration workspace.
- Daily ledger-bank reconciliation workspace.
- Repayment declaration and distribution workspace.
- Schedule override/version history.
- Secondary-market listing and transfer monitor.
- Non-standard secondary-market listing approval queue.
- Servicing calendar.
- Arrears/default status, recovery, notes, and document workspace.
- Document library.
- Document template/version workspace, if exposed in the platform.
- Email template/version workspace with variable registry, preview, test-send, examples, and validation.
- Failed email delivery/admin notification queue.
- Currency and FX configuration workspace.
- Balance ageing, withdrawal, reinvestment, and penalty monitoring workspace.
- Forced withdrawal and missing-IBAN queue.
- FX delta query and end-of-day exchange operations workspace.
- External FX settlement declaration and realized FX gain/loss workspace.
- Garanta accrued revenue and Garanta out/in transfer workspace.
- Finance/accounting export workspace.
- Borrower account statement generator.
- Borrower annual tax information statement generator.
- Garanta internal annual account and tax information report generator.
- Finance correction workspace.
- Audit log explorer.
- Reporting/export center for admin-only PDF, CSV, and ZIP evidence package exports.

## Workflow Requirements

- Launch admin work is organized through simple task queues and task queries, not full case-management files.
- Task assignment and queue filters.
- Status transitions with permission checks.
- Approval policy hooks for future maker-checker controls.
- Internal notes with visibility controls.
- File attachments.
- Bank operation declarations must be auditable, reversible only through correction/reversal records, and linked to ledger entries, bank statement references, evidence, and admin confirmation timestamp.
- Reconciliation workspaces must show bank-stated balance, ledger-stated investor balances, Garanta accrued revenue/commission balance, suspense/unmatched cash, pending/exception balances, and reconciliation difference by currency.
- Operational age/SLA columns for all daily operational queues/actions.
- Reason codes for approvals, overrides, and holds.
- Immutable audit logs.

At launch, "tracking an SLA" means the platform stores the task/event timestamp, optional due timestamp, current status, completion timestamp, responsible role/user where assigned, overdue state, and related audit trail. SLA tracking is internal operational visibility only unless Garanta later defines contractual or regulatory service commitments.

SLA tracking applies to all daily operational actions and queues in v1, including cash reconciliation, balance ageing, pending withdrawals and forced withdrawals, FX delta review/execution, failed communications, due/late/defaulted loan review, and pending admin actions.

Launch daily operational report set:

- Cash reconciliation.
- Balance ageing.
- Pending withdrawals and forced withdrawals.
- FX delta.
- Failed communications.
- Due, late, and defaulted loans.
- Pending admin actions.

Admin-created legal-entity lender mandatory fields:

- Legal name.
- Registration number.
- Jurisdiction.
- Registered address.
- Representative name.
- Representative email.
- Representative phone.
- Bank IBAN.
- Off-platform onboarding/KYB status.
- Off-platform onboarding/KYB date.
- Risk rating.
- Tax residency.

Legal-entity lender evidence must be recorded before financial activation. Exact upload categories can be configured, but the platform must support local Swiss-controlled storage or references to Garanta-controlled Swiss evidence storage for the KYB pack, register extract, proof of address, ownership/control evidence, tax form, bank proof, provider/off-platform report, manual AML review decision, and internal approval note.

## High-Risk Admin Actions

- Approve KYC/KYB exception.
- Approve, reject, reopen, or update a KYC/KYB manual review file.
- Download/import provider KYC/KYB reports and attach supporting evidence.
- Generate KYC/KYB/AML evidence export packages for VQF/SRO, auditors, banks, payment partners, and internal compliance reviews.
- Create legal-entity lender after off-platform onboarding.
- Manually add a legal-entity lender investment in a loan.
- Create borrower after off-platform onboarding.
- Override compliance hold.
- Approve borrower for listing.
- Record final loan terms.
- Publish loan listing.
- Close funding round.
- Validate received investment funds and order allocation.
- Confirm excess/refund-due handling.
- Release funds.
- Monitor secondary-market transfers and process correction/exception workflow steps where needed.
- Approve, reject, or remove non-standard secondary-market listing requests with reason and disclosure note.
- Change borrower or lender bank account details.
- Change Garanta collection account/IBAN details.
- Mark repayment as received or corrected.
- Override generated repayment schedule.
- Record early repayment, partial repayment, or operational loan change.
- Record default recovery event with gross recovered amount, externally deducted legal/recovery costs, third-party recovery costs declared at recovery time, Garanta recovery fee application decision/amount, net amount received, waterfall category split, evidence, and recovery rounding difference.
- Publish public loan note or send bulk investor email for material loan changes.
- Choose public loan note only, bulk email only, or both for material loan changes.
- Attach bank statement/payment evidence for lender distributions.
- Write off loan.
- Create, update, or publish a reusable document template version.
- Configure enabled currencies.
- Configure FX platform fee, enabled FX pairs, per-investor daily conversion limit, FX quote settings, and FX sanity-check thresholds.
- Configure balance deadline reminders and reminder email templates. Balance penalty mechanics are deployment/env-configurable at launch.
- Attempt or record forced withdrawal for balances at the 60-day limit when a usable IBAN is known.
- Review penalty-mode accounts missing usable IBAN and frozen financial actions.
- Query net FX deltas and record external FX execution evidence.
- Generate operational subledger and configurable monthly Bexio debit/credit accounting exports.
- Generate borrower account statements and annual tax information statements as PDF and CSV.
- Generate Garanta internal annual account and tax information reports.
- Approve finance correction entries.
- Generate report exports as PDF and CSV.
- Generate ZIP evidence packages for accounting, audit, regulatory, board, bank/payment partner, or operational review.
- Choose redacted or full export mode according to report purpose.
- Close clean/empty accounts and optionally apply reversible direct-identifier pseudonymization at closure.
- Change role permissions.

No high-risk action requires dual approval at launch. Each high-risk action should be modeled so dual approval can be enabled later by policy/configuration.

## Initial Authority Matrix

- Product/platform parametrizations: superadmin.
- Define borrower entities: admin.
- Define legal-entity lenders after off-platform onboarding: admin.
- Manually add legal-entity lender investments from the lender database: admin.
- Create and manage loans: admin.
- Approve onboarding exception: admin.
- Approve/reject/reopen KYC/KYB manual review file: admin, subject to role permission and audit logging.
- Generate KYC/KYB/AML evidence package: admin only.
- Record offline credit approval / approve loans for publication: admin.
- Publish listing: admin, subject to workflow rules.
- Close funding round: admin, subject to workflow rules.
- Confirm payments: admin.
- Enter borrower repayment amount and generate lender distribution: admin.
- Attach lender payment evidence/bank statement: admin.
- Override generated repayment schedule: admin, subject to workflow rules.
- Record early repayment, partial repayment, or operational loan change: admin, subject to workflow rules.
- Record default recovery event, recovery costs, recovery fee decision, waterfall allocation, and recovered amount details: admin, subject to workflow rules.
- Publish public loan note or bulk investor email for material loan changes: admin, subject to workflow rules.
- Validate investment orders after receipt of funds: admin.
- Process primary-market excess/full-excess refund tasks: admin.
- Manage secondary-market listings and transfers: admin, subject to workflow rules.
- Approve/reject/remove non-standard secondary-market listings: admin, with audit log, reason, and disclosure note.
- Release funds: admin, subject to workflow rules.
- Override compliance hold: admin, subject to compliance policy and workflow rules.
- Change borrower or lender bank account: admin, subject to workflow rules and audit logging.
- Change Garanta collection account/IBAN details: superadmin.
- Write off loan: admin, subject to workflow rules.
- Create admin accounts: superadmin.
- Reset admin passwords: superadmin.
- Manage admin role assignment: superadmin.
- Superadmin credential changes/removal: deployment/environment configuration.
- Create, update, or publish reusable document templates: superadmin.
- Create, update, or publish reusable email templates: superadmin.
- Review failed email delivery notices/tasks: admin.
- Configure enabled currencies: superadmin.
- Configure FX platform fee, enabled FX pairs, quote settings, and sanity-check thresholds: superadmin.
- Configure FX per-investor daily conversion limit: admin, with audit trail.
- Configure balance deadline reminders: superadmin.
- Configure day-60 balance penalty mechanics: deployment/env configuration at launch.
- Attempt or record forced withdrawal for day-60 balances: admin.
- Review missing-IBAN penalty-mode freezes: admin.
- Query net FX deltas and record external FX execution evidence: admin.
- Generate accounting exports and finance reports: admin.
- Generate borrower account statements and annual tax information statements as PDF/CSV: admin.
- Generate Garanta internal annual account and tax information reports: admin.
- Approve finance correction entries: admin or superadmin.
- Export reports and ZIP evidence packages: admin only.
- Close clean/empty account and apply optional reversible pseudonymization checkbox: admin.

## Dependencies

- All business modules.
- Security, Privacy, and Auditability.
- Reporting, Analytics, and Regulatory Exports.

## Q/A Backlog

1. Answered by Operating Model DEC-010: two role levels at launch: superadmin for parametrizations and admin for operational execution.
2. Answered by Operating Model DEC-011: no launch actions need dual approval; design must support enabling it later.
3. Answered: launch admin work uses simple task queues and filtered task queries, not full case-management files.
4. Answered: SLA tracking applies to all daily operational actions/queues. It means storing task/event timestamps, optional due timestamps, status, completion time, assigned owner/role, overdue state, and audit trail.
5. Answered by Operating Model DEC-010 and COMMS-DEC-006: there is no separate support role or support-ticket view at launch; only superadmin/admin portal roles are in scope, and external support is handled by normal email.
6. Answered by RPT-DEC-003: auditors/regulators do not need direct portal access at launch; admin generates and shares/export packages offline.
7. Answered: daily reports are cash reconciliation, balance ageing, pending withdrawals/forced withdrawals, FX delta, failed communications, due/late/defaulted loans, and pending admin actions.
8. Updated by KYC-DEC-005/KYC-DEC-008: legal-entity lender mandatory fields are legal name, registration number, jurisdiction, registered address, representative name/email/phone, bank IBAN, onboarding/KYB status and date, risk rating, and tax residency. KYB/AML evidence must be recorded before financial activation, with exact evidence categories configurable. Borrower mandatory fields are defined in the borrower/entity module.
9. Answered by FIN-DEC-004/006: admin generates borrower account statements and annual tax information statements as PDF/CSV, admin generates Garanta internal annual account/tax information reports, and admin or superadmin can approve finance corrections.
10. Answered by RPT-DEC-002/RPT-DEC-003: admin-only report exports support PDF, CSV, and ZIP evidence packages with redacted/full modes.
11. Answered by COMMS-DEC-004/005/007: failed emails create admin notices, admin chooses public note/email/both for material loan updates, and superadmin owns email template changes.
12. Answered by ACC-DEC-002/ACC-DEC-003: superadmin creates admins and resets passwords; initial superadmin credentials are environment-configured; Garanta collection account/IBAN changes are superadmin-only; no launch admin step-up authentication is required.
