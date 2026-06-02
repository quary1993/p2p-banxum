# BANXUM V1 Implementation Plan

Status: Implementation blueprint, agent-optimized.
Last updated: 2026-06-01.

This document turns the completed `/plan` documentation into an engineering implementation plan for the first production version of BANXUM.

The plan assumes Garanta Finanzgruppe AG operates the platform as a Swiss VQF-affiliated entity for the documented activities, and that the final legal, banking, accounting, technical, account/access, and provider-specific TODOs will be closed before handling real client money. The TODOs are split into `admin_todo_garanta.md`, `admin_todo_accounts.md`, and `admin_todo_tech.md`.

Authoritative business timezone: Europe/Zurich. Store timestamps in UTC, but calculate and render business deadlines, reminders, funding cutoffs, late/default statuses, penalties, day buckets, and reports using Europe/Zurich unless a module explicitly overrides it.

## 0. Documentation Policy

Canonical documentation is intentionally small:

- `/plan/*.md`: product, compliance, and operating-model decisions from the Q/A process.
- `IMPLEMENTATION_PLAN.md`: engineering architecture, module order, implementation status, durable deferrals, and technical decisions.
- `AGENTS.md`: short working rules and command guide for coding agents.
- `admin_todo_garanta.md`, `admin_todo_accounts.md`, and `admin_todo_tech.md`: unresolved or go-live TODOs by audience.
- `docs/runbooks/*`: operational procedures that must stay executable.
- `docs/claude-design/TODO.md`: UI/UX polish handoff items.

Resolved audits, completed work-item specs, boilerplate module READMEs, and temporary notes should not remain as separate files. Durable decisions from those artifacts must be merged into the canonical documents above, then the temporary file should be deleted.

## 0.1 Implementation Status

Implemented and committed:

- Phase 0 bootstrap: Django/React scaffold, CI, `make agent-check`, OpenAPI generation, generated frontend client, MSW setup, import-boundary checks, local Docker Compose, and app smoke tests.
- Phase 1 platform core foundation: currency registry, money/rate/time primitives, platform settings, audit events, domain events, outbox retry/idempotency, stored-file metadata/access checks, and DB-level append-only guards.
- Phase 2 first accounts/auth slice: custom user model, natural-person lender registration record, registration terms acceptance evidence, magic-link login tokens, sensitive-action email codes, basic session auth API endpoints, and focused tests.
- Phase 2 phone-verification foundation: authenticated phone verification request/confirm API, phone challenge records, encrypted local/mock verification codes, SMS outbox trigger without plaintext code payload, cooldown/attempt controls, audit/domain events, and focused tests.
- Phase 2 KYC compliance foundation: user KYC case/session/event records, mock Didit hosted-session creation, signed Didit webhook processing, provider-status normalization, KYC financial-access gate, audit/domain events, authenticated status/session API, and focused tests.
- Phase 2 admin-auth foundation: environment-managed superadmin bootstrap, superadmin-created admin accounts, admin email/password plus email-code login, investor/admin portal login separation, admin-auth throttles, audit/domain events, and focused tests.
- Phase 2 KYC/manual-control foundation: internal KYC manual-review queue, append-only manual-review decision evidence, admin review decision API, account restrict/lock/close/reactivate controls, append-only account access events, DB-level evidence guards, account activation after approved KYC, and focused tests.

Accepted implementation deferrals from the platform-core audit:

- Numeric balance penalty settings are deferred to the ledger/balance-ageing module because penalties must be posted through ledger entries, ageing lots, and accounting metadata. Until then `balance.penalty_policy_display` is display-only.
- Migration-seeded default platform settings are deferred to the admin/settings module because several launch settings remain deployment-specific. Until a verified settings bootstrap gate exists, deployments must run the seed command after migrations.
- Outbox claim/dispatch with `select_for_update(skip_locked)` is deferred to the background worker module. The current module owns the durable record, retry schedule, and idempotent enqueue behavior.
- Stored-file `infected`/`failed` scan transitions and audit events are deferred to the storage/scanner adapter module.
- Strict setting `value_type` schema validation is deferred to the superadmin settings UI and settings registry module.
- Real Twilio dispatch/verification-provider execution is deferred until the communications/provider worker slice because Twilio sandbox credentials, Verify service configuration, and delivery-webhook handling are external inputs. The current accounts slice records the auditable challenge and queues a redacted SMS outbox message.
- Real Didit session creation, report download, provider artifact storage, and provider-native status mapping are deferred until Didit sandbox credentials, workflow IDs, webhook signing details, and report/export API behavior are available. The current KYC slices provide the internal status/evidence backbone, mock session URLs, signed webhook ingestion boundary, manual-review workflow, and account-control gates.
- Didit-specific items that cannot be implemented or fully tested yet:
  - real hosted-session creation against Garanta's Didit sandbox or production account.
  - exact Didit workflow ID selection and country/risk/product workflow routing.
  - exact redirect/iframe/SDK callback behavior.
  - exact webhook header names, timestamp/freshness rules, event names, event payload shape, and retry behavior beyond the current HMAC-compatible generic mock.
  - exact provider status mapping against Garanta's configured Didit workflow.
  - provider-native report download/export API calls, report metadata capture, file checksums, local object-storage persistence, and evidence package inclusion.
  - Didit sandbox test-user/test-document scenarios.
  - provider-side ongoing-monitoring alert ingestion; v1 still expects Garanta to review Didit alerts in Didit/off-platform and record account controls manually in BANXUM.
  - end-to-end provider tests from registration to Didit completion to webhook to downloaded report retention.

Recent audit dispositions:

- Phone verification confirm ownership was fixed by binding confirmation to the authenticated user in the service layer and adding cross-user regression tests.
- Phone verification confirm throttling was added as defense in depth. Magic-link consume remains unthrottled because it uses single-use 256-bit tokens; this is low severity and not worth patching until a broader auth-abuse throttle pass.
- Staging and production throttle cache behavior was closed by defaulting `CACHE_URL` to shared `REDIS_URL` outside local environments. Local in-memory cache remains acceptable for development and tests.
- `PhoneVerified` domain-event idempotency was changed from per-user to per-challenge so future phone re-verification does not get deduplicated accidentally.
- Short-lived auth secret encryption/digest fallback to `SECRET_KEY` is accepted for local development. Production and staging should set dedicated `AUTH_DELIVERY_SECRET_ENCRYPTION_KEY` and `AUTH_SECRET_DIGEST_PEPPER`; rotating `SECRET_KEY` may invalidate in-flight short-lived tokens/codes if those dedicated values are absent.
- Fixed-bucket throttle windows and cache `add`/`incr` behavior are accepted for v1 as low severity. They are sufficient for abuse friction and can be replaced by a stricter distributed-rate-limit backend if launch traffic or abuse patterns justify it.
- Earlier platform-core audit items reported as still open are closed in the current codebase: outbox retry reaches the 48-hour delay and has sequence tests, append-only tables have DB triggers for PostgreSQL and SQLite, money allocation/splitting helpers have deterministic residue tests, and Zurich business-date helpers have tests.
- Registration terms hash handling is closed for the current auth scope because the server validates submitted terms against configured canonical `REGISTRATION_TERMS_VERSION` and `REGISTRATION_TERMS_HASH`. The documents/templates module will later replace the settings-backed source with persisted template/version ownership.
- Didit webhook signature enforcement was hardened. Non-local environments require a valid signature regardless of copied environment overrides, deploy checks flag missing/disabled Didit signature config, and env examples no longer pin an unsafe false value.
- KYC provider events now have both Django model/service append-only enforcement and DB-level append-only triggers for PostgreSQL/SQLite, matching the audit/domain/platform-setting version tables.
- Didit webhook `raw_payload` currently stores provider evidence as JSON in PostgreSQL. This is acceptable for the mock/internal foundation under encrypted infrastructure storage, but field-level encryption or restricted evidence-object storage is deferred to the KYC evidence-storage hardening/provider-artifact slice before production KYC data is retained.
- Domain events are the append-only internal event log. Outbox messages are required only when a workflow needs asynchronous external delivery or background-worker processing. Ledger events therefore remain `DomainEvent` records unless a later module has a concrete worker side effect, at which point that module must use `record_event_and_enqueue` or an equivalent atomic helper.
- The shared financial-access gate now lives in `platform_core.domain.access` so peer modules can use it without violating import boundaries. Natural-person lenders require active account status, verified phone, and approved KYC; legal-entity lender representatives require active account status and verified phone because their KYB is handled off-platform/admin-side. Every withdrawal, primary investment, secondary-market action, FX exchange, document-acceptance-for-transaction, and later money-moving endpoint must call this gate server-side before mutation.
- Admin authentication now has an operational backend foundation. The first superadmin is synchronized from environment variables through `bootstrap_superadmin`; regular admin users are created by an authenticated superadmin through the admin-auth API; admin login requires password plus an email code; and admin accounts are blocked from investor magic-link login.
- KYC manual review and account access controls now have an operational backend foundation. Provider outcomes that need Garanta attention open internal manual review; admins can approve review-routed cases, decline, request re-verification, or reopen; sanctions hits, provider-declined/confirmed-fraud outcomes, never-started cases, pending provider cases, expired cases, and re-verification-required cases cannot be manually approved in the current model. Admins can restrict, lock, close, or reactivate accounts with append-only evidence. Account closure currently requires admin clean-account confirmation because balances, investments, orders, payments, and ledger obligations do not exist yet; when those modules are implemented, closure must system-verify a zero/clean account before accepting admin confirmation. `restricted` and `locked` both block account access in the current backend; a later UX/policy pass may distinguish restricted read-only access from full lockout if Garanta wants that distinction.
- Phase 3 admin-ops task queue foundation is implemented as backend/API only. Admins can create, list, filter, update, and inspect operational tasks with type, priority, assignment, due date/SLA, related object, notes, status, and completion fields. Task lifecycle evidence is append-only at the application and database levels. Admins can query audit events through an admin-only API. The visible admin portal task-list UX remains for the later admin portal UI pass.
- Active admin/superadmin authorization predicates now live in `platform_core.domain.access` so admin, KYC, account-access, and admin-ops code use the same source of truth for admin account types and blocking account statuses. Admin audit-log searches now write an `audit_event.search_performed` audit event with filters and result count. Admin task status transitions remain intentionally flexible in v1; the internal ops queue allows admins to reopen, cancel, or resolve tasks without a hard state machine, while every change is captured in append-only task events and audit logs.
- Phase 4 borrower-entity foundation is implemented as backend/API only. Admins can create, list, filter, update, and inspect legal-entity borrower records; set off-platform KYB status and compliance hold; store optional financial disclosure amounts as integer minor units plus currency; link existing stored files as borrower documents; preview investor-facing borrower disclosure with empty optional fields omitted; and inspect append-only borrower events. Borrower document upload storage remains handled by the shared stored-file foundation; actual admin console screens remain for the admin-console UI slice.
- Phase 4 loan product and schedule foundation is implemented as backend/API only. Admins can create complete operational loan records, generate monthly repayment schedules for all launch repayment types, use manual schedule overrides at creation/update when principal totals reconcile, inspect LTV warnings, update loan data before committed investments, lower the total amount after committed investments with an investor message, publish loans only when borrower KYB/compliance gates pass, and inspect append-only loan events. Term sanity bounds are implemented as 1 to 600 months. If no first payment date is supplied, the schedule defaults to one month after the funding deadline. Exact golden schedule fixtures now pin every launch repayment-type mapping. The visible admin loan-management UI remains for the admin-console UI slice.
- Phase 5 ledger foundation is implemented as backend/API only. Admins can declare reconciled lender deposits, which create immutable bank-operation evidence, balanced double-entry journal entries/postings, and investor balance lots with Europe/Zurich 30-day investment and 60-day withdrawal deadlines derived from bank value date. The ledger exposes admin balance summaries, FIFO investment-eligibility planning against a loan funding deadline, investor withdrawal requests, admin withdrawal cancellation before bank payout, admin withdrawal finalization, and reconciliation snapshots comparing bank-stated balances to investor-balance liabilities plus withdrawal payables. Withdrawal requests consume FIFO balance lots and post an internal immutable journal from investor balance liability to withdrawal payable; admin cancellation of a requested/unfinalized withdrawal restores the exact lot allocations and posts a reversing withdrawal-payable-to-investor-liability journal; admin finalization creates a lender-withdrawal bank operation and posts withdrawal payable to collection cash. Bank operations, journal entries, postings, and reconciliation snapshots have application-level and DB-level append-only guards, and the raw SQL immutability test now asserts the append-only trigger message instead of relying on SQLite parameter errors. Balance lots have DB/service conservation checks, terminal-status zero-available checks, and are read-only in Django admin. Ledger idempotency keys now store request fingerprints and reject replay with different payloads; derived journal keys are bounded to the database key length. Reconciliation snapshots now include current-state semantics metadata, investor liability posting totals, signed credit-balance components for withdrawal payable/Garanta accrued revenue/suspense, account-sign anomaly metadata, collection-cash ledger comparison, and investor-level lot-versus-posting integrity break metadata/events. Balance-lot mutation beyond deposit/withdrawal, balance ageing reminders, forced-withdrawal task generation, day-60 freeze/penalty posting, FX, primary-market allocation, servicing distributions, and full reconciliation-break admin task workflows remain for later Phase 5+ slices.
- Phase 5 balance-ageing operations are now partially implemented as backend/API only. Admins can register one active verified payout instruction per investor/currency. The admin ageing scan records idempotent reminder-due domain events for days 25, 46, 53, 58, 59, and 60; creates forced withdrawal requests for overdue day-60 lots when a verified payout instruction exists; and moves overdue lots into `penalty_mode` with audit/domain evidence when no usable payout instruction exists. The configured `BALANCE_PENALTY_BPS_PER_DAY` is stored in penalty-mode lineage for audit. Actual penalty-fee ledger posting/charging, email delivery from reminder events, scheduled background scan execution, admin task creation from scan results, and investor-facing frozen-action enforcement in marketplace/FX flows remain for later Phase 5/security/communications slices.
- Withdrawal implementation deferral: the investor withdrawal API currently enforces the shared financial-access gate, but fresh sensitive-action email-code consumption remains deferred to the investor-portal/security integration slice because the sensitive-action service lives in `accounts_auth` and ledger cannot import peer modules directly. Before production, the investor portal withdrawal action must consume a valid `withdrawal` sensitive-action code through an allowed boundary/facade.
- Ledger production-validation deferral: full append-only trigger semantics and real duplicate-idempotency race behavior must still be run against PostgreSQL, because local `make agent-check` uses SQLite for backend tests. This is non-blocking for continuing implementation but is required before first production money movement or any production ledger data.
- Ledger hardening deferrals: endpoint throttling for ledger APIs, scheduled daily reconciliation jobs, and explicit HTTP mapping for integer overflow/extreme-money input errors remain deferred to the ledger/security hardening slice because current ledger APIs are admin/internal foundation endpoints and serializer-level positive-integer validation already protects normal API input. Same-account debit/credit net-zero journals are not deferred; they are already rejected by `post_journal_entry` and covered by ledger tests. These hardening items must be closed before production financial API exposure.

## 1. Review Outcome

All written planning files were reviewed one by one:

- `plan/00_index.md`
- `plan/01_operating_model_compliance.md`
- `plan/02_identity_kyc_kyb_aml.md`
- `plan/03_accounts_auth_access.md`
- `plan/04_investor_portal.md`
- `plan/05_borrower_entity_portal.md`
- `plan/06_admin_operations_portal.md`
- `plan/07_loan_product_catalog.md`
- `plan/08_origination_underwriting.md`
- `plan/09_marketplace_investments.md`
- `plan/10_payments_ledger_custody.md`
- `plan/11_loan_servicing_repayments.md`
- `plan/12_risk_collections_recoveries.md`
- `plan/13_documents_contracting_esign.md`
- `plan/14_communications_notifications.md`
- `plan/15_accounting_tax_finance.md`
- `plan/16_reporting_analytics.md`
- `plan/17_security_privacy_audit.md`
- `plan/18_integrations_api_events.md`
- `plan/19_infrastructure_devops.md`
- `plan/20_qna_workflow.md`
- `plan/21_consistency_review.md`
- `admin_todo_garanta.md`
- `admin_todo_accounts.md`
- `admin_todo_tech.md`

No blocking product questions remain that require halting before the implementation planning phase.

A few controlled documentation corrections were made during the final consistency pass:

- Older "case management" wording was aligned to the lighter v1 model of admin tasks, notes, and audit trails.
- A stale borrower "broker/introducer" launch reference was moved out of launch scope.
- Previously open operating-model questions were marked answered where later Q/A had already settled them.

Remaining unknowns are implementation inputs, go-live dependencies, or legal/accounting/banking/provider/technical details captured in the split admin TODO files. They should not block software architecture, but production use or specific integration modules must wait for the relevant blocking items.

## 2. Non-Blocking Inputs To Close Before Production Money Movement

These are not questions that stop implementation. They are external inputs needed before launch or before enabling the related production feature.

### Legal and Regulatory

- Final counsel/VQF/SRO/bank validation of the user-balance model, 30-day reinvestment rule, 60-day withdrawal requirement, forced withdrawal authority, and day-60 penalty wording.
- Final validation that FX conversion and internal balances remain inside Garanta's authorization perimeter.
- Final legal wording for registration terms, primary investment terms, secondary-market buyer terms, secondary-market seller/listing terms, risk disclosures, assigned-claim documentation, late/default disclosure, and partial-funding disclosure.
- Final jurisdiction matrix for any Switzerland + EU/EEA exclusions or manual-review countries.

### Banking and Payments

- Bank/payment partner.
- CHF and EUR collection IBANs.
- Statement export format and evidence requirements. The implementation baseline is manual bank-operation declaration with generic evidence attachment; bank-specific statement layouts can be configured later.
- Bank-compatible payment reference format. The planning assumption allows lender ID or a derived stable code, but this must be verified with the bank.
- Fallback rule for missing or corrected bank value dates.

### Accounting and Tax

- Bexio chart of accounts.
- Bexio import/export layout for monthly configurable journal data.
- Bexio tax-code mapping, including VAT/reverse-charge treatment approved by the Swiss accountant.
- Annual tax information statement final labels, disclaimer, optional CHF-equivalent rules, rounding, currency treatment, and report examples for lenders, borrowers, and Garanta internal finance.
- Accounting treatment for balance-ageing penalties, secondary-market fees, FX fees, externally deducted recovery costs, and recovery rounding differences.
- Final Bexio/account labels for Garanta accrued revenue/commission balances, Garanta out/in transfers, reconciliation differences, realized FX gain/loss, and residual FX deltas.

### Providers

- Didit sandbox and production credentials, webhook configuration, workflow type, provider-side AML settings, status/event names, report download/export access, raw webhook payload documentation, and report metadata to store.
- SendGrid account, domain, sender identity, templates, marketing list names, unsubscribe/suppression behavior, and support mailbox.
- Twilio account and phone-verification configuration.
- Yahoo Finance rate-source terms/API access, polling cadence, and failed-rate fallback behavior.

### Product Defaults

- Whether the 50 pending-order cap is global per investor, per loan, or per currency. Implementation should default to global per investor unless changed.
- Exact tie-break behavior for multiple deposits with the same bank value date. Implementation should use bank value date, then bank statement import/order sequence, then system receipt timestamp.
- V1 uses generic P2P lending risk acknowledgements and exposure metrics rather than a detailed suitability questionnaire or hard concentration limits.
- Final legal wording for secondary-market bulletin-board positioning, buyer/seller acknowledgements, non-standard listing warnings, and any non-zero minimum maker/taker fee configuration.
- Final admin SLA labels and targets for daily operational tasks.

## 3. Core Implementation Decision

Build v1 as a modular monolith.

This matches the documented product:

- The platform has tightly coupled financial state: balances, loan funding, claim assignments, repayment allocation, FX, and secondary-market transfers.
- Operational workflows are mostly manual at launch, but must be fully auditable.
- There is no public API requirement at launch.
- The team wants cost-conscious infrastructure with staging and production possibly sharing a server.
- Future provider automation, maker-checker approvals, bank feeds, and external APIs should be possible without splitting the system early.

The monolith must not be a tangled codebase. It should be a single deployable application with strict internal module boundaries, explicit service-layer APIs, append-only financial/audit records, and provider adapters.

Agent-readability is a first-class implementation constraint. The codebase should be structured so human engineers and coding agents can safely take isolated work items, understand the relevant module contract quickly, run deterministic checks locally, and avoid accidental cross-module financial side effects.

## 4. Recommended Technology Stack

### Backend

Use Python, Django, Django REST Framework, PostgreSQL, Celery, and Redis.

Rationale:

- Django is strong for regulated operational systems with complex admin workflows, permissions, forms, audit trails, and relational data.
- PostgreSQL is the correct system of record for ledger, balances, loans, documents, and audit data.
- Django REST Framework gives a clear API boundary for React portals without requiring a separate backend framework.
- Celery and Redis handle reminders, emails, webhooks, PDF generation, balance ageing, FX polling, reconciliation jobs, and report exports.
- Python has mature integrations for SendGrid, Twilio, PDF generation, file scanning, structured logging, and accounting/report generation.

Core backend libraries and tools:

- Django 5.x.
- Django REST Framework.
- `drf-spectacular` for OpenAPI schema generation.
- PostgreSQL 16+.
- Celery.
- Redis.
- `django-storages` and `boto3` for object storage.
- `psycopg` v3.
- Pydantic v2 for typed service command/result objects where it improves boundary clarity.
- `pytest`, `pytest-django`, `factory_boy`, and `freezegun`.
- `ruff`, `mypy`, and `django-stubs`.
- `import-linter` or equivalent import-boundary checks between domain modules.
- `structlog` or equivalent structured logging.
- `sentry-sdk` optional only if Garanta later wants external error tracking; otherwise email/structured-log alerts are enough for v1.
- WeasyPrint for launch HTML-to-PDF generation, with an early deployment-image proof for fonts/page breaks/file size.
- ClamAV-compatible local/containerized malware scanning for uploaded files, using quarantine status until clean.

### Frontend

Use TypeScript, React, Vite, TanStack Query, TanStack Table, React Hook Form, Zod, Orval-generated OpenAPI clients, MSW for frontend API mocks, and a restrained component system built with Tailwind CSS and accessible headless primitives.

Rationale:

- The investor portal and admin portal need rich forms, tables, filters, upload flows, status views, and transaction confirmations.
- TypeScript improves safety around financial, KYC, and workflow state.
- TanStack Query handles API caching, invalidation, and loading/error states cleanly.
- TanStack Table fits the admin-heavy operational screens.
- React Hook Form and Zod fit complex validated forms and confirmation flows.
- Orval-generated OpenAPI clients and TanStack Query hooks keep frontend and backend contracts synchronized and reduce agent mistakes.
- MSW lets agents build and test portal screens without needing every backend endpoint finished first.

Frontend structure:

- One repository.
- Two frontend entry points:
  - Investor portal at `/app`.
  - Admin portal at `/admin`.
- Shared frontend packages for components, formatting, validation schemas, API client, and money/date utilities.
- Generated API client and TanStack Query hooks should live under `frontend/src/api/generated` and should not be manually edited.
- Public marketplace preview can be served through a public frontend route backed by limited public APIs.

### Infrastructure

Target AWS-oriented cost-optimized hosting in AWS `eu-central-2` Europe (Zurich), using a single-host launch deployment with staging and production logically isolated.

Recommended launch shape:

- One EC2 host in AWS Zurich for staging and production at launch.
- Burstable general-purpose 2 vCPU / 8 GB RAM baseline, such as `t3.large`/`t3a.large` or a Graviton equivalent if all production containers are confirmed multi-architecture compatible.
- Docker Compose deployment.
- Dockerized Django application, worker, scheduler, reverse proxy, PostgreSQL, Redis, and malware scanner.
- PostgreSQL self-hosted in Docker at launch, with separate production/staging databases and users.
- Redis local/containerized at launch, with separate instances or namespaces.
- Private AWS Zurich S3 buckets/prefixes for documents, generated PDFs, evidence packages, backups, and KYC/KYB/AML retained evidence.
- Switzerland-located, Garanta-controlled restricted storage for KYC/KYB/AML evidence, provider reports, raw provider webhook payloads where retained, supporting documents, and evidence packages.
- CloudFront only if needed for public assets; private documents should remain signed and access-controlled.
- SES is not required because SendGrid is the email provider.
- GitHub Actions for CI/CD.
- AWS ECR as the container registry.
- Staging and production logically isolated through separate Docker Compose projects, databases, storage prefixes/buckets, Redis namespaces, environment variables, domains, logs, workers/queues, and external-provider sandbox/prod credentials.

Scale path:

- Resize EC2 vertically.
- Move PostgreSQL to RDS PostgreSQL.
- Move Redis to ElastiCache.
- Split staging and production onto separate EC2 hosts.
- Move app/worker containers to ECS/Fargate behind an ALB if traffic or operational requirements justify it.

Local development:

- Docker Compose for PostgreSQL, Redis, object-storage emulator, mail sink, and app services.
- Provider integrations run in sandbox or mock mode.
- Seed data for admin, natural-person lender, legal-entity lender, borrower, loan, deposits, and repayments.

### Agent-Friendly Toolchain

The implementation should include these tools from the first sprint:

- A root `Makefile` with stable commands:
  - `make setup`
  - `make up`
  - `make down`
  - `make test`
  - `make test-backend`
  - `make test-frontend`
  - `make lint`
  - `make typecheck`
  - `make migrate`
  - `make seed`
  - `make api-schema`
  - `make api-client`
  - `make agent-check`
- `make agent-check` must run the checks an implementation agent should run before handing off work:
  - backend lint.
  - backend type check.
  - backend tests for touched modules where practical.
  - frontend lint.
  - frontend type check.
  - OpenAPI schema generation.
  - generated API client freshness check.
- A root `AGENTS.md` created during Phase 0 with repository-specific instructions, command list, module boundaries, and financial-safety rules.
- `.env.example` files for backend and frontend.
- Pre-commit hooks for formatting, linting, import sorting, and basic secret scanning.
- Generated OpenAPI schema committed to the repository.
- Orval configuration committed under the frontend workspace so `make api-client` is deterministic.
- CI fails if the generated OpenAPI schema or Orval-generated frontend client is stale.
- Backend and frontend fixture/seed factories that create realistic domain objects without calling real providers.
- Temporary implementation task specs are allowed only for active multi-agent work and should be merged into this plan or deleted when resolved.
- A `docs/runbooks/` folder for operations, deployment, backups, reconciliation, and go-live procedures.

## 5. Architectural Principles

### Explicit Code Shape For Agents

The codebase should prefer boring, explicit patterns over framework magic.

Rules:

- Keep business logic out of Django model `save()` methods, serializer side effects, and signal handlers.
- Use model methods only for local invariants and simple derived values.
- Put financial mutations in service functions/classes with typed command inputs and result outputs.
- Put read/query logic in selectors, not scattered across views.
- Put provider calls behind adapters.
- Put scheduled/background behavior in named jobs that call the same services as synchronous flows.
- Keep serializers responsible for HTTP validation and representation, not domain decisions.
- Keep API views/controllers thin.
- Use explicit enums/status transition helpers instead of free-form status strings.
- Use a clock/time provider in tests for any age, deadline, due-date, or reminder behavior.
- Use stable IDs/reference generators through `platform_core`, not ad hoc string building.
- Every cross-module write must happen through a documented service API.

### Financial Correctness First

- Store money as integer minor units plus ISO currency.
- Never use floating point for money, rates, percentages, or FX.
- Use `Decimal` for rates and calculations.
- Store the rounding method and rate used for every calculated financial result.
- Persist calculation inputs when a legal or financial output must be reproducible.
- Use database transactions and row-level locks for allocation, ledger posting, balance consumption, FX execution, secondary-market settlement, loan closing, repayment distribution, and withdrawal state changes.

### Append-Only Where It Matters

- Ledger entries are immutable.
- Audit events are append-only.
- Regulatory/evidence records are append-only except for metadata explicitly designed to be superseded.
- Corrections are made through reversing entries, compensating events, or new versions, not destructive edits.

### Service Layer Over Direct Writes

Controllers, views, and background jobs should not directly mutate financial state.

Create explicit domain services for:

- Registration and KYC state transitions.
- KYC/KYB evidence import/download, manual review, and transaction approval gates.
- Balance credit/debit and lot ageing.
- Investment order placement.
- Primary allocation and loan closing.
- Loan schedule generation and recalculation.
- Borrower payment event application.
- Investor distribution.
- Secondary-market listing and settlement.
- FX quote and exchange execution.
- Withdrawal and forced withdrawal.
- Document generation and acceptance evidence.
- Report snapshot/export generation.

### Outbox and Idempotency

- Use an outbox table for emails, webhooks, provider calls, and report/PDF generation triggers.
- Every externally retried operation needs an idempotency key.
- Webhooks from Didit must be idempotent and signature-verified.
- Admin-submitted financial operations should receive a server-side idempotency key to avoid double posting on retries.

### Provider Adapters

All third-party integrations must sit behind internal interfaces:

- Didit KYC adapter.
- SendGrid email adapter.
- Twilio phone-verification adapter.
- FX rate adapter.
- Object storage adapter.
- Malware scanner adapter.
- Future bank-feed adapter.
- Accounting export adapter.

This allows the app to be built and tested with mock adapters before credentials are available.

### Contract-First Frontend/Backend Development

- Backend APIs must generate OpenAPI through `drf-spectacular`.
- Frontend API calls must use the generated client/query hooks.
- Handwritten `fetch` calls to application APIs should be prohibited except inside the generated-client wrapper.
- Every command endpoint should have a request schema, response schema, documented error cases, and idempotency behavior where applicable.
- Mock API handlers should be generated or kept in sync from the same endpoint names so frontend agents can work before backend completion.
- API changes should be made backend-first, schema regenerated, frontend client regenerated, and affected UI updated in the same work item unless the task is explicitly split.

### Future-Ready Controls

Do not require maker-checker approval in v1, but model workflows so a future approval step can be added without rewriting domain records.

Use workflow records with:

- Initiator.
- Status.
- Optional approver fields.
- Reason/note fields.
- Audit references.
- Effective timestamp.

## 6. Domain Modules

Implement the monolith as Django apps or internal packages with clear ownership. Module ownership is defined in this section, `AGENTS.md`, public service/selector modules, import-boundary checks, and focused tests. Avoid app-local boilerplate READMEs unless a module has genuinely unusual operational behavior that cannot live in this plan or a runbook.

Preferred backend module layout:

```text
backend/apps/<module>/
  models/
  migrations/
  services/
  selectors/
  api/
    serializers.py
    views.py
    urls.py
  jobs/
  adapters/
  events.py
  permissions.py
  tasks.py
  tests/
    factories.py
    test_services_*.py
    test_api_*.py
    test_jobs_*.py
```

Not every module needs every folder on day one, but new code should follow this shape instead of growing giant `models.py`, `views.py`, or `utils.py` files.

Preferred frontend layout:

```text
frontend/src/
  api/
    generated/
    client/
    mocks/
  app/
    investor/
    admin/
    public/
  components/
    ui/
    forms/
    tables/
    feedback/
  features/
    <domain-feature>/
      routes/
      components/
      hooks/
      schemas/
      tests/
  lib/
    money/
    dates/
    auth/
    permissions/
```

Import-boundary rule:

- `platform_core` can be imported by every module.
- `ledger` service interfaces can be called by financial modules, but other modules must not write ledger models directly.
- `documents`, `communications`, `audit`, and `outbox` should expose service APIs.
- Feature modules should not import each other's private models directly when a selector/service exists.
- Cross-module access should be enforced with `import-linter` once the initial package structure is in place.

### `platform_core`

Shared primitives:

- Money, percentage, rate, and rounding utilities.
- Currency registry.
- Business-date helpers.
- File upload primitives.
- Configuration registry.
- Feature flags.
- ID/reference generation.
- Common status enums.
- Base models and timestamps.

### `accounts_auth`

Identity, login, and account lifecycle:

- Investor account.
- Legal-entity lender account.
- Admin account.
- Superadmin env-backed bootstrap.
- Magic-link login.
- Email-code confirmation for sensitive investor actions.
- Admin password + email-code login.
- Phone verification.
- Session management.
- Account restriction, closure, and anonymization workflows.

### `kyc_compliance`

KYC/AML and compliance tasks:

- Didit sessions.
- Didit webhook events.
- KYC status.
- KYB status for legal-entity lenders and borrowers.
- AML screening metadata.
- Provider identifiers, report references, downloaded report metadata, and downloaded provider reports where possible.
- Raw provider webhook payloads where possible.
- Supporting-document references/local copies where possible.
- Manual AML review decisions and officer/admin evidence.
- Manual compliance/admin tasks.
- Account lock/restriction requests.
- Regulatory evidence package generation.

### `entities`

Borrowers and legal-entity lenders:

- Borrower legal entity records.
- Borrower display profile.
- Borrower uploaded documents.
- Legal-entity lender admin-created records.
- Off-platform onboarding status and evidence references.
- `borrower_investor_disclosure` is the single investor-facing borrower projection. Marketplace and investor borrower views must reuse it instead of rebuilding disclosure logic, so hide-absent optional fields and clean-scan document gating do not drift.
- `borrower_can_transact` is the shared borrower transaction gate. Loan publication, funding close, borrower disbursement, borrower repayment processing, and any later borrower transaction mutation must call it once those modules exist.

### `loans`

Loan product and lifecycle:

- Loan draft/publication record.
- Loan purpose.
- Collateral type, collateral value, and LTV.
- Risk rating.
- Interest and term.
- Repayment type.
- Generated schedule.
- Loan status.
- Loan documents.
- Public notes.

### `marketplace_primary`

Primary marketplace and investments:

- Public preview.
- KYC-gated full loan details.
- Investment order.
- Pending order cap.
- Balance allocation.
- Admin-entered investment.
- Funding progress.
- Full funding and accepted partial funding.
- Borrower fee accounting.
- Disbursement workflow.

### `ledger`

Financial ledger and balances:

- Double-entry journal.
- Accounts and subaccounts.
- Immutable transaction-level financial event store.
- User balance lots.
- Deposits.
- Withdrawals.
- Refunds.
- Suspense/unmatched cash.
- Bank operation declarations.
- Ledger-bank reconciliation by currency.
- Garanta accrued revenue/commission balances.
- Garanta out/in transfers.
- Penalty postings.
- Fees.
- Ledger statements.
- Balance ageing jobs.

### `servicing`

Repayments and loan schedule changes:

- Borrower payment event.
- Payment waterfall.
- Installment state.
- Early repayment.
- Partial payment.
- Multiple-installment payment.
- Schedule recalculation.
- Investor distribution.
- Lender payout notifications.
- Bank statement evidence uploads.

### `secondary_market`

Secondary-market claim transfers:

- Investor holding/claim view.
- Listing.
- Full-holding-only listings.
- Discount/premium price as percentage of current principal balance.
- Accrued-interest split.
- Non-standard listing approval.
- Buyer purchase.
- Maker and taker fees.
- Settlement through BANXUM balance and Garanta collection account.
- Claim assignment transfer.
- Buyer/seller documents and notifications.

### `fx`

Currency exchange:

- Rate polling.
- Executable quote.
- Quote expiry.
- Sanity checks.
- Exchange execution.
- FX fees.
- FX delta/external settlement report.
- External settlement evidence.
- Realized FX gain/loss calculation.

### `documents`

Templates, generated PDFs, and clickwrap evidence:

- Template categories.
- Template versions.
- Variable registry.
- Template preview and validation.
- PDF generation.
- Acceptance evidence.
- Generated document records.
- Secure document access.

### `communications`

Emails, notifications, and support:

- Email templates.
- SendGrid delivery.
- Retry logic.
- Delivery failures.
- Full sent-content archive.
- Marketing consent.
- SendGrid contact-list sync.
- Notification preferences where applicable.

### `reporting`

Operational, regulatory, accounting, and tax exports:

- Accounting exports.
- Ledger exports.
- Accrued revenue reports.
- Bank reconciliation reports.
- Bank operation reports.
- Realized FX gain/loss reports.
- Annual tax information statements for lenders, borrowers, and Garanta internal finance.
- Regulatory/audit evidence exports.
- Portfolio reports.
- Default/recovery reports.
- Admin activity reports.
- Redacted/full export variants.
- PDF, CSV, and ZIP generation.

### `admin_ops`

Admin portal operational workflows:

- Admin dashboard.
- Task queues.
- SLA tracking.
- Bank operation declaration.
- Ledger-bank reconciliation.
- Garanta accrued revenue transfer operations.
- Daily operations checklist.
- Audit log viewer.
- Configuration screens.
- Export request management.

## 7. Data Model Backbone

The exact model names can change during implementation, but the first schema should cover these records.

### Users and Access

- `InvestorAccount`
- `InvestorProfile`
- `LegalEntityLenderProfile`
- `AdminUser`
- `AdminRole`
- `AuthToken`
- `MagicLinkToken`
- `EmailActionCode`
- `PhoneVerification`
- `SessionRecord`
- `AccountRestriction`
- `AccountClosureRequest`
- `AccountAnonymizationRequest`

### KYC and Compliance

- `KycProviderSession`
- `KycProviderEvent`
- `KycStatusSnapshot`
- `AmlScreeningSnapshot`
- `ComplianceTask`
- `SanctionsPepAdverseMediaFlag`

### Entities and Loans

- `BorrowerEntity`
- `BorrowerFinancialProfile`
- `BorrowerDocument`
- `Loan`
- `LoanCollateral`
- `LoanRiskRating`
- `LoanDocument`
- `LoanSchedule`
- `Installment`
- `LoanPublicNote`
- `LoanStatusEvent`

### Marketplace

- `PrimaryInvestmentOrder`
- `InvestmentAllocation`
- `LoanFundingEvent`
- `LoanDisbursement`
- `InvestorHolding`
- `SecondaryMarketListing`
- `SecondaryMarketOrder`
- `SecondaryMarketSettlement`
- `ClaimTransfer`

### Ledger and Cash

- `Currency`
- `CollectionAccount`
- `LedgerAccount`
- `JournalEntry`
- `JournalPosting`
- `BalanceLot`
- `CashMovement`
- `BankOperation`
- `BankOperationEvidence`
- `LedgerBankReconciliationSnapshot`
- `ReconciliationBreak`
- `DepositRecord`
- `WithdrawalRequest`
- `RefundRecord`
- `ManualReconciliationBatch`
- `UploadedBankStatement`
- `GarantaAccruedRevenueBalance`
- `GarantaTransfer`
- `BalanceAgeingReminder`
- `BalancePenaltyEvent`

### Servicing and Recoveries

- `BorrowerPaymentEvent`
- `RepaymentApplication`
- `InvestorDistribution`
- `RepaymentEvidence`
- `DefaultStatusEvent`
- `RecoveryEvent`
- `RecoveryWaterfallConfig`
- `RecoveryCostLine`
- `RecoveryFeeApplication`
- `WriteOffEvent`

### FX

- `FxRateTick`
- `FxQuote`
- `FxExchange`
- `FxSanityAlert`
- `FxDailyDelta`
- `FxExternalSettlement`

### Documents and Communications

- `Template`
- `TemplateVersion`
- `TemplateVariableDefinition`
- `DocumentGeneration`
- `DocumentAcceptance`
- `StoredFile`
- `EmailTemplate`
- `EmailMessage`
- `EmailDeliveryAttempt`
- `MarketingConsent`
- `ProviderSuppression`

### Reporting and Audit

- `AuditEvent`
- `DomainEvent`
- `OutboxMessage`
- `ExportRequest`
- `GeneratedReport`
- `ReportDefinitionVersion`
- `AdminTask`
- `OperationalSlaEvent`

## 8. Implementation Phases

The phases below are ordered to reduce risk. Each phase should end with working software, tests, and admin-visible behavior where practical.

### Agent Work Unit Format

When implementation work is delegated to agents, each work item should be written as a small contract. A good task should fit in one module or one vertical slice and should name the exact files/folders the agent owns.

Each work item should include:

- Goal.
- Business context.
- Module owner.
- Write scope.
- Read-only context files.
- Public service/API contract to implement.
- Database migration expectations.
- Ledger impact, if any.
- Provider/mock behavior.
- Acceptance criteria.
- Required tests.
- Non-goals.
- Commands to run before handoff.

Default handoff command:

```text
make agent-check
```

For high-risk financial work, the handoff must also include the focused test command for the module, for example:

```text
make test-backend TEST=backend/apps/ledger/tests
```

Parallelization rules:

- Split work by module or vertical feature with disjoint write scopes.
- Do not let separate agents edit the same ledger service, migration, or generated API client at the same time.
- Generate API schema/client in a single integration pass when multiple API-changing agents finish.
- Keep UI-only agents on generated clients and MSW mocks until the backend contract is stable.
- Treat `ledger`, `servicing`, `fx`, `marketplace_primary`, and `secondary_market` as high-risk modules requiring extra review and golden tests.

### Phase 0: Project Bootstrap and Engineering Rules

Goal: create the implementation foundation before domain work starts.

Tasks:

- Initialize repository structure for backend, frontend, infrastructure, and docs.
- Create root `AGENTS.md`.
- Create root `Makefile` with stable commands.
- Add backend linting, formatting, typing, and test tooling.
- Add frontend linting, formatting, typing, and test tooling.
- Add Docker Compose for local PostgreSQL, Redis, object storage, mail sink, and app containers.
- Add base CI workflow in GitHub Actions.
- Add `docs/runbooks/` for durable operating procedures.
- Add secure settings structure for local, staging, and production.
- Add seed command for local development users and example data.
- Add engineering rules for financial mutations, migrations, logging, and test requirements.
- Add OpenAPI schema generation and frontend client generation pipeline.
- Add import-boundary configuration.
- Add MSW mock setup for frontend development.
- Add fixture factory conventions.

Acceptance criteria:

- A new developer can run the full local stack with one documented command.
- CI runs backend tests, frontend tests, linting, and type checks.
- The project can deploy a placeholder app to staging.
- Secrets are not committed.
- Agents have a single source of truth for commands, module boundaries, and handoff checks.
- Backend schema generation and frontend API client generation work locally and in CI.
- A new domain module can be scaffolded with the expected test/service/selector layout.

Tests:

- Smoke test for app boot.
- Database migration test.
- CI pipeline validation.
- `make agent-check` validation.
- OpenAPI generation and client freshness check.

### Phase 1: Foundation, Configuration, Audit, Events, and Files

Goal: build shared primitives used by every later module.

Tasks:

- Implement money, rate, percentage, and rounding primitives.
- Implement currency registry with CHF and EUR seed data.
- Implement superadmin-editable platform settings for launch-safe values:
  - Platform/brand name display value, legal operator display value, support email, domains, and document footer identities from configuration/template variables.
  - Enabled currencies.
  - Minimum investment per currency.
  - FX fee.
  - Balance ageing reminders.
  - Balance penalty policy display from deployment/env configuration.
  - Secondary-market maker/taker fees.
  - Lender payment fee.
  - Loan validation limits.
- Implement append-only audit event table.
- Implement domain event table and outbox table.
- Implement background job framework and retry/dead-letter conventions.
- Implement stored-file service with private object storage, metadata, access control, and malware-scan status.
- Implement structured logging fields:
  - actor type/id.
  - request id.
  - operation id.
  - ledger entry id where applicable.
  - loan id where applicable.
  - investor id where applicable.
  - admin id where applicable.
- Implement admin/tech email alert primitive.

Acceptance criteria:

- All modules can write audit events through one interface.
- Background jobs are idempotent where retried.
- Files cannot be downloaded without authorization.
- Platform settings are versioned/audited.

Tests:

- Money rounding and arithmetic tests.
- Currency configuration tests.
- Audit append-only tests.
- Outbox retry/idempotency tests.
- File access-control tests.

### Phase 2: Accounts, Authentication, Registration, and KYC

Goal: implement account access and KYC gates before any money features.

Tasks:

- Implement natural-person investor registration.
- Capture registration-time terms acceptance.
- Implement SendGrid-backed magic-link login.
- Implement Twilio-backed phone verification.
- Implement offline/admin-mediated account email recovery support:
  - admin records support request.
  - admin re-verifies identity using account/KYC evidence and verified phone/account data.
  - admin updates email/login access if approved.
  - audit old email, new email, actor, timestamp, reason, and evidence summary.
- Implement Didit KYC session creation and redirect/hosted-flow integration.
- Implement Didit webhook receiver with signature verification and idempotency.
- Store KYC status, provider references, structured fields, AML metadata, downloaded report metadata, provider reports where possible, raw webhook payloads where possible, supporting evidence where possible, and result snapshots in the Swiss-controlled evidence boundary.
- Implement internal status mapping: pending, approved, declined, manual review, high risk, sanctions hit, PEP hit, adverse media hit, expired, and re-verification required.
- Implement manual AML review workflow for PEP, high-risk, adverse media, unclear ownership, inconsistent documentation, and other non-standard cases.
- Implement blocking rules for sanctions hits and confirmed identity/document fraud.
- Gate investor dashboard/deposit/investment access behind passed KYC and phone verification.
- Implement account lock/restrict/close states.
- Implement legal-entity lender admin creation:
  - No self-service registration.
  - Off-platform onboarding/KYB status and local evidence records.
  - Financial activity blocked until KYB/AML approval and no compliance hold.
  - Optional representative login behaving like a normal lender once KYB/AML-approved and active.
- Implement borrower KYB approval gates used by later origination, marketplace, and payment modules.
- Implement admin authentication:
  - Superadmin from environment/bootstrap.
  - Admin users created by superadmin.
  - Email/password + email code.
  - No forgot-password flow.
- Implement sensitive-action email-code framework for investors:
  - Withdrawals.
  - Bank-account changes.
  - FX.
  - Primary investments.
  - Secondary-market listings.
  - Secondary-market purchases.

Acceptance criteria:

- A natural person cannot reach financial functionality without registration terms, phone verification, and successful KYC.
- A failed or pending KYC account remains blocked.
- Legal-entity lenders cannot self-register.
- Legal-entity lenders cannot perform financial actions until admin-recorded KYB/AML approval is complete.
- Borrowers cannot be used in platform transaction workflows until KYB/AML approval is complete.
- Provider reports, raw webhook payloads where possible, manual review decisions, and evidence exports are auditable.
- Admins can log in only through the admin auth flow.
- All auth and KYC transitions are audited.

Tests:

- Registration and magic-link tests.
- Magic-link single-use and expiry tests.
- Phone verification success/failure/rate-limit tests.
- Didit webhook idempotency tests.
- KYC gate tests.
- Admin auth and role tests.
- Sensitive-action code expiry/attempt tests.

### Phase 3: Admin Portal Shell and Operational Configuration

Goal: make the internal portal usable before adding complex financial operations.

Tasks:

- Build admin portal layout and navigation.
- Implement superadmin screens:
  - Admin user management.
  - Platform settings.
  - Currency settings.
  - Collection account settings.
  - Template management entry point.
  - Provider configuration status view.
- Implement admin screens:
  - Dashboard.
  - Task queue.
  - Audit log search.
  - User search.
  - Borrower/lender search.
  - File/document review.
- Implement admin task records and simple SLA fields:
  - type.
  - priority.
  - assigned admin.
  - due date.
  - status.
  - notes.
  - related object.
- Implement full audit for admin actions.

Acceptance criteria:

- Superadmin can configure launch parameters without code changes where documented.
- Admins can see a single operational task list.
- Admin actions are visible in audit logs.
- Role restrictions are enforced.

Tests:

- Admin RBAC tests.
- Platform-setting validation tests.
- Admin task filtering tests.
- Audit log permission tests.

### Phase 4: Borrower Entities, Loan Product, Risk, and Schedules

Goal: model borrowers and loans completely enough to publish investable products.

Tasks:

- Implement borrower legal-entity records with required fields:
  - entity name.
  - year founded.
- Implement optional borrower display fields:
  - assets.
  - liabilities.
  - revenue last year.
  - profit last year.
  - country.
  - presentation PDF.
  - financials PDF.
  - named generic documents.
- Hide optional borrower labels in the investor portal when values are absent.
- Implement borrower document uploads.
- Implement loan draft creation with strict mandatory fields before save:
  - borrower.
  - amount.
  - currency.
  - interest.
  - term.
  - repayment type.
  - generated schedule.
  - funding deadline.
  - purpose/use.
  - collateral type.
  - collateral value.
  - risk rating.
  - required investor-facing information.
- Enforce funding deadline defaults:
  - default 30 days.
  - maximum 60 days.
- Implement common loan purposes:
  - working capital.
  - liquidity.
  - refinancing.
  - debt consolidation.
  - acquisition.
  - bridge financing.
  - project finance.
  - capex.
  - development.
  - other.
- Implement collateral types:
  - real estate default.
  - corporate guarantee.
  - personal guarantee.
  - receivables.
  - invoices.
  - equipment.
  - inventory.
  - securities pledge.
  - cash collateral.
  - share pledge.
  - mixed collateral.
  - unsecured exception.
  - other.
- Implement free-text collateral description.
- Calculate LTV from principal and collateral value.
- Warn and hide LTV when collateral value is zero.
- Warn and show LTV when collateral value is greater than principal.
- Implement manual risk rating scale from strong to weak/unrated.
- Implement repayment schedule generation:
  - equal installments default.
  - bullet plus periodic interest.
  - amortizing principal and interest.
  - interest-only then bullet.
  - interest-only then amortizing.
- Allow admin manual override of generated schedule at creation time.
- Block publication for incomplete or invalid loan data.
- Allow all loan fields to be edited until committed investments exist.
- After committed investments exist, allow only lowering total amount, with required investor message/reason and notification.

Acceptance criteria:

- Incomplete loans are not saved as operational loan records.
- Published loans have complete schedules and mandatory information.
- Investor portal displays complete full data only after login/KYC.
- Public preview displays only allowed fields.
- Schedule totals reconcile with principal, interest, term, and repayment type.

Tests:

- Loan validation tests.
- Schedule generation golden tests.
- LTV warning/display tests.
- Borrower optional-field visibility tests.
- Post-commit edit restriction tests.

### Phase 5: Ledger, Balances, Deposits, Withdrawals, and Reconciliation

Goal: create the financial spine before marketplace transactions.

Tasks:

- Implement double-entry ledger accounts.
- Implement journal entries and postings with immutable records.
- Implement balance lots per investor and currency:
  - received timestamp.
  - bank value date or internal timestamp.
  - original amount.
  - available amount.
  - invested/withdrawn/penalized amount.
  - 30-day investment eligibility deadline.
  - 60-day withdrawal deadline.
  - source type.
- Implement collection accounts per currency.
- Implement bank-operation declaration:
  - lender deposit.
  - lender withdrawal.
  - borrower loan disbursement / initial borrower loan payment.
  - borrower repayment.
  - Garanta out.
  - Garanta in.
  - currency-exchange external settlement.
  - collection account.
  - booking date and value date.
  - amount and currency.
  - payer/payee name and account identifier where available.
  - bank/PSP reference and payment reference.
  - linked platform event(s).
  - evidence upload/reference.
  - confirming admin and timestamp.
- Implement admin deposit declaration/reconciliation as a specialized lender-deposit workflow:
  - matched investor.
  - collection account.
  - bank value date.
  - amount.
  - currency.
  - payment reference.
  - evidence upload.
- Implement ledger-bank reconciliation snapshots by currency:
  - bank-stated balance.
  - investor balance liabilities.
  - Garanta accrued revenue/commission balance held in collection account.
  - suspense/unmatched cash.
  - pending withdrawals/disbursements/refunds/FX settlement.
  - other exception balances.
  - reconciliation difference.
- Implement reconciliation-break work items for unexplained differences.
- Implement Garanta accrued revenue/commission balance tracking.
- Implement Garanta out/in transfer ledger events.
- Implement suspense/unmatched cash records.
- Implement investor balance display with breakdown:
  - total balance.
  - investable balance.
  - withdraw-only balance.
  - ageing deadlines.
  - penalty/freeze state.
- Implement FIFO balance consumption by source lot.
- Implement primary-market balance-source eligibility against loan funding deadline:
  - consumed source lots must still be within the 30-day investment/reinvestment window.
  - loan funding deadline must be on or before each consumed source lot's 30-day investment/reinvestment deadline.
  - otherwise block the order and show the amount as withdraw-only for that investment.
- Implement withdrawal request, admin cancellation before bank payout, and admin marking finalized.
- Implement forced withdrawal task generation on day 60 when usable IBAN exists.
- Implement freeze state when day-60 funds exist and no usable IBAN is available.
- Implement balance-ageing reminders:
  - day 25.
  - day 46.
  - day 53.
  - day 58.
  - day 59.
  - day 60.
- Implement day-60 penalty mode with env/deployment-configurable mechanics:
  - launch default 1% simple daily penalty.
  - base is the overdue source balance.
  - cadence uses Europe/Zurich calendar days.
  - cap at the remaining overdue source balance.
  - never create a negative balance.
  - terminal `penalty_exhausted` source status if the overdue source is fully consumed.
- Implement refund records for surplus, wrong reference, and full rejected payments.
- Implement account statements for investors.
- Implement complete annual account statement source views for lenders, borrowers, and Garanta internal finance.
- Implement arbitrary-period Garanta accrued revenue report source views.

Acceptance criteria:

- Ledger balances reconcile to user balance lots.
- Bank-stated balances reconcile by currency to investor balances, Garanta accrued revenue/commission balances, suspense/unmatched cash, and pending/exception balances.
- Every deposit, withdrawal, refund, fee, penalty, investment, repayment, FX exchange, and secondary-market settlement posts through the ledger.
- Every external bank movement has a declared bank-operation record or appears as pending/unmatched in reconciliation.
- A balance older than 30 days cannot be used for investment or reinvestment.
- A balance older than 60 days triggers forced withdrawal or freeze/penalty behavior.
- Admins can reconcile deposits and other bank-operation types manually and attach evidence.

Tests:

- Double-entry balance tests.
- Ledger immutability tests.
- FIFO lot-consumption tests.
- 30/60-day ageing tests with time travel.
- Forced-withdrawal and freeze tests.
- Manual bank reconciliation tests.
- Bank-operation declaration tests.
- Ledger-bank reconciliation equation tests.
- Garanta out/in transfer tests.
- Accrued revenue report tests.
- Refund posting tests.

### Phase 6: Documents, Templates, Clickwrap, and Communications

Goal: make terms, evidence, PDFs, and transactional communications available before investment flows.

Tasks:

- Implement four terms/template categories:
  - registration.
  - primary-market investment.
  - secondary-market purchase.
  - secondary-market listing.
- Implement superadmin template editor with versioning.
- Implement variable registry per template type.
- Show available variables and examples in the template editor.
- Validate templates before publication.
- Implement clickwrap acceptance evidence:
  - template version.
  - accepted text/hash.
  - user.
  - timestamp.
  - IP address.
  - user agent.
  - transaction context.
- Implement PDF generation from accepted/generated document snapshots.
- Implement secure document access in investor portal.
- Implement SendGrid transactional email system.
- Store full sent email content.
- Implement retry logic and admin notices after failures.
- Implement email templates for:
  - registration.
  - magic link.
  - phone verification support if needed.
  - KYC status.
  - deposit received.
  - balance-ageing reminders.
  - withdrawal status.
  - primary order created/accepted/rejected.
  - loan funded/accepted partial.
  - loan amount lowered with admin reason.
  - borrower installment received.
  - distribution credited.
  - secondary-market listing.
  - secondary-market purchase/sale settlement.
  - FX quote/exchange result.
  - default/late/public note notifications.
  - account locked/restricted/closed.
- Implement marketing consent and SendGrid list sync for future newsletters.

Acceptance criteria:

- Legal terms are accepted before the related transaction can complete.
- Generated PDFs are reproducible from stored template/data snapshots.
- Transactional emails are mandatory and cannot be opted out.
- Failed email sends create admin-visible notices.
- Superadmin template changes are audited.

Tests:

- Template validation tests.
- Acceptance evidence tests.
- PDF snapshot tests.
- Email outbox retry tests.
- Email variable rendering tests.

### Phase 7: Primary Marketplace, Investment Orders, Funding, and Disbursement

Goal: implement end-to-end primary investment.

Tasks:

- Implement public marketplace preview with limited fields:
  - borrower.
  - amount.
  - interest.
  - period.
  - loan type.
  - status.
  - borrower country.
  - currency.
- Implement KYC-gated full loan detail view.
- Implement investment order creation:
  - Requires active account.
  - Requires fresh sensitive-action email code.
  - Requires terms acceptance.
  - Minimum investment 1,000 CHF/EUR default.
  - Maximum investment equals remaining loan capacity.
  - Uses only investable balance lots not older than 30 days.
  - Enforces pending order cap.
- Implement pending order lifecycle.
- Implement admin-entered/manual investment lifecycle for off-platform or legal-entity cases.
- Implement balance-backed committed allocation.
- Move/reserve eligible investor balance into loan funding escrow when a committed order is accepted.
- Implement first-come-first-served allocation:
  - balance allocation timestamp for balance orders.
  - bank value date for externally funded/manual cases.
  - deterministic tie-breaker.
- Implement surplus handling and admin alerts.
- Implement full funding close.
- Implement admin-accepted partial funding close.
- For accepted partial funding, set the accepted funded amount as final loan principal, regenerate the repayment schedule from that principal, calculate borrower success fee on that principal, and require borrower repayment of that principal plus agreed interest.
- Implement investor notifications for partial funding and amount changes.
- Implement borrower success-fee accounting record:
  - 2% to 4% configurable or admin-entered per loan.
  - Deducted from disbursement.
  - No effect on borrower repayment schedule.
- Implement borrower disbursement workflow and evidence upload.
- Implement admin-created manual investments from lender database.
- Create investor holdings/claim records after loan closing.

Acceptance criteria:

- Investors cannot create investment orders without KYC, balance eligibility, sensitive email code, and terms acceptance.
- Orders do not over-allocate the loan.
- Funding close produces investor holdings and ledger postings.
- Borrower success fee is recorded for accounting but does not reduce scheduled principal.
- Accepted partial funding uses the accepted funded amount as final scheduled principal.
- Partial funding is explicit, admin-driven, and notified.

Tests:

- Investment eligibility tests.
- Concurrent order/allocation tests.
- Pending cap tests.
- Overfund/surplus tests.
- Full funding close tests.
- Partial funding close tests.
- Borrower fee accounting tests.
- Manual investment tests.

### Phase 8: Loan Servicing, Repayments, Schedule Recalculation, and Distributions

Goal: support borrower repayments and investor distributions.

Tasks:

- Implement due-date monitoring.
- Set loan/installment late status at day 5 past due.
- Set default status at day 16 past due.
- Implement admin borrower payment event entry:
  - loan.
  - amount.
  - currency.
  - bank value date.
  - evidence upload.
  - notes.
- Match payment against next due installment by default.
- Show warnings for underpayment, overpayment, multiple-installment payment, or early repayment.
- Allow admin to proceed after warning.
- Apply waterfall:
  - fees.
  - penalties.
  - scheduled/current interest.
  - scheduled/current principal.
  - future outstanding principal.
- Keep penalties configurable and set to zero/inactive at launch.
- Implement partial payments.
- Implement payments covering multiple installments for late/defaulted loans.
- Implement partial and full early repayment.
- Recalculate future schedule for same remaining period and lower outstanding principal after early repayment.
- Credit investor distributions to investor balances.
- Generate payment notification emails.
- Allow admin to attach bank statement evidence for lender payments/distributions.
- Mark loan paid when all principal is paid.

Acceptance criteria:

- Payment application is deterministic, auditable, and reversible only through correction events.
- Early repayment changes future schedule according to the documented rule.
- Investor distribution amounts reconcile to holdings.
- Lenders receive notifications when distributions are credited.
- Default/late status changes happen automatically based on due dates.

Tests:

- Regular installment golden test.
- Partial installment golden test.
- Multiple-installment late payment golden test.
- Healthy-loan early repayment golden test.
- Full early repayment test.
- Investor distribution rounding tests.
- Late/default scheduler tests.

### Phase 9: Currency Exchange

Goal: implement investor-facing auxiliary FX settlement and admin-facing external FX settlement management.

Tasks:

- Implement Yahoo Finance FX provider adapter.
- Restrict launch enabled pairs to CHF/EUR and EUR/CHF, while keeping pair configuration extensible.
- Implement no minimum exchange amount.
- Implement maximum conversion limit:
  - launch value CHF 100,000 per investor per day or equivalent.
  - configurable by admin with audit trail.
- Implement background display-rate polling.
- Implement executable quote creation:
  - live rate.
  - 1-minute fixed quote.
  - source currency/amount.
  - target currency/amount.
  - platform fee default 1.5%.
  - quote expiry.
- Implement FX precision/display rules:
  - store rates, execution rates, fees, and intermediate FX calculation values with at least 6 decimals.
  - normal website balances and amounts display 2 decimals.
  - FX quote/confirmation view may show 4 decimals before confirmation.
  - half-up rounding.
- Implement required sensitive-action email code for execution.
- Implement sanity checks:
  - reject zero, null, negative, NaN, malformed, or stale rates.
  - reject unsupported pairs.
  - reject obvious decimal-place errors through min/max per pair.
  - compare executable quote against previous-day average from the same Yahoo Finance provider; alert/hold on +/- 5%.
  - skip display ticks with +/- 2% move from last accepted display tick.
  - optional inverse-rate check when provider supports both directions.
  - fallback-provider divergence check is future-ready but not required at launch.
- Implement balance consumption from source currency.
- Implement target-currency balance credit with inherited ageing deadlines from consumed source balance entries.
- Implement FX fee ledger posting.
- Implement admin FX delta report by day/period:
  - gross sold by currency.
  - gross bought by currency.
  - platform fees.
  - net amount to settle externally.
  - quote/rate evidence.
- Implement admin external settlement bank-operation declaration:
  - sold currency and amount.
  - bought currency and amount.
  - final realized sold amount.
  - final realized bought amount.
  - booking date and value date.
  - bank/PSP references.
  - evidence upload/reference.
- Infer actual executed conversion rate including all fees/costs from the final realized external settlement amounts declared by admin.
- Implement realized FX gain/loss calculation by comparing internal user FX events with declared external execution.
- Implement realized FX surplus/deficit report by currency and period.
- Do not implement unhedged/exposure alerts at launch.

Acceptance criteria:

- Investors can exchange currencies only with eligible balances and valid quote acceptance.
- FX is presented and controlled as auxiliary settlement, not trading/speculation.
- Only CHF/EUR and EUR/CHF pairs are enabled at launch.
- No minimum amount applies, and the configured per-investor daily maximum conversion limit is enforced.
- Executed rate, quote, fee, source lots, and target lot are auditable.
- Admin can see end-of-day/net-period amount to settle externally.
- Admin can declare the actual external FX execution and see realized FX gain/loss without changing investor balances.
- Bad provider data cannot silently create an exchange.

Tests:

- Quote expiry tests.
- FX fee calculation tests.
- FX pair/limit tests.
- FX precision/display rounding tests.
- Sanity-check tests.
- FX inherited-deadline tests.
- FX ledger posting tests.
- Daily delta report tests.
- External FX settlement declaration tests.
- Realized FX gain/loss calculation tests.

### Phase 10: Secondary Market

Goal: implement claim resale and transfer.

Tasks:

- Implement investor holding selection for sale.
- Allow only full-holding listings. Do not allow partial sale, holding split, or partial transfer of a single holding.
- Allow each separate holding in the same project to be listed separately.
- Require positive current principal balance.
- Allow immediate listing after purchase/assignment for current/performing holdings; no minimum holding period.
- Implement sale price as a discount/premium percentage of current principal balance.
- Calculate accrued interest separately, daily, pro rata, through settlement date for current/performing holdings.
- Assign accrued interest up to settlement to seller and future interest after settlement to buyer.
- Calculate maker/taker fees on agreed transfer price excluding accrued interest.
- Round maker/taker fees half-up to nearest cent/minor unit.
- Support configurable minimum maker/taker fee, defaulting to no minimum unless configured.
- Calculate seller net proceeds as transfer price plus accrued interest minus seller fee.
- Calculate buyer total cost as transfer price plus accrued interest plus buyer fee.
- Display current principal balance, sale price, discount/premium, accrued interest, seller fee, seller net proceeds, buyer fee, and buyer total cost.
- Show loan status clearly, including days past due, recovery/default status, last payment date, and public admin note where applicable.
- Allow automatic publication only for current/performing holdings after system checks.
- Route late, overdue, restructured, under-observation, default, recovery, legal-enforcement, payment-incident, or otherwise non-standard holdings into listing request state.
- Implement admin approval/rejection/removal for non-standard listings with approval date, approving admin, reason, and disclosure note in the audit log.
- Require additional buyer risk acknowledgement for approved non-standard listings.
- Require listing terms checkbox and fresh sensitive-action email code.
- Implement public/eligible listing visibility to all active lenders.
- Implement buyer purchase:
  - Requires active account.
  - Requires sufficient eligible balance.
  - Requires secondary-market purchase terms checkbox.
  - Requires additional risk acknowledgement for approved non-standard listings.
  - Requires fresh sensitive-action email code.
  - No admin approval for current/performing listings after automatic checks; non-standard listings require pre-publication admin approval.
- Settle immediately in-platform:
  - debit buyer balance.
  - charge taker fee.
  - charge maker fee.
  - allocate accrued interest to seller where applicable.
  - credit seller proceeds.
  - post platform fees.
  - transfer holding/claim.
  - generate documents.
  - send buyer/seller emails.
- Support external cash path if operationally needed later, but default to balance-based settlement because v1 now keeps balances.

Acceptance criteria:

- Secondary-market listings transfer one full holding only.
- Current/performing listings can publish automatically after system checks.
- Non-standard listings are not visible until admin approval is audit logged.
- Buyer/seller displays reconcile current principal, transfer price, discount/premium, accrued interest, fees, seller net proceeds, and buyer total cost.
- Buyer and seller documents are generated and emailed.
- Claim ownership changes atomically with ledger settlement.
- Seller proceeds become balance lots subject to the same 30/60-day rules.

Tests:

- Full-holding-only listing tests.
- Partial holding sale rejection tests.
- Discount/premium price calculation tests.
- Accrued-interest split tests.
- Half-up fee rounding tests.
- Non-standard listing approval and acknowledgement tests.
- Buyer balance eligibility tests.
- Concurrent purchase tests.
- Maker/taker fee tests.
- Claim transfer and document generation tests.

### Phase 11: Risk, Collections, Recoveries, Public Notes, and Write-Offs

Goal: implement post-default operations without overbuilding legal collections.

Tasks:

- Implement automatic late/default status transitions from servicing.
- Implement loan notes and uploaded internal documents.
- Implement public note upload/authoring by admin.
- Implement optional bulk email/public-note notifications to affected investors.
- Implement recovery event:
  - gross recovered amount.
  - externally deducted legal/recovery costs.
  - third-party recovery costs declared at recovery time.
  - whether Garanta recovery fee applies to this payment.
  - Garanta recovery fee percent, fee base, and fee amount where applied.
  - net amount received by Garanta.
  - net amount available for waterfall allocation.
  - currency.
  - bank value date.
  - project recovery waterfall version/configuration.
  - recovery category split: external recovery/legal costs, platform-approved recovery costs including applied Garanta recovery fee, principal, contractual interest until default date, default/penalty interest after default date if applicable, and other penalties/costs.
  - evidence upload.
  - notes/observations.
- Cut off normal contractual interest at the official default declaration date.
- Calculate default/penalty interest from the official default declaration date instead of regular interest only when configured in the loan/project agreement. Store default/penalty interest percent per project.
- Apply the project-specific recovery waterfall. Default waterfall: external recovery/legal costs, platform-approved recovery costs including applied Garanta recovery fee, principal, contractual interest accrued until default, default/penalty interest, and other penalties/costs.
- Allocate lender-facing recovery buckets pro rata to lender holdings by current principal balance at the recovery event time unless project-specific allocation overrides exist.
- Round lender recovery distribution lines half-up to the currency minor unit and record recovery rounding differences separately.
- Generate recovery/write-off report and affected-lender notification for each recovery payment.
- Implement write-off event with document(s) and note.
- Implement investor portfolio visibility for defaulted loans.
- Allow secondary-market listing requests for defaulted/non-standard loans only through the admin-approved listing workflow with disclosure and additional buyer acknowledgement.

Acceptance criteria:

- Admin can close a default loan with gross recovery, external costs, third-party recovery costs, recovery fee decision, net received, waterfall allocation, category split, evidence, and explanation.
- Recovery allocations are deterministic, project-waterfall based, pro-rata by current principal balance for lender-facing buckets unless overridden by project agreement, rounded, and auditable.
- Recovery/write-off reports show gross-to-net recovery, recovery costs, Garanta recovery fee, waterfall category split, lender allocation, and rounding differences.
- Affected lenders receive recovery distribution notifications.
- Investors see loan status, days past due, and public notes.
- Write-off is documented and reported.

Tests:

- Late/default transition tests.
- Recovery allocation tests.
- Recovery waterfall configuration/version tests.
- Default/penalty interest accrual cutoff tests.
- Garanta recovery fee application tests.
- Third-party recovery cost declaration tests.
- Write-off tests.
- Public note visibility tests.
- Defaulted/non-standard secondary-market listing approval, disclosure, and acknowledgement tests.

### Phase 12: Accounting, Tax, Reporting, and Exports

Goal: provide launch reporting and exportability for admin, accounting, tax, and regulatory needs.

Tasks:

- Implement report request system:
  - on-demand.
  - custom ranges.
  - monthly.
  - quarterly.
  - yearly.
  - PDF.
  - CSV.
  - ZIP evidence packages.
- Implement accounting exports:
  - configurable monthly Bexio export.
  - transaction-level source ledger rows.
  - optional summarized rows by configured account/date/currency mapping.
  - cash movements.
  - fees.
  - borrower success fees.
  - secondary-market fees.
  - FX fees.
  - penalties.
  - withdrawals/refunds.
  - loan disbursements.
  - repayments/distributions.
  - Garanta accrued revenue/commission balances.
  - Garanta out/in transfers.
  - realized FX gain/loss.
  - bank reconciliation differences.
  - currency-specific ledger reports.
- Implement CHF base reporting where required, while keeping currency-specific ledgers.
- Leave revaluation to the accountant.
- Store configurable tax metadata and Bexio mapping fields; do not hardcode VAT/reverse-charge logic.
- Implement annual tax information statements:
  - available to all investors for lender statements.
  - admin-generated for borrowers because borrowers have no portal.
  - internal/admin-generated for Garanta.
  - English.
  - year-based.
  - generated from the same immutable transaction-level ledger and complete annual account statement.
  - participant-specific income/cost summary fields.
  - information-only principal and balance movement sections.
  - informational-only disclaimer, not tax advice.
  - regenerated on demand.
- Implement operational reports:
  - deposits and reconciliation.
  - bank operation declarations.
  - ledger-bank reconciliation by currency.
  - Garanta accrued revenue by arbitrary period.
  - Garanta accrued revenue/commission balance held in collection accounts.
  - withdrawals due.
  - ageing balances.
  - FX delta.
  - realized FX gain/loss.
  - pending orders.
  - loan funding.
  - repayment due/late/default.
  - investor exposure by defaulted loan.
  - action log.
  - write-off report.
  - failed emails.
  - KYC statuses stored locally.
- Implement redacted and full export variants.
- Implement report definition versioning.

Acceptance criteria:

- Admins can generate all launch reports as PDF and CSV.
- Evidence ZIPs include a manifest.
- Reports are reproducible from stored source data.
- Full/unredacted exports are audit logged.

Tests:

- Accounting export golden tests.
- Tax statement golden tests.
- Redaction tests.
- ZIP manifest tests.
- Report reproducibility tests.

### Phase 13: Investor Portal Completion

Goal: assemble the investor user experience across all financial features.

Tasks:

- Dashboard:
  - balances by currency.
  - ageing warnings.
  - portfolio summary.
  - pending actions.
  - recent activity.
- Deposits:
  - collection account instructions by currency.
  - payment reference.
  - reminders about 30/60-day rules.
- Withdrawals:
  - bank details.
  - available balance.
  - forced-withdrawal warning.
  - status history.
- Marketplace:
  - public preview.
  - gated full details.
  - invest flow.
- Portfolio:
  - holdings.
  - exposure metrics by borrower, loan, country, sector, rating, collateral type, maturity, and defaulted loan where available.
  - repayment history.
  - default/late disclosure.
  - documents.
- Secondary market:
  - create listing.
  - browse listings.
  - buy listing.
- FX:
  - quote preview.
  - countdown.
  - execute exchange.
  - history.
- Documents:
  - generated documents.
  - annual tax information statements.
  - account statements.
- Settings:
  - profile.
  - bank accounts.
  - marketing consent.
  - phone verification status.
  - account closure request instructions.

Acceptance criteria:

- The investor can complete the full lifecycle without admin help, except for manual bank-side operations.
- All financial actions show clear balances, deadlines, fees, and required confirmations.
- Text does not imply Garanta can extend the 60-day deadline.

Tests:

- Playwright end-to-end investor lifecycle.
- Responsive UI checks.
- Access-control checks for documents and loan data.

### Phase 14: Admin Operations Portal Completion

Goal: make daily operations executable through the admin portal.

Tasks:

- Daily dashboard:
  - deposits to reconcile.
  - withdrawals due.
  - forced withdrawals due.
  - ageing balances by day bucket.
  - FX settlement delta.
  - funding loans.
  - late/default loans.
  - due repayments.
  - failed emails.
  - KYC/admin tasks.
- User operations:
  - investor search.
  - legal-entity lender management.
  - restrictions/closure/anonymization.
  - balance view.
  - documents.
  - audit.
- Borrower and loan operations:
  - create borrower.
  - upload documents.
  - create loan.
  - publish/unpublish where allowed.
  - lower amount after commitments with custom message.
  - add public note.
- Cash operations:
  - reconcile deposits.
  - mark withdrawals finalized.
  - process refunds.
  - attach evidence.
- Servicing:
  - enter borrower payments.
  - review warnings.
  - apply payment.
  - attach bank statement.
- Secondary market oversight:
  - listing search.
  - settlement view.
  - fee reports.
- FX operations:
  - quote sanity alerts.
  - daily delta report.
  - settlement evidence.
- Reporting:
  - generate PDF/CSV/ZIP exports.
  - audit full exports.
- Audit:
  - search action log.
  - filter by actor, object, date, operation.

Acceptance criteria:

- All documented v1 daily operations are possible in the admin portal.
- Admins do not need database access for ordinary operations.
- Every admin operation writes audit events.

Tests:

- Admin Playwright flows.
- Permission tests.
- Audit completeness tests.
- Operational report tests.

### Phase 15: Security, Privacy, Hardening, and Data Lifecycle

Goal: make v1 production-ready under good internal controls.

Tasks:

- Implement strict server-side authorization checks.
- Add rate limits for auth, magic links, email codes, phone verification, and public endpoints.
- Add CSRF/session protections appropriate to the chosen auth model.
- Add secure cookie and transport settings.
- Add upload size/type restrictions.
- Add malware-scan enforcement.
- Add PII masking in logs.
- Add production data access logging for tech/admin access.
- Implement account closure:
  - allowed only for clean/empty accounts.
  - retain required documents and financial/audit records.
  - restrict login after closure.
- Implement anonymization workflow:
  - available as an admin checkbox at account closure time.
  - reversible pseudonymization/encryption, not irreversible deletion.
  - encrypt/pseudonymize name, email, and structured KYC/KYB/AML fields that directly identify the user.
  - preserve financial records, documents, KYC/KYB/AML evidence, ledger/audit/legal/tax records, and operational references intact.
  - use asymmetric encryption: public key available to the app through env/config/db; private decryption key kept offline outside the application.
  - audit closure, pseudonymization, and any later offline-key restoration/decryption event.
- Implement production-to-staging anonymization process.
- Implement backup jobs:
  - daily backups at 02:30 Europe/Zurich local time.
  - encrypted private S3 backup bucket in AWS Zurich.
  - 62-day lifecycle retention.
  - manual restore procedure.
  - quarterly restore drill and pre-money-movement restore drill.
- Implement tech-team email alerts for critical failures:
  - failed background jobs.
  - FX sanity failures.
  - repeated email failures.
  - provider webhook failures.
  - suspicious auth/rate-limit activity.
  - ledger imbalance detection.
- Implement a ledger integrity checker job.

Acceptance criteria:

- Security-sensitive behavior is tested.
- Backups can be restored in a test environment.
- Staging cannot send real emails/SMS or call production provider endpoints.
- Ledger imbalance alerts are impossible to ignore.

Tests:

- Authorization test matrix.
- Rate-limit tests.
- Upload security tests.
- Anonymization tests.
- Backup restore drill.
- Ledger integrity tests.

### Phase 16: Deployment, UAT, Migration, and Go-Live

Goal: move from built software to controlled production launch.

Tasks:

- Deploy staging.
- Configure provider sandboxes.
- Load sample data and run full UAT scripts.
- Deploy production infrastructure.
- Configure production secrets.
- Configure domains and TLS.
- Configure AWS Zurich EC2 host, EBS encryption, Docker Compose runtime, ECR image pull, private S3 buckets, and backup bucket lifecycle.
- Configure SendGrid sender domain.
- Configure Twilio production.
- Configure Didit production.
- Configure Yahoo Finance FX access.
- Configure bank collection accounts.
- Configure backup schedules.
- Configure alert recipients.
- Load final legal templates.
- Create superadmin env credentials.
- Create initial admin users.
- Run pre-launch data migration/seed:
  - currencies.
  - platform settings.
  - collection accounts.
  - templates.
  - fees.
  - reminder schedules.
- Run final acceptance scenarios.
- Freeze launch configuration.
- Launch first controlled loan with limited operational monitoring.

Acceptance criteria:

- Staging UAT passes all critical scenarios.
- Production smoke tests pass.
- Legal/provider/banking/accounting TODOs needed for real money are closed.
- Rollback and restore procedures are documented and tested.
- Admins can operate first loan without developer intervention.

Tests:

- Production smoke test.
- Provider sandbox/prod connectivity tests.
- End-to-end first-loan dry run.
- Backup restore drill.
- Report export validation.

## 9. Critical End-to-End Scenarios

These scenarios should become automated end-to-end tests or scripted UAT checks.

### Scenario A: Natural-Person Primary Investment

1. Investor registers.
2. Investor accepts registration terms.
3. Investor verifies phone.
4. Investor completes Didit KYC successfully.
5. Admin reconciles CHF deposit.
6. Investor sees investable balance.
7. Investor opens full loan detail.
8. Investor confirms email code.
9. Investor accepts primary-market terms.
10. Investor places investment.
11. Loan reaches full funding.
12. Admin closes funding.
13. Borrower success fee is recorded.
14. Holding is created.
15. Investment document is generated and emailed.

### Scenario B: Deposit Ageing and Forced Withdrawal

1. Investor deposit is credited with bank value date.
2. Day 25 reminder is sent.
3. Day 30 passes and lot becomes withdraw-only.
4. Day 46, 53, 58, and 59 reminders are sent.
5. Day 60 reminder is sent.
6. If usable IBAN exists, admin forced-withdrawal task is created.
7. If no usable IBAN exists, account enters penalty/freeze mode.
8. User cannot perform financial actions except adding usable IBAN.

### Scenario C: Early Repayment

1. Loan is healthy.
2. Next regular installment is 1,000 CHF.
3. Admin records a 3,000 CHF borrower payment.
4. System warns that payment exceeds next installment.
5. Admin proceeds.
6. Payment covers current interest.
7. Payment covers current principal.
8. Remaining amount reduces future outstanding principal.
9. Future installments are recalculated for the same remaining period.
10. Investor distributions are credited to balances.

### Scenario D: Secondary-Market Sale

1. Investor holds claim in active loan.
2. Investor lists one full holding.
3. System calculates current principal, transfer price, discount/premium, accrued interest, and maker/taker fees.
4. Investor accepts listing terms and confirms email code.
5. Buyer accepts listing with eligible balance.
6. Buyer accepts purchase terms and confirms email code.
7. Buyer balance is debited.
8. Maker and taker fees are posted.
9. Seller proceeds are credited.
10. Claim transfer is recorded.
11. Documents and emails are generated.

### Scenario E: FX Exchange

1. Investor has EUR balance.
2. Investor requests EUR to CHF quote.
3. Provider rate passes sanity checks.
4. Quote is fixed for 1 minute.
5. Investor confirms email code and executes.
6. EUR balance lot is consumed.
7. CHF balance lot is credited with inherited ageing deadlines from the consumed EUR source entries.
8. FX fee is posted.
9. Admin sees the net FX settlement delta in the daily delta report.

### Scenario F: Default and Recovery

1. Borrower misses due date.
2. Loan/installment becomes late at day 5.
3. Loan/installment becomes default at day 16.
4. Admin uploads public note or sends affected-lender communication.
5. Admin records gross recovery, external legal/recovery costs, third-party recovery costs, whether Garanta recovery fee applies, net received, note, and evidence.
6. System applies the project recovery waterfall, with contractual interest cutoff at default and separate default/penalty interest where applicable.
7. System allocates lender-facing recovery buckets pro rata to lender holdings based on current principal balance unless the project agreement defines a different allocation method.
8. Investor balances are credited.
9. Default/write-off/recovery report reflects gross-to-net, recovery costs, recovery fee, waterfall category split, lender allocation, and rounding difference.

## 10. Ledger Design Requirements

The ledger is the highest-risk component and should be implemented early and tested heavily.

Required characteristics:

- Double-entry postings.
- Immutable journal entries.
- Atomic posting inside database transactions.
- Deterministic account mapping.
- Currency-specific postings. Do not post cross-currency entries without explicit FX bridge records.
- Every user-facing balance must reconcile to ledger accounts and active balance lots.
- Every platform fee must be posted separately from investor principal/interest.
- Every correction must use reversing or compensating entries.
- Ledger postings must reference the source domain object.
- Ledger entries must include:
  - event id.
  - event type.
  - booking date.
  - value date.
  - effective date.
  - created timestamp.
  - currency.
  - gross amount.
  - net amount.
  - debit account.
  - credit account.
  - lender reference where applicable.
  - borrower reference where applicable.
  - loan/project reference where applicable.
  - bank/PSP reference where applicable.
  - evidence reference where applicable.
  - tax metadata and tax-category placeholders.
  - source type/id.
  - actor type/id.
  - idempotency key.
  - audit event id.
  - reversal/correction history reference where applicable.
- Client-money/settlement flows must not be posted as Garanta revenue. This includes lender principal, borrower repayments, interest distributed to lenders, deposits, withdrawals, and recovery distributions.
- Garanta P&L-relevant items must be posted separately, including Garanta fees, borrower success fees, secondary-market fees, FX margin/fees, penalties/handling fees if activated, and operating costs.

Recommended internal ledger account groups:

- Collection cash by currency.
- Investor liabilities by currency.
- Investor balance lots by source.
- Suspense/unmatched cash.
- Loan funding escrow/liability.
- Borrower disbursement payable.
- Platform fee income.
- Borrower success fee income/accrual.
- Secondary-market fee income.
- FX fee income.
- Withdrawal payable.
- Refund payable.
- Penalty income or liability treatment, subject to accounting decision.
- Recovery distribution payable.
- Recovery gross amount memo/reporting category.
- Externally deducted legal/recovery cost category.
- Third-party recovery cost category.
- Recovery fee revenue.
- Default/penalty interest payable/category.
- Recovery rounding difference account/category.

## 11. Schedule and Repayment Calculation Requirements

The schedule engine should be deterministic and versioned.

Requirements:

- Store schedule version.
- Store calculation inputs.
- Store rounding rules.
- Store installment rows as persisted records.
- Never silently mutate paid installments.
- Future schedule recalculation creates a new schedule version or superseded future rows.
- Payment events are the source of truth for modifications.
- Admin manual override is allowed at schedule creation, and all overridden rows must be marked as admin-overridden.
- Post-launch restructuring outside payment events is not a v1 feature.

Default assumptions to implement unless later changed:

- Due/late/default status checks use calendar days.
- Interest is an annual nominal rate.
- Monthly installments are the default installment frequency.
- Currency minor-unit rounding on each installment line.
- Final installment absorbs rounding residue.
- Interest rate stored with sufficient precision, not rounded only to display precision.

## 12. Balance Ageing Requirements

Balance ageing must be source-lot based, not account-total based.

Each lot needs:

- source type: deposit, installment, secondary-market proceeds, FX proceeds, refund, correction, penalty reversal.
- received timestamp.
- bank value date where applicable.
- internal effective timestamp where applicable.
- 30-day investment deadline.
- 60-day withdrawal deadline.
- reminder state.
- penalty state.
- freeze state contribution.

Rules:

- Deposits, installments, secondary-market proceeds, and FX proceeds are all subject to ageing.
- Lots older than 30 days cannot be invested or reinvested.
- Primary-market orders cannot consume source lots whose 30-day investment deadline is earlier than the loan funding deadline.
- Lots older than 60 days must be withdrawn or forced-withdrawn where possible.
- If no usable IBAN exists after day 60, financial actions are frozen except adding usable IBAN.
- Penalty default is 1% simple daily penalty after day 60, env/deployment-configurable, capped at the remaining overdue source balance, never negative, with terminal `penalty_exhausted` source status if fully consumed.
- FX conversion does not reset ageing for the target-currency lot. The target lot inherits deadlines from the consumed source lots; when multiple source lots are consumed, v1 uses the newest/latest consumed expiry timestamp while retaining source lineage.

## 13. Authorization Matrix

Launch roles:

- Superadmin.
- Admin.
- Investor.
- Legal-entity lender representative, if enabled.

Superadmin:

- Manage admin users.
- Manage platform parameters.
- Manage currencies.
- Manage collection accounts.
- Manage templates.
- Access all admin operational screens.

Admin:

- Create and manage borrowers.
- Create and manage legal-entity lenders.
- Create, publish, and operate loans.
- Reconcile deposits.
- Confirm withdrawals/refunds.
- Enter repayments.
- Manage secondary-market operations where needed.
- Generate reports.
- Close/restrict accounts.
- Upload notes/documents/evidence.

Investor:

- Register and complete KYC if natural person.
- View dashboard.
- Deposit to collection account.
- Invest in primary market.
- Receive repayments into balance.
- Withdraw balance.
- Exchange currencies.
- List holdings on secondary market.
- Buy secondary-market listings.
- View documents, statements, and tax reports.

Legal-entity lender representative:

- Behaves like investor after admin creation and activation.
- No self-service KYC flow.

## 14. API and Internal Boundary Style

No public API is required at launch.

Use internal APIs for the frontend:

- Version endpoints under `/api/v1/`.
- Separate public, investor, and admin route groups.
- Keep serializers/request schemas separate from domain models.
- Enforce permissions in backend, never only in frontend.
- Use explicit command endpoints for financial actions:
  - `POST /investments/orders`.
  - `POST /fx/quotes`.
  - `POST /fx/exchanges`.
  - `POST /secondary/listings`.
  - `POST /secondary/purchases`.
  - `POST /withdrawals`.
  - `POST /admin/repayments`.
  - `POST /admin/reconciliation/deposits`.
- Use idempotency keys for command endpoints.

## 15. Testing Strategy

Testing must be designed so agents can make changes confidently without needing to understand the full platform at once.

### Unit Tests

Focus:

- Money arithmetic.
- Rounding.
- Schedule generation.
- Payment waterfalls.
- LTV calculation.
- FX sanity.
- Template rendering.
- Permission policies.

### Integration Tests

Focus:

- Ledger posting.
- Balance lot ageing.
- KYC webhook handling.
- SendGrid/Twilio/Didit adapters in mock mode.
- Object storage and file access.
- Report generation.
- PDF generation.

### End-to-End Tests

Use Playwright.

Cover:

- Natural-person registration and KYC mock pass.
- Deposit reconciliation.
- Primary investment.
- Loan funding close.
- Borrower repayment.
- Investor withdrawal.
- FX exchange.
- Secondary-market sale.
- Default/recovery.
- Admin reporting export.

### Golden Tests

Create fixed-input expected-output fixtures for:

- Repayment schedules.
- Early repayment recalculation.
- Investor distribution allocation.
- Secondary-market fee settlement.
- FX quote/exchange settlement.
- Accounting exports.
- Tax statements.

Golden fixtures should live close to the owning module and use stable JSON or CSV inputs/outputs. When a golden output changes, the work item must explain why the financial behavior changed.

### Property/Invariant Tests

Add invariant tests for:

- Ledger debits equal credits.
- No negative user balance unless explicitly allowed by a correction state.
- Investment allocation never exceeds loan capacity.
- Holding principal never goes below zero.
- Source lots cannot be consumed twice.
- Day-30 lots cannot be invested.
- Day-60 lots cannot remain actionable without warning/freeze/forced-withdrawal state.

### Agent Test Packs

Each high-risk module should expose named test packs in the Makefile so agents do not need to discover test paths manually:

- `make test-ledger`
- `make test-balances`
- `make test-loans`
- `make test-marketplace`
- `make test-servicing`
- `make test-fx`
- `make test-secondary`
- `make test-documents`
- `make test-reports`

Each command should run the module's unit, integration, and golden tests, but not the entire suite unless required.

## 16. CI/CD and Environments

GitHub Actions should run:

- Backend lint.
- Backend type check.
- Backend tests.
- Frontend lint.
- Frontend type check.
- Frontend tests.
- Frontend build.
- Docker build.
- Migration check.
- OpenAPI schema generation.
- Generated frontend client freshness check.
- Import-boundary checks.
- `make agent-check`.

Deployment:

- `main` deploys to staging automatically after checks.
- Production deploys after checks according to the configured branch/tag process. The documented preference is no manual approval, but production deployment should still be traceable and reversible.
- Run database migrations as a release step.
- Keep rollback commands documented.

Environment separation:

- Separate Docker Compose project names.
- Separate databases.
- Separate object storage buckets or prefixes.
- Separate Redis instances or namespaces.
- Separate workers/queues.
- Separate logs/log labels.
- Separate SendGrid/Twilio/Didit/FX credentials or mock mode.
- Separate domains/subdomains.
- Staging must never send real user communications after anonymized data import.

## 17. Observability and Operations

V1 does not require sophisticated observability, but it does require useful telemetry and rich logs.

Implement:

- Structured request logs.
- Structured domain operation logs.
- Background job logs.
- Provider call logs with redacted payloads.
- Audit-event browser.
- Ledger integrity alert.
- Failed-job alert.
- Failed-email admin notice.
- FX sanity alert.
- Didit webhook failure alert.
- Backup failure alert.

Launch runtime logs should be JSON. Production logs should be shipped to CloudWatch Logs or equivalent AWS-native storage with 90-day retention if cost remains acceptable; local Docker logs should be rotated by size/short retention.

Daily admin operations view should show:

- Deposits to reconcile.
- Withdrawals and forced withdrawals.
- Balances approaching 30/60-day deadlines.
- Penalty/freeze accounts.
- FX settlement delta to settle.
- Loans funding.
- Loans nearing maturity.
- Repayments due.
- Late/default loans.
- Failed emails.
- KYC/admin tasks.
- Pending reports.

## 18. Privacy and Data Retention

Launch assumptions:

- Financial data retained at least 10 years.
- Audit logs retained indefinitely for now.
- Didit performs the launch natural-person KYC capture/check flow.
- Garanta stores full required local KYC/KYB/AML evidence on Garanta-controlled infrastructure located in Switzerland, including provider identifiers, statuses, decision metadata, downloaded reports where possible, raw provider webhook payloads where possible, supporting-document references/local copies where possible, manual-review decisions, and audit trail.
- KYC/KYB/AML evidence is retained for at least 10 years, subject to final legal/compliance confirmation.
- Platform copies of KYC-related data may be kept indefinitely at launch, subject to final legal policy.

Anonymization approach:

- Do not delete financial, audit, or legal records required for compliance.
- For eligible closed/empty accounts, optionally encrypt/pseudonymize direct identifiers through the admin closure checkbox.
- Treat v1 privacy anonymization as reversible pseudonymization, not true irreversible anonymization.
- Direct identifiers include name, email, and structured KYC/KYB/AML fields that would allow a third party to directly identify the user.
- Preserve ledger/accounting references, financial records, documents, KYC/KYB/AML evidence, and audit integrity.
- Store/use only the public encryption key in the application environment/configuration/database. Keep the private decryption key offline and outside the application.
- Require an offline key-controlled process for any restoration/decryption of direct identifiers.
- Keep closure and anonymization actions audited.

Production-to-staging data copy:

- Replace names, emails, phones, addresses, IBANs, document names, and provider IDs with deterministic fake values.
- Preserve relationships, statuses, balances, ledger structure, and edge cases.
- Remove tokens, secrets, webhooks, and provider credentials.
- Disable external email/SMS/provider calls.

## 19. Go-Live Checklist

Do not enable production real-money operations until these are complete:

- Legal approval for balances, FX, 30/60-day rule, forced withdrawal, and penalties.
- Final registration, investment, secondary-market, and listing terms loaded.
- Final legally approved risk acknowledgement/risk disclosure document loaded.
- Didit production configured and tested.
- SendGrid sender domain verified.
- Twilio phone verification configured.
- Yahoo Finance FX access validated and legal terms checked.
- Bank/payment partner selected.
- CHF and EUR collection IBANs configured.
- Statement/reconciliation process tested.
- Accounting chart/export mapping approved.
- Annual tax information statement output approved.
- Production backups configured and restore-tested.
- Admin users created.
- Staging and production isolation verified on the shared host.
- Superadmin env credentials verified and rotation procedure documented.
- Alert recipients configured.
- First loan data validated.
- End-to-end UAT scenarios passed.
- Admin operations runbook completed.
- Production smoke test passed.

## 20. Suggested Implementation Order Summary

1. Bootstrap project, CI, Docker, settings, and deployment skeleton.
2. Add agent-facing repo conventions: `AGENTS.md`, Makefile commands, import boundaries, OpenAPI generation, generated frontend client, MSW mocks, and fixture conventions.
3. Build foundation primitives: money, config, audit, events, files, jobs.
4. Build accounts, auth, KYC, phone verification, and role gates.
5. Build admin portal shell and configuration.
6. Build borrowers, legal-entity lenders, loans, risk, collateral, and schedules.
7. Build ledger, balance lots, deposits, withdrawals, ageing, and reconciliation.
8. Build templates, documents, clickwrap, PDFs, and email system.
9. Build primary marketplace and funding close.
10. Build servicing, repayments, distributions, and schedule recalculation.
11. Build FX quotes, exchanges, sanity checks, and delta reporting.
12. Build secondary market and claim transfers.
13. Build defaults, recoveries, write-offs, and public notes.
14. Build reporting, accounting exports, annual tax information statements, and evidence ZIPs.
15. Complete investor portal and admin daily operations views.
16. Harden security, privacy, backups, anonymization, and observability.
17. Run UAT, configure production providers, deploy, and launch first controlled loan.

## 21. V1 Definition of Done

V1 is complete when:

- Natural-person lenders can register, complete KYC, deposit, invest, receive repayments, exchange currency, use the secondary market, withdraw, and access statements/documents.
- Legal-entity lenders can be created by admin and can operate as lenders without a self-service Didit flow only after admin-recorded KYB/AML approval.
- Borrowers are legal-entity records only, have no portal, and cannot be used in platform transaction workflows until KYB/AML approval.
- Admins can create borrowers, loans, documents, investments, reconciliations, repayments, recoveries, reports, and exports without database access.
- Superadmins can configure platform parameters, currencies, templates, collection accounts, and admins.
- All financial movements post through an immutable double-entry ledger.
- Balance lots enforce 30-day investment and 60-day withdrawal rules.
- Balance-funded primary-market orders are blocked when the loan funding deadline exceeds the selected source lots' remaining 30-day investment window.
- FX is quote-based, fee-bearing, sanity-checked, and reportable.
- Primary and secondary market flows generate documents, emails, ledger entries, holdings, and audit events.
- Repayment events can handle regular, partial, multiple-installment, and early-repayment cases.
- Late/default/recovery/write-off flows are operational.
- Accounting, tax, regulatory, and operational exports are available in PDF/CSV/ZIP where applicable.
- Backups, audit logs, provider adapters, email retries, file access, and production alerts are working.
- UAT and critical automated tests pass.

## 22. Deferred After V1

These are intentionally not part of launch implementation:

- Borrower portal.
- Borrower self-service.
- Public API.
- Bank-feed automation.
- Automated withdrawals or automated external FX execution.
- E-signature provider.
- Maker-checker approval enforcement.
- Auto-invest.
- Sophisticated BI/data warehouse.
- Sophisticated observability platform.
- Formal public SLA tooling.
- In-platform legal collections workflow tracking beyond notes, documents, public notes, recovery events, and write-offs.
- In-platform ongoing AML monitoring beyond Didit status/result integration.
