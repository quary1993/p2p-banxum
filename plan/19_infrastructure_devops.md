# Infrastructure, DevOps, and Platform Operations

Status: Draft. Updated with security/data-residency, Swiss KYC/KYB/AML evidence storage, alerting, integration-architecture, cost-optimized AWS Zurich single-host launch deployment, backup, CI/CD, and operations decisions on 2026-06-01.

## Purpose

Define the deployment, runtime, observability, reliability, backup, environment, and operational practices needed to run BANXUM.

## Scope

- Cloud and hosting choices.
- Environments.
- CI/CD.
- Secrets management.
- Database operations.
- Object storage.
- Observability.
- Backup and disaster recovery.
- Incident management.
- Vendor operations.
- Release management.

## Decisions

### INFRA-DEC-001: AWS-Oriented Cost-Optimized Hosting

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta technology.

Decision:
AWS is the selected launch cloud provider baseline.

Launch infrastructure should be cost-optimized. Staging and production exist as separate logical environments but run on the same EC2 server/instance at launch.

If staging and production share the same server, they must still use separate environment variables, databases/schemas or clearly separated data stores, storage prefixes/buckets where applicable, domains/subdomains, logs, background workers, and deployment targets. Production data may be copied to staging only after anonymization.

Rationale:
The first version should avoid unnecessary infrastructure spend while preserving enough separation to test safely and operate production.

Risk note:
Shared staging/production hosting increases blast radius and weakens high-availability assumptions. This is acceptable for cost optimization at launch, but the architecture should allow later separation.

### INFRA-DEC-002: Launch Environments

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta technology.

Decision:
Hosted launch environments are staging and production.

Local developer environments are still expected for engineering work, but shared development, test/QA, and UAT hosted environments are not required unless Garanta later asks for them.

Rationale:
Staging plus production is enough for v1 and keeps costs controlled.

### INFRA-DEC-003: Production Operations Owner

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta management / technology.

Decision:
Garanta's internal tech team operates production.

Rationale:
Production operation, alert handling, deployment execution, and infrastructure access sit with the internal technical owner at launch.

### INFRA-DEC-004: Availability Target

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta technology / management.

Decision:
The launch availability target is 99.9%+ best effort.

This is not a formal customer SLA for v1. If staging and production share a single low-cost server, AWS platform reliability alone does not provide application-level high availability against instance, application, database, or deployment failures.

Rationale:
The business wants reasonable uptime without paying for a sophisticated HA setup before there is a clear need.

### INFRA-DEC-005: Backups and Recovery

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta technology.

Decision:
Backups run once per day at launch and are retained for two months.

Backups are stored in a private S3 backup bucket in AWS Zurich, encrypted server-side, preferably with KMS-backed keys if available. Daily backup time is 02:30 Europe/Zurich local time. Operational retention is 62 days through lifecycle expiration.

Launch recovery targets are cost-optimized:

- RPO: up to 24 hours, based on daily backups.
- RTO: best effort/manual restore, target within 24 hours where practical.

Backup failure alerts go to the tech alert mailbox. Restore is manual at launch and must be tested at least quarterly and before first production money movement. No heavy disaster-recovery program is required at launch.

Rationale:
Daily backups with two-month retention are a practical launch baseline. Stricter RPO/RTO would require additional infrastructure cost.

### INFRA-DEC-006: CI/CD and Deployment Approval

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta technology.

Decision:
GitHub Actions is the launch CI/CD stack.

Production deployments do not require manual approval at launch. Deployments may proceed automatically after the configured checks pass.

Launch workflow baseline:

- `ci.yml`: tests, lint, typecheck, OpenAPI/generated-client freshness checks, and security checks.
- `deploy-staging.yml`: deploys `main` to staging after CI passes.
- `deploy-production.yml`: deploys version tags such as `v*` after CI passes.
- Container registry: AWS ECR.
- GitHub Actions should use OIDC to authenticate to AWS where possible instead of long-lived AWS keys.

No formal release changelog or admin-visible version history is required in v1.

Rationale:
The launch team prefers faster, simpler deployment flow without manual gates or release-management overhead.

### INFRA-DEC-007: Lightweight Telemetry and Rich Logs

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta technology.

Decision:
Sophisticated observability tooling is not required at launch.

The platform should implement good telemetry and rich structured logs covering application errors, audit events, financial/event processing, background jobs, webhook handling, email sending, FX quote checks, payment reconciliation, and security-relevant events.

Tech-team email alerts remain required for critical technical/security conditions.

Launch logs use JSON structured logging. Immutable financial/audit events are stored in the database. Production runtime logs should be shipped to CloudWatch Logs or equivalent AWS-native log storage with 90-day launch retention if cost remains acceptable, while local Docker logs are rotated aggressively.

Rationale:
Structured logs and practical telemetry are enough for v1, while preserving the option to add a dedicated observability platform later.

### INFRA-DEC-008: Environment-Variable Secrets

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta technology.

Decision:
Secrets are stored as environment variables at launch.

Access to production environment variables must be limited to authorized tech-team users. Superadmin bootstrap credentials, provider API keys, webhook secrets, database credentials, and email/SMS/FX credentials are all treated as production secrets.

Launch secret files must stay off-repository, use strict filesystem permissions, and never be printed in CI/deployment logs. AWS Secrets Manager or SSM Parameter Store is a future upgrade if env-file operations become insufficient.

Rationale:
Environment variables keep launch operations simple. A cloud secret manager or vault can be added later if complexity or security requirements increase.

### INFRA-DEC-009: AWS Region and Swiss KYC Evidence Storage

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta technology.

Decision:
Launch region is AWS `eu-central-2` Europe (Zurich) for the full application stack: compute, database storage, object storage, backups, documents, generated PDFs, KYC/KYB/AML retained evidence, provider reports where retained, raw provider webhook payloads where retained, supporting documents, identity/KYB evidence, decisions, review notes, and evidence packages.

Frankfurt or another EU region remains a future option for general compute only if Garanta later accepts split-region complexity and the Swiss evidence boundary remains intact.

Rationale:
Using Zurich for the full launch stack is operationally simpler than splitting compute and evidence storage across regions, and it avoids accidental leakage of KYC/KYB/AML evidence outside the Swiss-controlled boundary.

### INFRA-DEC-010: Production-to-Staging Data Anonymization

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta technology / compliance.

Decision:
Production data may be copied to staging only after anonymization/pseudonymization.

The launch anonymization approach preserves system structure while replacing direct identifiers:

- Replace names, emails, phone numbers, IBANs, bank-account labels, addresses, and similar direct identifiers with deterministic fake values.
- Preserve internal IDs, relational links, balances, loan amounts, ledger structure, dates/timestamps, statuses, and event chronology where needed for realistic testing.
- Remove or replace external provider tokens, secrets, message IDs where sensitive, webhook secrets, and any provider credentials.
- Prevent staging from sending real emails/SMS or making real money-moving/provider calls.
- Keep any re-identification mapping out of staging.

Rationale:
Staging needs realistic operational and ledger structure for testing, but must not expose production personal/contact/bank details or trigger real external actions.

### INFRA-DEC-011: Launch Runtime Components

Status: Accepted.
Date: 2026-06-01.
Owner: Garanta technology.

Decision:
Launch uses a single EC2 host in AWS Zurich with Docker Compose.

Runtime baseline:

- Reverse proxy: Caddy, Traefik, or nginx with TLS automation.
- Application: Dockerized Django modular monolith.
- Frontend: built static assets served by the app/reverse proxy or a containerized frontend server, depending on implementation.
- Workers/scheduler: separate containers per environment.
- PostgreSQL: self-hosted in Docker on the launch host, with separate prod/staging databases and users.
- Redis: local/containerized at launch, with separate instances or namespaces per environment.
- Object storage: private AWS Zurich S3 buckets/prefixes.
- Malware scanning: local/containerized ClamAV-compatible scanner with quarantine workflow.
- PDF generation: WeasyPrint for launch server-side PDFs; Playwright/Chromium remains a frontend test tool and fallback PDF option only.

Initial EC2 sizing should target a burstable general-purpose 2 vCPU / 8 GB RAM instance class, such as `t3.large`/`t3a.large` or a Graviton equivalent if all containers are confirmed multi-architecture compatible.

Rationale:
This supports the expected 50-100 concurrent launch users at low cost while keeping the main future scaling options straightforward: resize EC2, move PostgreSQL to RDS, move Redis to ElastiCache, split staging/prod, then move app/worker containers to ECS/Fargate if needed.

### INFRA-DEC-012: Launch Security and Developer Workflow Defaults

Status: Accepted.
Date: 2026-06-01.
Owner: Garanta technology.

Decision:

- Production server access is limited to authorized tech-team users. Prefer AWS Systems Manager Session Manager over public SSH where feasible.
- Superadmin bootstrap env names are `GARANTA_SUPERADMIN_EMAIL`, `GARANTA_SUPERADMIN_PASSWORD_HASH`, `GARANTA_SUPERADMIN_FULL_NAME`, and `GARANTA_SUPERADMIN_ENABLED`.
- OpenAPI schema and Orval-generated frontend clients are committed to the repository; CI fails if they are stale.
- Provider/webhook failures retry up to 8 attempts using 1 minute, 5 minutes, 15 minutes, 1 hour, 3 hours, 12 hours, 24 hours, and 48 hours, then dead-letter and alert tech.
- Investor magic links are single-use, expire after 15 minutes, and are rate-limited. Sensitive-action email codes expire after 10 minutes, allow 3 attempts, and are rate-limited. Admin password plus email-code login uses the same 10-minute/3-attempt code baseline.
- No formal SOC 2, ISO 27001, external APM, public API, bank-feed automation, or admin-visible changelog is required at launch.

Rationale:
These defaults make the repository and runtime practical for agents and the internal tech team while keeping launch scope and cost controlled.

## Environments

- Local development for engineers.
- Staging.
- Production.
- Sandbox integrations where required by providers.

Production data may be copied to staging only after anonymization/pseudonymization and approval. The launch policy preserves operational structure while replacing direct identifiers with deterministic fake values and disabling real external sends/provider calls.

The launch stack uses AWS Zurich for production and staging. EU hosting remains acceptable for future general infrastructure only if Garanta later accepts split-region complexity and the Swiss KYC/KYB/AML evidence boundary remains intact.

## Application Architecture

The v1 platform is a modular monolith. Domain modules should be clearly separated inside one deployable application, with internal service/module boundaries that can later support service extraction if needed.

A dedicated external event bus is not required at launch. Asynchronous work should use an append-only event table and background jobs/workers.

## Reliability Requirements

- Defined uptime target.
- Health checks.
- Alerting for critical paths.
- Error budgets are not required at launch.
- Graceful degradation for vendor outages.
- Scheduled maintenance process.
- Backup and restore testing.
- Daily backup execution and two-month retention.
- Cost-optimized manual restore process.
- Formal disaster recovery plan is future scope unless Garanta requires it.

## Observability

- Application logs.
- Audit logs.
- Metrics.
- Distributed traces if services are used.
- Job queue monitoring.
- Background worker monitoring.
- Append-only event table processing monitoring.
- Payment reconciliation monitoring.
- Webhook processing monitoring.
- Security alerts.
- Tech-team email alerts for critical failures, security-relevant events, integration failures, ledger/export job failures, failed email retry exhaustion, failed webhook processing, and other operational conditions requiring technical attention.
- Sophisticated observability tooling is not required for v1.

## Release Controls

- Pull request review.
- Automated tests.
- Database migration checks.
- Security scanning.
- Formal release changelog is not required for v1.
- Rollback plan.
- No manual production deployment approval is required at launch after configured checks pass.
- Feature flags for risky launches.

## Data Stores

Likely storage categories:

- Relational database for transactional state.
- Append-only event/audit store.
- Background job queue/store.
- Object storage for documents.
- Switzerland-located restricted storage for KYC/KYB/AML evidence, provider reports, raw provider webhook payloads where retained, and evidence packages.
- Search index for admin search, if needed; otherwise database search is acceptable at launch.
- Data warehouse/analytics store is future scope, not required for v1.
- Environment variables/restricted host env files for launch secrets.

## Dependencies

- Security, Privacy, and Auditability.
- Integrations, APIs, and Event Architecture.
- Reporting, Analytics, and Regulatory Exports.

## Q/A Backlog

1. Answered by INFRA-DEC-001: AWS is the selected launch cloud provider baseline, with cost-optimized hosting.
2. Updated by SEC-DEC-001 and INFRA-DEC-009: EU hosting/data residency is acceptable for general launch infrastructure, but KYC/KYB/AML evidence must be stored in Switzerland on Garanta-controlled infrastructure.
3. Answered by INFRA-DEC-004: target 99.9%+ best effort, not a formal launch SLA.
4. Answered by INFRA-DEC-005: daily backups, two-month retention, RPO up to 24 hours, RTO best effort/manual restore targeting 24 hours where practical.
5. Answered by INFRA-DEC-003: Garanta internal tech team operates production.
6. Answered by INFRA-DEC-006: GitHub Actions CI/CD, no manual deployment approval, no formal release changelog/admin-visible version history in v1.
7. Answered by INFRA-DEC-007: skip sophisticated observability; implement good telemetry, rich structured logs, and tech-team email alerts.
8. Answered by INFRA-DEC-008: launch secrets are stored in environment variables.
9. Answered by INT-DEC-001/INT-DEC-002: v1 is a modular monolith using an append-only event table and background jobs instead of a dedicated event bus.
10. Answered by INFRA-DEC-002: hosted launch environments are staging and production; they may share a server if cost optimization requires it.
11. Updated by INFRA-DEC-009 and INFRA-DEC-011: launch uses AWS `eu-central-2` Zurich for the full stack, including compute, storage, backups, and KYC/KYB/AML evidence, to avoid split-region compliance complexity.
12. Answered by INFRA-DEC-010: production data copied to staging must be anonymized/pseudonymized by replacing direct identifiers with deterministic fake values while preserving operational/ledger structure and disabling real external sends/provider calls.
13. Answered by INFRA-DEC-011: launch uses one EC2 Docker Compose host for staging and production, with logical isolation and a documented scale path to RDS, ElastiCache, separate hosts, and ECS/Fargate.
14. Answered by INFRA-DEC-012: launch technical defaults are defined for production access, superadmin env variables, OpenAPI/client generation, webhook retry, auth/rate limits, and omitted future-scope platform services.
