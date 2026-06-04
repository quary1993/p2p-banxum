# Admin TODO: Garanta Business, Legal, Accounting, and Operational Decisions

Status: Working list for Garanta admins, management, legal/compliance advisors, finance, and operations.
Last updated: 2026-06-04.

This file is for non-technical Garanta stakeholders. It explains what business, legal, accounting, operational, and compliance decisions are still needed.

Blocking means engineering cannot complete the named module beyond generic defaults, mocks, or placeholders until Garanta provides the information. Non-blocking means implementation can continue, but the item must be closed before production launch, before a specific workflow is enabled, or before operational polish is complete.

## Blocking

### Manual Legal-Entity Lender Investment Workflow

Blocks: admin-created/manual investment flow for legal-entity lenders.

What Garanta must provide:

- Which admin evidence fields are required when an admin manually records a legal-entity lender investment.
- Whether uploaded evidence is mandatory or optional.
- Which status should be assigned before and after admin confirmation.
- Whether manual investments use the same order states as self-service investments.
- Whether the single legal-entity lender representative login is enabled by default or case by case.

Why this is needed:

Legal-entity lenders can be operated off-platform. The admin module needs a precise workflow so manually entered investments produce correct ledger, holding, document, and audit records.

## Non-Blocking

### FX Business Configuration Refinement

Needed before production FX is enabled, but no longer blocking for implementation.

Resolved baseline:

- FX is an auxiliary settlement function for Garanta, not a trading, investment, or speculative function.
- No minimum exchange amount applies at launch.
- Launch FX pairs are CHF/EUR and EUR/CHF only. More currency pairs can be added later through configuration.
- A maximum conversion limit applies. Launch value is CHF 100,000 per investor per day or equivalent in another enabled currency, configurable by admin with audit trail.
- FX rates used in the platform come from Yahoo Finance, subject to the documented sanity checks.
- The previous-day-average sanity check uses the same provider.
- FX values are stored in the database with at least 6 decimal places for rate/intermediate calculation precision.
- User-facing website balances and normal amounts show 2 decimals.
- During FX quote/confirmation, the investor may see exchange details with 4 decimals before confirming.
- Half-up rounding is used.
- No unhedged/exposure alerts are required at launch.
- After external FX execution, admin records the bank operation and declares final realized amounts. The platform infers the actual conversion rate including all fees/costs from those declared amounts.

What Garanta/bank/accountant may still refine:

- Final Yahoo Finance API/access method and legal/terms-of-use confirmation.
- Final bank statement/export evidence fields for external FX settlement.
- Final accounting labels and Bexio mapping for realized FX gain/loss and execution costs.

Why this is non-blocking:

Engineering has implemented the backend foundation for the FX module with the resolved launch pairs, limits, mock-provider adapter boundary, rounding/display rules, same-provider sanity checks, no exposure-alert requirement, external settlement declaration, and realized residual reporting. Remaining items refine provider access, evidence labels, and accounting export mapping before production operations.

### Manual Bank Operation Declaration and Reconciliation Evidence Refinement

Needed before production finance operations are finalized, but no longer blocking for implementation.

Resolved baseline:

- Admin declares all launch bank operations manually.
- Supported bank-operation types are:
  - lender deposit;
  - lender withdrawal;
  - borrower loan disbursement / initial borrower loan payment;
  - borrower repayment;
  - Garanta out, meaning transfer of accrued Garanta commissions or other Garanta-owned amounts from collection/settlement accounts to Garanta operating accounts;
  - Garanta in, reserved for future cases where Garanta funds defaults, guaranteed loans, or other Garanta-funded support;
  - currency exchange external settlement.
- The purpose of declaring bank operations is to reconcile bank/PSP/EMI statements against the platform ledger at any point where no pending bank operation remains open.
- When all due bank operations are declared and no suspense/unmatched/pending operation exists, the collection-account bank balance by currency should equal the platform ledger sum of investor balances and Garanta-owned accrued commissions/revenue still held in that collection account.
- The platform must provide a reconciliation view that compares bank-stated balances with ledger-stated balances by currency and highlights differences.
- Currency exchange is first executed instantly inside the platform for users. At end of day or beginning of next day, admin checks the platform FX report, performs the external FX needed to match user exchanges, and declares the external execution rate including fees.
- After admin declares the external FX settlement, the platform calculates realized FX gain/loss or surplus/deficit by currency compared with the internal user FX events.
- Garanta accrued revenue reports must be available for arbitrary date ranges.

What Garanta/bank/accountant may still refine:

- Exact bank statement fields and labels from the selected bank or PSP.
- Whether evidence upload is mandatory or optional for each bank-operation type.
- Final file formats for statement exports/imports, if any.
- Final usable-IBAN validation rules and forced-withdrawal evidence policy.
- Final accountant-approved labels for realized FX gain/loss, accrued commissions, and bank reconciliation difference reports.

Why this is non-blocking:

Engineering can continue implementing manual bank-operation declaration, generic evidence attachment, ledger-bank reconciliation, accrued revenue reporting, and production refinements. The FX external settlement declaration and realized residual report backend foundation is already implemented; bank-specific file layouts and final accounting labels can be configured before production operations.

### KYC/KYB/AML Evidence Storage Legal Confirmation

Needed before production onboarding and transaction activation.

Resolved baseline:

- All KYC/KYB/AML checks are performed through external providers, with Didit as the selected launch provider.
- Garanta must also store locally the full KYC/KYB/AML evidence required for regulatory, audit, VQF/SRO, bank/payment partner, and internal compliance purposes.
- All relevant KYC/AML data and documents must be stored on Garanta-controlled infrastructure located in Switzerland.
- KYC/AML files, KYB files, reports, decisions, audit logs, webhook payloads where legally/technically possible, and related evidence have a minimum retention period of 10 years, subject to final legal/compliance confirmation.
- The platform stores provider identifiers, verification report references, downloaded report metadata, final verification status, risk classification, detected flags, decision date, approving/rejecting AML officer where manual review is required, and links/references to all supporting documents.
- Internal Garanta statuses include pending, approved, declined, manual review, high risk, sanctions hit, PEP hit, adverse media hit, expired, and re-verification required.
- Sanctions hits and confirmed identity/document fraud block onboarding.
- PEP, high-risk, adverse media, unclear ownership, inconsistent documentation, and other non-standard cases route to manual AML review and are not automatically approved.
- Raw provider webhook payloads and full provider reports are retained where legally and technically possible.
- Immutable audit logs must show who reviewed, approved, rejected, reopened, or updated a KYC/KYB file.
- The platform must support evidence export packages for VQF/SRO, auditors, banks, payment partners, and internal compliance reviews.
- KYC/KYB approval is required before any lender or borrower can perform platform transactions.

What Garanta/legal/compliance may still refine:

- Final legal confirmation of exact retention period and whether any KYC/KYB/AML evidence must be retained beyond 10 years.
- Final Didit workflow names, event names, and provider-specific status mapping once the production Didit workflow is configured.
- Final AML officer role titles and manual review checklist wording.
- Whether the launch manual-review reason-code list needs any Garanta-specific additions or renaming before production operations. The current generic list covers PEP, high-risk, adverse-media, sanctions, provider-decline, inconclusive provider result, document/identity issue, re-verification, off-platform review, admin correction, and other.
- Final export package manifest layout and recipient-specific redaction rules.

Why this is non-blocking:

Engineering can implement the status model, Swiss evidence storage boundary, 10-year minimum retention, manual AML review workflow, audit logging, and evidence package exports now. Remaining items refine legal policy, provider-specific configuration, and export presentation.

### Recovery Allocation Report Wording and Accounting Mapping

Needed before production recovery/write-off reports are finalized.

Resolved baseline:

- Recovery allocation applies to amounts recovered from projects/loans in default or recovery.
- Each loan/project supports a configurable recovery waterfall. Unless otherwise defined in the project documentation, the default waterfall is external recovery/legal costs, platform-approved recovery costs including the applied Garanta recovery fee, principal, contractual interest accrued until default, default/penalty interest, and other penalties/costs.
- Project recovery configuration includes default/penalty interest percentage, Garanta percentage recovery fee, and the recovery waterfall order/version.
- If a payment/installment is recorded for a defaulted loan, admin must declare any third-party recovery costs and choose whether the Garanta recovery fee applies to that payment.
- Lender-facing recovery buckets are allocated pro rata to lenders holding participations in the relevant project based on the current principal balance of each holding at the time of the recovery event, unless the project agreement defines a different allocation method.
- The platform must separately show gross recovered amount, externally deducted legal/recovery costs, third-party recovery costs declared at recovery time, Garanta recovery fee if applied, net amount received by Garanta, net amount available for waterfall allocation, and net amount distributed to each lender.
- Normal contractual interest stops accruing on the official default declaration date.
- Default/penalty interest starts accruing from the official default declaration date instead of regular interest only if provided in the relevant loan/project agreement or project recovery configuration, and it must be calculated and reported separately from normal contractual interest.
- Amounts recovered after default may include principal, contractual interest accrued until default date, default/penalty interest, third-party recovery costs, Garanta recovery fee, penalties, and costs. These categories must be classified separately in the ledger and lender reports.
- Lender recovery distributions use currency minor-unit rounding with deterministic calculation. Rounding differences are recorded separately as recovery rounding differences, not silently hidden.
- Each recovery payment must generate ledger entries, a recovery/write-off report, and a notification to affected lenders.

What Garanta/accountant/legal may still refine:

- Final wording of lender notifications for recovered payments.
- Final PDF/CSV column labels for gross recovery, deducted costs, recovery fee, net received, waterfall allocation, lender allocation, and rounding difference.
- Final Bexio/accounting mapping for externally deducted legal/recovery costs, third-party recovery costs, Garanta recovery fee revenue, and recovery rounding differences.
- Final legal wording for default/penalty interest disclosure if activated in a loan/project agreement.

Why this is non-blocking:

Engineering can implement deterministic recovery allocation, interest cutoff, separate recovery categories, reports, ledger entries, and notifications now. Remaining items refine wording and accountant-approved export mapping.

### Write-Off Loss Recognition and Recovery Reconciliation Policy

Needed before the future loss-recognition settlement workflow, investor loss reporting, and final write-off/recovery tax statement logic are enabled.

Current implementation:

- Write-off records immutable evidence, component amounts, reason, notes, and supporting reference, then moves the loan to `written_off`.
- Write-off does not currently close investor holdings, reduce holding principal, or post investor loss ledger entries.
- Recovery payments recorded after default or write-off can reduce current holding principal and credit investors with recovered amounts.
- This means write-off evidence, remaining holding principal, cumulative recoveries, investor losses, and later tax/reporting treatment must be reconciled by a future loss-recognition workflow.

What Garanta/accountant/legal must decide:

- Whether investors recognize a loss at the write-off date, only when the recovery process is finally closed, or through a two-step model where write-off records an expected loss and later recoveries offset that loss.
- Whether write-off should immediately close or loss-adjust holdings, or whether holdings remain open until final recovery closure.
- Which ledger entries are required for investor loss recognition and whether those entries are informational, tax-relevant, or both.
- How later recoveries of written-off amounts should be reported against earlier write-off/loss evidence.
- Required investor-facing wording for write-off, later recovery, and any final loss/recovery statement.

Why this is non-blocking:

The current backend correctly records write-off evidence and recovery distributions without losing money conservation. The final loss-recognition/accounting policy is needed before building the future settlement/reporting workflow that turns write-off evidence into final investor loss treatment.

### Fully Recovered Impaired Loan Terminal Status

Needed before the future recovery-closure workflow, investor portfolio wording for fully recovered defaulted or written-off loans, and final recovery/write-off reports are finalized.

Current implementation:

- Recovery payments reduce holding principal where recovered principal is allocated.
- A loan can remain `defaulted` or `written_off` even if recovery payments reduce all affected holdings to zero.
- The platform does not automatically move such a loan to a separate `recovered`, `resolved`, or `closed after recovery` status.

What Garanta must decide:

- Whether a fully recovered impaired loan should remain in its historical impairment status (`defaulted` or `written_off`) or move to a new terminal status such as `recovered`, `resolved`, or `closed after recovery`.
- Which status wording investors should see in their portfolio and historical statements.
- Which status accounting, tax, and recovery reports should use.
- Whether this transition should happen automatically when all holding principal reaches zero, or manually after admin confirms the legal/recovery file is complete.

Why this is non-blocking:

Current recovery payments are correctly recorded and reported while preserving the impairment status. The terminal-status decision should be made before implementing a dedicated recovery-closure workflow or relying on a final status in investor/accounting reports.

### Privacy Closure and Reversible Pseudonymization Policy

Needed before production privacy operations are finalized.

Resolved baseline:

- Account closure remains an admin workflow after a support/email request and is allowed only when the account is clean/empty under the accounts module rules.
- At account closure time, admin can select a checkbox to run the privacy anonymization workflow.
- The v1 privacy anonymization workflow is reversible pseudonymization, not irreversible deletion/anonymization.
- Direct identifying profile fields are encrypted/pseudonymized. This includes name, email, and KYC/KYB/AML structured fields that would allow a third party to directly identify the user.
- Financial records remain intact. Ledger entries, balances, investments, repayments, withdrawals, reports, tax records, audit records, payment evidence, bank/payment references, contracts, generated documents, uploaded documents, KYC/KYB/AML evidence, and other retained documents are not deleted or destructively modified.
- Documents remain available as retained evidence according to normal access controls and retention rules. If documents contain personal data, access is restricted rather than deleting the document.
- The workflow is reversible through asymmetric encryption: the platform stores or can access only the public encryption key through environment/configuration/database settings, while the private decryption key remains offline and outside the application.
- Restoring direct identifiers requires an offline key-controlled process. Nothing required for financial, legal, tax, audit, KYC/KYB/AML, or regulatory purposes may be lost.
- Admin can approve/run the closure and reversible pseudonymization action at launch.
- Closed-user document requests are handled operationally by email/support outside the software workflow; no special closed-user portal/request feature is required.

What Garanta/legal/technology may still refine:

- Final closure reason-code list.
- Offline private-key custody procedure, including who holds the key, how dual control is handled if desired, and how a re-identification/decryption event is approved and logged.
- Final list of direct identifier fields in each table once the implementation data model exists.
- Final wording used in admin UI so staff understand this is reversible pseudonymization, not destructive anonymization.

Why this is non-blocking:

Engineering can implement closure, login restriction, reversible encrypted direct identifiers, intact financial/document retention, admin checkbox workflow, and audit logging now. Remaining items refine operations, wording, and key custody.

### Secondary-Market Legal Disclosure Wording and Minimum Fee Configuration

Needed before production secondary-market launch.

Resolved baseline:

- Garanta's secondary market is a claim/participation transfer mechanism between users, structured as a bulletin board and not as a regulated trading venue.
- A seller may list only an entire holding. Partial sales, splitting a holding, or partial transfers of a single holding are not allowed.
- If a lender has multiple separate holdings in the same project from different investments or allocations, each holding may be listed separately, but each listing transfers that holding in full.
- A current/performing holding may be listed immediately after purchase or assignment. There is no minimum holding period.
- No separate minimum secondary-market transfer size applies. The listed holding only needs a positive current principal balance.
- The seller may set the sale price at a discount or premium to current principal balance. The sale price is defined as a percentage of the current principal balance.
- Accrued interest up to the settlement date is calculated separately, daily, pro rata, and belongs to the seller up to the transfer date when the loan/project is current/performing. Future interest after settlement belongs to the buyer.
- Maker/seller and taker/buyer fees are calculated on the agreed transfer price, excluding accrued interest.
- Fee rounding uses standard half-up rounding to the nearest cent/minor currency unit.
- Minimum maker/taker fee support remains configurable. Launch configuration may use no minimum fee unless Garanta sets one.
- Seller net proceeds equal transfer price plus accrued interest minus seller fee.
- Buyer total cost equals transfer price plus accrued interest plus buyer fee.
- The buyer/seller interface must display current principal balance of the transferred holding, sale price, discount or premium, accrued interest, seller fee, seller net proceeds, buyer fee, and buyer total cost.
- Holdings related to current/performing loans/projects may be listed automatically after system checks.
- If a loan/project is late, overdue, restructured, under observation, in default, in recovery, under legal enforcement, subject to a payment incident, or otherwise not normal performing, the seller may only submit a listing request. The listing becomes visible only after explicit Garanta admin approval.
- Admin approval for a non-standard listing must be audit logged with approval date, approving admin, reason, and disclosure note.
- Buyers of approved non-standard listings must see a clear warning and confirm an additional risk acknowledgement before purchase.
- Non-standard listing pages must display loan status, days past due if applicable, recovery/default status, last payment date, and any public admin note.
- Garanta may reject or remove any non-standard listing at its discretion.
- Each completed secondary-market transfer must generate legal transfer evidence and accounting entries for Garanta secondary-market fees.

What Garanta/legal may still refine:

- Final legal wording confirming the bulletin-board positioning and not-regulated-trading-venue disclosure.
- Final secondary-market buyer and seller/listing checkbox wording.
- Final additional risk acknowledgement wording for non-standard listings.
- Whether any non-zero minimum maker/taker fee should be configured.
- Standard admin disclosure-note templates for late, overdue, default, recovery, legal enforcement, payment incident, or under-observation listings.

Why this is non-blocking:

Engineering can implement the full pricing, transfer, fee, audit, approval, and display model now. Remaining items are final legal copy, optional minimum-fee configuration, and operating templates.

### Annual Tax Information Statement Final Wording and Examples

Needed before production annual tax information statements are published or sent.

Resolved baseline:

- The module is not limited to a lender-only Swiss tax output. It is an Annual Tax Information Statements for Platform Participants module.
- The platform must generate a complete annual account statement for each involved party type:
  - lender.
  - borrower.
  - Garanta internal.
- The tax-relevant summary is automatically extracted from the same complete annual account statement and the same immutable transaction-level ledger used for accounting exports.
- The tax-relevant summary means income received/credited and costs incurred. Principal movements are separated and shown only for information or reconciliation, not as income.
- Statements are informational only and are not tax advice. Final tax treatment remains the responsibility of each party and its advisors.
- The annual period uses the calendar year by default, ending December 31.
- Reports show original transaction currency and currency-specific totals. CHF-equivalent fields should be configurable if Garanta's accountant/tax advisors later require them for specific outputs.

Default lender tax-summary sections:

- Interest received or credited.
- Platform/lender fees paid.
- FX costs and FX fees.
- Potential losses and write-offs.
- Recoveries.
- Secondary-market gains/losses or results.
- Balance penalties, if any.
- Information-only principal movements: deposits, withdrawals, funded principal, repaid principal, current outstanding principal, and balance movements.

Default borrower tax-summary sections:

- Interest paid.
- Garanta fees, including borrower success fee where applicable.
- Administrative costs.
- FX costs, if applicable.
- Penalties or recovery costs, if applicable.
- Information-only principal movements: principal received, principal repaid, outstanding principal, and drawdown/repayment movements.

Default Garanta internal tax-summary sections:

- Platform revenue, including borrower success fees, secondary-market fees, FX margin/fees, balance penalties/handling fees if activated, and other Garanta fees.
- Garanta operating costs recorded in the platform.
- Settlement/client-money movements separated from Garanta income and costs.
- Supporting detail by currency, event type, counterparty, loan/project, and ledger/event reference.

What Garanta/accountant/legal may still refine:

- Final title and field labels for each participant statement.
- Final disclaimer wording.
- Whether any report needs CHF-equivalent totals in addition to original currency totals, and which exchange-rate source/rule to use.
- PDF/CSV layout examples for a simple lender, lender with secondary-market/FX activity, borrower, and Garanta internal report.
- Any jurisdiction-specific tax wording or sections.

Why this is non-blocking:

Engineering can implement the module from the transaction-level ledger using the participant-specific sections above. Final wording, examples, and optional CHF-equivalent rules can be configured before production publication.

### Bexio Chart, Import Layout, and Tax Mapping

Needed before production accounting exports are used for monthly accounting.

Resolved baseline:

- Garanta uses Bexio as its Swiss accounting software: https://www.bexio.com/en-CH/.
- The platform must keep a complete, immutable, transaction-level operational ledger as the source of truth.
- The Bexio export is a configurable monthly accounting export generated from the operational ledger.
- Each financial event must be stored individually with event ID, event type, booking date, value date, currency, gross amount, net amount, debit/credit mapping, lender reference, borrower reference, loan/project reference, bank/PSP reference, evidence reference, tax metadata, and reversal/correction history.
- Lender principal, borrower repayments, interest distributed to lenders, deposits, withdrawals, and recovery distributions are client-money/settlement flows. They must not be treated as Garanta revenue.
- Garanta P&L items include Garanta fees, FX margin, secondary-market fees, penalties/handling fees if activated, and operating costs.
- VAT and reverse-charge treatment will be finalized by the Swiss accountant. The platform should store configurable tax metadata and tax-category fields instead of hardcoding VAT logic.

What Garanta/accountant must still provide:

- Bexio chart of accounts and account codes to use for cash, investor liabilities, borrower receivables, settlement accounts, Garanta revenue categories, penalties/handling fees, operating costs, suspense, and correction accounts.
- Required Bexio journal import layout, for example CSV columns, delimiter, encoding, debit/credit format, tax code fields, reference fields, and whether imports are journal-line or document-style.
- Tax codes, VAT/reverse-charge handling, and any country-specific tax metadata that should appear in exports.
- Monthly import procedure: who imports the Bexio file, when it is imported, and who reviews reconciliation differences.
- Examples of monthly and yearly accounting reports that Garanta expects to reconcile against platform exports.
- Whether the monthly Bexio export should include transaction-level rows only, summarized rows only, or both.

Why this is non-blocking:

Engineering can implement the full operational ledger and configurable Bexio export mapping now. Final Bexio account codes, tax codes, and import layout are needed before using production accounting exports, but they no longer block the core ledger/accounting module design.

### Balance, FX, 30-Day, 60-Day, Forced Withdrawal, and Penalty Legal Review

Needed before production money movement.

What Garanta must confirm:

- Whether the investor balance and FX model remains within Garanta's authorization perimeter.
- Whether the 30-day reinvestment rule and 60-day withdrawal rule are legally worded correctly.
- Whether Garanta has authority to force withdrawal when a usable IBAN is known.
- Whether the day-60 penalty wording and env-configured amount/mechanics are legally acceptable.

Resolved legal input:

- FX conversion does not reset the 30/60-day balance-ageing timers.
- FX target-currency balance entries inherit ageing deadlines from the source balance entries consumed by the exchange.
- If one FX conversion consumes multiple source balance entries with different deadlines, v1 uses the earliest consumed investment and withdrawal deadlines for the resulting target-currency balance entry, while retaining full lineage to every consumed source entry.
- Day-60 balance penalties are env/deployment-configurable. Launch default is 1% simple daily penalty on the overdue source balance, applied by Europe/Zurich calendar day, capped at the remaining overdue source balance, never creating a negative balance, with a terminal `penalty_exhausted` source status if fully consumed.

Why this is non-blocking:

Implementation can proceed using the documented launch assumptions, but production use must wait for legal/compliance approval.

### Final Legal Templates and Transaction Documents

Needed before production launch and before real transactions are enabled.

What Garanta must create and upload:

- Platform registration terms.
- Primary-market investment terms.
- Secondary-market buyer terms.
- Secondary-market seller/listing terms.
- Risk disclosures.
- Final legally approved P2P lending risk acknowledgement/risk disclosure document.
- Primary loan claim assignment template.
- Secondary-market assignment/reassignment template.
- Partial-funding consent language.
- Listing-change notification wording.
- Checkbox labels and acknowledgement text for every acceptance flow.

Why this is non-blocking:

The documents/template module can be implemented with placeholder templates and versioning. Final approved legal content can be uploaded later through the superadmin template UI.

### Jurisdiction and Cross-Border Policy

Needed before broad production onboarding and marketing.

What Garanta must provide:

- Whether any EU/EEA countries should be blocked or routed to manual review.
- Cross-border marketing restrictions by jurisdiction.
- Exact legal forms and jurisdictions allowed for borrower legal entities.
- Exact legal forms and jurisdictions allowed for legal-entity lenders.
- Any public marketplace preview restrictions by jurisdiction.

Why this is non-blocking:

The platform can implement configurable country/jurisdiction controls with the current default of Switzerland plus EU/EEA for natural-person self-service lenders.

### Borrower and Loan Display Policy

Needed before final marketplace presentation.

What Garanta must provide:

- Whether investor-facing risk rating should show the full internal scale or simplified labels.
- Final formatting rules for borrower financial values.
- Which optional borrower documents should be visible to investors by default.
- Whether offline credit review files/memos are ever uploaded to the platform.
- Whether any additional collateral warnings are needed beyond current zero-value and above-principal warnings.
- Final mandatory loan save/publish checklist, if Garanta wants to change the documented launch checklist.

Why this is non-blocking:

The current plan already defines mandatory launch fields and hides optional fields when absent. These decisions refine display and policy, not the core implementation.

### Marketplace and Order Labels

Needed before final UI polish and support operations.

What Garanta must provide:

- Exact final status labels for investment orders.
- Reason codes for refunds.
- Reason codes for balance credits.
- Reason codes for partial allocations.
- Whether the 50 pending-order cap should remain global per investor or change to per loan/per currency.
- Tie-break behavior if multiple payments share the same bank value date and bank statement ordering is not enough.

Why this is non-blocking:

Implementation can start with documented defaults: 50 pending orders globally per investor, and tie-break by bank value date, statement/import order, then system timestamp.

### Risk Acknowledgement and Exposure Metrics

Needed before production launch and investor-facing final wording.

What Garanta must provide:

- Final approved generic P2P lending risk acknowledgement text.
- Whether exposure metrics should be shown only in the investor portfolio, only in reports, or both.
- Any preferred warning wording for high exposure to one borrower, country, sector, rating, maturity, or collateral type.

Why this is non-blocking:

V1 does not enforce hard concentration limits or a suitability questionnaire. The software can calculate exposure metrics and display generic warnings while final wording is prepared.

### Recovery Public Notes and Investor Communication Policy

Needed before operating defaults/recoveries at scale.

What Garanta must provide:

- Who may publish a public note on a late/default/recovery loan.
- Whether public notes remain visible after resolution.
- Whether public notes should trigger email alerts automatically, or only when admin chooses bulk email.
- Standard wording for late/default/recovery investor notifications, if desired.

Why this is non-blocking:

The platform can support public notes, internal notes, uploads, and optional emails. Final operating policy can be configured and refined later.

### Communications Policy and Marketing Consent

Needed before final production copy and marketing use.

What Garanta must provide:

- Marketing consent wording.
- Whether marketing consent is collected only during registration or also in user settings.
- Failed-email retry expectations if Garanta wants different values from implementation defaults.
- Bounce/suppression handling policy.
- Retention period for full sent email content if Garanta wants a fixed period instead of launch indefinite retention.

Why this is non-blocking:

Transactional email mechanics can be implemented with default retry rules and audited full-content storage. Marketing sending is future scope.

### Report Layouts and Redaction Rules

Needed before final report polish.

What Garanta must provide:

- PDF layout preferences.
- CSV delimiter and encoding preferences.
- ZIP evidence package manifest format.
- Filename conventions.
- Maximum export size expectations.
- Which reports require redacted and full versions.
- Whether any legally required reports must be materialized and retained, rather than regenerated on demand.
- Whether full/unredacted exports should remain available to all active admins at launch, or require an extra reason code, superadmin approval, dual control, or a narrower finance/compliance role.
- Whether generated CSV/PDF/ZIP artifacts should be stored in Garanta-controlled object storage at generation time, or whether returning the artifact to the admin plus storing immutable checksum/manifest evidence is enough for launch.

Why this is non-blocking:

The reporting module can be built export-first with reproducible PDF/CSV/ZIP reports. Current backend foundation defaults to redacted exports, audits full exports, stores immutable report-run metadata/checksums, and does not persist the CSV file itself. Exact layout, redaction, full-export governance, and artifact-storage requirements can be refined once sample reports exist.

### Document Delivery, Retention, and Template Operations

Needed before production document operations are finalized.

What Garanta must provide:

- Document retention periods by document type, if Garanta wants something more specific than launch indefinite retention.
- Whether generated transaction PDFs are sent as email attachments or delivered by secure link.
- Email/file size limits, if any.
- Whether regulator/auditor evidence packages must include materialized PDFs or whether reproducible generation from stored template/data is enough.
- Whether superadmin template publication requires offline legal approval evidence.
- Template rollback process: who can roll back, when, and what evidence is recorded.

Why this is non-blocking:

The document module can implement versioned templates, reproducible PDFs, and secure downloads with defaults. These decisions refine production operations and legal evidence handling.

### Finance Corrections, Restatements, and Optional Fee Policies

Needed before finance operations are fully polished.

What Garanta must provide:

- Finance correction reason codes.
- Whether reports should show restatement markers when corrected after generation.
- Lender payment fee activation rules if the fee is later set above 0.
- Balance ageing penalty tax/accounting treatment.
- VAT, reverse-charge, withholding, or country-specific tax flags if advisors require them.

Why this is non-blocking:

Launch values are already defined for most fees, and corrections can be implemented with generic audited reversal/correction records. These items refine accounting and reporting behavior.

### Account Lifecycle Operations

Needed before production support procedures are finalized.

What Garanta must provide:

- Admin account creation reason codes.
- Admin disable/re-enable reason codes.
- Admin role-change reason codes.
- Account closure reason codes.
- Support handling steps for account closure requests.
- Whether user-visible session/device management should be prioritized after launch.

Why this is non-blocking:

The platform can implement audited admin actions and account closure prerequisites. Reason-code refinements can be configuration/polish.

### Legal-Entity Lender Evidence Category Policy

Needed before final operational procedure and production compliance operations.

What Garanta must confirm:

- Final evidence categories for legal-entity lender KYB/AML files.
- Which evidence must be stored as structured fields, uploaded files, provider report references, or references to another Garanta-controlled Swiss evidence store.
- Which uploaded file categories are mandatory before KYB/AML approval can be recorded.
- Which uploaded file categories are optional supporting evidence.
- Whether borrower KYB/AML evidence categories should mirror legal-entity lender categories or use a separate checklist.

Why this is non-blocking:

The platform can implement a configurable evidence checklist and Swiss-controlled evidence storage now. Final category names and mandatory/optional flags can be refined before production onboarding.

### Future Borrower Penalties and Late Fees

Needed only if Garanta activates borrower-side penalties or late fees later.

What Garanta must provide:

- Penalty percentage or formula.
- Whether penalties differ by loan.
- Whether late fees are charged separately.
- Legal wording and accounting treatment.

Why this is non-blocking:

Launch borrower-side penalties and late fees are 0/inactive.

### Future/Postponed Product Scope

Not needed for v1 implementation.

Items:

- Auto-invest.
- Automated reinvestment.
- Collateral-specific recovery workflows.
- Rich collateral data models.
- Borrower portal.
- Borrower self-service.
- E-signature provider.
- Support-ticket system.
- BI/data warehouse.
- Public API.

Why this is non-blocking:

These items are explicitly future scope. The v1 design should stay extensible, but implementation should not wait for them.
