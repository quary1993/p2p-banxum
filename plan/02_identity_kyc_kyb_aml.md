# Identity, KYC, KYB, and AML

Status: Draft. Updated with registration-time KYC, Didit integration, Swiss local evidence storage, and status-mapping decisions on 2026-05-29.

## Purpose

Define how BANXUM verifies users and entities, screens them for financial crime risk, monitors ongoing risk, and integrates Didit into onboarding and compliance operations.

## Scope

- Individual KYC/AML for natural-person lenders using the self-service client portal.
- Off-platform KYC/KYB/AML recordkeeping for legal-entity lenders and borrowers created by admin.
- AML screening including sanctions, PEP, adverse media, and risk scoring.
- Manual re-verification, periodic review triggers, and provider-side ongoing monitoring boundary.
- Compliance/admin task handling and manual review.
- Didit session creation, result retrieval, webhook processing, report/evidence download, and audit retention.
- Swiss local evidence storage, evidence export, and retention for identity/compliance evidence.

## Didit Integration Notes

Didit documentation describes hosted sessions as the recommended approach for user-facing flows. In that flow, the backend creates a verification session, Didit returns a verification URL and session token, the user completes verification, and the platform receives the result by webhook or API.

Didit API documentation shows session creation with a workflow ID, callback URL, optional vendor_data, metadata, contact details, and expected details. The vendor_data field should carry the internal BANXUM user or entity reference so webhook events can be matched safely.

Didit documentation also describes workflow features including ID verification, liveness, face matching, AML screening, NFC verification, database validation, IP analysis, phone verification, email verification, and address verification. The exact workflow configuration must be approved by compliance.

Didit may provide ongoing AML monitoring depending on the selected plan/workflow. In v1, Garanta does not build in-platform ongoing-monitoring automation. Didit handles ongoing monitoring on the provider side where enabled, and Garanta handles any resulting operational actions manually/off-platform.

Implementation status:

- The backend supports local mock KYC sessions and real Didit hosted-session creation through `DIDIT_SESSION_PROVIDER=api`, using the configured API key, workflow ID, callback URL, and user contact metadata.
- The Didit webhook receiver verifies configured V3 signatures/freshness before provider statuses can affect internal KYC state, and non-local deploy checks require webhook signature enforcement.
- The local ignored Didit credentials/workflow were validated once with a real hosted-session creation and local signature verification. Full webhook delivery, report/download artifact capture, workflow-specific status vocabulary, and sandbox test-user scenarios still require a reachable staging/production domain and live Didit console delivery testing.
- Ongoing AML monitoring alerts remain provider-side/off-platform in v1; Garanta records resulting account restrictions, locks, closures, or manual review decisions in BANXUM admin workflows where needed.

Source notes checked on 2026-05-15:

- Didit API overview: https://docs.didit.me/api-reference/overview
- Didit continuous AML monitoring: https://docs.didit.me/core-technology/aml-screening/continuous-monitoring-aml-screening
- Didit AML Screening API: https://docs.didit.me/standalone-apis/aml-screening
- Didit data retention: https://docs.didit.me/console/data-retention
- Didit pricing: https://docs.didit.me/getting-started/pricing

## Decisions

### KYC-DEC-001: Launch Onboarding Scope

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta management / compliance / product.

Decision:
Self-service registration in the client portal is for natural-person lenders only.

The platform supports legal-entity lenders, but their registration and KYC/KYB/AML are handled off-platform for now. Legal-entity lender records/accounts are created only by admin in the admin interface and should not have a visible self-registration flow in the client portal. When Garanta creates and KYB/AML-approves accounts for legal-entity lenders, they behave like regular lender accounts for balances and transactions, except their onboarding/KYC evidence is admin-recorded off-platform rather than completed through Didit.

Borrowers are legal entities created and managed by admin. Borrowers do not have client-portal accounts and cannot log in.

Rationale:
Launch onboarding is intentionally narrow on the client-facing side while still allowing Garanta to operationally support legal-entity lenders and borrowers through admin-managed records. Once legal-entity lender accounts are admin-created and approved, they should use the same financial ledger and balance behavior as other lenders.

Impacted modules:
Investor Portal; Borrower and Entity Records; Admin and Operations Portal; Accounts, Authentication, and Access Control; Documents, Contracting, and E-Signature.

Follow-ups:
Define the admin workflow and evidence fields for manually entering legal-entity lender investments from the lender database where Garanta operates without self-service action.

### KYC-DEC-002: Legal-Entity and Borrower KYC/KYB Responsibility

Status: Accepted.
Date: 2026-05-15. Updated 2026-05-29.
Owner: Garanta compliance / operations.

Decision:
UBO, director, authorized signatory, and legal-entity KYB rules are not in scope for automated client-portal onboarding. Legal-entity lenders and borrowers are onboarded off-platform or through external providers. The platform stores their admin-entered data, documents, compliance status, provider references, reports, decisions, and evidence, but does not expose a legal-entity self-service KYC/KYB workflow at launch.

KYC/KYB approval is required before any legal-entity lender can transact as a lender and before any borrower can be used in a platform transaction, including loan publication, funding close, disbursement, repayment processing, or secondary operational workflows where applicable.

Rationale:
The platform must support operational records and regulatory evidence without exposing a borrower or legal-entity lender self-service onboarding workflow.

Impacted modules:
Admin and Operations Portal; Borrower and Entity Records; Accounts, Authentication, and Access Control; Documents, Contracting, and E-Signature; Reporting, Analytics, and Regulatory Exports.

Follow-ups:
Define mandatory admin fields, document categories, and any provider-specific legal-entity workflow configuration.

### KYC-DEC-003: Natural-Person Lender KYC at Registration

Status: Accepted.
Date: 2026-05-20.
Owner: Garanta product / compliance.

Decision:
Natural-person lenders must complete KYC/AML during registration before they can access the authenticated dashboard, deposit sections, investor balances, primary-market investing, secondary-market actions, or currency exchange.

The registration flow is:

1. Register.
2. Accept registration-time platform terms by checkbox/clickwrap.
3. Platform sends relevant registration/KYC metadata to Didit and sends the user to Didit to complete KYC, selfie/liveness, and ID scan under the configured workflow.
4. Access dashboard, deposits, balances, currency exchange, and investment functionality if KYC/AML is approved and no compliance block applies.
5. If KYC/AML does not pass, the account is not opened for financial use and dashboard/deposit/balance/FX/investment access remains blocked.

If the lender already has valid KYC and no update is required, the investment flow should continue directly.

Rationale:
The balance model allows deposits, withdrawals, balance holding, and currency exchange. KYC/AML must therefore happen before authenticated financial functionality is available.

Impacted modules:
Investor Portal; Marketplace, Investments, and Allocations; Payments, Ledger, Custody, and Reconciliation; Documents, Contracting, and E-Signature.

Follow-ups:
Confirm whether logged-in-but-not-yet-KYC users can see any limited non-financial onboarding screens beyond KYC status/help, and whether public marketplace previews remain available before registration.

### KYC-DEC-004: Didit Scope for Launch

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta compliance / technology.

Decision:
Didit is used for natural-person lender KYC/AML. AML screening should include sanctions, PEP, and adverse media from day one, with Didit handling the checks through the configured workflow/API.

Rationale:
Didit is the selected vendor for individual lender onboarding and AML checks. The platform should consume Didit decisions and evidence while preserving Garanta's internal status and audit trail.

Impacted modules:
Investor Portal; Integrations, APIs, and Event Architecture; Security, Privacy, and Auditability; Reporting, Analytics, and Regulatory Exports.

Follow-ups:
Confirm the exact Didit workflow, AML thresholds, adverse-media setting, onboarding webhook events, and provider report/metadata storage.

### KYC-DEC-005: Didit Evidence Boundary and Local KYC Data Storage

Status: Accepted.
Date: 2026-05-22. Updated 2026-05-29.
Owner: Garanta compliance / technology.

Decision:
All KYC/KYB/AML checks are performed through external providers, with Didit as the selected launch provider. Garanta must also store locally the full KYC/KYB/AML evidence required for regulatory, audit, VQF/SRO, bank/payment partner, and internal compliance purposes.

All relevant KYC/AML data and documents must be stored on Garanta-controlled infrastructure located in Switzerland. The platform must be designed to download, import, or store local copies of provider reports and supporting documents where legally and technically possible. If a provider artifact cannot legally or technically be stored locally, the platform must store the strongest available reference, metadata, and gap note for compliance review.

For natural-person lenders, Garanta stores the platform-required KYC/AML data fields, Didit references, Didit statuses, Didit decisions, AML screening flags/results, provider report identifiers, downloaded report metadata, full provider reports where possible, raw webhook payloads where possible, supporting-document references/local copies where possible, and internal audit metadata.

For legal-entity lenders and borrowers, Garanta stores admin-entered data, UBO/director/authorized-signatory evidence where applicable, provider references, off-platform/provider reports, compliance status, decisions, supporting documents, and evidence uploads.

KYC/AML and KYB files, reports, decisions, audit logs, raw provider webhook payloads where possible, and related evidence are retained for at least 10 years, subject to final legal/compliance confirmation. Launch default remains no deletion unless a later approved retention schedule requires it.

Required stored provider/evidence fields include:

- Provider name and environment.
- Provider workflow ID/name.
- Provider session ID.
- Provider verification ID.
- Provider report ID/reference.
- AML screening ID/reference where separate.
- Provider subject/customer ID where available.
- Internal `vendor_data`/Garanta subject reference.
- Provider event IDs and webhook event types.
- Downloaded report metadata: report type, provider report ID, file name, MIME type, file size, checksum/hash, generated timestamp, downloaded timestamp, provider URL/reference where available, local storage object ID, and download actor/job.
- Final verification status.
- Risk classification.
- Detected flags.
- Decision date.
- Manual-review AML officer/admin where applicable.
- Approval/rejection/reopen/update reason.
- Supporting document references or local storage object IDs.

Rationale:
Didit and other providers perform the checks, but Garanta must retain enough local evidence under its control to satisfy regulatory, VQF/SRO, audit, bank/payment partner, and internal compliance reviews without depending only on provider availability.

Impacted modules:
Documents, Contracting, and E-Signature; Security, Privacy, and Auditability; Reporting, Analytics, and Regulatory Exports; Infrastructure, DevOps, and Platform Operations.

Follow-ups:
Confirm final legal retention policy, exact Didit workflow/report capabilities, and any provider artifacts that cannot be locally retained.

### KYC-DEC-006: Blocking Onboarding Statuses

Status: Accepted.
Date: 2026-05-15. Updated 2026-05-29.
Owner: Garanta compliance / product.

Decision:
Provider statuses are normalized into internal Garanta statuses:

- Pending.
- Approved.
- Declined.
- Manual review.
- High risk.
- Sanctions hit.
- PEP hit.
- Adverse media hit.
- Expired.
- Re-verification required.

Internal mapping rules:

- Provider not-started, session-created, in-progress, queued, or processing states map to pending.
- Provider approved/verified/clear states map to approved only if no unresolved blocking or manual-review flag exists.
- Provider declined/rejected/failed states map to declined.
- Provider review-required, inconclusive, ambiguous, or unable-to-verify states map to manual review.
- Provider expired/session-expired/document-expired states map to expired.
- Provider re-check/re-verification-needed states map to re-verification required.
- Sanctions matches map to sanctions hit.
- Confirmed identity/document fraud maps to declined and blocks onboarding.
- PEP matches map to PEP hit and route to manual AML review.
- High-risk classification maps to high risk and routes to manual AML review.
- Adverse-media matches map to adverse media hit and route to manual AML review.
- Unclear ownership, inconsistent documentation, or other non-standard legal-entity/KYB cases route to manual AML review.

Sanctions hits and confirmed identity/document fraud block onboarding. PEP, high-risk, adverse media, unclear ownership, inconsistent documentation, and other non-standard cases must not be automatically approved; they must be reviewed manually by an AML officer/admin before any approval.

The following statuses block dashboard, deposit, balance, FX, investment completion, contract acceptance, withdrawal, loan publication, funding close, disbursement, and other regulated or transactional actions until resolved: pending, declined, manual review, expired, high risk, sanctions hit, PEP hit, adverse media hit, and re-verification required.

Rationale:
Any unresolved, expired, or high-risk compliance state must prevent regulated platform actions until cleared.

Impacted modules:
Investor Portal; Marketplace, Investments, and Allocations; Payments, Ledger, Custody, and Reconciliation; Admin and Operations Portal.

Follow-ups:
Configure exact Didit event/status names against this internal mapping once the production workflow is available.

### KYC-DEC-008: KYC/KYB Approval Before Transactions

Status: Accepted.
Date: 2026-05-29.
Owner: Garanta compliance / operations / product.

Decision:
KYC/KYB approval is required before any lender or borrower can perform transactions on or through the platform.

For natural-person lenders, this blocks dashboard, deposit, balance, FX, primary-market investing, secondary-market listing/purchase, withdrawal, and transaction-document acceptance until KYC/AML is approved and no compliance hold applies.

For legal-entity lenders, this blocks account activation for financial transactions and manual/admin-entered investments until KYB/AML is approved and no compliance hold applies.

For borrowers, which do not have borrower portal accounts at launch, this blocks operational platform transactions involving that entity. Admin cannot publish a loan, close funding, disburse funds, process borrower-side transactional workflows, or otherwise activate loan operations for the entity until KYB/AML is approved and no compliance hold applies.

Rationale:
The platform should not allow financial, contractual, or settlement activity for parties that have not passed KYC/KYB/AML approval.

### KYC-DEC-007: Provider-Side Ongoing Monitoring and Manual Remediation

Status: Accepted.
Date: 2026-05-15.
Owner: Garanta compliance / technology.

Decision:
The BANXUM platform does not build ongoing-monitoring automation in v1. Ongoing monitoring, where enabled, is handled by Didit on the provider side.

Garanta handles subsequent KYC/AML updates manually/off-platform. Operational actions may include locking/suspending accounts, requesting new documents outside the platform, recording internal notes, or closing/restricting accounts through admin workflows where needed.

Rationale:
Launch needs a simple onboarding integration and clear account controls, not a separate in-platform ongoing-monitoring engine.

Impacted modules:
Integrations, APIs, and Event Architecture; Admin and Operations Portal; Communications and Notifications; Reporting, Analytics, and Regulatory Exports.

Follow-ups:
Confirm where Didit provider-side monitoring alerts are reviewed operationally and what admin status/reason codes should be used when Garanta manually restricts or closes an account after an off-platform review.

## Actors

- Investor user.
- Natural-person lender using the client portal.
- Legal-entity lender created by admin after off-platform onboarding.
- Borrower entity created by admin after off-platform onboarding.
- Compliance analyst.
- Compliance manager / MLRO.
- Admin handling support email; no separate support role at launch.
- Didit as verification vendor.

## Lifecycle

### Natural-Person Lender Lifecycle

1. Natural-person lender registers in the client portal.
2. Lender accepts registration-time platform terms by checkbox/clickwrap.
3. Before dashboard, deposit, balance, FX, primary-market, or secondary-market access, the platform checks KYC status.
4. If KYC is missing or invalid, the backend sends relevant registration/KYC metadata to Didit and creates a Didit session using the configured individual KYC/AML workflow.
5. Lender completes Didit KYC, selfie/liveness, and ID scan by hosted redirect, iframe, mobile SDK, or mobile webview.
6. Platform verifies webhook signature and freshness before processing.
7. Platform stores verification state, required KYC/AML data fields, vendor references, normalized decision, relevant provider metadata, downloaded provider reports where possible, raw webhook payloads where possible, supporting-document references/local copies where possible, and audit metadata in Swiss-controlled restricted storage.
8. If approved, the lender can access the dashboard and financial functionality.
9. If declined, inconclusive, expired, high risk, or flagged, the account is not opened for financial use and access remains blocked.
10. Later KYC/AML updates, document requests, account locks, and account closures are handled manually/off-platform by Garanta and recorded by admin where needed.

### Legal-Entity Lender Lifecycle

1. Legal-entity lender onboarding happens off-platform.
2. Admin creates the legal-entity lender record.
3. Admin stores required entity data, documents, provider/off-platform references, compliance status, manual-review decisions, and evidence.
4. Legal-entity lender financial actions remain blocked until KYB/AML is approved and no compliance hold applies.
5. If Garanta enables account access, the legal-entity lender account behaves like a regular lender account; admin can also manually enter investments from the legal-entity lender database where Garanta operates without self-service action.

### Borrower Entity Lifecycle

1. Borrower onboarding happens off-platform.
2. Admin creates the borrower entity record.
3. Admin stores required entity data, documents, provider/off-platform references, compliance status, manual-review decisions, and evidence.
4. Borrower platform activity remains blocked until KYB/AML is approved and no compliance hold applies.
5. Admin creates and manages borrower loan records. Borrowers do not log in.

## Verification States

- Not started.
- Session created.
- In progress.
- Approved.
- Declined.
- Needs manual review.
- Expired.
- High risk.
- Sanctions hit.
- PEP hit.
- Adverse media hit.
- Reverification required.
- Suspended by compliance.
- Off-platform approved.
- Off-platform blocked.

## Data Objects

- Identity profile.
- Business profile.
- Verification session.
- Verification decision.
- Beneficial owner record.
- Authorized representative record.
- AML screening result.
- Provider-side monitoring reference/note, if manually recorded.
- Risk rating.
- Compliance/admin task.
- Manual review note.
- Regulatory evidence package.
- Data retention timer.
- Provider report file/reference.
- Downloaded provider report metadata.
- Raw provider webhook payload.
- Supporting document storage object/reference.
- Manual AML review decision.

## Compliance Requirements

- Verify identity of contracting partners.
- Identify beneficial owners where relevant through off-platform procedures for legal entities.
- Clarify high-risk relationships, unusual activity, and PEP/high-risk-country exposure.
- Support suspicious activity escalation and reporting workflow.
- Prevent lenders under compliance hold from accessing balances, depositing, withdrawing, exchanging currency, completing investments, or changing critical details.
- Prevent legal-entity lenders without approved KYB/AML from financial activity.
- Prevent borrowers without approved KYB/AML from loan publication, funding close, disbursement, repayment processing, or other platform transaction activity.
- Store relevant KYC/KYB/AML data and documents on Garanta-controlled infrastructure located in Switzerland.
- Retain KYC/KYB/AML files, reports, decisions, audit logs, raw provider webhook payloads where possible, and related evidence for at least 10 years, subject to final legal/compliance confirmation.
- Support local evidence export packages for VQF/SRO, auditors, banks, payment partners, and internal compliance reviews.
- Maintain evidence of onboarding decisions and reviewer actions.
- Re-screen users and entities manually/off-platform when required by policy or risk triggers.

## Didit Webhook Handling

- Accept raw request body.
- Validate timestamp freshness.
- Verify Didit webhook signature using the configured secret.
- Enforce idempotency by vendor event/session ID.
- Match vendor_data to the internal natural-person lender.
- Store raw payload in restricted storage according to retention policy.
- Download or import provider reports and supporting evidence where legally and technically possible.
- Normalize the result into internal statuses.
- Create compliance/admin tasks for declined, suspicious, or ambiguous onboarding results.
- Never grant verified status from an unsigned, stale, replayed, or unmatched webhook.

## Admin Operations

- View verification status and summary risk indicators.
- Open manual review tasks.
- Request additional natural-person KYC re-verification through Didit where needed, or handle additional document requests off-platform and record resulting admin status/notes.
- Override status only with appropriate role and reason code; support second approval later if enabled by policy.
- Export local evidence packages for VQF/SRO, auditors, regulators, banks, payment partners, and internal compliance reviews, including provider metadata, downloadable reports where available, raw webhook payloads where retained, supporting documents where retained, manual decisions, and audit history.
- Create legal-entity lender records after off-platform onboarding.
- Create borrower entity records after off-platform onboarding.
- Upload and manage off-platform KYC/KYB/AML evidence.
- Configure workflows for natural-person lenders by country, risk tier, and product type.

## Dependencies

- Accounts, Authentication, and Access Control.
- Investor Portal.
- Borrower and Entity Records.
- Admin and Operations Portal.
- Security, Privacy, and Auditability.
- Integrations, APIs, and Event Architecture.

## Open Design Decisions

- Whether to use Didit hosted redirect, iframe, native SDK, or a mix.
- Exact Didit workflow for natural-person lender KYC/AML.
- Admin workflow and evidence requirements for manually entering legal-entity lender investments where Garanta operates without self-service action.
- Final legal confirmation of KYC/KYB/AML evidence retention beyond the 10-year minimum, if required.
- Exact export package manifest and recipient-specific redaction rules.
- How rejected users can appeal or retry.

## Q/A Backlog

1. Answered by KYC-DEC-001: self-service KYC applies to natural-person lenders only.
2. Updated by KYC-DEC-001, KYC-DEC-002, and PAY-DEC-025: legal-entity lenders and borrowers are onboarded off-platform and created by admin; admin-created legal-entity lender accounts behave like regular lenders for balances/transactions.
3. Answered by KYC-DEC-001 and KYC-DEC-002: borrowers have no platform accounts; borrower KYB is off-platform/admin-recorded.
4. Answered by KYC-DEC-003: registration-time terms acceptance and KYC are required before dashboard, deposit, balance, FX, and investment access; valid existing KYC lets the flow continue.
5. Answered by Operating Model DEC-003: natural-person lenders may be accepted from Switzerland and EU/EEA; legal-entity lenders and borrowers are admin/offline onboarded rather than governed by a self-service country matrix.
6. Partly answered by KYC-DEC-006: declined, manual review, expired, high risk, sanctions hit, PEP hit, and adverse-media hit block or route to manual review.
7. Answered by KYC-DEC-004: Didit should run AML screening for natural-person lenders, including sanctions, PEP, and adverse media.
8. Updated by KYC-DEC-005: Didit performs the launch natural-person KYC/AML checks, but Garanta stores the full local evidence boundary required for regulatory, audit, VQF/SRO, bank/payment partner, and internal compliance purposes on Swiss-controlled infrastructure, including provider reports and raw webhook payloads where legally and technically possible.
9. Answered by Operating Model DEC-010 and Admin Portal authority matrix: admin can decide onboarding/KYC/KYB exceptions at launch, subject to workflow rules and audit logging.
10. Updated by KYC-DEC-007 and KYC-DEC-008: the platform does not build ongoing-monitoring automation in v1; Didit handles provider-side monitoring where enabled, Garanta handles resulting actions manually/off-platform with admin account lock/restriction/closure where needed, and no lender or borrower can transact until the relevant KYC/KYB approval is complete.
