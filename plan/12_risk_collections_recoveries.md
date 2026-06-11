# Risk Monitoring, Collections, and Recoveries

Status: Draft. Updated with servicing, configurable recovery waterfall/reporting, non-standard secondary-market listing decisions, and final default loss-recognition handling on 2026-06-06.

## Purpose

Define post-origination risk monitoring, arrears/default status handling, Garanta-owned offline collections/recovery operations, recovered-payment recording, final default-resolution evidence, and investor communication for impaired loans.

In this module, "collections" means Garanta's operational follow-up after a borrower misses, delays, partially pays, or defaults on a repayment. Borrowers do not have a portal, so borrower contact, negotiation, legal notices, and collateral enforcement are handled offline. The platform records status, notes, documents, recovery events, final-resolution evidence when later defined, and investor-facing updates.

## Scope

- Portfolio risk monitoring.
- Basic borrower/loan monitoring.
- Generic monitoring notes and document uploads.
- Arrears workflow.
- Automatic late/default status changes.
- Admin-managed operational follow-up, where needed.
- Operational loan changes and recovery events.
- Default declaration.
- Generic recovery/legal evidence tracking.
- Default resolution and recovery allocation.
- Investor status display and investor notifications.

Out of launch scope:

- Borrower portal workflows.
- Detailed borrower contact method tracking.
- Detailed collections case CRM functionality.
- Predefined legal notice templates.
- Automatic recovery-cost calculation.
- Collateral-specific enforcement workflows.

## Decisions

### RISK-DEC-001: Garanta Owns Collections and Recovery Follow-Up

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta operations.

Decision:
Garanta owns collections and recovery follow-up at launch. Detailed loan-level collections tracking is not required in v1. Admins may upload ad hoc internal documents and write internal notes on loans.

Borrower contact and negotiation are performed offline. The platform does not need structured borrower contact-method fields in v1.

Rationale:
The launch process is operationally manual and borrower-facing activity is outside the platform. The platform still needs an evidence trail for internal, regulatory, investor, and accounting purposes.

Impacted modules:
- Loan Servicing and Repayments.
- Admin and Operations Portal.
- Documents, Contracting, and E-Signature.

Follow-ups:
Define document categories and access controls for internal notes/documents.

### RISK-DEC-002: Automatic Status Change, Manual Operational Handling

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta operations / risk.

Decision:
The system automatically changes loan status according to the servicing thresholds:

- `Late` on day 5 after due date if the required amount has not been recorded as paid.
- `Defaulted` on day 16 after due date if the required amount remains unpaid.

Day counting uses Europe/Zurich calendar days.

No automatic collections case is created at launch. Admin handles operational follow-up manually if needed.

Rationale:
Status automation is useful for consistency, reporting, and investor visibility, while manual operational follow-up can stay lightweight in v1.

Impacted modules:
- Loan Servicing and Repayments.
- Investor Portal.
- Reporting, Analytics, and Regulatory Exports.

Follow-ups:
None for v1. Late/default day counts are calendar days.

### RISK-DEC-003: Notes and Document Uploads Instead of Notice Templates

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta operations / legal.

Decision:
The platform does not provide predefined arrears, default, recovery, or legal notice templates in v1. Notices and communications prepared offline can be stored as uploaded documents or summarized in internal notes.

Rationale:
Legal and borrower communications are handled offline at launch. Generic evidence storage is enough for v1.

Impacted modules:
- Documents, Contracting, and E-Signature.
- Admin and Operations Portal.

Follow-ups:
Define accepted file types, retention, and whether some uploads can be marked public for investors.

### RISK-DEC-004: Investor Visibility During Arrears and Default

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta product / operations.

Decision:
Investors see the loan status and days past due for loans in their portfolio. Admin may add a public note to a loan if needed, or send a bulk email to affected lenders.

Investor updates are event-driven. Admin notifies investors when something material changes through email and/or public loan note.

Rationale:
This gives lenders essential status transparency without forcing a fixed investor-reporting cadence or detailed internal recovery disclosure.

Impacted modules:
- Investor Portal.
- Communications and Notifications.
- Reporting, Analytics, and Regulatory Exports.

Follow-ups:
Define public note visibility rules, authoring permissions, and whether historical public notes remain visible after resolution.

### RISK-DEC-005: Gross Recovery, Third-Party Costs, Recovery Fee, and Net Reporting

Status: Accepted.
Date: 2026-05-16. Updated 2026-06-01.
Owner: Garanta operations / finance / legal.

Decision:
Recovery and legal costs are handled case by case. Legal/recovery costs may be deducted from returned money before the net recovered amount is received by Garanta.

For each recovery payment, the platform must store and report:

- Gross recovered amount.
- Externally deducted legal/recovery costs already withheld before receipt by Garanta.
- Third-party recovery/legal costs declared by admin at recovery time, including whether they were externally deducted before receipt or deducted/paid from funds received.
- Whether Garanta applies the configured percentage recovery fee to this recovery payment.
- Applied percentage recovery fee amount, if any.
- Net amount received by Garanta.
- Net amount available for waterfall allocation after recovery costs/fees that are deducted from the received amount.
- Net amount distributed to each affected lender.
- Supporting evidence, notes/observations, and admin reviewer.

If a payment/installment is recorded for a defaulted loan, admin must be prompted to declare third-party recovery costs and choose whether to apply the Garanta recovery fee for that payment. Zero third-party costs and no recovery fee are valid choices, but the decision must be explicit and audited.

Externally deducted legal/recovery costs are reported separately as recovery-cost metadata/cost classification linked to the project, not silently netted away. Costs or recovery fees deducted from funds received reduce the amount available for waterfall allocation and must be ledgered separately.

Rationale:
Recovery cost treatment depends on the case, legal process, contract, and evidence available. The platform must still preserve a gross-to-net recovery trail so lender reports, default/recovery reports, and accounting exports explain why the net distribution differs from the gross recovered amount.

Impacted modules:
- Loan Servicing and Repayments.
- Payments, Ledger, Custody, and Reconciliation.
- Accounting, Tax, and Finance Operations.

Follow-ups:
Finalize accountant-approved Bexio/accounting mapping and final report labels for externally deducted legal/recovery costs, third-party recovery costs, Garanta recovery fee revenue, and recovery-cost deductions from received funds.

### RISK-DEC-006: Configurable Recovery Waterfall and Lender Allocation

Status: Accepted.
Date: 2026-05-16. Updated 2026-06-01.
Owner: Garanta operations / finance.

Decision:
Each loan/project must support a configurable recovery waterfall. Unless a project-specific agreement/configuration defines a different waterfall, recovered amounts are applied in this default order:

1. External recovery/legal costs.
2. Platform-approved recovery costs, including the Garanta percentage recovery fee when applied to that recovery payment.
3. Principal.
4. Contractual interest accrued until the official default declaration date.
5. Default/penalty interest accrued after the official default declaration date.
6. Other penalties/costs.

The project recovery configuration must include:

- `default_penalty_interest_percent`: default/penalty interest percentage that accrues from the official default declaration date instead of the regular contractual interest. Launch interpretation is annual nominal percentage unless the loan/project agreement defines another basis. If not defined, default/penalty interest is 0.
- `recovery_fee_percent`: Garanta's percentage commission for handling recovery. The fee is configurable per project and applied only when admin explicitly chooses to apply it for a specific recovery payment. The fee base must be configurable; default implementation should use the net recovered amount after declared third-party recovery/legal costs unless the project agreement defines another basis.
- `recovery_waterfall_order`: project-specific ordering of recovery categories, with the default order above.

When admin records a recovery payment for a defaulted/recovery loan, the system applies the configured waterfall and then allocates each lender-facing distributable bucket pro rata to the lenders holding participations in the relevant project based on the current principal balance of each holding at the time of the recovery event, unless the project agreement defines a different allocation method.

Amounts recovered after default may include:

- Principal.
- Contractual interest accrued until the official default declaration date.
- Default/penalty interest accrued after the official default declaration date, if provided in the relevant loan/project agreement.
- Penalties.
- Costs.

These categories must be classified separately in the ledger, default/recovery report, and lender reports. The allocation must not merge normal contractual interest, default/penalty interest, principal, penalties, or costs into a single generic recovery amount.

Normal contractual interest stops accruing on the official default declaration date. Default/penalty interest starts accruing from that date only if the relevant loan/project agreement provides for it. Default/penalty interest is calculated and reported separately from normal contractual interest.

Lender recovery distributions are calculated deterministically and rounded to the currency minor unit. Launch rounding uses half-up rounding for each lender distribution line. Any rounding difference between the net amount received and the sum of rounded lender distributions is recorded separately as a recovery rounding difference.

Rationale:
The platform should handle recovery economics deterministically while preserving project-level legal flexibility. Costs, Garanta recovery fees, lender distributions, interest cutoff, default/penalty interest, and rounding differences must be explicit rather than hidden inside a generic net recovery number.

Impacted modules:
- Loan Servicing and Repayments.
- Payments, Ledger, Custody, and Reconciliation.
- Accounting, Tax, and Finance Operations.

Follow-ups:
Finalize lender notification wording, final PDF/CSV report labels, and any non-default project waterfall language required by legal agreements.

### RISK-DEC-007: Generic v1 Recovery Events

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta operations / product.

Decision:
Recovery events are generic in v1. The platform does not need collateral-specific recovery fields for real estate, guarantees, assets, receivables, or other collateral types.

Generic recovery records may include recovered amount, date, notes/observations, uploaded documents, admin user, status change, and lender distribution result.

Rationale:
Collateral enforcement is handled offline and can vary substantially. Generic records keep the launch model flexible.

Impacted modules:
- Loan Product Catalog and Configuration.
- Origination, Credit Review, and Underwriting.
- Documents, Contracting, and E-Signature.

Follow-ups:
Consider collateral-specific recovery workflows in a later version if operational volume requires it.

### RISK-DEC-008: Final Default Resolution and Loss Recognition

Status: Accepted.
Date: 2026-05-16. Updated 2026-06-06.
Owner: Garanta operations.

Decision:
Admin can mark or confirm loans as defaulted where the workflow permits and can record risk notes, public notes, uploaded evidence, and recovery payments. Defaulted loans remain in `defaulted` status while Garanta handles recovery/resolution and records recovery evidence in the platform.

Final loss recognition is a separate admin-only default-resolution workflow, not a generic default-management shortcut. It may be used only after Garanta/legal/accounting decide the remaining exposure should be closed. The workflow requires a defaulted loan, written-off principal equal to remaining active holding principal, immutable per-investor loss-recognition lines, active-holding closure, terminal `written_off` loan status, and downloadable/reportable evidence.

Rationale:
The legal/accounting treatment of final impairment is sensitive and case-specific. Defaulted loans should stay in default/recovery handling until the final-resolution evidence, approvals, and investor/tax treatment are clear. When final loss recognition is used, it must be explicit, auditable, and linked to investor-level loss evidence rather than implied by a generic status change.

Impacted modules:
- Admin and Operations Portal.
- Loan Servicing and Repayments.
- Security, Privacy, and Auditability.

Follow-ups:
Define the production operating policy, evidence checklist, investor wording, report/PDF/CSV wording, and approval standard for using final loss recognition. Design the workflow so maker-checker approval can be enabled later for sensitive status changes.

The backend recovery-payment foundation does not automatically move a fully recovered impaired loan to a separate `recovered` or `resolved` terminal status. Garanta must decide whether a loan should remain in its historical impairment status (`defaulted`) or move to a new terminal status after recoveries reduce all holding principal to zero. This decision affects investor portfolio wording, recovery/default-resolution reports, tax statements, and accounting exports.

### RISK-DEC-009: Track Actual Recoveries Only

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta operations / finance.

Decision:
The platform tracks actual recovered payments only in v1. It does not track expected recovery amount, recovery probability, internal loss estimate, or provision estimate as structured fields.

Rationale:
Actual cash recovery and allocation are the core launch requirements. Estimates can remain offline until reporting needs justify structured support.

Impacted modules:
- Accounting, Tax, and Finance Operations.
- Reporting, Analytics, and Regulatory Exports.

Follow-ups:
Revisit expected recovery fields when portfolio risk reporting matures.

### RISK-DEC-010: Non-Standard Loans Remain Visible and Transferable by Approved Secondary-Market Request

Status: Accepted.
Date: 2026-05-16. Updated 2026-05-29.
Owner: Garanta product / operations / legal.

Decision:
Defaulted loans are not offered on the primary market. If a loan defaults after it is active, lenders continue to see it in their portfolio.

Lenders may submit listing requests for holdings in late, overdue, restructured, under-observation, default, recovery, legal-enforcement, payment-incident, or otherwise non-standard loans/projects. Such listings become visible on the secondary market only after explicit Garanta admin approval.

Admin approval must be audit logged with approval date, approving admin, reason, and disclosure note. Garanta may reject or remove any such listing at its discretion.

Approved non-standard listings require clear buyer warning and an additional buyer risk acknowledgement before purchase. The listing page must show loan status, days past due if applicable, recovery/default status, last payment date, and any public admin note.

Rationale:
Primary-market offerings should not include defaulted loans, but existing lenders may need liquidity. Secondary-market buyers must see the impairment or non-standard status before buying, and Garanta must review non-performing listing requests before publication.

Impacted modules:
- Marketplace, Investments, and Allocations.
- Investor Portal.
- Documents, Contracting, and E-Signature.

Follow-ups:
Define exact non-standard secondary-market disclosure wording and buyer acknowledgement text.

### RISK-DEC-011: Launch Recovery Reports

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta operations / finance.

Decision:
Launch reporting for this module should include:

- Default list.
- Investor exposure by defaulted loan.
- Action log.
- Default-resolution/loss-recognition report only after Garanta finalizes the recovery-closure policy.
- Recovery payment report showing gross recovered amount, externally deducted legal/recovery costs, third-party recovery costs declared at recovery time, Garanta recovery fee decision/amount, net amount received by Garanta, net amount available for waterfall allocation, recovery category split, lender allocations, and recovery rounding differences.
- Recovery waterfall report showing third-party recovery costs, whether the Garanta percentage recovery fee was applied, recovery fee amount, default/penalty interest percentage, waterfall category allocation, and lender distributions.

The action log covers platform actions, status changes, notes, document uploads, public notes, bulk investor emails, recovery events, and final-resolution events when later defined. It does not require structured borrower contact tracking.

Rationale:
These reports cover the launch needs for operations, investor exposure review, auditability, and finance follow-up.

Impacted modules:
- Reporting, Analytics, and Regulatory Exports.
- Security, Privacy, and Auditability.

Follow-ups:
Define report fields, filters, export formats, and permissions.

## Monitoring Signals

- Missed or late repayments.
- Manual admin/risk concern.
- Uploaded document or note indicating a risk event.
- Recovery/default/legal event recorded offline.

Future monitoring signals may include covenant breach, expired insurance/collateral documentation, deteriorating borrower financials, adverse media, compliance risk change, or bank-account change. These are not detailed structured workflows in v1.

## Arrears and Recovery Lifecycle

1. Scheduled repayment due date is reached.
2. Grace period runs through day 4 after due date.
3. System automatically changes loan status to `Late` on day 5 after due date if unpaid, using Europe/Zurich calendar days.
4. Admin handles offline follow-up if needed.
5. Admin may add internal notes/documents, public investor notes, or send bulk investor email when something material changes.
6. System automatically changes loan status to `Defaulted` on day 16 after due date if unpaid, using Europe/Zurich calendar days.
7. Admin records any generic recovery/legal event, recovered payment, or operational event.
8. If recovered funds are available for lenders, admin records the recovered amount and the system calculates lender distributions as investor balance credits.
9. A defaulted loan remains defaulted until Garanta defines a final recovered/resolved/loss-recognition workflow. The exact terminal status for a fully recovered defaulted loan is a Garanta policy decision tracked in `admin_todo_garanta.md`.

## Data Requirements

Loan risk/recovery records may include:

- Loan and borrower references.
- Days past due.
- Amount overdue.
- Current status.
- Internal notes.
- Internal uploaded documents.
- Public investor note, if any.
- Bulk investor email reference, if sent.
- Recovery event type.
- Gross recovered amount.
- Externally deducted legal/recovery costs.
- Third-party recovery/legal costs declared at recovery time.
- Whether the Garanta recovery fee is applied for this payment.
- Garanta recovery fee percentage, fee base, and fee amount where applied.
- Net amount received by Garanta.
- Net amount available for waterfall allocation.
- Project recovery waterfall version/configuration.
- Recovery category split: principal, contractual interest accrued until default date, default/penalty interest after default date if applicable, penalties, and costs.
- Default/penalty interest percentage and accrual period, where applicable.
- Recovery bank value date or receipt date.
- Notes/observations explaining recovered amount calculation.
- Attached evidence.
- Lender distribution calculation based on current principal balance per holding at recovery event time.
- Recovery rounding difference.
- Final default-resolution reason, only after that workflow is defined.
- Admin user and timestamp.

Detailed borrower contact history, promises to pay, contact methods, and notice templates are not required in v1.

## Investor-Facing Requirements

- Portfolio loans show status and days past due.
- Admin can publish a public loan note to affected investors when needed.
- Admin can send a bulk email to affected lenders when something material changes.
- Recovery distributions appear as balance-credit/payment events in investor payment history.
- Recovery notifications are sent to affected lenders and show at least loan/project, recovery event date, currency, lender credited amount, and where available the split between principal, contractual interest, default/penalty interest, penalties, costs, and rounding difference.
- Secondary-market listings for late/defaulted/non-standard loans require admin approval before publication and must clearly disclose the loan status.
- Internal recovery notes, internal documents, and bank evidence are not exposed to investors unless admin marks specific content as public.

## Controls

- Automatic late/default status changes must be auditable.
- Manual default/status changes must require reason/notes and be auditable.
- Final loss recognition can be performed only through the dedicated default-resolution workflow, requires advisor-approved operating policy before production use, and must close remaining active holdings with immutable investor-level loss evidence.
- Admin can close a defaulted loan and input recovered amount plus notes/observations.
- Recovery records must preserve gross recovered amount, externally deducted legal/recovery costs, third-party recovery costs declared at recovery time, Garanta recovery fee decision/amount, net amount received by Garanta, net amount available for waterfall allocation, and net amount distributed to lenders.
- Recovery payments must apply the project-specific recovery waterfall. If no project-specific waterfall overrides exist, the default order is external recovery/legal costs, platform-approved recovery costs including applied Garanta recovery fee, principal, contractual interest accrued until default, default/penalty interest, and other penalties/costs.
- Lender-facing recovery buckets are allocated pro rata to current lender holdings based on current principal balance at the time of the recovery event unless the project agreement defines a different allocation method.
- Recovery category splits must separately classify principal, contractual interest accrued until default date, default/penalty interest after default date if applicable, other penalties/costs, third-party recovery costs, and Garanta recovery fee.
- Contractual interest stops accruing on the official default declaration date.
- Default/penalty interest starts accruing from the official default declaration date only if provided in the relevant loan/project agreement or configured project waterfall. It accrues instead of regular contractual interest from default time and is reported separately.
- Recovery distribution rounding differences must be recorded separately.
- Each recovery payment must generate ledger entries, a default/recovery report, and affected-lender notifications.
- Investor communications are event-driven and should be timely and consistent.
- Direct free-form restructuring is out of scope at launch; operational loan changes must follow defined servicing events and document/notification requirements.
- Recoveries are allocated according to contract.
- The future final-resolution workflow should be designed so approvals can be added later.
- Sensitive cases are access-controlled.

## Dependencies

- Loan Servicing and Repayments.
- Communications and Notifications.
- Documents, Contracting, and E-Signature.
- Accounting, Tax, and Finance Operations.
- Reporting, Analytics, and Regulatory Exports.

## Q/A Backlog

1. Answered by SERV-DEC-008 and RISK-DEC-002: day 5 late, day 16 default, using Europe/Zurich calendar days.
2. Answered by RISK-DEC-001: Garanta owns collections and recovery follow-up; detailed tracking is not required.
3. Answered by RISK-DEC-001/RISK-DEC-003: borrower contact, legal notices, and negotiation are handled offline; the platform stores notes/documents only.
4. Answered by RISK-DEC-003: no predefined notice templates in v1.
5. Answered by RISK-DEC-004: investors see status and days past due; admin may add public note or send bulk email.
6. Answered by RISK-DEC-004: investor updates are event-driven when something material changes.
7. Updated by RISK-DEC-005 and RISK-DEC-006: recovery records show gross recovered amount, externally deducted legal/recovery costs, third-party recovery costs declared at recovery time, optional Garanta percentage recovery fee, net amount received by Garanta, waterfall allocation, category split, lender allocation based on current principal balance unless project-specific allocation overrides exist, and separate rounding differences.
8. Answered by RISK-DEC-007: v1 recovery fields are generic, not collateral-specific.
9. Updated by RISK-DEC-008: admin can mark/confirm default, record notes/documents/recovery payments, and record final default loss recognition only through the dedicated advisor-policy-controlled workflow.
10. Answered by RISK-DEC-009: track actual recovered payments only.
11. Answered by RISK-DEC-010: defaulted and other non-standard loans remain visible in portfolio; holdings may be sold on the secondary market only after admin-approved listing publication, clear disclosure, and additional buyer acknowledgement.
12. Updated by RISK-DEC-011: launch reports are default list, investor exposure by defaulted loan, action log, recovery payment/waterfall report with gross-to-net, third-party costs, recovery fee, category split, lender allocation, and rounding difference fields, and final loss-recognition evidence/reporting once Garanta approves the production wording and use policy.
