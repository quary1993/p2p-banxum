# Loan Servicing and Repayments

Status: Draft. Updated with payment, balance, servicing, and configurable recovery waterfall decisions on 2026-06-01, and with the fixed-amount installment / repayment-in-advance servicing model on 2026-07-08.

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
Borrower repayments are declared from the Loans table through Manage > "Record borrower repayment", which shows the loan's current schedule. Declaring a regular installment payment uses a fixed amount: it must equal the outstanding amount of the next due installment and cannot be edited.

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
Launch repayment allocation waterfall:

1. Fees.
2. Penalties.
3. Current installment interest.
4. Current installment principal.
5. Future outstanding principal when the received amount exceeds currently due scheduled amounts.

Late fees are not charged at launch, so late-fee allocation is inactive unless added later.

Borrower-side penalties remain configurable in the data model but are set to 0/inactive at launch until Garanta finalizes business and legal policy. While penalties are 0, the penalty waterfall step has no monetary effect.

For a healthy loan with a CHF 1,000 regular installment, if the borrower pays CHF 3,000, admin declares it as a repayment in advance with the borrower repayment bank date. The system pays all unpaid scheduled interest of installments due on or before the bank date, plus pro-rata accrued interest on the outstanding principal for the days since the last installment due date up to the bank date; the remainder reduces outstanding principal. The future schedule is then regenerated as a new schedule version for the same remaining due dates using the new outstanding principal.

Rationale:
The waterfall preserves fee/penalty priority while keeping loan economics tied to the agreed schedule.

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

Early repayment is declared as a "Repayment in advance": admin checks the repayment-in-advance option in Manage > "Record borrower repayment", enters the received amount, and selects the "Borrower repayment bank date". The waterfall then pays:

1. All unpaid scheduled interest of installments due on or before the bank date.
2. Pro-rata accrued interest on the outstanding principal for the days since the last installment due date up to the bank date: outstanding x monthly rate x days elapsed / days in period, where monthly rate = annual bps / 120000.
3. The remainder reduces outstanding principal.

The future schedule is then regenerated as a new immutable schedule version: only future rows are regenerated, original due dates are preserved, and the first regenerated installment's interest is prorated for the remainder of the current period. Before anything is written, the admin gets a preview/confirmation dialog showing the allocation and both the old and the new schedule (backend endpoint `POST /api/v1/servicing/admin/borrower-repayments/advance-preview/`). A full payoff through repayment in advance marks the loan repaid.

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
When a defaulted loan has a recovered amount available, admin records the recovery event, notes/observations, and supporting documents. The recovery record must include gross recovered amount, externally deducted legal/recovery costs, third-party recovery/legal costs declared at recovery time, whether the Garanta percentage recovery fee is applied, net amount received by Garanta, net amount available for waterfall allocation, recovery bank value date/receipt date, and the recovery category split.

The platform applies the project-specific recovery waterfall before lender distribution. Unless the project agreement/configuration defines another waterfall, the default recovery waterfall is:

1. External recovery/legal costs.
2. Platform-approved recovery costs, including the Garanta percentage recovery fee where applied.
3. Principal.
4. Contractual interest accrued until the official default declaration date.
5. Default/penalty interest accrued after the official default declaration date.
6. Other penalties/costs.

Lender-facing recovery buckets are distributed pro rata to lenders holding participations in the relevant project, based on the current principal balance of each holding at the time of the recovery event, unless the project agreement defines another allocation method.

Normal contractual interest stops accruing on the official default declaration date. Default/penalty interest starts accruing from that date instead of regular interest only if provided in the relevant loan/project agreement or project recovery configuration. It must be calculated using the project `default_penalty_interest_percent` and reported separately from normal contractual interest.

Recovered amounts may include principal, contractual interest accrued until default date, default/penalty interest, penalties, and costs. These categories must be classified separately in the ledger, default/recovery report, and lender reports.

Distribution rounding uses deterministic currency minor-unit rounding. Launch rounding is half-up per lender distribution line, with any rounding difference recorded separately as a recovery rounding difference.

Each recovery payment must generate ledger entries, a default/recovery report, and notification to affected lenders.

Rationale:
Default recovery is case-specific and handled offline, but the waterfall, lender distribution, interest cutoff, category classification, recovery fee, third-party costs, rounding, reporting, and notification must still be deterministic and auditable.

Follow-ups:
Finalize lender notification wording, accountant-approved recovery report labels, and any non-default project waterfall wording required by project agreements.

## Loan States

- Approved.
- Funding.
- Funded.
- Contracted.
- Drawn.
- Current.
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

## Repayment Allocation Waterfall

Launch waterfall:

1. A regular installment declaration uses the fixed outstanding amount of the next due installment; it is allocated to that installment's fees, penalties, interest, and principal.
2. Any other amount (except for defaulted loans, which go through recovery) is declared as a repayment in advance with a borrower repayment bank date.
3. For a repayment in advance, allocate to fees.
4. Allocate to penalties.
5. Allocate to all unpaid scheduled interest of installments due on or before the bank date.
6. Allocate to pro-rata accrued interest on the outstanding principal for the days since the last installment due date up to the bank date (outstanding x monthly rate x days elapsed / days in period, monthly rate = annual bps / 120000).
7. Allocate the remainder to outstanding principal.
8. Regenerate the future schedule as a new schedule version: only future rows, original due dates preserved, first regenerated installment interest prorated for the remainder of the current period. A full payoff marks the loan repaid.
9. Require admin confirmation of the previewed allocation and old/new schedules before any ledger write.
10. Calculate each lender's pro-rata distribution.
11. Apply configured `lender_payment_fee` per lender distribution. Launch value is 0.
12. Put unmatched, surplus, or unexplained amounts into suspense until admin resolves them.

Investor-facing treatment must match contracts.

For default recovery events, the project-specific recovery waterfall is applied before lender distribution. Unless overridden per project, the default waterfall is external recovery/legal costs, platform-approved recovery costs including applied Garanta recovery fee, principal, contractual interest accrued until default date, default/penalty interest after default date if applicable, and other penalties/costs. Lender-facing buckets are allocated pro rata to current lender holdings based on current principal balance at the time of the recovery event unless the project agreement defines a different method. The recovery record separately classifies gross recovered amount, third-party/external recovery costs, Garanta recovery fee, net amount received, net amount available for waterfall allocation, principal, contractual interest accrued until default date, default/penalty interest after default date if applicable, other penalties/costs, lender distributions, and recovery rounding difference.

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
10. Updated by SERV-DEC-013 and RISK-DEC-005/RISK-DEC-006: default recovery payments are admin-recorded with gross recovery, externally deducted costs, third-party recovery costs declared at recovery time, optional Garanta percentage recovery fee, net received, project recovery waterfall allocation, category split, lender allocation by current principal balance unless project-specific overrides exist, separate default/penalty interest where applicable, and explicit recovery rounding differences.
