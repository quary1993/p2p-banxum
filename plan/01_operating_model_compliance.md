# Operating Model and Compliance

Status: Draft. Updated with operating-model, marketplace, secondary-market bulletin-board, balance, and FX decisions through 2026-05-29.

## Purpose

Define the regulated operating model for BANXUM, including the role of Garanta Finanzgruppe AG, target jurisdictions, licensing assumptions, governance, compliance processes, and non-negotiable control requirements.

This module anchors every other module. Before implementation, the platform must know what business it is legally allowed to conduct, whose money it may hold, who can invest, which borrowers can be served, and what disclosures are required.

## Scope

- Operator identity and regulated perimeter.
- Target markets and user eligibility.
- Investor risk acknowledgement and disclosure rules; richer investor classification/suitability rules are future-ready only unless later required.
- Borrower/entity eligibility rules.
- AML/KYC/KYB operating obligations.
- Licensing and authorization dependencies.
- Governance, policies, committees, and scalable approval controls.
- Regulatory recordkeeping and audit support.
- Complaints, disputes, incident handling, and regulator-facing evidence.

## Working Regulatory Frame

Garanta Finanzgruppe AG is described as a FINMA-regulated Swiss entity. The exact license or authorization type must be captured in this module because it controls product scope.

FINMA public materials indicate that Swiss FinTech companies must assess anti-money laundering and authorization requirements before launching operations. FINMA also states that businesses are most likely subject to AMLA where client assets are paid into their accounts or where payment transactions, currency exchange, fiduciary services, asset management, lending, leasing, or issuing payment instruments are part of the model.

FINMA's FinTech licence materials state that the licence permits accepting public deposits up to CHF 100 million or crypto-based assets if the deposits are not invested and no interest is paid on them. The plans must not assume that this licence fits the P2P model without legal confirmation.

FINMA materials on self-regulatory organisations state that FINMA supervises recognised SROs in the context of combating money laundering and terrorist financing. The platform must therefore treat VQF affiliation as an AML/SRO supervision framework, not as prudential banking, securities, collective investment, or portfolio-management authorization.

## Decisions

### DEC-000: Canonical Platform Name and Legal Operator

Status: Accepted.
Date: 2026-06-01.
Owner: Garanta management / product / legal / technology.

Decision:
The platform/brand name is BANXUM. The legal operator remains Garanta Finanzgruppe AG.

BANXUM must be used for product/platform naming in user-facing portal copy, templates, generated documents, and internal documentation where the platform brand is intended. Garanta Finanzgruppe AG must be used where the legal operator, contracting party, regulatory entity, account holder, or required legal footer is intended.

Implementation must expose the platform name, legal operator name, support email, domains, and legal footer identities as configuration/template variables. Email templates, legal PDFs, account statements, tax statements, and notices must not hardcode these names directly.

Rationale:
The product brand and regulated legal operator are related but distinct. Keeping them configurable prevents template/legal-document drift and makes domain/branding changes safer.

### DEC-001: Regulatory Status and Permitted Activity Scope

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta management / compliance.

Decision:
Garanta Finanzgruppe AG is affiliated with VQF, a self-regulatory organization authorized by FINMA. The relevant activity scope includes loans, leasing, payment, crowdfunding, and crowdlending.

Garanta does not operate this platform under a banking licence, securities firm licence, collective investment scheme licence, or portfolio management licence.

Rationale:
The platform must be designed as a VQF/SRO-supervised financial intermediary activity and must avoid product structures or platform behavior that would require a banking, securities, fund, or portfolio management authorization unless separately approved.

Impacted modules:
Payments, Ledger, Custody, and Reconciliation; Marketplace, Investments, and Allocations; Loan Product Catalog and Configuration; Documents, Contracting, and E-Signature; Reporting, Analytics, and Regulatory Exports.

Follow-ups:
Confirm with Swiss counsel and compliance whether each launch product, marketing approach, and cross-border flow remains inside the approved activity perimeter.

### DEC-002: Investor Balances, Segregated Client Funds, and Holding Limits

Status: Accepted.
Date: 2026-05-20.
Owner: Garanta management / compliance / finance.

Decision:
Garanta will support investor balances on the website. Investors may hold balances in enabled currencies, starting with CHF and EUR. Deposits, borrower repayment/installment proceeds, secondary-market seller proceeds, refunds credited to balance, and FX proceeds can be credited to investor balances.

Client funds must be held in segregated settlement or collection accounts, must be non-interest-bearing, must not be used for Garanta's own account, and must be tracked in the platform ledger by investor, currency, source entry, received timestamp, and ageing deadline.

Every balance source entry is subject to a 30-day investment/reinvestment deadline and a 60-day absolute withdrawal deadline under the launch interpretation. The 60-day deadline is treated as regulatory/compliance-driven and non-extendable. Balances remaining after day 60 are subject to an env/deployment-configurable penalty policy. Launch default is 1% simple daily penalty on the overdue source balance, applied using Europe/Zurich calendar days, capped at the remaining overdue balance, and never creating a negative balance.

After day 30, the balance source becomes withdraw-only and cannot be used for investment/reinvestment. Currency exchange does not reset the 30/60-day ageing clocks and cannot restore investment eligibility. The target-currency source inherits ageing deadlines from the source balance entries consumed by the FX transaction, using the earliest consumed investment and withdrawal deadlines when multiple source entries are consumed in one exchange. After day 60, admin attempts forced withdrawal if a usable verified IBAN is known. If no usable IBAN is known, penalty mode freezes investor financial actions until a usable IBAN is declared, while preserving read-only access.

Rationale:
The updated product model requires multi-currency investor balances while preserving segregation from Garanta operating funds, non-interest treatment, source-level auditability, and hard ageing controls.

Impacted modules:
Payments, Ledger, Custody, and Reconciliation; Investor Portal; Marketplace, Investments, and Allocations; Accounting, Tax, and Finance Operations; Communications and Notifications; Security, Privacy, and Auditability.

Follow-ups:
Validate with Swiss counsel, compliance, VQF/SRO, bank/payment partners, and auditors whether the balance and FX model remains inside Garanta's authorization perimeter or requires additional authorisation, partner structure, disclosures, controls, or licensing. Define the exact bank account structure, payment reference model, reconciliation process, automated 30/60-day monitoring, penalty treatment, and escalation path.

### DEC-003: Launch Jurisdictions

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta management / compliance.

Decision:
Natural-person lenders may be accepted from Switzerland and EU/EEA countries at launch, subject to onboarding, KYC/AML checks, sanctions screening, tax considerations, marketing restrictions, and other applicable cross-border restrictions.

Legal-entity lenders are admin-created after off-platform onboarding and do not use a self-service country matrix in the platform at launch.

Borrowers do not have accounts or self-service onboarding. Borrower entities are created/administered by Garanta admin after offline onboarding, so borrower country eligibility is handled through offline policy and admin approval rather than a client-portal country matrix.

Rationale:
The launch perimeter for self-service natural-person lenders is Switzerland plus EU/EEA. Legal-entity lenders and borrowers are handled through admin/offline onboarding, so their jurisdiction checks are operational/compliance policy rather than client-portal registration rules.

Impacted modules:
Identity, KYC, KYB, and AML; Investor Portal; Borrower and Entity Records; Marketplace, Investments, and Allocations; Communications and Notifications; Reporting, Analytics, and Regulatory Exports.

Follow-ups:
Confirm any EU/EEA countries that should be blocked or routed to manual review due to marketing, tax, sanctions, operational, or legal constraints.

### DEC-004: Launch Investor Classes

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta management / compliance.

Decision:
Launch investors may include retail, professional, and institutional lenders.

For v1, the platform will not implement a detailed investor classification or suitability questionnaire as a blocking workflow. Investor protection is handled through KYC/AML gating, jurisdiction controls, generic P2P lending risk acknowledgements, transaction-specific terms acceptance, and investor-facing disclosures.

The platform should still store enough account/profile structure to support richer investor classification, suitability checks, or product restrictions later if legal/compliance policy requires them.

Rationale:
Launch should avoid overbuilding suitability mechanics before Garanta's final policy and legal documents are approved. The data model should remain ready for future classification-specific eligibility, disclosure, suitability, concentration-limit, and reporting rules.

Impacted modules:
Investor Portal; Accounts, Authentication, and Access Control; Marketplace, Investments, and Allocations; Loan Product Catalog and Configuration; Documents, Contracting, and E-Signature.

Follow-ups:
Draft and approve the final risk acknowledgement/risk disclosure document before production use. Revisit investor classification questions, evidence, limits, and investment restrictions if legal/compliance policy later requires them.

### DEC-005: Investor Legal Exposure

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta management / legal / compliance.

Decision:
Investors receive loan exposure through a pro-rata assignment of receivables or loan claims. The intended instrument is a loan claim assignment, not a note, bond, fund unit, collective investment product, or portfolio management product.

Rationale:
The marketplace, contracts, disclosures, ledger, reporting, and servicing model must be based on assigned loan claims and must avoid presenting investor exposure as a security, fund participation, managed portfolio, or deposit product unless separately approved.

Impacted modules:
Marketplace, Investments, and Allocations; Documents, Contracting, and E-Signature; Loan Servicing and Repayments; Accounting, Tax, and Finance Operations; Reporting, Analytics, and Regulatory Exports.

Follow-ups:
Draft the claim assignment agreement, investor disclosure language, transfer restrictions, servicing authority, and recovery allocation mechanics.

### DEC-006: Launch Loan Backing and Purpose Flexibility

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta management / product / credit.

Decision:
The launch lending focus is real-estate backed loans. This describes the collateral/security backing, not necessarily the borrower's use of funds. Loan purpose can be mixed and does not have to be real-estate acquisition, development, or refinancing. Most loans are expected to be backed by real estate collateral, with exceptions possible.

The product catalog and platform architecture must remain open and easily extendable to other collateral/backing types and loan purposes.

Rationale:
The platform must separate loan purpose from collateral/backing. Real estate collateral is the common backing for launch loans, but the loan purpose may be working capital, liquidity, refinancing, project finance, acquisition, or another admin-defined purpose.

Impacted modules:
Loan Product Catalog and Configuration; Origination, Credit Review, and Underwriting; Marketplace, Investments, and Allocations; Documents, Contracting, and E-Signature; Risk Monitoring, Collections, and Recoveries.

Follow-ups:
Define the collateral data model, valuation policy, loan-to-value constraints, required property/security documents, and allowed exception process for non-real-estate-backed loans.

### DEC-007: Launch Borrower Type

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta management / compliance.

Decision:
Launch borrowers are legal entities only. Natural-person borrowers are out of scope for launch.

Rationale:
Legal-entity borrowers simplify the first borrower perimeter and align launch operations around admin-managed entity records, off-platform KYB, beneficial ownership, signatory authority, and corporate documentation. Borrower relationship management, negotiation, KYB, contracting, and communications are kept offline between Garanta and the borrower and recorded by admin where needed.

Impacted modules:
Borrower and Entity Records; Identity, KYC, KYB, and AML; Origination, Credit Review, and Underwriting; Documents, Contracting, and E-Signature.

Follow-ups:
Define which legal-entity forms are accepted by jurisdiction and whether special purpose vehicles are allowed.

### DEC-008: Secondary Market

Status: Accepted.
Date: 2026-05-15. Updated 2026-05-29.
Owner: Garanta management / legal / product.

Decision:
The platform will include a secondary market for lender exits or transfers at launch. Garanta's secondary market is a claim/participation transfer mechanism between users, structured as a bulletin board and not as a regulated trading venue.

Sellers may list only an entire holding, not a fraction of a holding. If a lender has multiple separate holdings in the same project from different investments or allocations, each holding may be listed separately, but each listing transfers that holding in full. Splitting, partial sales, or partial transfers of a single holding are not allowed.

Sellers can set their sale price as a discount or premium percentage of the holding's current principal balance. Accrued interest up to settlement is calculated separately, daily, pro rata, and belongs to the seller when the loan/project is current/performing. Future interest after settlement belongs to the buyer.

Buyers pay from available balance or send purchase money to Garanta, Garanta deducts maker and taker secondary-market fees, updates assigned-claim ownership, and credits the seller net proceeds to the seller balance. Settlement should normally complete much faster than 60 days from receipt/reservation of buyer funds, with a maximum operational period of 60 days.

Only current/performing holdings may be listed automatically. Non-performing or otherwise non-standard holdings require a Garanta admin-approved listing request before becoming visible, plus clear buyer warning and additional acknowledgement.

Rationale:
Secondary market support affects the legal assignment structure, lender eligibility checks, settlement flows, tax/accounting treatment, servicing records, and investor disclosures.

Impacted modules:
Marketplace, Investments, and Allocations; Payments, Ledger, Custody, and Reconciliation; Documents, Contracting, and E-Signature; Investor Portal; Accounting, Tax, and Finance Operations; Reporting, Analytics, and Regulatory Exports.

Follow-ups:
Finalize legal wording for bulletin-board positioning, transfer documents, buyer/seller acknowledgements, and non-standard listing disclosures.

### DEC-009: Investor Risk Warnings

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta management / legal / compliance.

Decision:
Investor risk warnings will initially be documented generically for the industry and tailored later through a formal document or disclaimer. The warnings must fit a Swiss FINMA-regulated/SRO-supervised crowdlending context and the assigned-claim structure.

Rationale:
The platform needs explicit risk acknowledgement flows before investment, while final legal wording will be refined separately.

Impacted modules:
Investor Portal; Marketplace, Investments, and Allocations; Documents, Contracting, and E-Signature; Communications and Notifications.

Follow-ups:
Draft legal-approved risk warning and disclaimer templates, including real estate collateral risks, borrower default risk, illiquidity, secondary-market limitations, no guarantee of return, no deposit protection, platform risk, tax risk, and cross-border restrictions.

### DEC-010: Launch Admin Role Levels

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta management / operations.

Decision:
The admin portal will support two launch role levels: superadmin and admin.

Superadmin owns parametrizations and configuration-level administration. This includes product parameters, platform settings, system-level configurations, and other non-routine setup or control-plane changes.

Admin owns operational execution. Admin can approve loans, create and manage borrower entities, create and manage loans, confirm payments, handle onboarding exceptions, and perform the operational actions needed to run the platform.

Rationale:
The launch role model should be simple and clearly separate parametrization from operations. High-risk regulated actions still need explicit permission checks, audit logs, and reason codes. Maker-checker approval must be supportable as a future configurable control, but it is not required at launch.

Impacted modules:
Admin and Operations Portal; Accounts, Authentication, and Access Control; Security, Privacy, and Auditability; Payments, Ledger, Custody, and Reconciliation.

Follow-ups:
Define which parametrizations are superadmin-only and whether any emergency break-glass path is needed.

### DEC-011: Launch Approval Control Model

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta management / operations / compliance.

Decision:
No launch operation requires two sets of eyes or mandatory maker-checker approval. The platform must still be designed so maker-checker approval can be enabled later by action type, risk level, amount, product, role, jurisdiction, or workflow state without a structural redesign.

Rationale:
Launch operations should remain simple, while the system should be able to scale into stricter approval controls as volume, risk, staffing, or regulatory expectations increase.

Impacted modules:
Admin and Operations Portal; Accounts, Authentication, and Access Control; Payments, Ledger, Custody, and Reconciliation; Origination, Credit Review, and Underwriting; Security, Privacy, and Auditability.

Follow-ups:
Model action approval policies as configuration, with launch defaults set to single-actor approval. Define future maker-checker triggers separately.

### DEC-012: Currency Exchange Service

Status: Accepted.
Date: 2026-05-20.
Owner: Garanta management / compliance / finance / product.

Decision:
The platform will support investor currency exchange between enabled balance currencies. Launch currencies are CHF and EUR. Enabled currencies, FX fee, and reminder templates are superadmin-configurable. Balance penalty mechanics are deployment/env-configurable at launch.

The FX service is an auxiliary settlement function, not a trading or speculative feature. It uses Yahoo Finance as the launch market-rate source where legally and technically permitted and applies a platform fee. Launch default FX fee is 1.5%.

Launch FX pairs are CHF/EUR and EUR/CHF, with no minimum exchange amount and an initial CHF 100,000 per-investor daily maximum or equivalent configurable by admin. Admin must be able to query net FX deltas for any day or period so Garanta can execute external currency exchange at end of day or the beginning of the next day and avoid carrying currency risk as far as operationally possible.

Rationale:
Multi-currency balances require a controlled FX workflow, clear fee disclosure, accounting treatment, and operational risk monitoring.

### DEC-013: Authoritative Business Timezone and Day Counting

Status: Accepted.
Date: 2026-06-01.
Owner: Garanta management / operations / technology / compliance.

Decision:
The authoritative business timezone for BANXUM is Europe/Zurich.

All calendar-day business rules use Europe/Zurich local dates unless a module explicitly states otherwise. This includes 30-day investment/reinvestment deadlines, 60-day withdrawal/holding deadlines, balance reminders, day-60 penalty mode, loan funding deadlines, secondary-market operational deadlines, day-5 late status, day-16 default status, scheduled background jobs, report cutoffs, and admin dashboard day buckets.

Timestamps should still be stored in UTC with timezone-aware values. User-facing dates, business deadline calculations, scheduler cutoffs, and reports should render and evaluate using Europe/Zurich.

Rationale:
Using one authoritative business timezone prevents off-by-one errors that could trigger reminders, penalties, late statuses, defaults, or funding-deadline actions a day early or late.

Impacted modules:
Investor Portal; Payments, Ledger, Custody, and Reconciliation; Admin and Operations Portal; Accounting, Tax, and Finance Operations; Reporting, Analytics, and Regulatory Exports; Communications and Notifications.

Follow-ups:
Confirm legal/regulatory treatment of currency exchange, FX rate-provider licensing/terms, instant platform FX with end-of-day/next-morning external settlement, and the accounting/tax treatment of FX fee and deltas.

## Key Business Questions

- What exact FINMA authorization, licence, SRO affiliation, or supervisory regime applies to Garanta Finanzgruppe AG? Answered by DEC-001.
- Will Garanta Finanzgruppe AG hold client money, or will all funds remain with a regulated payment/custody partner? Answered by DEC-002.
- Will the platform operate only in Switzerland, or will it onboard EU, UK, US, or other international users? Answered by DEC-003: natural-person self-service lenders may register from Switzerland and EU/EEA, while legal-entity lenders and borrowers are admin/offline onboarded.
- Are investors retail, professional, institutional, or all three? Answered by DEC-004.
- Will borrowers be companies only, natural persons only, or both? Answered by DEC-007.
- Which loan categories are in launch scope? Answered by DEC-006: mixed-purpose loans, usually real-estate backed.
- Will the platform originate loans directly, broker loans, assign claims, issue notes, or operate another legal structure? Answered by DEC-005, DEC-006, and MKT-DEC-012: Garanta admins enter borrower/loan opportunities directly, and investor exposure is assigned loan claims.
- Will investors invest in loan fractions, claims, bonds, notes, funds, tokenized instruments, or contractual participations? Answered by DEC-005.
- Will there be a secondary market or transfer facility? Answered by DEC-008.
- Which disclosures must investors accept before each investment? Partly answered by DEC-009; final legal text still required.
- What regulator-facing reports and audit files must be produced? Answered by RPT-DEC-001/RPT-DEC-002/RPT-DEC-003: admin-only PDF/CSV reports and ZIP evidence packages are generated and shared offline.

## Operating Roles

- Board and executive management: accountable for strategy, risk appetite, regulatory compliance, and operational resilience.
- Compliance officer / MLRO: owns AML/KYC/KYB policies, suspicious activity escalation, sanctions handling, and regulatory reporting.
- Risk committee: approves credit policy, risk rating model, exposure metrics, any future concentration limits, and exception handling.
- Credit committee: approves credit policy and offline credit decisions according to delegated authorities, if used.
- Operations team: handles onboarding exceptions, document review, payments exceptions, and borrower/investor support.
- Finance team: owns accounting, reconciliation, fee/revenue tracking, account statements, tax exports, and reproducible month-end reporting.
- Technology/security team: owns platform availability, data protection, incident response, access control, and audit logs.
- External auditors/advisors: review regulatory controls, financial controls, security posture, and operating evidence.

## Required Policies

- AML/KYC/KYB policy.
- Sanctions and PEP policy.
- Customer risk rating policy.
- Investor risk acknowledgement and disclosure policy. Investor classification/suitability policy can be added later if required.
- Borrower eligibility and underwriting policy.
- Conflicts of interest policy.
- Marketplace disclosure policy.
- Client money and safeguarding policy.
- Investor balance, withdrawal, and ageing policy.
- Currency exchange and FX risk policy.
- Complaints and dispute resolution policy.
- Data protection and retention policy.
- Information security policy.
- Business continuity and incident response policy.
- Outsourcing/vendor risk policy.

## Core Controls

- No investment before the investor passes required onboarding, eligibility, and risk checks.
- No legal-entity lender financial activity before admin-recorded KYB/AML approval and no compliance hold.
- No borrower listing before entity verification, borrower KYB/AML approval, offline credit approval, mandatory structured loan information, and listing approval are complete.
- No funds release before the loan reaches funding conditions, contractual documents are effective, borrower KYB/AML remains approved, and payment reconciliation passes.
- Relevant KYC/KYB/AML evidence must be stored on Garanta-controlled infrastructure located in Switzerland and retained for at least 10 years, subject to final legal/compliance confirmation.
- Client funds and investor balances must remain segregated, non-interest-bearing, and unused for Garanta's own account.
- External bank movements must be admin-declared as bank operations at launch and reconciled against the platform ledger by currency.
- When no pending/suspense/exception items remain, collection-account bank balances must equal investor balances plus Garanta accrued commissions/revenue held in those accounts.
- Investor balance source entries must track received timestamp, 30-day investment/reinvestment deadline, 60-day withdrawal deadline, and penalty status.
- Investor balance source entries older than 30 days must be blocked from investment/reinvestment and shown with explicit user-facing errors.
- Balance deadline reminders must be sent on days 25, 46, 53, 58, 59, and 60, with day 60 announcing penalty application.
- Day-60 balances trigger forced withdrawal if a usable IBAN is known; missing usable IBAN triggers penalty mode and freezes financial actions until an IBAN is declared, while preserving read-only access.
- The 60-day holding limit is non-extendable in platform terms and operational handling.
- Loan/funding-campaign settlement funds must be transferred to the borrower, returned to investor balance, or withdrawn within the applicable funding period and never held beyond the permitted period without escalation/penalty handling.
- Currency exchange must use configured rates/fees, generate auditable ledger entries, inherit target-source ageing deadlines from consumed source balances, retain original source lineage, provide admin FX delta reporting, and calculate realized FX gain/loss after external settlement is declared.
- Launch borrower workflows must support legal entities only.
- Launch loan workflows must support mixed-purpose loans that are usually real-estate backed, without blocking future collateral/backing types.
- Secondary market transfers must re-check buyer eligibility, transfer restrictions, and assignment documentation before settlement.
- Investor investment flows must require risk acknowledgement before order submission.
- No launch operation requires maker-checker approval.
- Approval workflows must be designed so maker-checker can be enabled later by policy/configuration without redesign.
- Every lifecycle event must have an immutable audit trail.
- Compliance holds must override product flows.
- Admin permissions must be role-based, least-privilege, and periodically reviewed.
- Regulatory records must be exportable and retained according to policy.

## Dependencies

- Identity, KYC, KYB, and AML.
- Payments, Ledger, Custody, and Reconciliation.
- Documents, Contracting, and E-Signature.
- Reporting, Analytics, and Regulatory Exports.
- Security, Privacy, and Auditability.

## Deliverables

- Regulatory perimeter decision record.
- Market and user eligibility matrix.
- Product legal structure decision record.
- Compliance control matrix.
- Operating role and approval authority matrix.
- Required policy list and document owners.
- Go-live compliance checklist.

## Q/A Backlog

1. Answered by DEC-001: VQF/SRO affiliation for loans, leasing, payment, crowdfunding, and crowdlending; no banking, securities firm, collective investment scheme, or portfolio management licence.
2. Answered by DEC-002 and PAY-DEC-003/PAY-DEC-017: investor balances are in scope, held in segregated non-interest-bearing collection accounts with source-level ageing, 30-day reinvestment deadline, 60-day withdrawal deadline, and penalty handling.
3. Answered by DEC-003: natural-person lenders may be accepted from Switzerland and EU/EEA; legal-entity lenders and borrowers are admin/offline onboarded rather than governed by a self-service country matrix.
4. Answered by DEC-004: retail, professional, and institutional lenders may be supported.
5. Answered by DEC-005: pro-rata assignment of receivables/loan claims.
6. Answered by DEC-006: mixed-purpose loans, usually real-estate backed as collateral/security; exceptions and future collateral/backing types must be supported.
7. Partly answered by DEC-009: generic industry risk warning/disclaimer for Swiss FINMA-regulated/SRO-supervised crowdlending; final legal wording required.
8. Answered by DEC-010: two launch roles. Superadmin owns parametrizations/configuration. Admin owns operational execution, including loan approvals, entity and loan management, payment confirmations, onboarding exceptions, and other operational actions.
9. Answered by RPT-DEC-001/RPT-DEC-002/RPT-DEC-003: reporting is export-first at launch with industry-standard operational, finance/accounting-source, risk, balance/FX, investor, borrower, audit, and evidence reports in PDF/CSV plus ZIP evidence packages; admin-only exports are shared offline with external parties.
10. Answered by DEC-011: no maker-checker required at launch; design must remain scalable to support it later.
11. Answered by DEC-012: currency exchange is in scope with configurable enabled currencies, neutral/free rate source, configurable FX fee, and admin FX delta reporting.
