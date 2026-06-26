# BANXUM Go-Live And Real-Money Readiness Checklist

Status: working launch runbook.
Last updated: 2026-06-23.

This checklist is the operational gate before BANXUM handles real lender money or real production KYC evidence. It complements `admin_todo_accounts.md`, `admin_todo_garanta.md`, `admin_todo_tech.md`, and `docs/runbooks/server-deployment.md`.

## 1. Go-Live Checklist

Complete these before calling any environment production-like.

- DNS and TLS:
  - Final production and staging domains point to the BANXUM server through the TLS reverse proxy.
  - Public access uses only `https://` on ports `80/443`.
  - Internal app ports such as `8081` and `8082` are not public.
  - `PUBLIC_APP_BASE_URL`, `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, cookie domain, and provider callback URLs match the final domains.
  - `SESSION_COOKIE_SECURE=true`, `CSRF_COOKIE_SECURE=true`, `SECURE_SSL_REDIRECT=true`, and `DJANGO_USE_X_FORWARDED_PROTO=true`.
- Credentials and access:
  - Any admin/superadmin passwords used during raw-IP or plaintext testing have been rotated.
  - Environment-managed superadmin is synchronized with `make bootstrap-superadmin`.
  - A dedicated scheduler service admin exists and is configured as `SCHEDULED_JOBS_ACTOR_EMAIL`.
  - `QA_DEV_MODE_ALLOWED=false` in production, and the QA mode admin panel is not used against real
    customer data.
  - Production server and database access are limited to authorized tech users.
- Database, cache, and backups:
  - Production and staging PostgreSQL databases/users/volumes are separate.
  - Redis/cache is shared per environment, not in-process memory, so throttles work across workers.
  - Full backend suite has passed against PostgreSQL.
  - `make test-postgres-hardening` has passed against a disposable/Postgres test database.
  - Daily encrypted backup is configured and a restore drill has been performed.
- Provider settings:
  - Didit is in API mode with real workflow ID, webhook signing secret, signed webhooks required, and public callback URL.
  - SendGrid is authenticated for the sender domain and can deliver transactional mail from the approved sender.
  - Twilio Verify has a live service SID, credentials, spending/fraud controls, and country policy.
  - Yahoo Finance adapter is the active FX provider outside local/test; mock FX is disabled.
- Platform settings:
  - CHF collector account: `Garanta_CHF`, IBAN `CH1183019GARANTAFI001`, QR IBAN `CH8330334GARANTAFI001`, BIC `YAPECHZ2`.
  - EUR collector account: `Garanta_EUR`, IBAN `CH8183019GARANTAFI002`, BIC `YAPECHZ2`.
  - CHF QR payload is the verified payload in `docs/payment-assets/chf-collector-qr-payload.txt`.
  - EUR has no supplied QR payload; investors see IBAN/BIC plus their BANXUM payment reference.
- Legal and documents:
  - Registration lender user agreement template is counsel-approved, imported, reviewed in Superadmin Settings, and published.
  - Primary-market project investment confirmation / claim-assignment template is counsel-approved, imported, reviewed, and published.
  - Secondary-market buyer/listing terms are approved and published before enabling secondary-market actions. `seed_demo` currently publishes temporary placeholder buyer/listing terms only when no current secondary-market template exists, so private testing can exercise the flow; these placeholders are explicitly not approved production legal content.
  - Generated agreement PDFs/CSVs are rendered on demand from immutable acceptance evidence and are downloadable from investor Documents plus the admin Users document-history modal. Legal terms and transaction-agreement PDFs are not emailed by default.
- Communications and monitoring:
  - Scheduled jobs are installed for email dispatch, daily balance ageing/penalty charging, servicing status scan, campaign expiry scan, and reconciliation-break task sync.
  - `check_scheduled_jobs` runs at least every 15 minutes and alerts on non-zero exit.
  - Failed email/outbox queues are visible in the admin dashboard.
  - Operational mailbox owners are assigned for support, tech alerts, provider alerts, and DMARC reports.

## 2. Admin Operations Checklist

Use this as the daily operating checklist once the environment is live.

- Dashboard:
  - Open Daily dashboard.
  - Work queues in priority order: overdue SLA, urgent/high priority, reconciliation breaks, failed emails, KYC reviews, withdrawals/forced withdrawals, bank exceptions, balance ageing, servicing due, funding loans, secondary approvals, FX settlement.
  - On the Reconciliation breaks queue, use `Create tasks` so breaks become trackable admin tasks.
- Compliance:
  - Review Didit/KYC manual-review cases.
  - Record AML decisions only after provider evidence is checked.
  - Use account access controls for restrict/lock/close/reactivate, with reason, note, and evidence summary.
  - Do not approve sanctions/declined cases through manual review.
- Finance:
  - Match lender deposits from bank statements using the `BX-{currency}-{investor_reference}` reference first.
  - Verify collector account/currency/value date against the bank line.
  - Register verified payout IBANs before finalizing withdrawals or expecting day-60 forced withdrawals to succeed.
  - Run balance-ageing scan as dry-run first, then live only after the preview is understood.
  - Create reconciliation snapshots after bank-operation batches and investigate every break/anomaly.
  - Finalize withdrawals and borrower disbursements only after the external bank transfer is actually executed.
  - Declare external FX settlement after comparing internal delta and realized bank execution.
- Loans and marketplace:
  - Publish only approved-KYB/no-hold borrowers.
  - Keep funding deadlines inside the publishable campaign window.
  - Cancel expired campaigns through the campaign-expiry scan or manual cancellation.
  - Close funding only after confirming allocations/accepted amount.
  - Record borrower repayments with exact value date and warning acknowledgement for irregular payments.
  - Record recoveries only for defaulted loans and use final loss recognition only after Garanta/legal/accounting approval.
- Reports and documents:
  - Generate report artifacts with the least redaction level needed.
  - Use Full/unredacted mode only when authorized.
  - Download generated PDFs/ZIPs through the artifact download button and record destination notes.
  - Use Superadmin Settings to verify legal templates are current before onboarding/investment testing.
- Superadmin:
  - Create admin users only for named staff with a real operational need.
  - Rotate credentials when staff leave or when credentials were exposed in testing.
  - Keep template publication tied to a legal-review reference.

## 3. Provider Validation Checklist

Run these checks in staging before production, and again in production before real users.

- SendGrid:
  - Sender domain DNS authentication is green in SendGrid.
  - DMARC has exactly the intended policy record; remove duplicate/conflicting DMARC records before production.
  - Magic-link email is delivered to a real mailbox and the link is clickable.
  - Admin email-code login is delivered within the expected latency.
  - Sensitive-action email code is delivered and not exposed in portal notifications.
  - Legal-document acceptance does not enqueue/send PDF attachments; any legacy document-acceptance email outbox row renders as a portal notice with no attachment.
  - Bounce/suppression handling is visible in SendGrid activity logs.
- Twilio Verify:
  - Start verification succeeds for a Swiss number and for at least one allowed EEA test number.
  - Re-send cooldown appears in the UI and Twilio does not send duplicate messages during cooldown.
  - Wrong-code attempts are capped and persisted.
  - Correct code verifies the phone and activates the next onboarding step.
  - Failed provider responses are shown as actionable user-facing errors, not raw 500s.
- Didit:
  - Hosted session opens from the investor onboarding flow.
  - Successful verification webhook is received, signature-verified, and activates the lender without manual database work.
  - Manual-review/failure webhook routes to the Compliance queue.
  - Repeated webhook delivery is idempotent.
  - Provider report identifiers are stored; report download/export remains tracked if not yet automated.
- Yahoo Finance FX:
  - CHF/EUR and EUR/CHF quotes issue from the real adapter.
  - Weekend/holiday/stale-rate behavior is intentionally fail-closed unless Garanta approves a different policy.
  - Sanity checks reject rates outside configured absolute bounds or previous-close deviation.
  - Mock provider is unavailable outside local/test.
- Bank/collector accounts:
  - CHF instructions show IBAN, QR IBAN, BIC, payment reference, and QR image.
  - Scan the generated CHF QR and compare it to `docs/payment-assets/chf-collector-qr-payload.txt`.
  - EUR instructions show IBAN, BIC, and payment reference but no QR until an EUR QR payload is supplied.
  - Incoming test transfers can be matched by `BX-{currency}-{investor_reference}`.

## 4. What To Test Before Real Money

Run this as an end-to-end staging rehearsal with test users and small provider-safe amounts before enabling real lender funds.

- Investor onboarding:
  - Register a new lender.
  - Accept the generated lender user agreement.
  - Verify phone through Twilio.
  - Complete Didit verification on another device and confirm the waiting screen unlocks without a broken dashboard.
  - Confirm the investor can log out/log in and resume the correct onboarding or portal state.
- Deposit and balance:
  - View CHF/EUR deposit instructions and payment references.
  - Declare a CHF test deposit from a bank-statement line.
  - Confirm dashboard balance, balance lots, ageing deadlines, and deposit notification.
  - Run a dry-run ageing scan and verify no unintended money movement.
- Primary investment:
  - Publish a test borrower/loan with valid KYB and funding deadline.
  - Place an investment order with automatic email-code issuance.
  - Accept project investment confirmation and download the generated PDF.
  - Allocate, close funding, and verify holding creation.
  - Confirm the loan no longer accepts release/cancel actions after close.
- Loan servicing:
  - Finalize borrower disbursement after bank-side payout.
  - Record an on-time repayment.
  - Confirm investor balance lot credit, holding principal reduction, and repayment notification.
  - Run servicing scan and confirm late/default transitions on controlled test loans.
- Withdrawals and ageing:
  - Register a payout instruction.
  - Request an investor withdrawal with email code.
  - Finalize and cancel separate test withdrawals.
  - Test day-60 forced-withdrawal behavior with and without verified IBAN.
  - Test daily penalty charging only after Garanta has approved the policy.
- Secondary market and FX:
  - List a holding, cancel the seller listing, relist, and approve a non-standard listing.
  - Purchase a listing and confirm buyer/seller anonymity in UI and emails.
  - Issue and execute an FX quote using Yahoo rates; declare external FX settlement and verify reconciliation remains balanced.
- Documents and reports:
  - Download lender user agreement and project investment confirmation PDFs from the investor portal.
  - Open the admin Users document-history modal for the same investor and generate the accepted-document PDF from there; verify the rendered artifact is audit-attributed to the admin actor.
  - Generate redacted and full admin reports as allowed by role.
  - Verify report checksums, PDF formatting, and audit-log entries.
  - Generate participant account statement and annual tax report for the test investor.
- Integrity and operations:
  - If QA time travel was used in staging, revert the QA database snapshot or rebuild staging before
    treating the environment as a clean rehearsal.
  - Create reconciliation snapshot and confirm zero difference for the controlled scenario.
  - Force a known reconciliation break in staging only and confirm dashboard/task sync surfaces it.
  - Confirm scheduled jobs run, failures alert, and `check_scheduled_jobs` is green.
  - Confirm backups are created and one restore drill has been performed.
