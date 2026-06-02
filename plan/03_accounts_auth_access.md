# Accounts, Authentication, and Access Control

Status: Draft. Updated with identity, balance, access, magic-link, admin-auth, phone-verification, KYB approval-gating, and closure pseudonymization decisions on 2026-05-30.

## Purpose

Define how users, internal staff, service accounts, and future external auditor/reviewer access authenticate and receive permissions across BANXUM.

## Scope

- User registration and login.
- Passwordless investor login, investor sensitive-action email-code confirmation, admin password login, admin email-code verification, and recovery flows.
- Role-based access control for portals and admin tools.
- Admin-created legal-entity lender accounts and optional representative access.
- Explicit exclusion of borrower portal/account access.
- Staff access governance.
- API/service account authentication.
- Session management, device management, and access audit logs.

## Account Types

- Natural-person lender with self-service registration.
- Legal-entity lender account/record created by admin after off-platform onboarding.
- Single legal-entity lender representative/login created by admin where Garanta enables account access.
- Borrower entity record created by admin after off-platform onboarding.
- Borrower representative recorded as entity data, not as a launch login account.
- Borrower beneficial owner recorded as entity data, not as a launch login account.
- Internal operations user.
- Internal compliance user.
- Internal finance user.
- Internal credit/risk user.
- Internal administrator.
- External auditor/read-only reviewer, future only; launch uses admin-generated export packages instead of direct auditor portal access.
- Service account for integrations.

## Core Capabilities

- Register user account.
- Verify email and mandatory natural-person investor phone.
- Send magic-link login emails for investor accounts.
- Send email-code confirmations for investor sensitive/financial actions.
- Enforce email/password plus email-code verification for admin accounts.
- Support one representative/login per legal-entity lender account at launch.
- Manage trusted devices and active sessions.
- Lock, suspend, or close accounts.
- Export access logs.
- Review and recertify staff access.

## Decisions

### ACC-DEC-001: Investor Magic-Link Login and Mandatory Phone Verification

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta product / technology / security.

Decision:
Investor/client portal login uses email magic links at launch. Investors do not use passwords, and baseline login does not require MFA beyond magic-link authentication.

Phone verification is mandatory for natural-person investors and is performed through Twilio SMS verification.

If an investor loses access to their email address or email delivery repeatedly bounces, account access recovery is handled offline through support. Admin/support must re-verify the investor's identity using available KYC/account evidence and the verified phone number where appropriate before changing the account email or restoring access. The recovery action must be audit logged with actor, timestamp, reason, old email, new email, verification evidence summary, and supporting note/document reference where applicable.

Rationale:
Magic-link login keeps the investor authentication flow simple while mandatory phone verification provides an additional verified contact factor during onboarding.

Impacted modules:
- Investor Portal.
- Communications and Notifications.
- Integrations, APIs, and Event Architecture.

Follow-ups:
Define magic-link expiry, resend limits, rate limits, device/session behavior, Twilio verification retry limits, and exact support identity-reverification checklist for email recovery.

### ACC-DEC-002: Admin and Superadmin Authentication

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta technology / security / superadmin.

Decision:
Admin users authenticate with email, password, and an email code. Admin user records are stored in the database and include:

- Email.
- Password hash.
- Full name.
- Role/permissions metadata.
- Status and audit metadata.

Admin users do not have a forgot-password flow. Only superadmin can reset an admin password.

The initial superadmin account is configured through environment variables at deploy time. Superadmin credentials and superadmin account removal are managed from environment/deployment configuration, not from the database UI.

Rationale:
The launch admin model is small and controlled. Superadmin-owned admin creation and reset avoids self-service recovery risk in the admin portal.

Impacted modules:
- Admin and Operations Portal.
- Security, Privacy, and Auditability.
- Infrastructure, DevOps, and Platform Operations.

Follow-ups:
Define environment variable names, secret rotation process, password policy, admin email-code expiry, and bootstrap/deployment procedure.

### ACC-DEC-003: No Admin Step-Up Authentication at Launch

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta operations / technology / security.

Decision:
Admin sensitive actions do not require step-up authentication at launch. Every sensitive admin action must be logged with actor, timestamp, action type, target object, before/after values where appropriate, and reason/evidence where required by workflow.

Changing Garanta collection account/IBAN details is superadmin-only.

Rationale:
Launch admin operations rely on strict role permissions and auditability rather than extra authentication prompts for each sensitive admin action.

Impacted modules:
- Admin and Operations Portal.
- Payments, Ledger, Custody, and Reconciliation.
- Security, Privacy, and Auditability.

Follow-ups:
Design sensitive-action logs so admin step-up authentication can be added later if required.

### ACC-DEC-004: Legal-Entity Lender Access and Investor Representation

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta product / operations / compliance.

Decision:
Legal-entity lender accounts have one login/representative at launch. They behave like regular lender accounts once enabled and KYB/AML-approved, except onboarding/KYC/KYB evidence is admin-recorded off-platform rather than completed through Didit.

No separate legal-entity lender internal roles are required in v1. There are no viewer, transaction-user, balance-user, or approver distinctions for legal-entity lender portal users at launch.

One person cannot represent multiple investor accounts/entities at launch.

Borrower representative relationships remain stored as entity data only and do not create borrower login accounts.

Rationale:
Single-user lender accounts match the launch scope and avoid premature organization/permission complexity.

Follow-ups:
If legal-entity multi-user access is introduced later, define representative roles, signatory authority, organization membership, and optional maker-checker rules.

### ACC-DEC-005: No Admin Impersonation at Launch

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta operations / technology / security.

Decision:
Admin/support impersonation of investor users is not supported at launch.

Support and technical investigation rely on audit logs, event logs, support email, and admin-visible operational records.

Rationale:
Avoiding impersonation reduces security and privacy risk while preserving auditability for troubleshooting.

Follow-ups:
If impersonation is ever introduced, it must be read-only, purpose-limited, and heavily audited.

### ACC-DEC-006: Account Closure, Access Restriction, and Reversible Pseudonymization

Status: Accepted.
Date: 2026-05-22. Updated 2026-05-30.
Owner: Garanta operations / compliance / product.

Decision:
Users request account closure by emailing support/admin. There is no self-service account-closure workflow in the portal at launch.

Account closure is allowed only when the user has a clean/empty account, meaning no active investments, non-zero balances, pending orders, unresolved payments, unresolved KYC/compliance issues, or other open operational obligations.

Implementation note:
Until the ledger, balance, holdings, order, payment, and servicing modules exist, the backend records this as an admin clean-account attestation. Once those modules are implemented, account closure must be blocked unless the system verifies the clean-account prerequisites directly. Admin attestation alone is not sufficient after the relevant data exists.

When an account is closed, login is restricted. Garanta retains documents and data according to legal, regulatory, audit, tax, and business retention requirements.

At closure time, admin may select a checkbox to run the privacy anonymization workflow. In v1 this means reversible pseudonymization/encryption of direct identifiers, not irreversible deletion. Direct identifiers include name, email, and structured KYC/KYB/AML fields that would allow a third party to directly identify the user.

The workflow preserves financial records, documents, KYC/KYB/AML evidence, ledger/accounting references, tax records, contractual records, and audit trail intact. The security/privacy module defines the public-key encryption and offline private-key recovery model.

Inactive accounts are not automatically locked at launch. They remain accessible unless admin manually restricts access under policy.

Restricted and locked account statuses are intentionally equivalent in the current backend access gate: both block login and financial actions. If Garanta later wants "restricted" to mean read-only portal access while "locked" means no portal access, that distinction should be implemented in the account lifecycle UI and access-control policy.

Rationale:
Closure must not interfere with open financial, regulatory, tax, or audit obligations.

Follow-ups:
Define closure request workflow, closure reason codes, final direct-identifier field list, and offline private-key custody procedure. Closed-user document requests are handled through email/support outside the software workflow.

### ACC-DEC-007: Session and Device Management

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta product / technology / security.

Decision:
User-visible session/device management, such as "log out all devices", is nice to have in user settings but not a hard v1 requirement.

Rationale:
Launch can rely on server-side session controls while leaving user-facing session management as a polish item.

### ACC-DEC-008: Investor Long-Lived Sessions and Sensitive-Action Email Codes

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta product / technology / security.

Decision:
Investor sessions should be long-lived rather than expiring on a short idle timer. The investor remains logged in until explicit logout, admin restriction, session revocation, or a security event requiring re-authentication.

Sensitive or financial investor actions require a fresh email-code confirmation before execution. Launch sensitive-action list includes:

- Withdrawal creation or withdrawal bank-account change.
- Currency exchange.
- Primary-market investment.
- Secondary-market listing.
- Secondary-market purchase.
- Other investor actions later classified as sensitive by product/security policy.

Investor sensitive-action email-code defaults:

- Code expiry: 10 minutes.
- Maximum attempts per code: 3.
- Resend throttling: required and configurable. Implementation should start with at least a short resend cooldown to prevent repeated sends.

Rationale:
Long-lived investor access reduces login friction while email-code confirmation protects money-moving and legally binding actions.

Follow-ups:
Define exact resend cooldown/window, global rate limits, session revocation behavior, trusted-device behavior, and whether any low-risk actions can be exempted.

## Permission Model

Permissions should be based on roles plus scoped resources.

Launch lender portal accounts use a single permission set. More granular investor permissions are future-ready examples only:

- Investor viewer: view portfolio and documents.
- Investor transaction user: create investment orders or transfer requests.
- Investor balance user: view balances, deposit instructions, withdrawals, and currency exchange.
- Investor approver: approve legal-entity investment orders if dual approval is enabled in a future policy.
- Borrower representative record: stored as entity data only, with no platform login.
- Borrower signatory record: stored as entity data only, with no platform login.
- Compliance analyst: review KYC/KYB cases but cannot release funds.
- Finance user: reconcile payments according to admin permissions and workflow rules.
- Admin: perform operational platform actions according to workflow rules.
- Superadmin: manage parametrizations and configuration-level administration.

## Security Requirements

- Investor accounts use magic-link login and mandatory phone verification.
- Admin accounts use email, password, and email code.
- Admin sensitive actions do not require step-up authentication at launch.
- Investor sensitive/financial actions require fresh email-code confirmation.
- Sensitive actions require detailed audit logs.
- Admin sessions expire based on risk and role. Investor sessions are long-lived but revocable.
- Access tokens are short-lived.
- Refresh tokens are revocable.
- Passwords, if used, must follow modern hashing and breach detection controls.
- Login and permission changes create audit events.
- Admin impersonation is not supported at launch.

## Organization Model

Legal-entity lenders are admin-created after off-platform onboarding. When Garanta creates and KYB/AML-approves accounts for them, they behave like regular lender accounts for balances, deposits, withdrawals, FX, and investments. Launch supports one representative/login per legal-entity lender account. Borrower organization access is out of scope because borrowers do not log in and the Garanta-borrower relationship is kept offline.

The future organization model may support:

- Organization profile.
- User membership.
- Role assignment.
- Beneficial owner links.
- Authorized signatory links.
- Approval rules.
- Document access restrictions.
- Organization-level onboarding status.

## Launch Registration Rules

- Natural-person lenders can register through the client portal.
- Phone confirmation is mandatory for natural-person lenders and is performed through Twilio SMS verification at launch.
- Natural-person lenders must accept registration-time terms and complete KYC/AML before dashboard, deposit, balance, FX, primary-market, or secondary-market access.
- Legal-entity lenders cannot self-register at launch; admin creates the entity/account after off-platform onboarding.
- Admin-created legal-entity lender accounts do not complete Didit KYC; their KYC/KYB/AML evidence is recorded by admin and financial actions remain blocked until KYB/AML approval is complete.
- Borrowers cannot register or log in; admin creates borrower entity records.
- Legal-entity lender accounts can behave like regular lender accounts once active and KYB/AML-approved; admin can also enter legal-entity lender investments manually from the lender database where Garanta operates without self-service action.
- Auditor/regulator direct portal access is out of launch scope; admins generate PDF/CSV/ZIP evidence exports offline.

## Dependencies

- Identity, KYC, KYB, and AML.
- Investor Portal.
- Borrower and Entity Records.
- Admin and Operations Portal.
- Security, Privacy, and Auditability.

## Q/A Backlog

1. Answered by ACC-DEC-001/ACC-DEC-002: investors use magic-link login with mandatory phone verification and offline support recovery for lost/bouncing email access; admins use email/password plus email code; superadmin credentials are configured through environment variables.
2. Updated by ACC-DEC-001/ACC-DEC-002/ACC-DEC-008: baseline investor login uses magic links and mandatory phone verification, with sensitive-action email-code confirmation for financial/legal actions; admin login uses email-code verification.
3. Answered by ACC-DEC-004: no legal-entity lender maker-checker approval or internal roles are required at launch.
4. Answered by ACC-DEC-004: one person cannot represent multiple investor accounts/entities at launch; borrower representative relationships are tracked only as entity data.
5. Answered by ACC-DEC-005: admin/support impersonation is not supported at launch.
6. Updated by ACC-DEC-006 and SEC-DEC-004: account closure is requested by email support/admin, requires a clean/empty account, restricts login, retains required documents/data, and may optionally trigger reversible direct-identifier pseudonymization through an admin checkbox.
7. Answered by RPT-DEC-003: auditor/regulator direct portal access is out of launch scope; admins generate export packages offline.
8. Answered by Operating Model DEC-010: superadmin and admin.
9. Updated by KYC-DEC-001, KYC-DEC-003, KYC-DEC-008, and PAY-DEC-025: self-service registration is natural-person lenders only; legal-entity lenders are admin-created and behave like regular lender accounts once KYB/AML-approved; borrowers have no login; natural-person lenders need registration-time terms acceptance and KYC before dashboard/deposit/balance/FX/investment access.
10. Answered by COMMS-DEC-001: Twilio SMS is used for phone confirmation only; other security messaging is email-only in v1.
11. Updated by ACC-DEC-003 and ACC-DEC-008: admin sensitive actions do not require step-up authentication, but investor sensitive/financial actions require fresh email-code confirmation; detailed logs are required.
12. Answered by ACC-DEC-006/ACC-DEC-007/ACC-DEC-008: inactive accounts are not automatically locked; investor sessions are long-lived and revocable; user-visible session/device management is nice to have.
