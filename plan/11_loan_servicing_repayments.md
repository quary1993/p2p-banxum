# Loan Servicing and Repayments

Status: Draft. Updated with payment, balance, servicing, and recovery decisions on 2026-06-01, with the fixed-amount installment / repayment-in-advance servicing model on 2026-07-08, with disbursement activation, ACT/365 interest, and canonical schedule-history rules on 2026-07-27, and with the universal non-overridable payment waterfall on 2026-08-05.

## Purpose

Define how active loans are serviced after drawdown, including schedules, repayment collection, allocations, investor distributions, borrower notices, arrears, operational loan changes, and closure.

## Scope

- Repayment schedule generation.
- Borrower account statements or payment reminders.
- Repayment intake.
- Payment allocation.
- Investor distribution calculations.
- Admin-generated lender distribution/balance-credit lists.
- Arrears; late fees are future/inactive at launch.
- Early repayment.
- Operational loan changes.
- Generic note/document tracking.
- Loan closure.

## Decisions

### SERV-DEC-001: Launch Repayment Types

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta product / operations / finance.

Decision:
Launch servicing supports all standard generated repayment types except custom/manual schedule as a repayment type:

- Equal installments.
- Bullet principal with periodic interest.
- Amortizing principal and interest.
- Interest-only period then bullet.
- Interest-only period then amortizing.

Custom/manual schedule is not a launch repayment type. However, admin may manually override a generated schedule under SERV-DEC-002.

Rationale:
The platform needs broad repayment support but should avoid fully free-form schedules as a product type in the first version.

Follow-ups:
Confirm schedule display labels. Launch formula defaults are calendar-day status checks, annual nominal interest, monthly installments by default, currency minor-unit rounding per installment, and final installment rounding-residue absorption.

### SERV-DEC-002: Schedule Generation and Controlled Event-Driven Edits

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta product / operations / finance.

Decision:
Repayment schedules are generated automatically from loan terms and repayment type. Admin may make controlled edits to generated schedules only through declared payment or operational events. These controlled edits can materially change future installments, but they must remain tied to an auditable event rather than arbitrary free-form schedule creation.

Examples of controlled events:

- Regular installment payment at the fixed next-due amount.
- Repayment in advance with a borrower repayment bank date, covering partial, multi-installment, and early repayment amounts.
- Installment buyback.
- Execution/recovery event.

Controlled edits must be versioned, audited, and recalculate borrower remaining obligations and expected investor distributions.

Rationale:
Automatic generation reduces setup errors, while controlled event-driven edits preserve operational flexibility without introducing a fully custom/manual schedule product.

Follow-ups:
Define event types, override permissions, reason codes, audit fields, recalculation formulas, and whether future maker-checker applies to schedule-changing events.

### SERV-DEC-003: Borrower Repayment Matching

Status: Accepted.
Date: 2026-05-16. Updated 2026-07-08 for fixed-amount installments and repayment in advance.
Owner: Garanta finance / operations.

Decision:
Borrower repayments are declared from the Loans table through Manage > "Record borrower repayment", which shows the loan's current schedule. A loan must be `active` or `late`; `funded` means funding closed but borrower disbursement is still pending and cannot accept repayment. Declaring a regular installment payment uses a fixed amount: it must equal the outstanding amount of the next due installment and cannot be edited. If the value date is more than one day before the due date, admin must explicitly acknowledge that the borrower is paying the full timely installment, including its full contractual interest. Otherwise the payment must use the repayment-in-advance flow.

To declare any other amount (except for defaulted loans, which go through the recovery workflow), the admin checks "Repayment in advance" and selects a "Borrower repayment bank date". The declared amount is then allocated through the repayment-in-advance waterfall (SERV-DEC-007) and the future schedule is regenerated as a new schedule version. Before anything is written, the admin gets a preview/confirmation dialog showing the allocation and both the old and the new schedule.

The old free-amount declaration with a "warning acknowledged" checkbox for partial payments and overpayments was removed.

Rationale:
The fixed next-due-installment amount keeps regular operations simple and mistake-proof, while the explicit repayment-in-advance flow with bank date, deterministic allocation, and a mandatory preview replaces ad-hoc warnings for irregular amounts.

Follow-ups:
Define how payments covering multiple installments are displayed in investor-facing history.

### SERV-DEC-004: Repayment Allocation Waterfall

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta finance / operations / legal.

Decision:
Every payment uses the following universal allocation order:

1. Garanta legal costs and recovery fee.
2. Penalty, including separately reported default/penalty interest where applicable.
3. Contractual interest.
4. Principal.

This order applies to direct loans and Loan-Originator loans and to active, late, and default/recovery handling. It cannot be overridden by loan terms, project configuration, admin input, or an imported payment split. A tier may be zero when no amount is due. Principal never receives cash while any higher tier remains due.

Late fees are not charged at launch, so late-fee allocation is inactive unless added later.

Borrower-side penalties remain configurable in the data model but are set to 0/inactive at launch until Garanta finalizes business and legal policy. While penalties are 0, the penalty waterfall step has no monetary effect.

For a healthy loan with a CHF 1,000 regular installment, if the borrower pays CHF 3,000, admin declares it as a repayment in advance with the borrower repayment bank date. The system pays all unpaid scheduled interest of installments due on or before the bank date, plus exact ACT/365 interest on outstanding principal from the latest date through which interest was already paid up to, but excluding, the new bank date; the remainder reduces outstanding principal. Interest accrues at end of day, so two advance repayments with the same bank date produce no additional elapsed-day interest on the second payment. The future schedule is then regenerated as a new schedule version for the same remaining due dates using the new outstanding principal.

Rationale:
One server-owned allocator prevents loan types and servicing states from drifting and prevents a caller from relabeling principal in order to bypass costs, penalties, or interest.

Follow-ups:
Define future borrower-side penalty policy before activating any non-zero penalty configuration.

### SERV-DEC-005: No Launch Late Fees

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta product / finance / legal.

Decision:
Late fees are not charged at launch.

Rationale:
Skipping late fees reduces servicing and disclosure complexity in the first version.

Follow-ups:
Keep late-fee support as a future configurable extension if business/legal policy changes.

### SERV-DEC-006: Partial Borrower Repayments

Status: Accepted.
Date: 2026-05-16. Updated 2026-07-08 for the repayment-in-advance model.
Owner: Garanta operations / finance.

Decision:
Partial borrower repayments are accepted case by case, but they are no longer declared as a free amount against the next installment. Any amount that differs from the outstanding amount of the next due installment is declared through the "Repayment in advance" flow with a borrower repayment bank date (defaulted loans go through recovery instead). The platform allocates the amount through the repayment-in-advance waterfall, regenerates the future schedule as a new version, credits the related lender distribution to investor balances pro rata, and requires admin confirmation of the previewed allocation before anything is written.

Rationale:
The launch model is manual/admin-controlled, and partial repayment handling must match actual cash movement and lender balance credits. Routing irregular amounts through one deterministic flow removes the ambiguity of warned free-amount declarations.

Follow-ups:
Define how partial payments affect arrears displays, balance source ageing edge cases, and lender notification wording.

### SERV-DEC-007: Early Repayment (Repayment in Advance)

Status: Accepted.
Date: 2026-05-16. Updated 2026-07-08 for the repayment-in-advance model.
Owner: Garanta operations / finance / legal.

Decision:
Early repayment is allowed at launch. Both full and partial early repayment are allowed. No early repayment fee is charged.

Early repayment is declared as a "Repayment in advance": admin checks the repayment-in-advance option in Manage > "Record borrower repayment", enters the received amount, and selects the "Borrower repayment bank date". The universal waterfall first pays any recorded Garanta legal costs/recovery fee and penalty due; both tiers are zero in the current ordinary active/late advance flow. The contractual-interest tier then pays all unpaid scheduled interest through the bank date plus ACT/365 accrued interest on outstanding principal from the latest interest-paid-through date up to, but excluding, the bank date: `outstanding principal x annual rate bps x elapsed days / (10,000 x 365)`, rounded half-up to integer currency minor units. A regular installment pays interest through its contractual due date; a prior repayment in advance pays interest through its actual borrower bank date. No future interest is collected. Only the remainder reduces outstanding principal.

The future schedule is then regenerated as a new immutable schedule version: only future rows are regenerated, original due dates are preserved, and the first regenerated installment's interest uses the same ACT/365 rule from the repayment bank date to its due date. Before anything is written, the admin gets a preview/confirmation dialog showing the allocation, accrual period/day count, and both the old and new schedule (backend endpoint `POST /api/v1/servicing/admin/borrower-repayments/advance-preview/`). A full payoff through repayment in advance marks the loan repaid.

This is an intentional mixed convention. Complete contractual monthly periods continue to use the schedule engine's nominal annual rate divided by 12. Only irregular stub periods created by a repayment in advance use ACT/365 for the exact elapsed calendar days. The platform must not silently replace full-period contractual interest with ACT/365 or charge a full monthly amount for a shortened stub.

Rationale:
Early repayment flexibility matches expected loan operations and avoids unnecessary penalty complexity at launch. The explicit bank date makes interest accrual deterministic, and the mandatory preview lets admin verify the allocation and resulting schedule before the ledger is touched.

Follow-ups:
Define lender notification wording. Launch recalculation preserves the remaining due dates with lower remaining principal, annual nominal interest, monthly installment defaults, currency minor-unit rounding, and final installment rounding-residue absorption.

### SERV-DEC-008: Late and Default Status Timing

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta risk / operations.

Decision:
A loan becomes `Late` on day 5 after the due date if the required amount has not been recorded as paid. A loan becomes `Defaulted` on day 16 after the due date if the required amount remains unpaid. Day counting uses Europe/Zurich calendar days.

Rationale:
Explicit thresholds make status calculation, investor notifications, reporting, and arrears/default handling deterministic.

Follow-ups:
None for v1. Day counts are calendar days at launch.

### SERV-DEC-009: Operational Loan Changes Instead of Direct Restructuring

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta operations / legal / finance.

Decision:
Admins do not directly restructure loans through an arbitrary edit workflow at launch. Loans are changed through defined operational events, including:

- Installment buybacks by the borrower.
- Execution/recovery events.
- Early repayment events that modify the schedule.

Investor notification is required. Explicit investor consent is not required at launch for these operational changes if the legal terms permit the treatment.

Rationale:
Operational events create a clearer audit trail than free-form restructuring and better match the launch servicing model.

Follow-ups:
Define each operational event type, permissions, schedule effects, accounting treatment, and document/notice requirements.

### SERV-DEC-010: Covenant Tracking

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta operations / risk.

Decision:
Detailed covenant tracking is not required at launch. The platform should provide a generic admin note and document upload area for servicing, monitoring, and operational evidence.

Rationale:
This keeps launch servicing focused on payments and status while preserving a place to store relevant evidence.

Follow-ups:
Define note/document categories and access controls.

### SERV-DEC-011: Installment and Loan Closure Evidence

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta finance / operations.

Decision:
No special separate evidence is required to mark a loan fully repaid and closed. Installment evidence is built from the repayment distribution process:

1. Borrower payment is received.
2. Admin declares the received amount.
3. System tells admin how to pay lenders pro-rata.
4. Platform credits lender balances and records distribution evidence.
5. Installment is marked repaid after lender balance-credit evidence is recorded/confirmed.

When payments, including partial payments, full installments, multiple installments, or early repayments, pay all outstanding principal after scheduled priority allocation, the loan is marked repaid. The evidence is the borrower receipt plus the internal lender balance-credit/distribution records and any bank/payment records where external transfers occurred.

Rationale:
The repayment and distribution evidence trail is sufficient for closure in the launch process.

Follow-ups:
Define required attachment metadata, whether statement attachment is optional or mandatory, and controlled correction rules.

### SERV-DEC-012: Lender Payout Artifacts and Notifications

Status: Accepted.
Date: 2026-05-16.
Owner: Garanta finance / operations / product.

Decision:
Lender distribution artifacts are internal platform/admin finance artifacts, including the distribution list, balance-credit records, payment/account statement, and any bank export needed where funds are externally transferred. They are not sent to lenders as files by default.

Lenders receive an email notification that their balance was credited and the amount. The credit can represent a partial installment, full installment, multiple installments, late/default recovery payment, or early repayment.

Rationale:
This keeps lender communications simple while preserving the operational evidence needed by finance/admin.

Follow-ups:
Define whether investor portal transaction history shows the same breakdown as the internal distribution artifact.

### SERV-DEC-013: Default Recovery Payment Handling

Status: Accepted.
Date: 2026-05-16. Updated 2026-06-01.
Owner: Garanta operations / finance.

Decision:
When a defaulted loan has a recovered amount available, admin records the recovery event, notes/observations, and supporting documents. The recovery record must include gross recovered amount, externally deducted legal/recovery costs, third-party recovery/legal costs declared at recovery time, whether the Garanta percentage recovery fee is applied, net amount received by Garanta, net amount available for allocation, recovery bank value date/receipt date, and evidence-backed outstanding penalty/default-interest and contractual-interest obligations. Current principal is derived from active holdings; admin does not submit the applied category split.

The server applies the same universal order before lender distribution: Garanta legal/recovery costs and applied recovery fee, penalty/default interest, contractual interest accrued until default, then principal. The order is not project-configurable.

Lender-facing recovery buckets are distributed pro rata to lenders holding participations in the relevant project, based on the current principal balance of each holding at the time of the recovery event, with deterministic largest-remainder rounding.

Normal contractual interest stops accruing on the official default declaration date. Default/penalty interest starts accruing from that date instead of regular interest only if provided in the relevant loan agreement or recorded loan recovery terms. It must be calculated using the loan `default_penalty_interest_percent` and reported separately from normal contractual interest.

Recovered amounts may include principal, contractual interest accrued until default date, default/penalty interest, penalties, and costs. These categories must be classified separately in the ledger, default/recovery report, and lender reports.

Distribution rounding uses deterministic currency minor-unit rounding. Launch rounding is half-up per lender distribution line, with any rounding difference recorded separately as a recovery rounding difference.

Each recovery payment must generate ledger entries, a default/recovery report, and notification to affected lenders.

Rationale:
Default recovery is case-specific and handled offline, but the waterfall, lender distribution, interest cutoff, category classification, recovery fee, third-party costs, rounding, reporting, and notification must still be deterministic and auditable.

Follow-ups:
Finalize lender notification wording and accountant-approved recovery report labels. Loan agreements must describe the universal priority rather than define an alternate project order.

### SERV-DEC-014: Funding Close, Disbursement, and Servicing Activation

Status: Accepted.
Date: 2026-07-27.
Owner: Garanta finance / operations.

Decision:
Funding close moves lender capital into borrower-disbursement payable and sets the loan to `funded`. This status means the campaign closed successfully but no borrower repayment can yet be recorded. Admin borrower-disbursement finalization must clear the complete payable through borrower cash plus the BANXUM fee, then moves the loan to `active` and records immutable disbursement evidence. Normal repayments and servicing scans operate on `active` and `late` loans. This explicitly prevents repayment before the borrower received the financed principal.

The canonical full-loan schedule projection is an immutable history plus the latest future obligation view. It merges every recorded regular/advance repayment event (actual payment date and actual principal/interest applied) with only the outstanding rows from the current schedule version. Superseded schedule versions remain stored for audit but are not duplicated into the normal full schedule. Investor holding projections remain future/outstanding only.

Rationale:
Separating funding completion from cash drawdown prevents an impossible repayment lifecycle. Combining immutable payment events with the current schedule preserves historical truth after one or more schedule regenerations without presenting superseded future projections as current obligations.

Follow-ups:
Uploaded disbursement evidence files and controlled correction/reversal events remain separate hardening items.

## Loan States

- Approved.
- Funding.
- Funded (funding closed; borrower disbursement pending).
- Active/current (borrower disbursed; servicing enabled).
- Grace period.
- Late.
- Defaulted.
- Operationally changed.
- Repaid.
- Final resolution pending, only after Garanta defines a future recovered/resolved/loss-recognition workflow.
- Cancelled.

## Schedule Requirements

- Support generated schedules for launch repayment types.
- Exclude custom/manual schedule as a launch repayment type.
- Use annual nominal interest at launch.
- Use monthly installments as the default installment frequency.
- Use calendar-day due/late/default status checks.
- Round each installment line to the currency minor unit.
- Absorb rounding residue in the final installment.
- Store original and current schedules.
- Version schedule changes.
- Allow controlled event-driven edits to generated schedules with reason and audit metadata.
- Track due date, principal due, interest due, fees due, paid amounts, late amounts, and status.
- For refinancing loans, the original loan schedule computed from the admin-declared original loan data is purely informational for investors: it is never persisted and never serviced. The installments ticked as "paid before publication" during the publish review must be a contiguous prefix of past-due original-schedule rows, but they have no effect on servicing. The serviced schedule is always generated from the financeable principal, exactly as for a standard loan.
- Recalculate expected investor distributions when schedules change.
- Preserve historical schedule versions for audit and reporting.
- Present canonical full schedules as immutable repayment-event rows followed by outstanding rows from the latest schedule version. Historical regular and advance payments remain visible after every schedule regeneration; projected investor schedules remain future/outstanding only.

## Repayment Allocation Waterfall

Launch waterfall and servicing mechanics:

1. Apply Garanta legal costs and recovery fee due for the payment.
2. Apply penalty/default interest due.
3. Apply contractual interest due.
4. Apply the remainder to principal. Principal cannot be paid until every earlier due tier is satisfied.
5. A regular installment declaration uses the fixed outstanding amount of the next due installment. More than one day before due, admin must acknowledge that the full contractual installment is intended; otherwise use repayment in advance.
6. Any other amount (except for defaulted loans, which go through recovery) is declared as a repayment in advance with a borrower repayment bank date.
7. For repayment in advance, contractual interest due comprises all unpaid scheduled interest through the bank date plus ACT/365 interest on outstanding principal from the latest interest-paid-through date up to, but excluding, the bank date (`principal x annual bps x days / (10,000 x 365)`, half-up minor-unit rounding). Interest accrues end of day and future interest is never collected.
8. Regenerate the future schedule as a new schedule version: only future rows, original due dates preserved, first regenerated installment interest calculated by ACT/365 from bank date to due date. A full payoff marks the loan repaid.
9. Require admin confirmation of the previewed allocation and old/new schedules before any ledger write.
10. Calculate each lender's pro-rata distribution.
11. Apply configured `lender_payment_fee` per lender distribution. Launch value is 0.
12. Put unmatched, surplus, or unexplained amounts into suspense until admin resolves them.

Investor-facing treatment must match contracts.

For default recovery events, the same universal waterfall is applied before lender distribution: Garanta legal/recovery costs and recovery fee, penalty/default interest, contractual interest accrued until default, then principal. Lender-facing buckets are allocated pro rata to current lender holdings based on current principal balance at the time of the recovery event. The recovery record separately classifies gross recovered amount, third-party/external recovery costs, Garanta recovery fee, net amount received, net amount available for allocation, principal, contractual interest accrued until default date, default/penalty interest after default date if applicable, other penalties/costs, lender distributions, and recovery rounding difference.

## Offline Borrower Servicing Operations

- Admin records or sends upcoming repayment schedule information off-platform.
- Admin records or sends payment instructions off-platform.
- Admin records repayment confirmations.
- Admin handles late reminders, borrower outreach, negotiation, and legal notices offline.
- Admin records early repayment requests received off-platform.
- Admin records operational change requests received off-platform.
- Admin stores generic servicing, arrears, recovery, and default-resolution documents and notes.
- Detailed borrower contact method tracking is not required in v1.

## Investor Servicing Features

- Expected cash flow calendar.
- Received repayments.
- Balance-credit status for each distribution.
- Loan status updates.
- Late/default notices.
- Recovery updates.
- Downloadable statements.
- Email notifications for received lender balance credits.

## Controls

- Repayment matching must be traceable to external payment references.
- Admin declares borrower repayments from the Loans table through Manage > "Record borrower repayment", which shows the loan's current schedule, before distributions are generated.
- A regular installment declaration uses the fixed outstanding amount of the next due installment; the amount cannot be edited.
- Any other amount (except for defaulted loans, which go through recovery) requires the "Repayment in advance" checkbox and a borrower repayment bank date; the system allocates it through the repayment-in-advance waterfall and regenerates the future schedule as a new version.
- Repayment-in-advance declarations require admin confirmation of a preview showing the allocation and both the old and the new schedule before anything is written.
- System must produce the lender distribution list with lender, balance currency, reference, and amount due.
- System may generate internal balance-credit records and account statements for admin processing/evidence.
- Lender distribution artifacts are internal and are not sent to lenders as files by default.
- Lenders receive email notification of the credited amount.
- Investor distributions are credited to investor balances and become subject to balance ageing/deadline rules.
- Controlled payment/operational event overrides require reason and admin confirmation.
- Late status is day 5 after due date; default status is day 16 after due date, using Europe/Zurich calendar days unless changed by policy.
- Borrower operational changes that affect investor economics require admin confirmation and investor notification.
- Direct free-form restructuring is out of scope; changes happen through defined operational events.
- Direct arbitrary schedule editing is out of scope; material schedule changes must be caused by declared payment or operational events.
- Write-off is not an operational v1 workflow. Defaulted loans remain in default/recovery handling until Garanta defines a separate advisor-approved recovered/resolved/loss-recognition workflow.
- Closed loans are locked except for controlled corrections.

## Dependencies

- Payments, Ledger, Custody, and Reconciliation.
- Documents, Contracting, and E-Signature.
- Communications and Notifications.
- Risk Monitoring, Collections, and Recoveries.
- Accounting, Tax, and Finance Operations.

## Q/A Backlog

1. Answered by SERV-DEC-001: all standard generated repayment types except custom/manual schedule as a repayment type.
2. Updated by SERV-DEC-003 and PAY-DEC-005/PAY-DEC-006/PAY-DEC-017: admin declares regular installments at the fixed next-due amount and other amounts as repayments in advance; system calculates lender pro-rata balance credits and configurable lender payment fee, initially 0; credited balances are subject to ageing rules.
3. Answered by SERV-DEC-005: no late fees at launch.
4. Answered by SERV-DEC-007: full and partial early repayment are allowed through the repayment-in-advance flow, with no early repayment fee.
5. Answered by SERV-DEC-006: partial repayments are accepted case by case through the repayment-in-advance flow.
6. Answered by SERV-DEC-008: day 5 late, day 16 default, using Europe/Zurich calendar days.
7. Answered by SERV-DEC-009: no direct free-form restructuring; changes happen through defined operational events.
8. Answered by SERV-DEC-010: no detailed covenant tracking at launch; generic notes/document upload only.
9. Answered by SERV-DEC-011: closure evidence is the repayment/distribution evidence trail, including attached bank statements/payment records where used.
10. Updated by SERV-DEC-013 and RISK-DEC-005/RISK-DEC-006: default recovery payments are admin-recorded with gross recovery, externally deducted costs, third-party recovery costs, optional Garanta percentage recovery fee, net received, outstanding penalty/interest obligations, server-derived universal waterfall allocation, lender allocation by current principal balance, separate default/penalty interest where applicable, and explicit recovery rounding differences.

## Loan Originator Claim Servicing

### SERV-DEC-015: Dated Entitlements

Garanta services an originator loan once investor claims exist. The borrower pays Garanta. Each payment first follows the same universal waterfall as a direct loan: Garanta legal costs/recovery fee, penalty, contractual interest, then principal. The platform then allocates principal by current assigned versus unsold principal and allocates interest/penalties by immutable accrual intervals. Pre-assignment accrual belongs to originator; post-assignment accrual to the current holder. Largest-remainder splits reconcile each component exactly. Investor amounts create balance lots; originator amounts create servicing payable. Principal-only weights must not be used for the first post-sale payment.

In the Loan Originator replacement CSV, `fee_minor` is the evidence field for Garanta legal costs/recovery fee due in the first waterfall tier. It is not a caller-defined platform fee or an amount payable to investors or the originator. `penalty_minor`, `interest_minor`, and `principal_minor` represent the remaining tiers in that exact order. The server recomputes the amount due for every tier from the immutable prior import and the current schedule, then rejects an imported payment row whose component split attempts to relabel principal or bypass a higher tier.

### SERV-DEC-016: Payments and Repricing

Regular and advance repayments reuse loan-type-specific schedule and accrual calculations but always use the universal payment-allocation priority. The imported CSV component split is evidence, not authority, and is rejected if it attempts to pay a lower tier before a higher due tier. Each payment atomically updates schedule state, holdings, unsold principal, entitlement projections, opportunity availability, and quote validity; secondary listings retain their premium/discount while repricing current principal. No restructuring exists: extensions settle the old loan and create a new one. Opportunity closes at repayment, hold/late/default, or 30 days to maturity. Garanta handles recovery without originator recourse/buyback.
