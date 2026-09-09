# BANXUM Go-Live And Real-Money Readiness Checklist

Status: working launch runbook.
Last updated: 2026-09-07.

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
  - `DJANGO_ADMIN_ENABLED=false` and `API_DOCS_ENABLED=false` outside explicitly isolated local development; `/admin/django/`, `/api/docs/`, and `/api/schema/` return 404 publicly.
- Database, cache, and backups:
  - Production and staging PostgreSQL databases/users/volumes are separate.
  - Redis/cache is shared per environment, not in-process memory, so throttles work across workers.
  - Full backend suite has passed against PostgreSQL.
  - `make test-postgres-hardening` has passed against a disposable/Postgres test database.
  - Daily encrypted off-host backup is configured with `infra/deploy/backup_postgres.sh`, `BANXUM_BACKUP_REQUIRE_OFFSITE=true`, and a private Zurich-region S3 destination.
  - `infra/deploy/check_backup_freshness.sh` is monitored and a restore drill into a disposable database has been performed.
- Provider settings:
  - Didit is in API mode with real workflow ID, webhook signing secret, signed webhooks required, and public callback URL.
  - Twilio Email API is authenticated with a dedicated API-key SID/secret; the sender domain is approved and transactional mail reaches a real mailbox.
  - Twilio Verify has a live service SID, credentials, spending/fraud controls, and country policy.
  - Yahoo Finance adapter is the active FX provider outside local/test; mock FX is disabled.
- Platform settings:
  - CHF collector account: `Garanta_CHF`, IBAN `CH1183019GARANTAFI001`, QR IBAN `CH8330334GARANTAFI001`, BIC `YAPECHZ2`.
  - EUR collector account: `Garanta_EUR`, IBAN `CH8183019GARANTAFI002`, BIC `YAPECHZ2`.
  - CHF QR payload is the verified payload in `docs/payment-assets/chf-collector-qr-payload.txt`.
  - EUR has no supplied QR payload; investors see IBAN/BIC plus their BANXUM payment reference.
- Demo and QA data:
  - No published/open opportunity title starts with `Demo - ` or `Demo LO - `. Direct-loan demo
    campaigns have been cancelled through the normal funding-cancellation flow and demo Loan
    Originator opportunities have been placed on hold before real lender money is accepted.
  - The deploy workflow's `seed_marketplace_demo_loans` and `seed_originator_demo_loans` options are
    disabled for ordinary and go-live deployments; they are explicit private-QA actions, not
    production reference-data seeding.
  - Demo financial records and their append-only evidence are not removed with direct database
    deletes. Rebuild an environment when a completely clean QA dataset is required.
- Legal and documents:
  - Registration lender user agreement template is counsel-approved, imported, reviewed in Superadmin Settings, and published.
  - Primary-market project investment confirmation / claim-assignment template is counsel-approved, imported, reviewed, and published.
  - Secondary-market buyer/listing terms and the generic risk disclosure are counsel-approved and published before enabling those actions. `seed_demo` may publish temporary placeholders only when an operator runs it deliberately for private testing; deployed startup runs `seed_reference_data` and never creates legal templates.
  - Existing private-test placeholder template versions are replaced by counsel-approved current versions before real-money use; stopping automatic seed does not make already-published placeholders legally valid.
  - Generated agreement PDFs/CSVs are rendered on demand from immutable acceptance evidence and are downloadable from investor Documents plus the admin Users document-history modal. Legal terms and transaction-agreement PDFs are not emailed by default.
  - Loan Originator subscription wording has counsel approval for: reservation
    during finite funding, no investor accrual during funding or on the boundary
    installment, automatic activation at successful funding close, par principal,
    separate interest/penalty participation, preserved reservations on close failure,
    cancellation with restoration of original lots and deadlines,
    no recourse/buyback, Garanta servicing, and secondary transfer at par/discount.
- Loan Originators:
  - Each enabled originator has current off-platform KYB/AML evidence, an internal
    risk decision, active status, verified settlement account name/IBAN/BIC, an
    operations owner, and approved subscription/component-participation terms.
  - Finance/accounting approves funding-escrow, activation originator-payable,
    servicing-payable, and external-settlement account mappings in each currency.
  - Day-3 settlement tasks and day-5 escalation are monitored. Operations has a
    named backup approver/operator for every settlement day.
  - The strict import examples in `imports_examples/` have been reconciled against
    each originator's real export format; no spreadsheet formulas or decimal money
    values enter the import boundary.
  - New refinancing-loan creation remains disabled. Existing legacy refinancing
    records remain readable/serviceable and are not silently converted.
- Privacy and retained evidence:
  - Didit/KYC raw provider payloads are field-encrypted or moved to restricted Swiss evidence storage before production KYC retention; encrypted disks alone are not the final control.
  - Closure-time reversible pseudonymization, offline private-key custody, and the recovery procedure are implemented and tested before processing a production closure request.
  - Production data is never copied to staging without an approved anonymization/pseudonymization process.
- Communications and monitoring:
  - Scheduled jobs are installed for email dispatch, daily balance ageing/penalty charging, servicing status scan, campaign expiry scan, reconciliation-break task sync, Loan Originator settlement-task sync, and Loan Originator opportunity/activation lifecycle scan.
  - `check_scheduled_jobs` runs at least every 15 minutes and alerts on non-zero exit.
    Verify missing job history, overdue success, failed runs and stuck runs all fail;
    a dry run must not satisfy successful execution coverage or suppress a real run.
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
  - Review the originator settlement queue by currency every business day. Reconcile
    activated subscription and servicing items, payable, oldest age, and selected
    references before executing the external transfer.
  - Settle the complete selected originator batch; v1 does not support arbitrary
    partial settlement. Record bank/payment/evidence references only after the
    external transfer has executed.
  - Escalate day-3 originator payable tasks immediately and never allow the oldest
    unsettled item to exceed five calendar days.
- Loans and marketplace:
  - Confirm company KYB offline before publication. No platform KYB file is required; explicit borrower holds and declined/manual-review decisions must block publication.
  - Verify PAY-DEC-031 admission checks, short/long-window source selection, same-day close-before-ageing ordering, and automatic retries. A persistent failed close is an urgent technical incident; the available-balance sweep does not cover reserved escrow.
  - Keep funding deadlines inside the publishable campaign window.
  - Confirm each direct loan's minimum subscription (default 50%) before publication; publication freezes it even when no commitment exists yet.
  - Run the funding-deadline resolver: at/above the threshold it closes automatically at the subscribed amount; below it, it cancels and restores reservations.
  - Confirm `funding_close_failed` loans are not public, retain reservations, create an urgent task, and send an alert to `OPERATIONS_ALERT_EMAIL`.
  - Repair failed-close causes promptly and verify the scheduled retry succeeds. Do not choose a different funding outcome, release individual reservations after deadline, or cancel a threshold-qualified direct loan.
  - Record borrower repayments with exact value date and warning acknowledgement for irregular payments.
  - Record recoveries only for defaulted loans and use final loss recognition only after Garanta/legal/accounting approval.
  - For a current originator claim, verify originator status/settlement instructions,
    anonymized borrower disclosure, funding deadline, boundary installment and
    resulting principal, coupon, interest/penalty participation, minimum investment,
    retention, current outstanding principal, import as-of date, and maturity.
  - Put an originator opportunity on hold for any contract/import/bank discrepancy.
    Do not edit amounts merely to make an import validate.
  - Record an originator repayment only with a replacement CSV that preserves every
    prior payment and adds exactly the declared new bank payment.
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

- Twilio Email API:
  - Sender domain DNS authentication is green in the Twilio Console.
  - `COMMUNICATIONS_EMAIL_PROVIDER=twilio_email`; email API-key credentials are separate from Twilio Verify credentials.
  - DMARC has exactly the intended policy record; remove duplicate/conflicting DMARC records before production.
  - Magic-link email is delivered to a real mailbox and the link is clickable.
  - Admin email-code login is delivered within the expected latency.
  - Sensitive-action email code is delivered and not exposed in portal notifications.
  - Legal-document acceptance does not enqueue/send PDF attachments; any legacy document-acceptance email outbox row renders as a portal notice with no attachment.
  - The asynchronous operation reaches `COMPLETED`, and the recipient email reaches `DELIVERED` rather than only receiving HTTP 202.
  - Bounce/suppression handling is visible in Twilio Email activity/operation records.
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
- Loan Originator operations:
  - An allocated order creates one reservation and no holding, entitlement, or
    originator payable. Exact replay creates no duplicate reservation.
  - Full subscription closes automatically; the deadline scan closes any positive
    partial round and cancels an empty round. Successful close creates one
    holding/purchase/entitlement set per allocated order and one
    escrow-to-originator-payable journal in the same transaction. The boundary
    installment is excluded from every investor projection and distribution.
  - Published schedule inconsistency or an explicit hold prevents close. A close
    failure hides the offer, preserves reservations and creates an urgent task/email.
    Cancellation refunds the original lots; retry must not change accepted economics.
  - Opportunity access fails closed for inactive/blocked originators, holds,
    late/default/repaid loans, no sellable principal, stale revisions, invalid
    funding dates, and invalid activation terms.
  - Day-3 task generation and day-5 overdue severity work under the scheduler/QA
    clock, and a completed batch cannot settle the same items twice.

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
  - Publish a test borrower/loan after offline company KYB, with no explicit hold or
    adverse decision, and with a funding deadline no later than the 50th inclusive subscription date.
  - Place an investment order with automatic email-code issuance.
  - Accept project investment confirmation and download the generated PDF.
  - Allocate above the configured minimum, advance past the deadline/run the resolver, and verify automatic close plus holding creation.
  - Repeat below the threshold and verify cancellation plus exact reservation restoration.
  - Exercise a controlled resolution failure and verify the non-public failure status, preserved reservations, urgent task, operations email, and successful retry.
  - Confirm the loan no longer accepts release/cancel actions after close.
- Loan Originator claim:
  - Import and publish one controlled loan for every enabled repayment type, plus a
    loan with a historical advance payment.
  - Confirm the public opportunity shows Loan Originator, underlying coupon, nominal
    participating yield, separate interest/penalty participation, minimum investment,
    funding deadline, maturity, retention, and approved anonymized borrower fields.
  - Allocate a non-round at-par subscription and confirm balance-lot conservation,
    one escrow reservation, no holding, no investor accrual, and no originator payable.
  - Repeat with the same idempotency key and confirm no duplicate financial/evidence
    records. Confirm full subscription auto-closes and positive partial funding closes
    only through deterministic deadline resolution.
  - Verify successful close immediately creates holdings, post-boundary entitlements,
    originator payable and downloadable evidence, without an activation task or bank import.
    A failure anywhere in that transaction must leave no partial holding or settlement.
  - Record the real boundary payment later. Confirm every component belongs to the
    LO, investor balances are unchanged, and the original entitlement schedule remains intact.
  - Test historical closed reservations from the previous release: healthy records
    upgrade from original evidence without invented bank receipts; held/inconsistent
    records create an immediate repair task/email and do not starve later scan entries.
  - Test a partial/changed payment through servicing and reject unapproved removal of
    future interest/penalty from a regular-payment import. Simulate close failure and
    verify urgent task/email/retry. Cancellation restores original lots and ageing dates.
  - Record regular and advance payments through replacement imports.
    Reconcile principal ownership and separate investor interest/penalty participation
    plus originator servicing payable to every imported component exactly.
  - Transfer a performing originator holding on the secondary market. Confirm the
    buyer sees current projected returns but never seller acquisition economics;
    confirm premium listing is rejected for a current originator holding and a
    late/defaulted originator holding cannot be listed in v1.
  - Run Finance Ops settlement for the accumulated activation/servicing payable and
    verify reconciliation remains balanced before and after external settlement.
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
