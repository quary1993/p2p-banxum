# Accounts, Authentication, and Access Control

Status: Draft. Updated with identity, balance, access, magic-link, admin-auth, phone-verification, KYB approval-gating, and closure pseudonymization decisions on 2026-05-30. Sign-in and security rules replaced on 2026-11-19 (Phase 18.5); see "Current Sign-In And Security Rules".

## Current Sign-In And Security Rules (2026-11-20, Phase 18.5)

This section is the current rule. It replaces the sign-in, confirmation and recovery parts of ACC-DEC-001, ACC-DEC-002, ACC-DEC-008 and ACC-DEC-009 below. Those decision texts stay as history and are marked "Superseded". Sources: `plan/22_u33_redesign_decisions.md` (U33-DEC-01, D-1 to D-6) and `IMPLEMENTATION_PLAN.md` 18.5 (with "Audit step 4 fixes").

- **Investor sign-in:** email and password, then one second factor: an SMS code (Twilio Verify) or an authenticator app code (RFC 6238), or a single-use recovery code (10 codes, stored hashed). There are no magic links and no passkeys. A trusted device (optional, 30 days) skips the second factor; the password is always asked.
- **Passwords (investors and administrators):** 12 to 128 characters, no forced mix, a common-password list and the Have I Been Pwned range check (k-anonymity).
- **Administrator sign-in:** use the password and an authenticator app. First setup also requires a code from the newest setup email. A verified contact phone is not a sign-in factor. If the email code reaches its attempt limit, restart setup with the password, scan the new QR code, and use the new email. The limit on that email code does not lock the account. After setup, use only the password and the app for sign-in.
- **Administrator app reset:** a superadmin can reset another administrator's app. This ends existing sessions and invalidates unfinished setup and sign-in steps. The administrator receives a security email and a task. Do not share QR codes or setup keys with support. If an active key was shared, reset the app. There is no self-service password recovery for administrators.
- **Sensitive operations (D-1):** after a review step, the email code and the PIN. An investor with an authenticator app types its code in place of the PIN and has no PIN. The email code is bound to one operation (action, amount, currency, destination, loan or listing) and is single use; changed data needs a new code.
- **PIN:** only investors with the SMS factor have a PIN (set at registration after the factor). Forgotten PIN: password and SMS code.
- **Recovery:** forgotten password = single-use email link and the second factor. Lost factor without recovery codes = assisted recovery: a support case, a new Didit identity check that the system compares with the stored identity, a confirmation by a person with the compliance role, an approval by a second person, a 24-hour notice with a "This was not me" link, then a single-use link, a new password and a new factor. At most 3 requests per account in 7 days. An account without a stored verified name (from an approved identity check) cannot use the assisted recovery; the investor does a new identity check first. After it, 72 hours without new bank accounts or a change of the default return account.
- **Limits:** per account and IP, per IP, and for each account from all addresses (failed sign-ins, wrong factor codes, SMS sends, sensitive-action codes). A browser that already signed in to the account is not held by the account-wide sign-in limit.
- **Security tab:** password, second factor, recovery codes, trusted devices, sessions and sign-in history. A change that gives or changes access asks the password and the second factor first. Signing out a session and removing a trusted device need the signed-in session only.
- **Privacy:** the account tables keep IP addresses as keyed hashes only. The clickwrap evidence of a contract keeps the raw address (plan 13). The sign-in place is a city or country from a local database or the proxy header, marked as approximate.
- **Resets:** every reset is notified; a password or factor reset ends the other sessions and revokes the trusted devices.

## Purpose

Define how users, internal staff, service accounts, and future external auditor/reviewer access authenticate and receive permissions across BANXUM.

## Scope

- User registration and login.
- Investor sign-in with password and second factor, investor sensitive-action confirmation (email code with PIN or authenticator code), admin sign-in with password and authenticator app, and recovery flows.
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
- Sign investors in with email, password and a second factor (SMS code or authenticator app), with recovery codes and optional trusted devices.
- Send email-code confirmations for investor sensitive/financial actions, bound to one operation.
- Require the investor's 6-digit PIN, or the authenticator app code for investors with the app, with the email code for every sensitive action (ACC-DEC-009, D-1).
- Enforce email, password and authenticator app for admin accounts.
- Support one representative/login per legal-entity lender account at launch.
- Manage trusted devices and active sessions.
- Lock, suspend, or close accounts.
- Export access logs.
- Review and recertify staff access.

## Decisions

### ACC-DEC-001: Investor Magic-Link Login and Mandatory Phone Verification

> Superseded 2026-11-19 (Phase 18.5, implemented; U33-DEC-01): investors sign in with a password and a mandatory second factor (SMS or authenticator app). Magic links are removed. Lost access is handled by the assisted recovery with a new Didit check, not by the offline procedure below. See "Current Sign-In And Security Rules". Phone verification stays mandatory. The text below is history.

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta product / technology / security.

Decision:
Investor/client portal login uses email magic links at launch. Investors do not use passwords, and baseline login does not require MFA beyond magic-link authentication.

Phone verification is mandatory for natural-person investors and is performed through Twilio SMS verification.

If an investor loses access to their email address or email delivery repeatedly bounces, account access recovery is handled offline through support. Admin/support must re-verify the investor's identity using available KYC/account evidence and the verified phone number where appropriate before changing the account email or restoring access. The recovery action must be audit logged with actor, timestamp, reason, old email, new email, verification evidence summary, and supporting note/document reference where applicable.

Updated 2026-10-09 (security audit A-47, A-49, A-50, A-57):
- Login links carry the token in the URL fragment (`/login#token=...`); the portal removes it from the address bar before any API call. Links from older emails (`?token=`) still work for their 15 minutes. Only the newest link of an account works.
- The stored copy of every sent email shows `[redacted]` in place of a login link or code. Only the email provider receives the live value.
- Request limits that name an email address always pair it with the caller's IP, so nobody can lock another person out. Per address, a new link email waits while the last link is unused (backoff from 1 minute, doubling, always shorter than the link lifetime); the caller still gets the normal "check your inbox" answer.
- Registration gives the same answer for a new address and an existing one. A repeated registration never changes stored data. The owner gets an email instead: a sign-in link (unfinished or finished investor account), the blocked notice (restricted/locked), or a notice without a link (admin, closed), at most once an hour or within the link backoff. Phone numbers must be in E.164 form. Until the phone is verified and KYC has started, the signed-in owner can correct the number when they request the SMS code.
- Sign-in endpoints refuse cross-site browser posts (login CSRF).

Rationale:
Magic-link login keeps the investor authentication flow simple while mandatory phone verification provides an additional verified contact factor during onboarding.

Impacted modules:
- Investor Portal.
- Communications and Notifications.
- Integrations, APIs, and Event Architecture.

Follow-ups:
Define magic-link expiry, resend limits, rate limits, device/session behavior, Twilio verification retry limits, and exact support identity-reverification checklist for email recovery.

Implementation status:
The backend supports local/mock phone verification for development and Twilio Verify for staging/production through `PHONE_VERIFICATION_PROVIDER=twilio_verify`. In Twilio mode, BANXUM stores the local challenge/audit evidence and Twilio verification SID but not a local OTP digest; confirmation is checked through Twilio while local ownership, expiry, attempt limits, and throttles are still enforced. Non-local deploy checks require Twilio credentials and Verify service configuration. Live SMS delivery must be tested once staging/production credentials and phone-number policies are active.

### ACC-DEC-002: Admin and Superadmin Authentication

> Superseded in part 2026-11-19 (Phase 18.5, implemented): administrators sign in with email, password and an authenticator app; the email code is removed. Passwords follow the platform policy (12 to 128 characters, common list, Have I Been Pwned). See "Current Sign-In And Security Rules". The rules below for admin creation, the superadmin account and the missing self-service recovery stay in force.

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

Updated 2026-10-09 (security audit A-47, A-52, A-57, SECCODE-17): admin passwords need at least 12 characters and must not be on Django's offline list of common passwords. Wrong passwords slow down only the same email and IP pair (5 free attempts, then a doubling wait up to 15 minutes); other IPs are not affected. The admin login takes the same time for unknown, investor and admin emails. The Django admin (`/admin/django/`, password only) exists in local development only.

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

### ACC-DEC-005: Read-Only Superadmin Impersonation

Status: Accepted. Updated 2026-07-04 (supersedes the launch-time "no impersonation" rule).
Date: 2026-05-22. Updated 2026-07-04.
Owner: Garanta operations / technology / security.

Decision:
Superadmins may open a read-only impersonation view of an investor account for support and
technical investigation. The feature follows the constraints this decision originally set for
any future introduction:

- Superadmin-only: only an active superadmin can start or use an impersonation context; regular admins cannot.
- Read-only: mutating requests are rejected while impersonating; only viewing is possible.
- Restricted targets: admin and superadmin accounts can never be impersonated.
- Short-lived: access uses a signed, purpose-scoped token (default 30 minutes, deployment-configurable) presented alongside the superadmin's own authenticated session; the token grants nothing on its own.
- Heavily audited: every impersonation start is recorded as a high-risk audit event with the acting superadmin, target identity, and token lifetime.

Support and technical investigation otherwise continue to rely on audit logs, event logs, support email, and admin-visible operational records.

Rationale:
A read-only, superadmin-gated, audited view resolves real support cases (seeing exactly what an investor sees) without granting the ability to act on the account, preserving the security and privacy intent of the original decision.

Follow-ups:
Any future write-capable impersonation or admin-role targeting would require a new decision with compliance sign-off.

### ACC-DEC-006: Account Closure, Access Restriction, and Reversible Pseudonymization

> Updated 2026-11-08 (`plan/22_u33_redesign_decisions.md`), approved, implementation pending (IMPLEMENTATION_PLAN.md Phase 17): U33-DEC-26 and U33-DEC-28 confirm this decision: verified personal data change only through support after identity verification; the "Close account" button sends a closure request to the team.
>
> Implemented 2026-11-10 (Phase 17.2, U33-DEC-28): "Close account" posts `kind: account_closure` to `POST /api/v1/investor/portal/support-requests/`. The request is stored (`communications.InvestorSupportRequest`, reference CLS-YYYY-NNNN), emailed to the support mailbox (`platform.support_email`, then `SUPPORT_EMAIL`) with the investor's email as Reply-To, and opens an "Account access review" admin task with the checks to make. The investor gets a receipt email and a receipt in the portal saying the account is not closed yet; the closure itself stays the admin access action and is confirmed by a separate email. At most 3 closure requests per day per investor; a retry with the same request key returns the same receipt.

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

Updated 2026-10-09: the user is told why. An open portal session of a restricted, locked or closed account shows an "Account access" page naming the status and the support address instead of the portal screens. A login-link request for a restricted or locked account still gets the generic response (account existence stays private) but emails the owner an `email.account_login_blocked` notice with the status and support address, at most once per hour; a link issued before the restriction answers 403 `account_restricted`/`account_locked` and the login screen explains it.

Rationale:
Closure must not interfere with open financial, regulatory, tax, or audit obligations.

Follow-ups:
Define closure request workflow, closure reason codes, final direct-identifier field list, and offline private-key custody procedure. Closed-user document requests are handled through email/support outside the software workflow.

### ACC-DEC-007: Session and Device Management

> Updated 2026-11-08 (`plan/22_u33_redesign_decisions.md`), approved, implementation pending (IMPLEMENTATION_PLAN.md Phase 17): U33-DEC-25: investors get a session list with remote sign-out, a sign-in history and new-device security alerts.
>
> Implemented 2026-11-10 (Phase 17.3). A device is one browser: at sign-in it gets a random value in the HTTP-only, SameSite=Lax cookie `banxum_device` (2 years); the sign-in event stores only its keyed hash. A sign-in is from a new device when the account has earlier sign-ins and none with this value (a sign-in recorded before the cookie still counts by its browser label). A browser whose cookies were cleared counts as new.
>
> Implemented 2026-11-10 (Phase 17.2, U33-DEC-25): every sign-in creates an `accounts_auth.UserSession` (linked to the server-side session by its id) and a `SignInEvent` (time, device and browser from the user agent, country from the trusted proxy header `SIGN_IN_COUNTRY_HEADER` when configured, method, result; the IP only as a keyed hash). Refused sign-ins of a known account (blocked account, wrong admin password) are recorded too. `GET /api/v1/auth/sessions/` lists the open sessions (this device first), `POST /api/v1/auth/sessions/<id>/revoke/` and `POST /api/v1/auth/sessions/revoke-others/` end sessions; `UserSessionMiddleware` signs an ended session out on its next request (401 `session_expired` with its own text) and keeps the last activity (written at most every 5 minutes). `GET /api/v1/auth/sign-in-history/` gives the last 50 sign-ins within `security.sign_in_history_retention_days` (default 365); the scheduled job `account_security_retention` deletes older history and ended sessions. A sign-in from a device not seen before sends `email.security_new_sign_in` (not for the first recorded sign-in of an account), independent of marketing consent. Sessions started before this change get a record on their next request. Profile & Settings -> Security shows "Signed-in devices" (with "Sign out" and "Sign out on all other devices") and "Sign-in history". The place is a country, not a city: a city needs a geolocation source that is not chosen.

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta product / technology / security.

Decision:
User-visible session/device management, such as "log out all devices", is nice to have in user settings but not a hard v1 requirement.

Rationale:
Launch can rely on server-side session controls while leaving user-facing session management as a polish item.

### ACC-DEC-008: Investor Long-Lived Sessions and Sensitive-Action Email Codes

> Superseded in part 2026-11-19 (Phase 18.5, implemented; D-1 of 2026-11-19 replaces the note of 2026-11-08): the email code for operations stays, with the PIN or the authenticator app code. The code is bound to one operation (action, amount, currency, destination, loan or listing), expires and is single use; changed data needs a new code. Sign-in is by password and second factor, not by magic link. See "Current Sign-In And Security Rules". The session rules below stay in force with the update of 2026-10-09.

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

Updated 2026-10-09 (QA regression decision): investor and admin sessions now end a fixed time after login, default 2 hours (`AUTH_SESSION_MAX_AGE_SECONDS`), absolute rather than idle-based. The login time is kept in the server-side session and enforced by `accounts_auth.middleware.SessionLifetimeMiddleware`; after expiry every authenticated API call from that browser answers 401 `{"code": "session_expired"}` until the next login or sign-out, and the investor portal and admin console return to their login screen with a "session expired" notice. Read-only superadmin impersonation ends with the superadmin's session. The real clock is used, so the QA simulated clock never ends or extends sessions. The per-code attempt limit is configurable through `AUTH_SENSITIVE_CODE_MAX_ATTEMPTS` (default 3).

### ACC-DEC-009: Investor PIN for Every Sensitive Action

> Superseded in part 2026-11-19 (Phase 18.5, implemented; D-1): the PIN is used with the email code, as below. Changes: only investors with the SMS factor have a PIN; an investor with an authenticator app types the app code in place of the PIN (API field `pin`); the PIN step of the registration comes after the second factor; a forgotten PIN needs the password and an SMS code (no email code). A PIN change still needs the current PIN and an email code. The public wording about a magic link is no longer used. See "Current Sign-In And Security Rules".

Status: Accepted.
Date: 2026-10-16 (owner decision of 2026-10-15, row 12).
Owner: Garanta product / technology / security.

Decision:
Every investor has a 6-digit PIN. Every sensitive action needs the fresh email code (ACC-DEC-008) and the PIN. Public wording: "Access your account with a magic link sent to your email; an extra code and a PIN code for every sensitive operation".

- Storage: only a Django password hash (`accounts_auth.SensitiveActionPin`), with set/changed times, the wrong-attempt count and the lock time. The PIN never appears in responses, logs, audit metadata or the outbox.
- Rules: exactly 6 digits; not one digit repeated (111111) and not a straight run up or down (123456, 654321, 012345). The registration screen shows the rules as a checklist.
- Check order, in the shared `platform_core.services.sensitive_actions.verify_sensitive_action_code`, so every module gets it: PIN lock, then PIN, then email code. A wrong PIN never uses up the email code, and counts toward the lock even when the email code is right. A correct PIN resets the count. Like the email-code attempts, the check commits on its own before any rollbackable financial transaction.
- Lock: 5 wrong PINs in a row lock the PIN for 30 minutes (`AUTH_PIN_MAX_ATTEMPTS`, `AUTH_PIN_LOCK_SECONDS`, real clock), with the audit event `auth.pin_locked` and the email `email.pin_locked` ("Your PIN was locked after 5 wrong attempts").
- Actions: withdrawal, bank account change, FX, primary investment (single order, Smart-Invest batch, Loan Originator claim purchase), secondary-market listing (create and edit) and purchase. Each request carries `pin` next to `sensitive_action_code_id`/`sensitive_action_code`. Admin login (password and authenticator app) has no PIN. Since 18.5 the field `pin` carries the authenticator app code for an investor with the app.
- Registration (changed in 18.5: the PIN step comes after the second-factor step and only for investors with the SMS factor; an investor with the app sets no PIN): a PIN step after terms and phone verification and before the KYC hand-off (steps Account, Email and phone, PIN, KYC). The PIN is entered twice and needs no email code (pending-KYC account, phone just verified). The KYC session cannot start for a natural person without a PIN (409 `pin_required`).
- Existing accounts: after login, an account without a PIN sees "Create your PIN" before anything else; outside registration the first PIN needs a fresh email code for `pin_setup`. Until then every sensitive action answers 409 `pin_required`.
- Change PIN (Settings): current PIN, an email code for `pin_change` and the new PIN twice.
- Forgot PIN (Settings and the PIN prompt; changed in 18.5: the password takes the place of the email code): the password, an SMS code to the verified phone (the phone-verification provider, Twilio Verify in staging/production) and the new PIN twice; it clears the lock. The reset SMS also counts for the SMS limits of the account (audit S4-2). A PIN-reset SMS code never verifies a phone number.
- After any change or reset the investor gets the email `email.pin_changed` ("Your PIN was changed. If this was not you, contact support"). Audit events: `auth.pin_set`, `auth.pin_verified`, `auth.pin_check_failed`, `auth.pin_locked`, `auth.pin_changed`, `auth.pin_reset`, `auth.pin_reset_sms_requested`, `auth.pin_reset_sms_failed`.

API (`/api/v1/auth/pin/`, session auth, throttled per IP and account: `AUTH_PIN_HOURLY_LIMIT`/`AUTH_PIN_DAILY_LIMIT`; the reset SMS follows the registration SMS limits):
- `GET status/`: `pin_set`, `locked_until`, `attempts_left`, `max_attempts`, `setup_requires_email_code`, `reset_available`, `phone_last_digits`. The `/auth/me/` user also carries `pin_set` and `pin_locked_until`.
- `POST set/`: `new_pin`, `new_pin_confirmation`, and outside registration `sensitive_action_code_id`/`sensitive_action_code` (`pin_setup`).
- `POST change/`: `pin`, `new_pin`, `new_pin_confirmation`, email code (`pin_change`).
- `POST reset/start/`: `password`; sends the SMS code; answers `phone_challenge_id`. `POST reset/confirm/`: `phone_challenge_id`, `phone_code`, `new_pin`, `new_pin_confirmation`.

Error codes (body `{"detail", "code", ...}`): 400 `pin_invalid` (`attempts_left`), 423 `pin_locked` (`locked_until`), 409 `pin_required` (no PIN yet), 400 `pin_weak`, 400 `pin_mismatch`, 400 `pin_unchanged`, 409 `pin_already_set`, 403 `pin_not_available` (admin or blocked account), 409 `phone_verification_required`, 409 `pin_reset_unavailable` (no verified phone), 400 `email_code_invalid`, 429 `email_code_attempts_exceeded`, 400 `phone_code_invalid`, 429 `phone_code_attempts_exceeded`, 429 `phone_code_throttled`. A sensitive-action request without a valid `pin` field answers 400 with a `pin` field error. Wrong or expired email codes keep their existing answers.

QA: the QA seed (`seed_qa_starting_point`) gives the synthetic QA investor the known PIN shown in its output (`investor_pin`) and resets it on every run; synthetic regression investors created by the QA reset get the same known PIN. Known PINs are refused in production.

Rationale:
The PIN adds a knowledge factor to the email-code step-up, so a compromised mailbox alone cannot move money or change the payout account.

Follow-ups:
Claude Design polish of the PIN screens (docs/claude-design/TODO.md); decide whether repeated locks should escalate (longer locks or a support review).

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

- Investor accounts use password sign-in with a mandatory second factor (SMS or authenticator app) and mandatory phone verification.
- Admin accounts use email, password, and an authenticator app.
- Admin sensitive actions do not require step-up authentication at launch.
- Investor sensitive/financial actions require fresh email-code confirmation and the investor PIN, or the authenticator app code for investors with the app (ACC-DEC-009, D-1).
- Sensitive actions require detailed audit logs.
- Admin sessions expire based on risk and role. Investor sessions are long-lived but revocable.
- Access tokens are short-lived.
- Refresh tokens are revocable.
- Passwords follow modern hashing and breach detection controls (platform password policy with the Have I Been Pwned range check).
- Login and permission changes create audit events.
- Investor impersonation is read-only, superadmin-only, short-lived, blocked for admin targets, and audited (ACC-DEC-005).

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
- Admin-created legal-entity lenders do not complete Didit KYC. Garanta completes and retains company KYB/AML offline; the platform requires an active, unrestricted, phone-verified representative, not a local company compliance file.
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

1. Answered by ACC-DEC-001/ACC-DEC-002 and replaced on 2026-11-19 (Phase 18.5): investors use password sign-in with a second factor and mandatory phone verification, with the assisted recovery for lost access; admins use email, password and an authenticator app; superadmin credentials are configured through environment variables.
2. Updated by ACC-DEC-001/ACC-DEC-002/ACC-DEC-008 and replaced on 2026-11-19 (Phase 18.5): investor sign-in needs the password and a second factor; sensitive/financial actions need the email code with the PIN or the authenticator app code; admin sign-in needs the authenticator app.
3. Answered by ACC-DEC-004: no legal-entity lender maker-checker approval or internal roles are required at launch.
4. Answered by ACC-DEC-004: one person cannot represent multiple investor accounts/entities at launch; borrower representative relationships are tracked only as entity data.
5. Updated by ACC-DEC-005 (2026-07-04): support impersonation exists as a read-only, superadmin-only, short-lived, audited view of investor accounts; no write-capable impersonation.
6. Updated by ACC-DEC-006 and SEC-DEC-004: account closure is requested by email support/admin, requires a clean/empty account, restricts login, retains required documents/data, and may optionally trigger reversible direct-identifier pseudonymization through an admin checkbox.
7. Answered by RPT-DEC-003: auditor/regulator direct portal access is out of launch scope; admins generate export packages offline.
8. Answered by Operating Model DEC-010: superadmin and admin.
9. Updated by KYC-DEC-001, KYC-DEC-003, KYC-DEC-008, and PAY-DEC-025: self-service registration is natural-person lenders only; legal-entity lenders are admin-created and behave like regular lender accounts once KYB/AML-approved; borrowers have no login; natural-person lenders need registration-time terms acceptance and KYC before dashboard/deposit/balance/FX/investment access.
10. Answered by COMMS-DEC-001: Twilio SMS is used for phone confirmation only; other security messaging is email-only in v1.
11. Updated by ACC-DEC-003 and ACC-DEC-008: admin sensitive actions do not require step-up authentication, but investor sensitive/financial actions require fresh email-code confirmation; detailed logs are required.
12. Answered by ACC-DEC-006/ACC-DEC-007/ACC-DEC-008: inactive accounts are not automatically locked; investor sessions are long-lived and revocable; user-visible session/device management is nice to have.
