# Security, Privacy, and Auditability

Status: Draft. Updated with document acceptance, balance, FX, reporting/export, communication-retention, authentication, retention, privacy, production-access, reversible pseudonymization, and Swiss KYC/KYB/AML evidence storage decisions on 2026-05-30.

## Purpose

Define platform-wide security, privacy, data protection, and auditability requirements for a regulated lending platform handling identity, financial, and contractual data.

## Scope

- Security architecture.
- Data classification.
- Encryption and key management.
- Secrets management.
- Access control.
- Audit logging.
- Privacy and retention.
- Secure development.
- Vendor risk.
- Incident response.
- Business continuity.

## Data Classification

- Public: marketing or public platform material.
- Internal: operational data not customer-sensitive.
- Confidential: customer profiles, loan data, internal decisions, document acceptance events, generated document snapshots, full sent email content, email template/data snapshots, balance ageing metadata, FX quote/execution data.
- Restricted: natural-person KYC data fields, provider identifiers, full downloaded KYC/KYB/AML reports, raw provider webhook payloads, identity document copies or references where retained, locally uploaded legal-entity/off-platform KYC/KYB documents, beneficial owner data, bank details, payment data, investor balances, ledger entries, compliance cases, full/unredacted exports, ZIP evidence packages, security secrets.

## Security Requirements

- Encryption in transit and at rest.
- Production secrets stored as environment variables at launch, with restricted tech-team access and rotation procedures.
- Investor magic-link authentication.
- Admin email/password authentication with email-code verification.
- Least-privilege access.
- Periodic access reviews.
- Immutable audit logs for regulated actions.
- Immutable audit logs for checkbox/clickwrap acceptance, including template version, data snapshot reference, timestamp, user, and available technical evidence.
- Tamper-resistant ledger events.
- Secure platform file uploads with malware scanning. Didit performs the launch natural-person KYC capture/check flow, but Garanta retains local KYC/KYB/AML evidence under the identity module boundary where legally and technically possible.
- Dependency and vulnerability management.
- Centralized logging and monitoring.
- Tech-team email alerts for critical launch incidents. Formal incident-response runbooks are future scope unless Garanta requires them.
- Backup and restore testing.

## Privacy Requirements

- Data minimization.
- Purpose limitation.
- Retention schedules.
- Right-of-access and correction workflows where applicable.
- Account closure and personal-data anonymization/pseudonymization workflows where legally permitted.
- Cross-border transfer assessment.
- Vendor data processing agreements.
- Restricted access to identity and compliance evidence.

## Decisions

### SEC-DEC-001: Launch Security Standard and Data Residency

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta management / technology / security.

Decision:
Launch targets good internal controls for v1. No formal SOC 2, ISO 27001, or other certification target is required unless Garanta specifies one later.

Production hosting in the EU is acceptable for general launch infrastructure, subject to vendor due diligence, contracts, and data-processing terms. KYC/KYB/AML evidence is an exception: all relevant KYC/AML data and documents must be stored on Garanta-controlled infrastructure located in Switzerland.

Rationale:
The first version should implement practical controls without committing to a formal certification program before there is a business requirement.

Follow-ups:
If a future investor, partner, regulator, or bank requirement imposes a formal standard, update this module and the infrastructure module.

### SEC-DEC-002: Append-Only Financial Audit and Log Retention

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta technology / finance / operations.

Decision:
Audit/event logging should be append-only at launch.

The ledger and all financial events must be append-only and treated as immutable source records. Financial events include deposits, withdrawals, forced withdrawals, balance credits/debits, investments, secondary-market transactions, repayments, distributions, FX quotes/executions, fees, penalties, finance corrections, report/export generation, and related admin actions.

Logs are not deleted at launch. Garanta will monitor log growth and decide later whether a cleanup, archive, or retention-tiering system is needed.

Rationale:
Financial auditability matters more than storage optimization in v1.

Follow-ups:
Define storage monitoring thresholds and a future log cleanup/archive policy once real production volume is known.

### SEC-DEC-003: Retention Baseline

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta compliance / finance / technology.

Decision:
Financial records are retained for at least 10 years.

KYC/KYB/AML files, reports, decisions, audit logs, raw provider webhook payloads where possible, and related evidence are retained for at least 10 years, subject to final legal/compliance confirmation.

For launch, Garanta keeps all platform records indefinitely unless and until a more granular retention schedule is approved. This includes financial records, ledger entries, audit logs, reports, documents, full email content, KYC/KYB metadata, provider references, downloaded provider reports where possible, raw provider webhook payloads where possible, supporting evidence, and compliance evidence.

Rationale:
A conservative retention baseline avoids premature deletion in a regulated financial workflow.

Follow-ups:
Legal/compliance should later define a granular retention schedule and whether any records must be deleted, archived, redacted, or retained permanently.

### SEC-DEC-004: Account Closure and Reversible Personal-Data Pseudonymization

Status: Accepted.
Date: 2026-05-22. Updated 2026-05-30.
Owner: Garanta operations / compliance / technology.

Decision:
Account closure requests are sent by email/support. Admin can close an account when the account is clean/empty under the accounts module rules. At account closure time, admin may select a checkbox to run the privacy anonymization workflow.

The v1 privacy anonymization workflow is reversible pseudonymization, not irreversible deletion or true anonymization.

The workflow encrypts/pseudonymizes direct identifying fields used in normal application views, including name, email, and structured KYC/KYB/AML fields that would allow a third party to directly identify the user. Bank/payment data, financial records, ledger entries, balances, investments, repayments, withdrawals, reports, tax records, audit records, payment evidence, contracts, generated documents, uploaded documents, KYC/KYB/AML evidence, and other retained documents remain intact and must not be destructively modified or deleted by this workflow.

Documents and evidence files are retained under normal retention and access-control rules. If a document contains personal data, access is restricted; the document is not deleted or altered solely because the account was closed.

The reversible pseudonymization mechanism uses asymmetric encryption:

- The public encryption key may be stored in environment variables, configuration, or database settings.
- The private decryption key remains offline and outside the application.
- The application can encrypt/pseudonymize direct identifiers but cannot decrypt them without an offline key-controlled process.
- Any restoration/decryption event must be audited with actor, timestamp, scope, and reason.

The platform must keep closure and pseudonymization actions audited, including admin, timestamp, account, checkbox selection, affected field groups, and reason where captured.

Rationale:
Regulated financial, contractual, tax, audit, and KYC/KYB/AML records cannot be lost. Reversible pseudonymization reduces normal operational exposure of direct identifiers while preserving recoverability for legal, regulatory, audit, and support needs.

Follow-ups:
Define final closure reason codes, direct identifier field list after implementation data modeling, offline private-key custody procedure, and decryption approval/logging process.

### SEC-DEC-005: Production Access, Export Visibility, and Field Masking

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta management / technology / operations.

Decision:
Production customer data may be accessed by authorized admins through the application and by the tech team where operationally necessary.

Full/unredacted exports require audit logging, but no extra approval or reason-code gate is required at launch.

Sensitive fields are not masked by default in the admin UI at launch.

Rationale:
Launch operations require direct administrative and technical access. Audit logs are the initial control.

Follow-ups:
Define production access policy, tech-team access logging, break-glass conventions if later needed, and whether future masking/reason-code controls are required.

### SEC-DEC-006: Upload Boundary and Malware Scanning

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta technology / operations.

Decision:
Didit performs the launch natural-person KYC capture/check flow. Garanta stores local copies, reports, provider metadata, raw provider webhook payloads, and supporting evidence where legally and technically possible under the identity module boundary. Any local KYC/KYB/AML evidence must use restricted Swiss-controlled storage and access controls.

Other platform file uploads remain in scope, including borrower documents, legal-entity/off-platform KYB evidence, bank statements, servicing documents, recovery documents, and internal notes/evidence. These uploads should be file-type restricted, access-controlled, and malware-scanned.

Rationale:
KYC/KYB/AML checks are delegated to Didit or other providers, but Garanta still retains local regulatory evidence and the platform handles non-KYC operational files.

### SEC-DEC-007: Incident Alerts

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta technology.

Decision:
A formal incident-response program and severity model is not required for v1.

The platform should create tech-team email alerts for critical failures, security-relevant events, integration failures, ledger/export job failures, failed email retry exhaustion, failed webhook processing, and other operational conditions that require technical attention.

Rationale:
Email alerts provide a pragmatic launch control without introducing a full incident-management process.

## Audit Events

Examples:

- Login success/failure.
- Magic link requested/sent/consumed/expired.
- Admin email-code requested/verified/failed.
- Admin password reset by superadmin.
- Superadmin credential changed through deployment configuration.
- Permission changes.
- KYC/KYB status change.
- KYC/KYB provider report downloaded or imported.
- KYC/KYB raw webhook payload stored.
- KYC/KYB evidence package exported.
- KYC/KYB manual review opened/reopened.
- KYC/KYB manual review approved/rejected.
- Account closed.
- Reversible privacy pseudonymization applied.
- Direct identifiers restored/decrypted through offline key-controlled process.
- Compliance hold placed/removed.
- Borrower approval.
- Credit approval.
- Listing publication.
- Investment order submission.
- Fund release approval.
- Ledger correction.
- Document checkbox/clickwrap acceptance.
- Generated document delivery.
- Investor deposit credited.
- Investor balance credited/debited.
- Withdrawal requested/processed.
- Balance ageing reminder sent.
- Balance penalty applied.
- Penalty-mode freeze enabled/disabled.
- Forced withdrawal attempted/finalized.
- Offline withdrawal return/failure note added.
- Currency exchange quote accepted.
- FX executable quote issued/expired.
- FX display-rate tick rejected.
- FX quote sanity-check failure.
- Currency exchange completed/failed.
- External FX execution recorded.
- Document template version created/updated/published by superadmin.
- Email template version created/updated/published by superadmin.
- Marketing consent captured/withdrawn.
- Email queued/sent/failed/retried.
- Admin email failure notice created.
- Phone verification requested/completed.
- Bank account change.
- Garanta collection account/IBAN changed by superadmin.
- Data export.
- Report export generated.
- ZIP evidence package generated.
- Full/unredacted export generated.
- Redacted export generated.
- Admin override.

## Reporting and Export Controls

- Report exports are admin-only at launch.
- Superadmin does not receive export access unless also assigned/admin-granted the admin operational role.
- Sensitive reports must support redacted and full modes.
- Full/unredacted exports require audit logging but no extra approval, masking, or reason-code gate at launch.
- Exports must log report type, date range, filters, redaction mode, generated timestamp, generating admin, report definition/version, and handling/destination note if captured.
- ZIP evidence packages must include a manifest where feasible.
- Auditor/regulator direct portal access is out of scope for launch; admins generate and share/export packages offline.

## Communication Security and Retention Controls

- Full sent email content is stored at launch and must be protected as confidential data.
- Email records should include template version, data snapshot, recipient, provider message id, delivery/failure status, and timestamps where available.
- Marketing consent capture/withdrawal must be auditable.
- SendGrid and Twilio credentials are secrets and must use the same secret-management controls as other production integrations.
- Launch secret management uses environment variables; production environment-variable access must be restricted and audited where feasible.
- Phone verification through Twilio must store minimal verification metadata and avoid storing one-time codes longer than needed.

## Production-to-Staging Data Controls

- Production data may be copied to staging only after anonymization/pseudonymization.
- Names, emails, phone numbers, IBANs, bank-account labels, addresses, and similar direct identifiers must be replaced with deterministic fake values.
- Raw identity documents, full KYC/KYB/AML provider reports, raw provider webhook payloads, sanctions/PEP/adverse-media detail, and unrestricted compliance evidence should be excluded from staging copies unless a specific synthetic/redacted fixture is created.
- Internal IDs, relational links, balances, loan amounts, ledger structure, dates/timestamps, statuses, and event chronology may be preserved where needed for realistic testing.
- Provider credentials, webhook secrets, external tokens, and sensitive provider identifiers must be removed or replaced.
- Staging must not send real emails/SMS or make real money-moving/provider calls.
- Any re-identification mapping must remain outside staging.

## Authentication and Access Controls

- Investor/client portal uses magic-link login at launch.
- Natural-person investor phone verification is mandatory at launch.
- Baseline investor login does not require MFA beyond magic-link authentication and mandatory phone verification.
- Admin users authenticate with email, password, and email code.
- Admin forgot-password/self-service reset is not available; superadmin resets admin passwords.
- Initial superadmin credentials are configured through environment variables and managed at deploy time.
- Admin sensitive actions do not require step-up authentication at launch, but must be logged with actor, timestamp, action type, target object, and before/after values where appropriate.
- Investor sensitive/financial actions require fresh email-code confirmation before execution, including withdrawals, withdrawal bank-account changes, currency exchange, primary-market investments, secondary-market listings, and secondary-market purchases.
- Admin/support impersonation is not supported at launch.

## Session Policy Notes

Launch session policy:

- Investor magic links are single-use and expire after 15 minutes.
- Investor sessions are long-lived and do not use a short idle timeout. They remain valid until explicit logout, admin restriction, session revocation, or a security event requiring re-authentication.
- Investor sensitive-action email codes are required for sensitive/financial actions. Codes expire after 10 minutes, allow 3 attempts, and require resend throttling.
- Admin email codes expire after 10 minutes.
- Admin sessions expire after 15 minutes of inactivity and no later than 8 hours after login.
- Failed login/code attempts and magic-link requests are rate-limited by account, IP, and email address.

These defaults balance investor usability with action-level controls for money-moving and legally binding actions.

## Dependencies

- All modules.
- Infrastructure, DevOps, and Platform Operations.

## Q/A Backlog

1. Answered by SEC-DEC-001: good internal controls for v1; no formal security standard unless Garanta specifies one later.
2. Updated by SEC-DEC-001 and KYC-DEC-005: EU hosting/data residency is acceptable for general launch infrastructure, but KYC/KYB/AML evidence must be stored on Garanta-controlled infrastructure located in Switzerland.
3. Answered by SEC-DEC-003 and KYC-DEC-005: financial records are retained for at least 10 years; KYC/KYB/AML evidence is retained for at least 10 years subject to final legal/compliance confirmation; launch keeps all records indefinitely pending granular retention policy.
4. Answered by SEC-DEC-007: no formal incident-response model is required at launch; tech-team email alerts are required.
5. Answered by SEC-DEC-002: ledger and all financial events must be append-only/immutable; logs are not deleted at launch.
6. Updated by SEC-DEC-004: account closure is an admin workflow triggered by email/support request; optional closure-time privacy anonymization is reversible pseudonymization using an offline private decryption key, while financial records, documents, audit trail, and KYC/KYB/AML evidence remain intact.
7. Answered by SEC-DEC-005: production data access is available to admins and tech team where operationally necessary.
8. Answered by SEC-DEC-005: full/unredacted exports require audit logging only at launch; no default field masking in admin UI.
9. Answered by RPT-DEC-003: report exports are admin-only and support redacted/full modes; direct auditor/regulator portal access is out of launch scope.
10. Answered by COMMS-DEC-004: full sent email content is stored, with delivery metadata and template/data snapshot.
11. Updated by ACC-DEC-001/ACC-DEC-002/ACC-DEC-003/ACC-DEC-005/ACC-DEC-008: investor magic-link login, mandatory phone verification, investor sensitive-action email-code confirmation, admin email/password plus email-code login, no admin step-up, and no impersonation.
12. Updated by SEC-DEC-006 and KYC-DEC-005: Didit performs the launch natural-person KYC capture/check flow, while Garanta stores local KYC/KYB/AML evidence where legally and technically possible; all uploads and retained evidence require restricted access, encryption, retention controls, and malware-scanning where applicable.
13. Updated by ACC-DEC-008: investor sessions are long-lived; investor sensitive-action email codes expire after 10 minutes, allow 3 attempts, and require resend throttling; admin session defaults are 15-minute idle and 8-hour maximum. Exact global rate-limit implementation remains a security configuration detail.
