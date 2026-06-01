# Origination, Credit Review, and Underwriting

Status: Draft. Updated with operating-model, product, origination, and document decisions on 2026-05-20.

## Purpose

Define how offline-reviewed borrower loans are recorded, validated, priced, prepared for marketplace listing, and published.

## Scope

- Complete loan record intake.
- Admin document upload or reference where available.
- Selected borrower financial disclosure capture.
- Offline credit result recording.
- Manual risk rating.
- Collateral data recording.
- Fraud and compliance checks.
- Listing readiness validation.
- Audit trail.

## Decisions

### ORIG-DEC-001: Credit Review Location

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta operations / credit.

Decision:
Credit review is performed off-platform at launch. The platform stores admin-entered loan, borrower, collateral, repayment, and risk data after offline review.

Rationale:
The first version is an operational record and publication system, not a full credit workflow engine.

Follow-ups:
Define whether links/files from offline credit review should be uploaded later.

### ORIG-DEC-002: Credit Memo

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta operations / credit.

Decision:
A platform-generated credit memo is not required in v1. Admin-entered data is enough.

Rationale:
Credit work is handled offline, and launch only needs the structured data required to publish and service loans.

Follow-ups:
Consider credit memo upload/generation in a later release.

### ORIG-DEC-003: Borrower Profile Fields and Disclosure

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta product / operations.

Decision:
Borrower/entity profile fields for launch are:

- Entity name: mandatory.
- Year founded: mandatory.
- Assets: optional.
- Liabilities: optional.
- Revenue last year: optional.
- Profit last year: optional.
- Presentation PDF: optional.
- Financials PDF: optional.
- Extra generic borrower documents uploaded and named by admin: optional.

If an optional field or document is not declared by admin, the investor/client portal must not show the label or an empty value for that field.

Rationale:
Investor-facing disclosure should not display empty placeholders or imply missing data where Garanta chose not to publish it.

Follow-ups:
Define formatting for financial values and document visibility rules.

### ORIG-DEC-004: Manual Risk Rating

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta operations / credit.

Decision:
Admin manually sets the loan risk rating. The picker should include common credit-grade options and can be changed later.

Initial options:

- AAA.
- AA+.
- AA.
- AA-.
- A+.
- A.
- A-.
- BBB+.
- BBB.
- BBB-.
- BB+.
- BB.
- BB-.
- B+.
- B.
- B-.
- CCC.
- CC.
- C.
- D.
- Unrated.

Rationale:
Manual risk grades reflect offline credit judgment while preserving a familiar rating scale.

Follow-ups:
Confirm whether investor-facing labels use the same full scale or a simplified display.

### ORIG-DEC-005: Calculated LTV

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta product / operations / finance.

Decision:
Admin declares collateral value. The platform calculates LTV from loan principal and collateral value. Admin does not manually enter LTV in v1.

Formula:
`LTV = loan principal / collateral value * 100`.

If collateral value is 0, the platform issues a warning and does not show LTV. If collateral value is higher than principal, the platform issues a warning and still shows the calculated LTV.

Rationale:
Calculated LTV reduces input errors and keeps the metric consistent.

Follow-ups:
Define rounding and whether additional warnings apply when collateral value is below principal or outside expected policy ranges.

### ORIG-DEC-006: Marketplace Publication Completeness

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta product / operations.

Decision:
The platform assumes loan documents are signed and valid offline. Marketplace publication is blocked by incomplete structured loan information, including missing collateral type, missing collateral value, missing interest rate, missing repayment schedule, or any mandatory field.

Rationale:
Document execution is handled offline for v1, while the platform must ensure that published loans have the structured information required for investor display, calculation, payment, and servicing.

Follow-ups:
Define the final mandatory-field checklist for save and publish.

### ORIG-DEC-007: No Rejections or Incomplete Loan Records

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta product / operations.

Decision:
Rejected loans are not tracked in the platform at launch. Incomplete loans are not persisted. If a loan does not have all required fields, it is not saved in the system until admin enters/declares all required information.

Rationale:
The launch system should store only loans that are complete enough to operate.

Follow-ups:
Decide later whether draft loans, rejection history, and offline credit workflow tracking are needed.

## Launch Scope

Launch origination supports legal-entity borrowers only and mixed-purpose loans that are usually real-estate backed.

The workflow must separate loan purpose from collateral/backing. A loan may be real-estate backed even when the borrower use of funds is not real-estate purchase, development, or refinancing.

The workflow should be extensible to richer collateral/backing records later, but launch underwriting must support:

- Admin-recorded off-platform legal-entity KYB and beneficial ownership checks.
- Borrower KYB/AML approval before loan publication, funding close, disbursement, or other platform transaction activity.
- Collateral/backing type.
- Collateral value.
- Calculated LTV.
- Optional free-text collateral description.
- Optional/admin-uploaded borrower, generic borrower, and collateral documents where available.

## Origination Lifecycle

1. Offline borrower KYB/AML approval and credit review completed.
2. Admin enters complete borrower, loan, collateral, repayment, and risk data.
3. Platform validates mandatory fields and sanity checks.
4. Platform calculates LTV.
5. Loan is saved only if required information is complete.
6. Admin publishes listing when ready, provided borrower KYB/AML status remains approved and no compliance hold applies.

## Offline Credit Inputs and Optional Evidence

Credit review happens off-platform. The platform does not require the full credit file to save or publish a loan, unless a field is part of the structured mandatory checklist. Admin may store selected supporting files or references where useful.

- Financial statements.
- Bank statements.
- Existing debt schedule.
- Revenue and cash flow data.
- Tax records where required.
- Management information.
- Collateral/backing type.
- Collateral value.
- Calculated LTV.
- Optional collateral free-text description.
- Guarantees.
- Credit bureau or registry data if available.
- Sector/geography risk.
- Historical repayment behavior if repeat borrower.

## Risk Rating

Risk rating is set manually by admin based on offline credit review. The initial picker should include common credit-grade options from AAA through D plus Unrated.

## Approval Controls

- Platform approval workflow is minimal in v1 because credit review is offline.
- Admin-entered loan data is enough; no platform-generated credit memo is required.
- Launch credit approvals may be decided by admin under Operating Model DEC-010. Maker-checker is not required at launch but should be supportable later.
- Loans cannot be saved or listed until mandatory fields are complete.
- Marketplace publication is blocked by missing collateral type, missing collateral value, missing interest rate, missing repayment schedule, or any mandatory field.

## Dependencies

- Borrower and Entity Records.
- Identity, KYC, KYB, and AML.
- Loan Product Catalog and Configuration.
- Documents, Contracting, and E-Signature.
- Marketplace, Investments, and Allocations.

## Q/A Backlog

1. Answered by ORIG-DEC-001: credit review is done off-platform.
2. Answered by ORIG-DEC-004: risk rating is manually set by admin from common credit-grade options.
3. Answered by ORIG-DEC-003 and DOC-DEC-006: entity name and year founded are mandatory; assets, liabilities, revenue last year, profit last year, presentation PDF, financials PDF, and admin-named generic borrower documents are optional.
4. Answered by ORIG-DEC-001/ORIG-DEC-003: no external credit data source is required in-platform for launch; credit review happens offline and admin-entered borrower/loan data is sufficient.
5. Answered by Operating Model DEC-010/DEC-011: admin approves loans at launch; no two-person approval or authority-limit matrix is required in v1.
6. Answered by KYC-DEC-001/KYC-DEC-002 and ORIG-DEC-007: borrowers have no portal account and incomplete loans are not persisted.
7. Answered by ORIG-DEC-007: rejected loans are not tracked in the platform at launch.
8. Answered by ORIG-DEC-002: no credit memo required in v1.
9. Answered by ORIG-DEC-006: publication is blocked by incomplete structured loan information.
10. Answered by PROD-DEC-003 and ORIG-DEC-005: v1 captures collateral type, collateral value, and optional free-text description; LTV is calculated.
11. Partly answered by ORIG-DEC-005: collateral value 0 triggers a warning and hides LTV; collateral value higher than principal triggers a warning and still shows LTV. Other policy warnings remain open.
