# Reporting, Analytics, and Regulatory Exports

Status: Draft. Updated with marketplace, balance, FX, servicing, recovery allocation, Bexio accounting, annual participant tax information statements, KYC/KYB evidence exports, and reporting/export decisions on 2026-05-30.

## Purpose

Define operational, management, investor, borrower, finance, regulatory, and audit reporting and export requirements.

## Scope

- On-demand reports and exports.
- Future internal dashboards.
- Portfolio analytics.
- Marketplace analytics.
- KYC provider report integration references.
- AML/KYC/KYB evidence exports where stored locally.
- Finance reports.
- Risk and arrears reports.
- Regulatory exports.
- Audit evidence packages.
- Future data warehouse readiness.

## Decisions

### RPT-DEC-001: Launch Report Pack

Status: Accepted.
Date: 2026-05-21.
Owner: Garanta operations / finance / compliance / product.

Decision:
At launch, the platform supports industry-standard operational, finance, accounting-source, risk, balance/FX, investor, borrower, and audit reports. The platform should include report sets normally expected by Garanta management, accountants, auditors, VQF/SRO or other supervisory stakeholders, the board, and bank/payment partners, while final report wording and exact external submission requirements remain subject to legal/accounting/compliance review.

For Swiss company accounting support, the platform does not replace the accounting system or statutory financial statements, but it must provide source reports commonly needed to prepare and audit them:

- Operational subledger export.
- Configurable monthly Bexio debit/credit journal export, using transaction-level or summarized rows according to the final accountant-approved import layout.
- Trial balance/source ledger report.
- General ledger/subledger source report.
- Balance-sheet support schedules, including client/investor balances by currency, cash/collection account reconciliation, borrower receivables, suspense balances, and fee/revenue balances.
- Profit-and-loss support schedules, including borrower success fees, secondary-market fees, FX fees, balance penalties, and other platform revenue/expense-relevant events.
- Payment/bank reconciliation report.
- Investor balance liability report.
- Borrower receivables and repayment report.
- FX activity, FX delta, external execution, and residual settlement difference report.
- Tax-relevant amount export.
- Audit trail/action log report.
- Evidence package export.

Rationale:
Garanta needs standard source reporting for Swiss accounting, audit, board, operational, and regulatory oversight without implementing a full accounting or BI system in the first version.

Impacted modules:
- Accounting, Tax, and Finance Operations.
- Admin and Operations Portal.
- Payments, Ledger, Custody, and Reconciliation.
- Security, Privacy, and Auditability.

Follow-ups:
Garanta will later provide examples for accounting reports. Finalize exact report layouts, Bexio import fields, Bexio chart-of-accounts mapping, and tax-code mapping with the accountant/auditor.

### RPT-DEC-002: On-Demand Ranges, Formats, and Evidence Packages

Status: Accepted.
Date: 2026-05-21.
Owner: Garanta operations / finance / technology.

Decision:
Reports are generated on demand by admin with custom date ranges and default presets. Default presets include daily, weekly, monthly, quarterly, yearly/calendar-year, and annual/fiscal-year ranges where applicable.

Every launch report must be exportable as both PDF and CSV. Where a report needs supporting artifacts, the platform must also support a ZIP evidence package containing the PDF, CSV, manifest, and related evidence files or references.

The manifest should include report type, date range, filters, redaction mode, generated timestamp, generator admin, report definition/version, and source-data reference or checksum where feasible.

Rationale:
On-demand exports are enough for launch and allow admins to download/store the packages needed for accountants, auditors, board materials, regulatory requests, and operating reviews.

Follow-ups:
Define CSV delimiter/encoding, PDF layout, ZIP manifest schema, filename conventions, and maximum export size.

### RPT-DEC-003: Export Permission and Redaction Modes

Status: Accepted.
Date: 2026-05-21.
Owner: Garanta operations / security / compliance.

Decision:
Only admin can export reports at launch. Superadmin does not receive export access unless also assigned/admin-granted the admin operational role. Auditors/regulators do not need direct portal access at launch; Garanta admins generate and share/export packages offline.

Sensitive exports must support two modes:

- Redacted: masks or removes PII, bank details, identity data, restricted compliance data, and other sensitive fields not needed for the report purpose.
- Full: includes sensitive fields where required for an authorized operational, accounting, audit, regulatory, or compliance purpose.

Every export is logged with report type, range, filters, redaction mode, generated timestamp, generating admin, and destination/handling note if captured.

Rationale:
Admin-only export keeps the launch permission model simple while redacted/full modes support least-privilege sharing and audit needs.

Follow-ups:
Define the exact redaction rules per report. Full exports require audit logging only at launch; reason codes or enhanced confirmation can be reconsidered later.

### RPT-DEC-004: No Launch BI Layer or Dashboards Required

Status: Accepted.
Date: 2026-05-21.
Owner: Garanta product / technology.

Decision:
Built-in dashboards and a dedicated BI/data warehouse layer are not required for launch. CSV/PDF/ZIP exports are enough initially.

The reporting design must still be BI-ready: report definitions, source events, ledger entries, dimensions, and metrics should be structured so a data warehouse, BI tool, or dashboard layer can be added later without rewriting the core business ledger.

Investor-facing analytics beyond the basic launch portfolio view are not in scope. Launch investor-facing data is limited to portfolio view, statements, annual lender tax information statement, expected/received cashflows, late/default status, and relevant document/download views.

Rationale:
Exports are the practical first version, but the data model should not block later analytics.

Follow-ups:
Define a future analytics dimensional model once BI becomes a roadmap item.

### RPT-DEC-005: KYC Provider Reports and Local Evidence Boundary

Status: Accepted.
Date: 2026-05-21.
Owner: Garanta compliance / technology.

Decision:
Formal KYC/AML provider reports are generated by the KYC provider, such as Didit, rather than rebuilt inside the platform at launch.

The platform must handle the integration and store local evidence according to the identity module. This includes provider references, statuses, decision metadata, required KYC/KYB data fields, downloaded provider report metadata, downloaded provider reports where legally and technically possible, raw provider webhook payloads where legally and technically possible, supporting documents where retained, manual-review decisions, and audit history.

The platform does not recreate the provider-native screening engine, but it must be able to export locally retained KYC/KYB/AML evidence packages for VQF/SRO, auditors, banks, payment partners, and internal compliance reviews.

Rationale:
The provider is the system that produces formal KYC/AML screening reports. The platform should integrate with it, preserve local regulatory evidence, and export evidence packages rather than duplicating the provider screening engine.

Follow-ups:
Finalize provider-specific Didit workflow names, event names, report availability, report download endpoints, downloadable-file metadata, and any provider artifact that cannot legally or technically be retained locally.

### RPT-DEC-006: Reproducible Reports Instead of Stored Snapshots

Status: Accepted.
Date: 2026-05-21.
Owner: Garanta finance / operations / technology.

Decision:
Reports do not need to be stored permanently as generated snapshots if they are reproducible from ledger/event/source data and report definition versions.

Admins may download and store generated PDFs, CSVs, and ZIP evidence packages externally where needed. The platform must retain enough generation metadata and source lineage to reproduce a report for the same period, filters, and definition version.

Rationale:
Reproducibility avoids unnecessary storage of repeated report artifacts while preserving auditability.

Follow-ups:
Define report definition versioning, source-data immutability guarantees, and whether any legally required reports must be materialized and retained.

## Report Categories

### Executive

- Originations volume.
- Funded volume.
- Active investors.
- Active borrowers.
- Portfolio yield.
- Default/arrears rate.
- Revenue.
- Operational SLA performance.
- Recoveries.
- FX fees.
- Platform balances by currency.

### Compliance

- KYC provider report references and integration status.
- Local KYC/KYB/AML evidence export, including downloaded provider reports where possible, raw provider webhook payloads where retained, manual decisions, status history, and supporting documents.
- Admin-entered off-platform legal-entity lender and borrower evidence status.
- Manual compliance overrides recorded in the platform.

Formal KYC provider reports, including KYC status, failed/rejected KYC, high-risk users, PEP/sanctions/adverse-media flags, and provider-native case reports, are generated by the provider and downloaded/stored locally where legally and technically possible.

### Risk/Credit

- Exposure by borrower.
- Exposure by sector.
- Exposure by product.
- Exposure by rating.
- Arrears aging.
- Defaults and recoveries.
- Late loans from day 5 after due date, using Europe/Zurich calendar days.
- Defaulted loans from day 16 after due date, using Europe/Zurich calendar days.
- Default list.
- Investor exposure by defaulted loan.
- Recovery/write-off action log covering platform actions, status changes, notes, document uploads, public notes, bulk investor emails, recovery events, and write-off events.
- Write-off report.
- Recovery payment/waterfall report showing gross recovered amount, externally deducted legal/recovery costs, third-party recovery costs declared at recovery time, Garanta recovery fee decision/amount, net amount received by Garanta, net amount available for waterfall allocation, contractual-interest cutoff at default, default/penalty interest percent and amount after default if applicable, principal/interest/penalty/cost category split, lender allocations, and recovery rounding differences.
- Early repayments.
- Partial repayments.
- Schedule overrides and operational loan changes.
- Covenant breaches, future/detailed tracking.

### Finance

- Ledger trial balance.
- Operational subledger export.
- Configurable monthly Bexio debit/credit journal export.
- General ledger/subledger source report.
- Balance-sheet support schedules.
- Profit-and-loss support schedules.
- Payment reconciliation.
- Bank operation declarations by type: lender deposit, lender withdrawal, borrower loan disbursement, borrower repayment, Garanta out, Garanta in, and currency-exchange external settlement.
- Ledger-bank reconciliation by currency, including bank-stated balance, investor balances, Garanta accrued revenue/commission balance, suspense/unmatched cash, pending/exception balances, and difference.
- Investor balances by currency.
- Currency-specific ledgers for CHF, EUR, and later enabled currencies.
- CHF base reporting summaries.
- Accounting source data for accountant-performed FX revaluation.
- Balance ageing and deadline report.
- Balance penalty report.
- Withdrawals.
- Fees earned.
- Accrued Garanta revenue/commissions by arbitrary date range.
- Garanta accrued revenue/commission balance still held in collection accounts by currency.
- Garanta out and Garanta in transfers.
- FX fees earned.
- FX delta report by day/period.
- External FX execution/reconciliation report.
- Realized FX gain/loss or surplus/deficit by currency after external FX settlement declaration.
- Investor distributions.
- Internal distribution artifacts and attached payment evidence.
- Recovery distributions, gross-to-net recovery reporting, third-party recovery costs, Garanta recovery fee revenue where applied, recovery waterfall category splits, and recovery rounding differences.
- Borrower receivables.
- Investor account statements.
- Annual investor statements.
- Annual tax information statements for lenders, using calendar-year cutoff by default.
- Borrower account statements as admin-generated PDF and CSV.
- Borrower annual tax information statements as admin-generated PDF and CSV.
- Garanta internal annual account and tax information reports.
- Tax-relevant amount exports covering participant income received/credited, costs incurred, fees, interest, losses/write-offs, recoveries, secondary-market results, FX activity, and balance penalties.
- Information-only principal/balance movement sections separating deposits, withdrawals, funded principal, repaid principal, principal received, principal repaid, outstanding principal, drawdowns, and repayment principal from income/cost totals.
- Finance corrections approved by admin or superadmin.
- Suspense balances.

### Marketplace

- Listing conversion.
- Funding velocity.
- Investor concentration.
- Pending unpaid orders.
- Validated funded orders.
- Order closures and refunds.
- Oversubscription rates.
- Secondary-market listings, approval status, transfers, current principal balance, transfer price, discount/premium, accrued interest, buyer/seller fees, seller net proceeds, buyer total cost, and fees.
- Secondary-market proceeds credited to balances.

### Balance and FX

- Total investor balances by currency.
- Balance source entries by age bucket.
- Entries approaching day 25, 46, 53, 58, 59, and 60 reminders.
- Balance split by investable, withdraw-required, FX-eligible, and penalty/frozen amounts.
- Entries past day 60 and penalties applied.
- Forced withdrawals finalized by admin, with optional offline return/failure notes or documents.
- Missing-IBAN penalty-mode freezes.
- Deposits by currency.
- Withdrawals by currency.
- Currency exchanges by pair.
- Currency-exchange source-entry lineage for audit exports.
- Currency-exchange target entries with inherited ageing deadlines and source-entry lineage.
- Net FX delta by day or period.
- FX fee revenue.
- External FX execution evidence and residual settlement difference.
- Instant platform FX credits versus external end-of-day/next-morning settlement.
- Realized FX gain/loss by currency.

## Data Requirements

- Reports must be reproducible for historical dates.
- Month-end reports must be reproducible, but no formal period lock/close is required at launch.
- Accounting exports must preserve source-event lineage to the platform operational subledger.
- Accounting exports must be generated from immutable transaction-level ledger events that retain event ID, event type, booking date, value date, currency, gross/net amounts, debit/credit mapping, lender/borrower/loan references, bank/PSP reference, evidence reference, tax metadata, and reversal/correction history.
- Annual tax information statements must be generated from the same immutable transaction-level ledger and complete annual account statement used for the participant.
- Tax-relevant summaries must separate income/cost items from information-only principal and balance movements.
- Annual tax information statements must be informational only and must not present platform-generated tax advice.
- Metrics must have definitions.
- Data lineage must connect reports to source events.
- Sensitive reports require role-based access and redacted/full export modes.
- Exports must be logged with admin, timestamp, report type, range, filters, redaction mode, and report definition/version.
- Regulatory, accounting, and audit reports must be versioned by report definition.
- Launch reports must be exportable as PDF and CSV.
- Evidence-package exports must be ZIP files with a manifest.
- Direct auditor/regulator portal access is out of launch scope.

## Dependencies

- All business modules.
- Integrations, APIs, and Event Architecture.
- Security, Privacy, and Auditability.

## Q/A Backlog

1. Partly answered by RISK-DEC-011: risk/recovery launch reports include default list, investor exposure by defaulted loan, action log, and write-off report.
2. Answered by RPT-DEC-001: launch uses industry-standard operational, finance/accounting-source, risk, balance/FX, investor, borrower, audit, and evidence reports; exact external layouts can be refined later with examples.
3. Answered by RPT-DEC-002: reports are on demand with custom ranges and daily, weekly, monthly, quarterly, yearly/calendar-year, and annual/fiscal-year presets.
4. Answered by RPT-DEC-004: no launch BI/data warehouse layer is required, but the reporting architecture must be BI-ready.
5. Answered by RPT-DEC-003: admin only can export reports at launch.
6. Answered by RPT-DEC-002/RPT-DEC-003: launch exports support PDF, CSV, and ZIP evidence packages, with redacted and full modes.
7. Answered by RPT-DEC-004: no investor-facing analytics beyond launch portfolio view, statements, tax statement, expected/received cashflows, late/default status, and documents.
8. Answered by PAY-DEC-020: admin needs FX delta reporting by day or period.
9. Answered by PAY-DEC-017: balance ageing, reminder, deadline, and penalty reports are required.
10. Answered by FIN-DEC-002/003: finance exports must support Bexio monthly accounting exports, CHF base reporting, currency-specific ledgers, and accountant-performed FX revaluation.
11. Answered by FIN-DEC-001/005: annual tax information statements and tax-relevant amount exports are required for lenders, borrowers, and Garanta internal finance, generated from the same transaction-level ledger and complete annual account statement.
12. Answered by FIN-DEC-004: borrower account statements and annual tax information statements are admin-generated as PDF and CSV; invoices are not generated at launch.
13. Answered by FIN-DEC-006: month-end reports are reproducible without period locking; finance corrections can be approved by admin or superadmin.
14. Updated by RPT-DEC-005 and KYC-DEC-005: KYC provider reports are generated by the provider and downloaded/stored locally where legally and technically possible. The platform stores integration references, statuses, decision metadata, required KYC/KYB data fields, report metadata, raw webhook payloads where possible, supporting evidence where possible, manual decisions, and audit history for evidence exports.
15. Answered by RPT-DEC-006: reports only need to be reproducible from source data; admins download/store artifacts as needed.
16. Answered by RPT-DEC-003: auditors/regulators do not need direct portal access at launch; admins generate and share/export packages offline.
17. Answered by PAY-DEC-026/FIN-DEC-007: finance reports include bank operation declarations, ledger-bank reconciliation by currency, Garanta accrued revenue/commission balances, and arbitrary-period accrued revenue reports.
18. Answered by PAY-DEC-027/FIN-DEC-008: FX reports include external settlement execution details and realized FX gain/loss or surplus/deficit by currency.
