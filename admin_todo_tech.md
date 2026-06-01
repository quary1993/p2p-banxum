# Admin TODO: Technical Architecture and Implementation Decisions

Status: Launch technical baseline resolved.
Last updated: 2026-06-01.

This file tracks architecture and strictly technical decisions. It does not track provider credentials, legal wording, accounting policy, or business procedure unless the decision is a technical implementation detail.

Blocking means the technical team cannot complete the named implementation area without making or confirming the decision. Non-blocking means the implementation plan already has a safe default, or the item is future/polish.

## Blocking

No technical architecture blockers remain for implementation after the 2026-06-01 launch-infrastructure decision set.

Real deployment still needs the accounts/access items in `admin_todo_accounts.md`, especially AWS, GitHub, DNS, provider credentials, SendGrid, Twilio, Didit, Yahoo Finance access, and bank/collection-account details.

## Resolved Launch Technical Decisions

### Production/Staging Deployment Topology

Decision:

- Use AWS as the launch cloud provider.
- Use AWS `eu-central-2` Europe (Zurich) as the default launch region for the whole application stack, not only KYC/KYB/AML evidence storage.
- Run staging and production on the same EC2 instance at launch for cost reasons.
- Use Docker Compose on a VM/EC2 instance, not ECS/Fargate/Kubernetes at launch.
- Use a burstable general-purpose EC2 instance class. Launch target: 2 vCPU / 8 GB RAM baseline, such as `t3a.large`, `t3.large`, or Graviton equivalent if all production containers are confirmed multi-architecture compatible.
- Use encrypted EBS for the application host volume.
- Keep staging and production logically isolated on the same host:
  - separate Docker Compose project names.
  - separate environment files.
  - separate PostgreSQL databases and users.
  - separate Redis instances or Redis databases/namespaces.
  - separate object-storage buckets or prefixes.
  - separate background workers and queues.
  - separate logs and log labels.
  - separate domains/subdomains.
  - separate provider credentials or staging mock/sandbox mode.
- Use one reverse proxy on the host, such as Caddy, Traefik, or nginx, with TLS automation and routing to the prod/staging app containers.
- Staging must never send real user emails/SMS, call production provider endpoints, or perform real money-moving operations.

Rationale:

This is the lowest-complexity AWS deployment that is still operationally sound for the expected launch traffic of roughly 50-100 concurrent users. Choosing Zurich for the full stack avoids split-region compliance complexity for KYC/KYB/AML evidence and keeps later migration paths clean. Docker Compose on EC2 is cheaper and easier to operate than ECS/RDS/ElastiCache at launch, while the codebase still keeps adapter boundaries so services can be moved out later.

Scale path:

- Step 1: resize the EC2 instance vertically.
- Step 2: move PostgreSQL to RDS PostgreSQL, preferably single-AZ first for cost control.
- Step 3: move Redis to ElastiCache or a managed Redis-compatible service.
- Step 4: split staging and production onto separate EC2 instances.
- Step 5: move app/worker containers to ECS/Fargate behind an ALB if traffic or operational needs justify it.
- Step 6: add CloudFront only if public/static traffic or asset distribution needs it.

### Database and Redis

Decision:

- Use self-hosted PostgreSQL in Docker on the launch EC2 instance for the first cost-optimized production version.
- Use separate PostgreSQL databases and users for staging and production.
- Use WAL archiving or daily logical backups at launch; RDS point-in-time recovery is a later scaling/safety upgrade.
- Use Redis in Docker at launch, with separate Redis instances or strict DB/namespace separation for staging and production.
- Redis is treated as disposable operational state. Durable financial state must remain in PostgreSQL and append-only ledger/event tables.

Rationale:

Self-hosted PostgreSQL and Redis minimize launch cost. This is acceptable only because launch traffic is expected to be low and the platform has daily encrypted backups, manual restore runbooks, ledger integrity checks, and a documented RDS migration path.

### Object Storage and KYC Evidence Storage

Decision:

- Use private S3 buckets in AWS Zurich for documents, generated PDFs, evidence packages, KYC/KYB/AML retained evidence, and backups.
- Use separate buckets or prefixes for production and staging.
- Use server-side encryption for all buckets. KYC/KYB/AML evidence, backups, and privacy-sensitive exports should use KMS-backed encryption where feasible.
- Block public access on all private buckets.
- Use signed URLs or backend-mediated downloads only.
- Do not replicate KYC/KYB/AML evidence outside Switzerland unless legal/compliance later approves that architecture.

Rationale:

Zurich S3 keeps the evidence boundary simple and reduces implementation complexity compared with split compute/storage regions.

### Backup and Restore Implementation

Decision:

- Store backups in a dedicated private S3 bucket in AWS Zurich, separate from live document buckets.
- Encrypt backups server-side, preferably with KMS-backed keys if available in the account.
- Run daily backups at 02:30 Europe/Zurich local time.
- Keep two months of backups through S3 lifecycle expiration, using 62 days as the operational retention setting.
- Back up:
  - PostgreSQL production database.
  - PostgreSQL staging database where useful, lower priority than production.
  - object-storage metadata and manifest/checksum files.
  - encrypted copies of application configuration needed for restore, excluding plaintext secrets in repository artifacts.
- Backup jobs must emit success/failure records and email the tech alert mailbox on failure.
- Restore process is manual at launch:
  - provision or clean target host/environment.
  - stop app/worker containers.
  - restore selected database dump.
  - verify migrations/schema version.
  - verify object manifest/checksums and required private objects.
  - run ledger integrity and smoke checks.
  - reopen app access.
- Run a restore drill at least quarterly and before first production money movement.

Rationale:

Daily encrypted backups with a tested manual restore keep cost low while providing a concrete operational recovery path.

### Production-to-Staging Anonymization Rules

Decision:

- Production data may be copied to staging only through an anonymization command or pipeline.
- Direct identifiers are deterministically replaced:
  - names.
  - emails.
  - phone numbers.
  - addresses.
  - IBANs and bank account labels.
  - provider IDs where they could identify a real person or case.
  - document file names that contain personal or bank data.
- Preserve:
  - internal IDs where safe.
  - relationships.
  - balances.
  - ledger/event structure.
  - dates/timestamps.
  - loan and repayment states.
  - edge cases needed for testing.
- Remove or replace:
  - provider credentials.
  - webhook secrets.
  - access tokens.
  - message IDs where sensitive.
  - signed URL material.
- Staging must force all outbound email/SMS/provider/bank integrations into sandbox, mock, or disabled mode.
- No re-identification mapping is stored in staging.

Rationale:

This preserves realistic financial and operational structure for testing without exposing production personal/contact/bank data or triggering real external actions.

### PDF Rendering Engine

Decision:

- Use WeasyPrint as the launch HTML-to-PDF rendering engine for server-generated transactional, tax, statement, and evidence PDFs.
- Use strict HTML/CSS templates that do not rely on client-side JavaScript.
- Keep Playwright/Chromium available for frontend/browser tests and as a future fallback PDF renderer only if WeasyPrint cannot satisfy a template requirement.
- Include a deployment-image proof early in implementation to verify fonts, page breaks, file size, and PDF rendering on the production container image.

Rationale:

WeasyPrint is simpler and lighter for server-side legal/accounting PDFs than running Chromium in production, which fits the cost-optimized single-host launch model.

### File Malware Scanning Approach

Decision:

- Use a ClamAV-compatible scanner adapter at launch, running locally/containerized on the application host.
- Store uploads first in private quarantine storage.
- Scan asynchronously.
- Files are not visible, downloadable, or usable in regulated workflows until scan status is `clean`.
- Files with scan status `infected`, `failed`, or `timeout` remain quarantined and create an admin/tech task.
- Launch maximum upload size: 50 MB per file unless a stricter module-specific limit applies.
- Larger files are rejected in-platform and handled offline if Garanta needs them.
- Scanner definitions update at least daily.

Rationale:

Asynchronous quarantine avoids blocking uploads on scanner latency while still preventing unscanned files from entering operational workflows.

### OpenAPI and Generated Client Freshness Policy

Decision:

- Generate OpenAPI with `drf-spectacular`.
- Commit the generated OpenAPI schema.
- Generate TypeScript API clients/hooks with Orval.
- Commit generated frontend client files.
- CI fails if the OpenAPI schema or generated client files are stale.
- Generated files live under stable paths and are not manually edited.

Rationale:

Committed generated contracts make the repository easier for implementation agents to work with and reduce frontend/backend contract drift.

### Webhook Retry and Dead-Letter Defaults

Decision:

- Use idempotent webhook/event processing.
- Retry failed provider/webhook jobs up to 8 attempts.
- Launch retry schedule: 1 minute, 5 minutes, 15 minutes, 1 hour, 3 hours, 12 hours, 24 hours, 48 hours.
- After final failure, move the event to dead-letter status and email the tech alert mailbox.
- Admin portal may show failed integration tasks, but v1 replay can be a tech-team management command rather than a full admin UI replay tool.

Rationale:

This is operationally safe without building a large integration-operations UI before volume justifies it.

### Structured Logging and Telemetry Field Standards

Decision:

- Use JSON structured logs for app, worker, scheduler, provider, and deployment jobs.
- Include at minimum:
  - timestamp.
  - environment.
  - service.
  - version/git SHA.
  - request ID/correlation ID.
  - actor/user/admin ID where available.
  - IP/user-agent where relevant.
  - event type.
  - domain object type and ID.
  - severity.
  - outcome/status.
  - duration.
  - provider name/status where relevant.
  - redacted error details.
- Never log plaintext secrets, passwords, full tokens, full IBANs, full document contents, or unredacted provider payloads in app logs.
- Store immutable audit/ledger events in the database, not only in log files.
- Ship production logs to CloudWatch Logs or equivalent AWS-native log storage with 90-day launch retention if cost remains acceptable.
- Keep local Docker logs rotated aggressively, for example 14 days or size-based rotation.
- Critical alerts go to the tech alert mailbox.

Rationale:

This gives enough operational visibility without paying for a full APM stack on day one.

### Production Access Control Process

Decision:

- Production server access is limited to authorized tech-team users.
- Prefer AWS Systems Manager Session Manager over public SSH where feasible.
- If SSH is required, restrict by key, disable password login, and limit access through security groups/VPN or trusted IPs.
- All production access must be logged.
- Production database access should use named technical users, not shared personal passwords where practical.
- Direct production data inspection requires a reason recorded in a lightweight access log or ticket.

Rationale:

This is a practical internal-control baseline without requiring a formal enterprise access platform at launch.

### Superadmin Environment Variable Names and Rotation Procedure

Decision:

- Use these launch environment variables:
  - `GARANTA_SUPERADMIN_EMAIL`.
  - `GARANTA_SUPERADMIN_PASSWORD_HASH`.
  - `GARANTA_SUPERADMIN_FULL_NAME`.
  - `GARANTA_SUPERADMIN_ENABLED`.
- The password hash is generated by a management command and stored as an environment secret, not committed.
- Rotation:
  - generate a new password hash.
  - update the production env file/secret source.
  - redeploy/restart the app.
  - verify superadmin login.
- Removal:
  - set `GARANTA_SUPERADMIN_ENABLED=false` or remove the env values and redeploy.

Rationale:

This matches the documented rule that superadmins are managed at deploy/environment level, not through the database UI.

### Environment Secret Management

Decision:

- Use environment variables and restricted host env files at launch.
- Keep `.env.production` and `.env.staging` off-repository.
- Store env files with strict filesystem permissions.
- Do not print env values in logs or CI output.
- AWS Secrets Manager or SSM Parameter Store can be introduced later when operational complexity justifies it.

Rationale:

Env-based secrets keep launch deployment simple and low-cost while remaining compatible with later migration to managed secret storage.

### CI/CD Workflow Details

Decision:

- Use GitHub Actions.
- Use AWS ECR as the production/staging container registry.
- Use GitHub Actions OIDC to authenticate to AWS where possible; avoid long-lived AWS access keys in GitHub.
- Workflows:
  - `ci.yml`: tests, lint, typecheck, schema/client freshness, security checks.
  - `deploy-staging.yml`: deploys `main` to staging after CI passes.
  - `deploy-production.yml`: deploys version tags such as `v*` after CI passes, without a separate manual approval gate.
- Rollback:
  - redeploy the previous known-good image tag.
  - database rollback is not assumed automatic; use forward correction migrations unless a destructive migration rollback has been explicitly prepared.

Rationale:

This gives continuous staging, deliberate production releases through tags, and no extra approval bureaucracy.

### Authentication and Rate-Limit Defaults

Decision:

- Investor magic link:
  - single-use.
  - 15-minute expiry.
  - resend cooldown: 60 seconds.
  - rate limit: 5 requests per email per hour and 20 per day, plus IP-based throttles.
- Investor sessions:
  - long-lived as previously documented.
  - revocable by admin/security action.
  - sensitive/financial actions still require fresh email-code confirmation.
- Sensitive-action email code:
  - 10-minute expiry.
  - 3 attempts.
  - resend cooldown: 60 seconds.
  - rate-limited by user and IP.
- Admin authentication:
  - email/password plus email code.
  - password minimum 14 characters.
  - Argon2 or Django's strongest configured hasher.
  - email code expiry: 10 minutes.
  - 3 code attempts.
  - temporary lockout after repeated failed login/code attempts.
- Breach-password checking is not required at launch.

Rationale:

These defaults are consistent with the existing user/account plan and are strict enough for v1 without adding MFA hardware/app complexity.

### Template Variable Registry Validation

Decision:

- Template variables are defined by strict schema per template type.
- Superadmin template editing includes:
  - variable picker.
  - examples.
  - preview rendering with fixture data.
  - save-time validation.
  - publish-time validation.
- Invalid templates cannot be published.

Rationale:

This protects regulated transactional documents and emails from broken variable references.

### Required Security Standards

Decision:

- No SOC 2, ISO 27001, or other formal security certification is required for v1.
- Build with good internal controls:
  - audit logging.
  - least-privilege access.
  - encrypted storage.
  - secure defaults.
  - backup/restore testing.
  - structured logs.
  - critical alerts.

Rationale:

This matches Garanta's current stated need and avoids premature compliance overhead.

### Log Cleanup, Archive, and Retention Tiering

Decision:

- Financial ledger, audit events, KYC/KYB/AML evidence, generated documents, and accounting/tax/report source data are retained according to the product/compliance plan and are not subject to launch log cleanup.
- Application/runtime logs:
  - local Docker logs rotated by size and short retention.
  - CloudWatch/equivalent production log retention default: 90 days.
- Revisit log retention after real production volume is known.

Rationale:

This avoids uncontrolled log growth without weakening financial/audit retention.

### Sophisticated Observability/APM

Decision:

- Do not use Datadog, New Relic, Grafana Cloud, Sentry, or similar as a required launch dependency.
- Keep application hooks compatible with adding Sentry/APM later.
- Launch uses structured logs, health checks, job status, ledger integrity checks, and email alerts.

Rationale:

External APM is useful later, but not necessary for a low-traffic cost-optimized launch.

### Formal Incident-Response Program

Decision:

- No formal incident-response program is required for v1.
- Maintain a lightweight technical runbook for:
  - production outage.
  - failed deployment.
  - backup failure.
  - ledger integrity alert.
  - suspected security issue.
  - provider outage.

Rationale:

The team needs practical operating instructions, not a full governance program at launch.

### Public API and Partner API

Decision:

- No public or partner API is required at launch.
- Keep internal service boundaries and OpenAPI-generated frontend contracts clean enough to add partner APIs later if needed.

### Bank-Feed Automation Adapter

Decision:

- No bank-feed automation is required at launch.
- Manual bank-operation declaration remains the launch flow.
- Implement reconciliation through service boundaries that can later accept file/API bank feeds.

### Admin-Visible Release Changelog

Decision:

- No admin-visible release changelog is required in v1.
- Git tags, deployment logs, and commit history are sufficient.

## Non-Blocking

### Future Managed-Service Migration

Needed when traffic, operational risk, or compliance expectations justify higher infrastructure cost.

Future migration candidates:

- Self-hosted PostgreSQL to RDS PostgreSQL.
- Local Redis to ElastiCache.
- Single EC2 Docker host to ECS/Fargate plus ALB.
- Shared staging/prod host to separate staging and production hosts.
- Env-file secrets to AWS Secrets Manager or SSM Parameter Store.
- Structured logs/email alerts to external APM/security monitoring.

Why this is non-blocking:

The launch implementation is designed with container boundaries, provider adapters, OpenAPI contracts, database migrations, and environment isolation so these migrations can be done incrementally.
