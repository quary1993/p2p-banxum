# Admin TODO: Accounts, Credentials, API Access, and Domains

Status: Working list.
Last updated: 2026-06-01.

This file tracks accounts, credentials, API access, domains, portals, and third-party access that must be provided to make the platform functional.

Blocking means the related integration or deployment module cannot be completed with real services until the item is provided. In most cases, engineering can continue with mocks, local fixtures, or sandbox placeholders, but the real integration cannot be finished.

## Blocking

### Didit KYC/AML Account and API Access

Blocks: real Didit sandbox integration for identity, KYC, AML, registration-time onboarding, and webhook handling.

Provide:

- Didit sandbox account access.
- Sandbox API credentials.
- Sandbox webhook signing secret or verification configuration.
- Confirmation that staging/sandbox Didit webhooks are signed and that the platform should reject unsigned sandbox/staging webhooks.
- Didit workflow ID for natural-person lender onboarding.
- Confirmation of the chosen Didit flow: hosted redirect, iframe, SDK, or mixed flow.
- Callback/webhook URL requirements from Didit.
- Didit event names/statuses that the platform should consume.
- Didit report download/export API or console access, including provider report identifiers and downloadable metadata fields.
- Didit raw webhook payload/event documentation, including retention limitations if any.
- Test users or test documents supported by the Didit sandbox.
- Didit console users who can download provider-native KYC/AML reports.

Why this is needed:

The software can implement a mock Didit adapter without these credentials, but it cannot complete real sandbox session creation, webhook verification, or status mapping against Didit until sandbox access and workflow details exist. Production credentials are listed below as non-blocking because they are needed for launch, not for module implementation.

Current implementation boundary:

- Implemented without Didit account access:
  - internal KYC case/session/event storage.
  - mock Didit session URLs.
  - signed generic webhook ingestion boundary.
  - internal status normalization for known/common provider words and AML flags.
  - manual-review queue and append-only admin decisions.
  - account activation after approved KYC.
  - account restrict/lock/close/reactivate controls for Garanta admins.
  - append-only audit/evidence records and DB-level append-only guards.
- Still blocked by missing Didit sandbox/account details:
  - real Didit session creation API calls.
  - exact Didit workflow ID and workflow routing.
  - exact redirect/iframe/SDK behavior and callback URLs.
  - exact webhook signature headers, freshness/timestamp behavior, event names, payload fields, retry behavior, and status vocabulary for Garanta's configured workflow.
  - provider report download/export API integration.
  - provider report metadata, file checksum, local object-storage persistence, and report inclusion in evidence exports.
  - sandbox test users, test documents, and negative test scenarios.
  - end-to-end tests against Didit sandbox or production.
  - Didit ongoing-monitoring alert ingestion, if Garanta later wants platform-side ingestion rather than off-platform review and manual account controls.

### SendGrid Transactional Email Account

Blocks: real sandbox/staging email delivery for magic-link login, admin email-code login, investor sensitive-action email codes, and transactional notices.

Provide:

- SendGrid account access.
- SendGrid transactional email API key for sandbox/staging if available.
- Verified sender identity.
- Sender domain decision.
- DNS access or DNS records needed for sender authentication.
- Default from-name and from-address.
- Reply-to address, usually the support email.
- SendGrid sandbox/test-mode approach for staging.
- Access to SendGrid activity logs, bounces, suppressions, and delivery metadata.

Why this is needed:

The app relies on email for login and sensitive-action confirmation. Without transactional email access, the auth and notification modules can only be tested through a local mail sink or mock adapter. Production API keys are launch inputs, not implementation blockers.

### Twilio Phone Verification Account

Blocks: real sandbox/staging phone verification.

Provide:

- Twilio account access.
- Twilio Verify service SID or equivalent service configuration.
- Twilio sandbox/staging API credentials.
- Sandbox/test configuration if available.
- Allowed countries/phone formats.
- SMS spending limits.
- Retry limits or fraud-prevention limits configured in Twilio.

Why this is needed:

Phone verification is mandatory for natural-person lenders. The module can be mocked locally, but real sandbox verification cannot be completed without Twilio access and country/rate-limit configuration.

### FX Rate Provider Access

Blocks: real currency-exchange quotes and FX sanity-check integration.

Provide:

- Yahoo Finance access method/API endpoint to be used by the platform.
- API credentials if required by the chosen Yahoo Finance access method.
- Base URL and endpoint documentation.
- Supported launch currency pairs: CHF/EUR and EUR/CHF.
- Provider rate timestamp semantics.
- API rate limits.
- Terms-of-use approval for platform use.
- Fallback provider or reference source only if Garanta later wants one; not required for launch.

Why this is needed:

The FX module can be implemented against the Yahoo Finance adapter interface, but production executable quotes, background display rates, rate sanity checks, and provider failure behavior need the real access method and terms confirmation.

### Bank/Payment Partner and Banking Access

Blocks: real deposit instructions, production bank statement/export configuration, withdrawal evidence, collection account setup.

Provide:

- Bank/payment partner name.
- CHF collection account/IBAN.
- EUR collection account/IBAN.
- Account holder names exactly as shown by the bank.
- Supported payment rails for CHF and EUR.
- Bank portal access for authorized finance/admin users, if the platform team must observe statement exports.
- Statement export formats available from the bank.
- Example bank statements for CHF and EUR.
- Final bank-compatible payment reference format.
- Any bank constraints on payment reference length, characters, or QR/payment slips.
- Evidence files Garanta expects admins to upload for lender deposits, lender withdrawals, borrower loan disbursements, borrower repayments, Garanta out, Garanta in, and FX external settlement.

Why this is needed:

The platform can build generic manual bank-operation declaration and reconciliation screens from the documented operation taxonomy. Production payment instructions and any bank statement parsing/export support depend on the selected bank and its formats.

### AWS and Hosting Access

Blocks: real staging/prod deployment.

Provide:

- AWS account access.
- Billing owner/contact.
- IAM model: who can create infrastructure, deploy, rotate secrets, and view logs.
- AWS `eu-central-2` Europe (Zurich) region must be enabled and usable in the account.
- Access/permission to create one EC2 host, encrypted EBS volumes, private S3 buckets, ECR repositories, IAM roles/policies, CloudWatch Logs where used, Route 53 records if DNS is hosted in AWS, and backup lifecycle rules.
- Swiss-controlled storage is expected to be AWS Zurich S3 in the same account unless Garanta chooses a separate Swiss-controlled storage account/provider.
- Access to DNS/domain records if hosted in AWS Route 53.
- Confirmation whether Garanta already has a VPC/subnet/security-group baseline that must be reused; otherwise engineering will create a minimal cost-optimized VPC/security-group setup.
- Backup storage account/location only if Garanta does not want to use the dedicated private AWS Zurich S3 backup bucket.

Why this is needed:

Local implementation can continue without AWS. Staging/prod infrastructure, backups, storage, domains, and deployment automation cannot be completed without cloud access.

### GitHub and Deployment Access

Blocks: CI/CD implementation and automated deployment.

Provide:

- GitHub organization/repository access.
- Users or teams that can approve repository settings.
- GitHub Actions secrets access.
- AWS ECR repository access for staging/production images.
- Deployment target credentials.
- Deployment secret values or approval for engineering to generate and install them, including Django secret keys, auth delivery-secret encryption keys, auth digest peppers, database passwords, Redis passwords where applicable, and provider webhook secrets.
- Branch protection expectations, if Garanta wants them.
- Permission to configure GitHub Actions OIDC access to AWS if available.

Why this is needed:

Engineering can scaffold CI locally, but working CI/CD and deployment secrets require repository and environment access.

### Domains and DNS

Blocks: production web app, Didit callbacks, SendGrid domain authentication, Twilio/Didit callback URLs if domain-specific.

Provide:

- Public domain name for the platform.
- Staging subdomain.
- Production app subdomain.
- Admin portal subdomain or route preference, if separate.
- DNS provider access or the person responsible for adding records.
- Sender domain for SendGrid.
- Any domain branding restrictions.

Why this is needed:

Provider callbacks, authenticated email sending, TLS, and production routing require actual domain names and DNS records.

## Non-Blocking

### Production Provider Credentials

Needed before production launch.

Provide:

- Didit production account access and production API credentials.
- Didit production webhook signing secret.
- Confirmation that production Didit webhook signatures are enabled and must be required by the platform.
- Didit production report download/export permissions.
- Didit production webhook/report retention settings.
- SendGrid production transactional email API key.
- Twilio production API credentials.
- Yahoo Finance production API credentials if the selected access method separates sandbox/test and production.

Why this is non-blocking:

Implementation can proceed with local mocks and sandbox credentials. Production credentials should be added only when production infrastructure and secret handling are ready.

### Support Mailbox

Needed before production support links and email reply-to settings are finalized.

Provide:

- Public support email address.
- Support mailbox/provider access.
- Operational owner of the support inbox.
- Reply-to address for transactional emails.
- Whether support email should appear in footer, FAQ, help page, or all of them.

Why this is non-blocking:

The app can use placeholder support text and a configurable support-email setting during implementation. The real mailbox is needed before production launch.

### Didit Ongoing Monitoring Console Ownership

Needed before production compliance operations if Didit ongoing monitoring is enabled.

Provide:

- Who monitors Didit ongoing-monitoring alerts.
- Whether Didit sends alerts by email or only in-console.
- Which Garanta admin records account restrictions after off-platform review.

Why this is non-blocking:

The v1 platform does not consume ongoing-monitoring webhooks automatically. It only needs manual admin actions when Garanta decides to restrict or close an account.

### SendGrid Marketing Lists

Needed for future newsletter/marketing workflows.

Provide:

- SendGrid list/audience names.
- Marketing sender identity if different from transactional sender.
- Unsubscribe/suppression sync rules.

Why this is non-blocking:

V1 only captures marketing consent. Active newsletter sending is not required for launch.

### Bexio Accounting System Credentials

Needed only if Garanta later wants direct Bexio API integration.

Provide:

- Bexio account/API access, if direct import/API integration is desired.
- Bexio test company or sandbox account, if available.
- Bexio API documentation and app credentials if Garanta wants the platform to push exports directly later.

Why this is non-blocking:

V1 exports Bexio-ready accounting data as PDF/CSV. No direct Bexio API integration is required.

### Future Bank-Feed Credentials

Needed only if Garanta later automates bank reconciliation.

Provide:

- Bank API credentials.
- Open banking provider credentials.
- Bank-feed sandbox access.

Why this is non-blocking:

Launch reconciliation is manual. The software should keep adapter boundaries ready, but no live bank feed is required for v1.

### Optional Observability or APM Accounts

Needed only if Garanta chooses external observability tooling.

Provide:

- Sentry, Datadog, New Relic, Grafana Cloud, or similar account access if selected.

Why this is non-blocking:

Launch requires rich structured logs, AWS-native/local log retention, and tech-team email alerts. Sophisticated observability is not required.

### Cloud Secret Manager or Vault Account

Needed only if env-based secrets become insufficient.

Provide:

- AWS Secrets Manager, Vault, Doppler, 1Password Secrets Automation, or other chosen secret tooling.

Why this is non-blocking:

Launch plan uses restricted environment files/environment variables on the host. A cloud secret manager is future scope if env-based secrets become insufficient.
