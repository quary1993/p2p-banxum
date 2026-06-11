# Accounting, Tax, and Finance Operations

Status: Draft. Updated with Swiss accounting, Bexio export, annual participant tax information statements, balance, FX, bank reconciliation, marketplace, servicing, recovery allocation, document/tax, and finance-output decisions on 2026-06-01.

## Purpose

Define the financial operations layer that turns loan, payment, fee, balance, FX, and servicing events into operational subledger records, accounting exports, tax-relevant data, statements, and finance controls.

## Scope

- Debit/credit accounting export mapping.
- Revenue and fee tracking.
- Investor statements.
- Borrower statements.
- Tax reporting.
- Reconciliation with accounting system.
- Month-end reporting.
- Finance adjustments.
- Audit support.

## Finance Events

- Investor deposit or payment.
- Investor balance credit.
- Investor balance debit.
- Investor withdrawal.
- Bank operation declared.
- Bank reconciliation break opened.
- Balance ageing penalty.
- Forced withdrawal.
- Investment order validation.
- Partial investment order validation.
- Oversubscription excess refund due.
- Full excess refund due.
- Borrower drawdown.
- Borrower loan disbursement bank operation.
- Borrower success fee charged and withheld from disbursement after full funding or admin-approved partial close.
- Servicing fee charged.
- Repayment received.
- Partial repayment received.
- Early repayment received.
- Schedule recalculation.
- Interest accrued.
- Principal repaid.
- Investor distribution.
- Investor distribution credited to balance.
- Lender payment fee, initially 0.
- Refund.
- Secondary-market buyer payment.
- Secondary-market seller proceeds.
- Secondary-market seller proceeds credited to balance.
- Secondary-market maker fee revenue.
- Secondary-market taker fee revenue.
- Secondary-market transfer settlement.
- Currency exchange requested.
- Currency exchange completed.
- Currency exchange fee revenue.
- External FX execution/reconciliation.
- Realized FX gain/loss, residual FX delta, or rounding adjustment.
- Garanta accrued commission/revenue balance updated.
- Garanta out transfer to operating account.
- Garanta in transfer from operating account or other Garanta-owned source.
- Late fee, future/inactive at launch.
- Gross recovery recorded.
- Externally deducted legal/recovery cost recorded.
- Third-party recovery cost declared.
- Recovery waterfall applied.
- Garanta percentage recovery fee charged, if applied.
- Net recovery received.
- Recovery distribution credited to lender balances.
- Contractual interest cutoff at default.
- Default/penalty interest accrued, if provided by loan/project agreement.
- Recovery rounding difference.
- Advisor-approved final default loss recognition.
- Annual tax information statement generated.
- Investor account statement generated.
- Borrower account statement generated.
- Garanta internal annual account/tax information report generated.
- Accounting export generated.
- Manual correction.

## Decisions

### FIN-DEC-001: Annual Tax Information Statements for Platform Participants

Status: Accepted.
Date: 2026-05-21. Updated 2026-05-29.
Owner: Garanta finance / tax / product.

Decision:
The platform must generate annual tax information statements for platform participants at launch. The module is not limited to a lender-only Swiss tax output.

The platform must generate a complete annual account statement for each involved party type and automatically extract the tax-relevant summary from that same statement:

- Lenders.
- Borrowers.
- Garanta internal finance/accounting.

All annual statements and tax summaries must be generated from the same immutable transaction-level ledger used for operational reporting and accounting exports. The tax-relevant summary means income received/credited and costs incurred. Principal movements are separated and shown only for information, reconciliation, and balance explanation, not as income.

For lenders, the tax-relevant summary includes interest received or credited, fees paid, FX costs/fees, potential losses after final default resolution where advisor-approved, recoveries, secondary-market results, and balance penalties if any. Recovery reporting must separate principal recovered, contractual interest accrued until default date, default/penalty interest after default date if applicable, third-party recovery costs, Garanta recovery fee if charged to the recovery waterfall, penalties/costs, and rounding differences. Deposits, withdrawals, funded principal, repaid principal, outstanding principal, and balance movements are shown as information-only principal/balance movements.

For borrowers, the tax-relevant summary includes interest paid, Garanta fees including borrower success fee where applicable, administrative costs, FX costs if applicable, penalties, default/penalty interest if applicable, and recovery costs if applicable. Principal received, principal repaid, outstanding principal, drawdown movements, repayment principal, and recovered principal are separated from income/cost items.

For Garanta, the internal report extracts Garanta's own revenue and own costs. Garanta revenue includes platform fees, borrower success fees, secondary-market fees, FX margin/fees, balance penalties/handling fees if activated, and other Garanta fees. Client-money/settlement movements are separated from Garanta income and costs.

The annual cutoff is the calendar year ending December 31 by default. Reports show original transaction currency and currency-specific totals. CHF-equivalent fields should be configurable if Garanta's accountant/tax advisors require them for a specific output.

Every annual tax information statement must state that it is informational only and is not tax advice. Final tax treatment remains the responsibility of each party and its advisors.

Rationale:
All participant-facing and internal tax information should be derived from the same complete ledger-backed annual statement, avoiding separate tax logic that could drift from account statements or accounting exports.

Impacted modules:
- Investor Portal.
- Admin and Operations Portal.
- Documents, Contracting, and E-Signature.
- Reporting, Analytics, and Regulatory Exports.

Follow-ups:
Finalize title/field labels, disclaimer wording, optional CHF-equivalent rules, PDF/CSV layout examples, and jurisdiction-specific tax wording with Garanta's accountant/legal advisors.

### FIN-DEC-002: Swiss Accounting Context

Status: Accepted.
Date: 2026-05-21. Updated 2026-05-29.
Owner: Garanta finance / accounting.

Decision:
Garanta is a Swiss company and uses Bexio as its Swiss accounting software.

The platform ledger is the complete, immutable, transaction-level operational subledger and source of truth for investor balances, loan balances, fee events, FX events, repayment allocations, secondary-market settlement, balance ageing, and recovery distributions.

Bexio receives a configurable monthly accounting export generated from the platform ledger. The export must support configurable debit/credit mapping, tax metadata, evidence references, and transaction-level or summarized rows depending on the final accountant-approved Bexio import layout.

The finance module must support Swiss accounting evidence, CHF reporting, and currency-specific subledgers for CHF, EUR, and later enabled currencies.

Rationale:
The platform must preserve the full operational ledger while producing monthly accounting exports that are useful in Bexio and reconcilable by Garanta's accountant.

Impacted modules:
- Payments, Ledger, Custody, and Reconciliation.
- Reporting, Analytics, and Regulatory Exports.

Follow-ups:
Confirm Bexio chart of accounts mapping, journal import layout, tax code mapping, accountant-approved report examples, and who performs the monthly Bexio import.

### FIN-DEC-003: Base Currency, Currency Ledgers, and FX Revaluation

Status: Accepted.
Date: 2026-05-21.
Owner: Garanta finance / accounting.

Decision:
Garanta's base reporting currency is CHF.

The platform maintains currency-specific ledgers and reports for each enabled currency. Launch currencies are CHF and EUR. The platform does not perform accounting FX revaluation at launch. Revaluation into CHF is handled by the accountant in the accounting system.

The platform must export enough source data for revaluation and audit, including balance by currency, loan currency, fee currency, FX quote/rate, external FX execution evidence, FX fee, and residual FX delta.

Rationale:
Keeping accounting revaluation in the accounting system reduces platform accounting complexity while preserving auditable source records.

Impacted modules:
- Payments, Ledger, Custody, and Reconciliation.
- Reporting, Analytics, and Regulatory Exports.

Follow-ups:
Confirm the accountant's required export structure, exchange-rate source for accounting revaluation, and any period-end evidence package requirements.

### FIN-DEC-004: Statements Instead of Invoices

Status: Accepted.
Date: 2026-05-21.
Owner: Garanta finance / operations / product.

Decision:
The platform does not generate invoices at launch.

The platform generates account statements and finance reports instead. This includes investor account statements, annual investor statements, annual tax information statements for lenders, borrower account statements, borrower annual tax information statements, Garanta internal annual tax information reports, and operational finance exports.

Borrower-side statements are admin-generated because borrowers have no portal. Admin can generate borrower account statement and annual tax information outputs as PDF and CSV and send or handle them offline.

Rationale:
Garanta needs account evidence and reporting, not customer-facing invoicing, in the first version.

Impacted modules:
- Admin and Operations Portal.
- Documents, Contracting, and E-Signature.
- Reporting, Analytics, and Regulatory Exports.

Follow-ups:
Define statement templates, PDF/CSV columns, numbering/reference conventions, and whether statements need legal/accounting approval before use.

### FIN-DEC-005: Tax-Relevant Amount Storage and Exports

Status: Accepted.
Date: 2026-05-21.
Owner: Garanta finance / tax / product.

Decision:
The platform stores tax-relevant amounts and makes them available for exports. It does not hardcode VAT, reverse-charge, withholding tax, or other tax obligations at launch unless a later legal/accounting review requires it.

Stored/exportable statement and tax-summary source data includes fees, contractual interest, default/penalty interest if applicable, principal movements, losses after final default resolution where advisor-approved, gross recoveries, externally deducted legal/recovery costs, third-party recovery costs declared at recovery time, Garanta recovery fee if applied, project recovery waterfall configuration/version, net recoveries received by Garanta, net amount available for waterfall allocation, lender recovery distributions, recovery rounding differences, secondary-market results, FX activity, balance penalties, borrower success fee, lender payment fee if non-zero later, secondary-market maker/taker fees, FX fees, configurable tax categories, tax-code placeholders, and source-country/counterparty metadata where available.

Principal movements are retained for account-statement, reconciliation, and information-only sections. They must not be included in income/cost totals unless a later accountant-approved rule explicitly classifies a specific principal-related loss/recovery/final-resolution amount as tax-relevant.

Rationale:
The platform should provide complete source data while leaving tax interpretation, VAT/reverse-charge mapping, and filing treatment to Garanta's accountants and the investor's advisors.

Impacted modules:
- Reporting, Analytics, and Regulatory Exports.
- Documents, Contracting, and E-Signature.

Follow-ups:
Confirm specific Swiss or cross-border tax fields, VAT flags, reverse-charge flags, withholding flags, country-specific export formats, and Bexio tax-code mappings.

### FIN-DEC-006: Month-End Reporting and Finance Corrections

Status: Accepted.
Date: 2026-05-21.
Owner: Garanta finance / operations.

Decision:
No formal month-end close process or accounting-period lock is required at launch.

Month-end reports must be reproducible for a selected date/period, but the platform does not lock prior periods. Corrections remain auditable and should use correction/reversal entries rather than destructive edits.

Finance corrections may be approved by admin or superadmin at launch.

Rationale:
The first version prioritizes auditable operational flexibility over formal period locking. A lock/close workflow can be added later if accounting operations require it.

Impacted modules:
- Admin and Operations Portal.
- Security, Privacy, and Auditability.
- Reporting, Analytics, and Regulatory Exports.

Follow-ups:
Define correction reason codes, evidence attachments, report restatement markers, and whether higher-risk correction types should later require dual approval.

### FIN-DEC-007: Bank-Ledger Reconciliation and Accrued Revenue Reporting

Status: Accepted.
Date: 2026-06-01.
Owner: Garanta finance / accounting / operations.

Decision:
The finance module must reconcile bank-stated balances against platform ledger-stated balances by currency.

At launch, admins declare bank operations manually. The bank-operation types are lender deposit, lender withdrawal, borrower loan disbursement, borrower repayment, Garanta out, Garanta in, and currency-exchange external settlement. These operation records link external cash movement evidence to immutable ledger events.

When there are no pending bank operations, suspense/unmatched cash items, pending withdrawals/disbursements/refunds/FX settlements, or explicit exception balances, the expected reconciliation equation is:

```text
bank-stated balance by currency
= investor balances by currency
+ Garanta accrued commissions/revenue held in the collection account by currency
```

If pending or exception items exist, the reconciliation report must show them separately so the difference is explainable. Any unexplained difference creates a reconciliation break work item.

Garanta accrued revenue must be reportable for arbitrary date ranges independently of whether the cash has already been transferred out of collection/settlement accounts to Garanta operating accounts. `garanta_out` transfers move Garanta-owned accrued amounts out of collection/settlement accounts and must not affect investor balances.

Rationale:
Garanta needs both a transaction-level operational ledger and practical daily bank reconciliation. Revenue recognition/reporting should not depend only on when Garanta periodically transfers commissions to its operating account.

Impacted modules:
- Payments, Ledger, Custody, and Reconciliation.
- Admin and Operations Portal.
- Reporting, Analytics, and Regulatory Exports.

Follow-ups:
Confirm final accountant-approved labels and Bexio mappings for accrued commission balances, `garanta_out`, `garanta_in`, reconciliation differences, and realized FX gain/loss.

### FIN-DEC-008: External FX Settlement Result

Status: Accepted.
Date: 2026-06-01.
Owner: Garanta finance / accounting / operations.

Decision:
When admin declares the external FX settlement executed to offset user platform FX activity, the platform calculates realized FX surplus/deficit by currency by comparing user-facing FX events and fees with the actual external execution rate, amounts, and fees/costs declared by admin.

The realized FX result is Garanta-owned. Positive differences are reported as FX gain/margin where mapped by accounting policy; negative differences are reported as FX loss/cost. Investor balances must remain based on the accepted user FX quotes and must not be retroactively changed because external execution differs.

Rationale:
Instant user FX creates an external settlement obligation until Garanta settles the aggregate currency delta externally. The external result must be visible, auditable, and separated from investor balances.

Impacted modules:
- Payments, Ledger, Custody, and Reconciliation.
- Reporting, Analytics, and Regulatory Exports.

Follow-ups:
Confirm final accounting account names, Bexio mappings, and tax treatment for FX gains, FX losses, execution fees, and residual deltas.

## Accounting Requirements

- Ledger reports tie to general ledger.
- Each finance event has a source business event.
- Platform ledger is the immutable transaction-level operational subledger/source of truth.
- Bexio receives a configurable monthly accounting export and supporting reports.
- Each financial event must be stored individually with event ID, event type, booking date, value date, currency, gross amount, net amount, debit/credit mapping, lender reference, borrower reference, loan/project reference, bank/PSP reference, evidence reference, tax metadata, and reversal/correction history.
- Each external bank/PSP/EMI movement must have a declared bank-operation record linked to ledger entries and evidence.
- Revenue accounts separate borrower fees, investor fees, servicing fees, future/inactive late fees if enabled later, and other income.
- Client-money/settlement flows are not Garanta revenue. This includes lender principal, borrower repayments, interest distributed to lenders, deposits, withdrawals, and recovery distributions.
- Garanta P&L items include Garanta fees, borrower success fees, secondary-market fees, FX margin/fees, penalties/handling fees if activated, and operating costs.
- Garanta accrued commissions/revenue held in collection accounts must be separately reportable until moved through a `garanta_out` transfer.
- `garanta_in` transfers are Garanta-owned funding/support movements and must not be treated as lender deposits or investor balances.
- Bank reconciliation reports must compare bank-stated balances with investor balances, Garanta accrued revenue/commission balances, suspense/unmatched cash, pending/exception balances, and differences by currency.
- Client money or safeguarded funds are reported separately from operating cash if applicable.
- Borrower principal obligation remains the funded principal amount even when Garanta deducts the borrower success fee from disbursement.
- Borrower success fee is stored for accounting/net-revenue reporting and does not affect investor-facing website economics or the borrower repayment schedule.
- Investor distributions are credited to investor balances and become subject to balance ageing/deadline rules.
- Investor balance consumption is FIFO within each currency.
- Pending unpaid orders are not accounting events and do not create loan funding, investor exposure, or settlement liabilities until funds are received and validated.
- Primary-market excess/full-excess payments create refund payable entries.
- Secondary-market transfer price, accrued interest, discount/premium, seller proceeds, buyer payment, maker fee, and taker fee must be separately reportable. Launch secondary-market fees are 0.25% maker/seller and 0.75% taker/buyer, both charged at settlement and calculated on transfer price excluding accrued interest with half-up minor-unit rounding.
- Currency-exchange source amount, target amount, market rate, applied rate, platform FX fee, external execution rate, external execution fees/costs, realized FX gain/loss, and residual FX delta must be separately reportable.
- Currency-exchange ledger records must retain source-entry lineage for audit/regulatory review, and target-currency entries must inherit balance-ageing deadlines from the source entries consumed by the FX transaction rather than receiving fresh 30/60-day deadlines.
- Balance ageing penalties must be separately ledgered and reportable if applied.
- Withdrawals and forced withdrawals must be separately ledgered/reportable as finalized once admin records execution; later bank failures or returns are handled offline and may be attached as notes/documents.
- Borrower repayments allocate to fees, penalties, then loan interest and principal according to the current schedule; borrower-side penalties are configurable but 0/inactive at launch.
- Normal contractual interest stops accruing on the official default declaration date.
- Default/penalty interest starts accruing from the official default declaration date instead of regular interest only if provided in the relevant loan/project agreement or project recovery configuration and must be reported separately from contractual interest.
- Recovery records must separately show gross recovered amount, externally deducted legal/recovery costs, third-party recovery costs declared at recovery time, Garanta recovery fee decision/amount, net amount received by Garanta, net amount available for waterfall allocation, lender distributions, recovery category split, and recovery rounding differences.
- Recovery records must store the project recovery waterfall version/configuration used for the calculation.
- Externally deducted legal/recovery costs are not treated as Garanta revenue by default. They are stored as project-linked recovery cost metadata/accounting categories unless the accountant maps a specific event differently.
- Garanta recovery fee, when applied, is Garanta revenue and must be separately ledgered/exportable from lender principal/interest recovery flows.
- Recovery distributions are client-money/settlement flows and are not Garanta revenue.
- Late fees are not charged at launch.
- Partial and early repayments must update outstanding principal, interest expectations, investor distribution records, and schedule versions.
- Each loan is accounted for in a single currency.
- Investor balances and collection accounts are separated by enabled currency at launch: CHF and EUR.
- Swiss accounting/reporting must support CHF reporting and currency-specific subledgers.
- Base reporting currency is CHF.
- Platform reports currency-specific ledgers and does not perform accounting FX revaluation at launch; revaluation is handled by the accountant/accounting system.
- No invoices are generated by the platform at launch.
- Account statements and finance exports replace invoice outputs in v1.
- Annual participant tax information statements are generated from the complete annual account statement for the participant and the underlying transaction-level ledger.
- Tax-relevant summaries separate income/cost items from principal and balance movements.
- Tax-relevant amounts and tax metadata are stored and exportable, but VAT/reverse-charge/withholding/other tax calculations are not hardcoded by the platform at launch.
- Corrections are reversing entries, not destructive edits.
- Admin and superadmin can approve finance corrections at launch.
- Month-end reports are reproducible, but prior periods are not locked at launch.

## Lender Outputs

- Transaction statement.
- Annual statement.
- Annual tax information statement.
- Calendar-year tax information statement ending December 31 by default.
- Interest received or credited.
- Principal outstanding.
- Platform/lender fees paid.
- Balance movements by currency.
- Currency-exchange activity and fees.
- Balance ageing penalties, if any.
- Losses after final default resolution, if advisor-approved.
- Recoveries.
- Recovery category split: principal, contractual interest until default date, default/penalty interest after default date if applicable, third-party recovery costs, Garanta recovery fee if applied, other penalties/costs, and rounding differences.
- Secondary-market results.
- Information-only deposits, withdrawals, funded principal, repaid principal, and balance movements.
- Tax forms if required by jurisdiction.

## Borrower Outputs

- Loan statement.
- Repayment schedule.
- Payment receipt.
- Interest paid statement.
- Account statement PDF generated by admin.
- Account statement CSV generated by admin.
- Annual tax information statement PDF generated by admin.
- Annual tax information statement CSV generated by admin.
- Interest paid.
- Garanta fees, including borrower success fee where applicable.
- Administrative costs, FX costs, penalties, and recovery costs where applicable.
- Contractual interest and default/penalty interest shown separately where applicable.
- Information-only principal received, principal repaid, outstanding principal, drawdowns, and repayment principal.
- Default/recovery cost statement.

## Garanta Internal Outputs

- Annual internal account statement.
- Annual internal tax information report.
- Platform revenue summary by type.
- Accrued revenue report for arbitrary date ranges.
- Accrued revenue/commission held in collection accounts by currency.
- Garanta out and Garanta in transfer report.
- Realized FX gain/loss report by currency and period.
- Bank-ledger reconciliation report by currency.
- Platform cost summary where recorded in the platform.
- Client-money/settlement movement summary separated from Garanta income and costs.
- Supporting detail by currency, event type, counterparty, loan/project, ledger event, evidence reference, and correction/reversal history.

## Dependencies

- Payments, Ledger, Custody, and Reconciliation.
- Loan Servicing and Repayments.
- Marketplace, Investments, and Allocations.
- Reporting, Analytics, and Regulatory Exports.

## Q/A Backlog

1. Answered by FIN-DEC-002: Garanta uses Bexio as its Swiss accounting software.
2. Answered by FIN-DEC-002: the platform ledger is the immutable transaction-level operational source of truth, and Bexio receives a configurable monthly accounting export; final chart of accounts, import layout, and tax-code mapping remain non-blocking Garanta/accountant TODOs.
3. Answered by PAY-DEC-006: borrower success fee of 2% to 4% after successful full raise or admin-approved partial close, deducted from disbursement and stored for accounting/net-revenue reporting; lender payment fee configurable per installment distribution, launch value 0.
4. Answered by FIN-DEC-005: platform stores tax-relevant amounts and tax metadata; VAT/reverse-charge/withholding/other tax calculations are not hardcoded at launch unless later legal/accounting review requires them.
5. Answered by FIN-DEC-001: annual tax information statements are generated for lenders, borrowers, and Garanta internal finance from the complete annual account statement and immutable transaction-level ledger; tax summaries separate income/cost items from principal/balance movements and are informational only, not tax advice.
6. Answered by FIN-DEC-004: no invoices are generated at launch; platform generates account statements, annual participant tax information statements, and finance reports.
7. Answered by FIN-DEC-006: no formal close/period lock at launch; month-end reports remain reproducible.
8. Answered by FIN-DEC-006: admin or superadmin can approve finance corrections.
9. Updated by FIN-DEC-002 and FIN-DEC-003: Swiss accounting is required through Bexio, base currency is CHF, and currency-specific ledgers are maintained; final Bexio chart mapping remains a non-blocking Garanta/accountant TODO.
10. Answered by FIN-DEC-003 and PAY-DEC-020/PAY-DEC-024: platform reports currency-specific ledgers, FX activity, FX deltas, and external execution evidence; accounting FX revaluation is handled by the accountant/accounting system.
11. Answered by FIN-DEC-004: borrower account statements and annual tax information statements are admin-generated as PDF and CSV because borrowers have no portal.
12. Answered by FIN-DEC-007: bank reconciliation compares bank-stated balances with investor balances, Garanta accrued revenue/commission balances, suspense/unmatched cash, and pending/exception balances by currency; accrued revenue reports are available for arbitrary periods.
13. Answered by FIN-DEC-008: external FX settlement differences are calculated as Garanta-owned realized FX gain/loss or residual delta and do not retroactively change investor FX balances.
