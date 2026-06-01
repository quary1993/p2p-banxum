# Borrower and Entity Records

Status: Draft. Updated with operating-model, identity, KYC/KYB approval gating, origination, servicing, and document decisions through 2026-05-29.

## Purpose

Define how borrower entity records are represented in the platform. Borrowers do not have portal accounts and cannot log in. Borrower onboarding, KYB, document collection, negotiation, contracting coordination, and communication are handled off-platform between Garanta and the borrower, then recorded by admin where needed.

## Scope

- Admin-created borrower entity profiles.
- Off-platform KYB/AML evidence storage.
- Beneficial owner and authorized signatory data recorded by admin where required.
- Admin-created complete loan records.
- Admin-uploaded documents where available.
- Offline credit result or evidence recording where needed.
- Contracting and signing tracked by admin.
- Drawdown and repayment monitoring visible to admin.
- Post-funding information requests tracked operationally.

## Entity Types

Launch borrowers are legal entities only. Natural-person borrowers are out of scope for launch.

Potential launch entity types to confirm:

- Swiss company.
- Non-Swiss company.
- Real estate project company, where relevant.
- Special purpose vehicle.

Future or excluded launch types:

- Sole proprietor.
- Individual borrower.
- Broker/introducer-submitted borrower.

## Launch Operating Model

Borrower-facing self-service and borrower portal access are out of scope. The platform is the admin record system for borrower data and offline Garanta-borrower operations.

### Admin Entity Creation

1. Admin creates borrower entity.
2. Admin enters registration, address, ownership, director, and signatory data.
3. Admin uploads off-platform KYB/AML evidence and borrower documents.
4. Admin sets compliance status.
5. Borrower remains blocked from platform transactions until KYB/AML is approved and no compliance hold applies.
6. Admin creates loan records under the borrower entity.

### Admin Loan Record Creation

1. Admin confirms borrower KYB/AML approval, borrower onboarding, and offline credit review are complete.
2. Admin selects loan purpose/product.
3. Admin enters principal amount, currency, term, interest rate, repayment type, repayment schedule, use of funds, collateral type, collateral value, optional collateral description, and selected borrower disclosure fields.
4. Platform calculates LTV and validates mandatory fields and broad sanity checks.
5. Admin uploads optional documents or evidence where useful.
6. Loan record is saved only if all required fields are complete.
7. Admin publishes the listing when operationally ready.

### Funded Loan Management

1. Admin views loan status and repayment schedule.
2. Admin records drawdown confirmation.
3. Admin uploads generic monitoring documents received off-platform.
4. Admin tracks reminders, borrower communication, and servicing exceptions.

## Required Data

Mandatory borrower/entity fields:

- Entity legal name.
- Year founded.

Optional borrower/entity fields:

- Assets.
- Liabilities.
- Revenue last year.
- Profit last year.
- Presentation PDF.
- Financials PDF.
- Extra generic borrower documents uploaded and named by admin.

Operational/entity fields where admin has them:

- Registration number.
- Registered address.
- Operating address.
- Industry and activity.
- Ownership structure.
- Beneficial owners.
- Directors/officers.
- Authorized signatories.
- Bank account details.

Mandatory loan/collateral fields:

- Principal amount.
- Currency.
- Term.
- Interest rate.
- Repayment type.
- Repayment schedule.
- Loan purpose and use of funds.
- Collateral/backing type.
- Collateral value.

Derived loan/collateral metrics:

- Calculated LTV.

Optional loan/collateral fields:

- Collateral free-text description.

Mandatory borrower display fields for launch are entity name and year founded. Assets, liabilities, revenue last year, profit last year, presentation PDF, financials PDF, and admin-named generic borrower documents are optional and should be hidden from the investor/client portal when not declared or published by admin.

## Controls

- Admin cannot save the loan until mandatory fields are complete.
- Borrower must be a supported legal entity before a loan record is saved or published.
- Borrower cannot publish to marketplace directly and has no portal access.
- Off-platform compliance status must be acceptable before listing.
- KYB/AML approval is required before loan publication, funding close, disbursement, repayment processing, or any other platform transaction involving the borrower.
- Off-platform credit review must be complete before admin saves or publishes the loan.
- Signatory authority must be verified before contract signature.
- Bank account changes require elevated verification and approval.
- All uploaded files are malware-scanned and access-controlled.

## Dependencies

- Identity, KYC, KYB, and AML.
- Origination, Credit Review, and Underwriting.
- Documents, Contracting, and E-Signature.
- Payments, Ledger, Custody, and Reconciliation.
- Communications and Notifications.

## Q/A Backlog

1. Partly answered by Operating Model DEC-007: legal entities only; exact legal forms and jurisdictions still need definition.
2. Updated by KYC-DEC-001, KYC-DEC-002, and KYC-DEC-008: borrowers are entered and managed by admin; no borrower self-service accounts; borrower KYB/AML approval is required before platform transactions involving the entity.
3. Partly answered by DOC-DEC-004 and DOC-DEC-006: borrower-side documents are optional admin uploads in v1; borrower presentation, financial PDF, and admin-named generic documents can be investor-visible when uploaded/published.
4. Answered by MKT-DEC-012: no broker/introducer submission workflow in v1; Garanta admins enter borrower/loan opportunities directly.
5. Answered: borrowers cannot see loan progress in a portal; admin tracks it internally.
6. Answered: borrowers cannot negotiate offers in a portal; negotiations are off-platform and recorded by admin.
7. Answered by origination/admin model: admin can manage multiple loans under one borrower entity.
8. Answered by SERV-DEC-010/RISK-DEC-001/RISK-DEC-003: no structured borrower post-funding reporting workflow is required in v1; admin may store generic notes/documents from offline borrower handling.
