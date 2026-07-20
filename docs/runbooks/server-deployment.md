# BANXUM Server Deployment

This runbook covers the first shared-server deployment for BANXUM staging and production.

The server also runs unrelated trading bots. BANXUM deployment must remain isolated:

- Use only BANXUM-specific directories under `/opt/banxum`.
- Use Docker Compose project names `banxum_staging` and `banxum_prod`.
- Do not run global Docker cleanup commands such as `docker system prune`.
- Do not stop containers or processes that are not labeled with the BANXUM Compose project.
- Do not bind common bot or development ports unless they are confirmed unused.

## Current Topology

The first shared-server deployment keeps each BANXUM environment behind a local frontend nginx
container:

- Staging internal HTTP: `http://127.0.0.1:8081`
- Production internal HTTP: `http://127.0.0.1:8082`

These HTTP ports are for server-local smoke checks and SSH-tunneled testing only. They must not be
opened to the public internet for any environment that contains real credentials, real sessions,
personal data, KYC data, or financial data.

Public browser access must go through a host-level TLS reverse proxy on `80/443`, using real domains
and certificates. `infra/deploy/Caddyfile.example` shows the intended launch pattern:

- production domain -> `127.0.0.1:8082`
- staging domain -> `127.0.0.1:8081`

On the first deployment, both environments were healthy from inside the server, but public access to
`80`, `443`, `8081`, and `8082` was blocked externally. Keep `8081` and `8082` blocked externally.
Open only `80` and `443` once DNS and TLS are ready.

Each environment has its own:

- Postgres container and volume.
- Redis container and volume.
- Backend container.
- Frontend nginx container.
- Media volume.

The frontend nginx container serves the built React app and proxies:

- `/api/` to the backend.
- `/admin/django/` to the backend only at the proxy layer; Django returns 404 unless `DJANGO_ADMIN_ENABLED=true` (local-only by default).
- `/static/` to the backend/WhiteNoise.

Django's framework admin and interactive OpenAPI/schema routes are local-only by default. Keep
`DJANGO_ADMIN_ENABLED=false` and `API_DOCS_ENABLED=false` in staging and production; the supported
operator interface is the BANXUM `/admin` SPA.

## Mandatory HTTPS And Cookie Security

Plain HTTP is not acceptable for production or for any staging environment that contains real user
data, provider credentials, KYC evidence, financial data, or real admin credentials. Cookie-based auth,
CSRF protection, KYC workflows, admin login, and financial data all depend on encrypted transport.

Before using any non-local environment with real credentials or data:

- Point DNS to the server.
- Open inbound `80` and `443` in the AWS security group.
- Keep inbound `8081` and `8082` closed publicly.
- Put the app behind HTTPS with a real certificate.
- Enable `SESSION_COOKIE_SECURE=true`.
- Enable `CSRF_COOKIE_SECURE=true`.
- Enable `SECURE_SSL_REDIRECT=true`.
- Set `DJANGO_USE_X_FORWARDED_PROTO=true`.
- Restrict allowed hosts to the final domains.
- Set `PUBLIC_APP_BASE_URL` to the HTTPS app URL for each environment.

If raw-IP HTTP was used to test a superadmin/admin login, rotate those credentials before treating the
environment as production. Do not keep production superadmin passwords in local notes or repository
files; store them in a password manager or secrets manager and use environment-managed password hashes.

## Deployment Files

- `infra/deploy/docker-compose.yml`: isolated staging/prod Compose stack.
- `backend/Dockerfile.deploy`: production backend image with Gunicorn.
- `frontend/Dockerfile.deploy`: production React build served by nginx.
- `infra/deploy/nginx.conf`: frontend/static/API reverse proxy routing.
- `infra/deploy/Caddyfile.example`: example host-level TLS reverse proxy routing.
- `infra/deploy/backup_postgres.sh`: locked, validated PostgreSQL backup with optional encrypted S3 upload.
- `infra/deploy/check_backup_freshness.sh`: checksum and age monitor for the latest environment backup.

## Server Directories

The first deployment uses:

- `/opt/banxum/staging/app`
- `/opt/banxum/production/app`

Each directory contains a copy of the app source and `infra/deploy/.env` for that environment.

## Standard Commands

The preferred deployment path is the manual GitHub Actions workflow:

```text
Actions -> Deploy -> Run workflow -> environment: staging | production | both
```

The workflow uploads the checked-out commit as a release archive, preserves the target
environment's existing `infra/deploy/.env`, rebuilds only the BANXUM Compose project, and runs the
server-local health check. It must use only the configured BANXUM SSH secrets and the directories /
Compose project names listed below.

Container startup applies migrations, collects static files, runs `seed_reference_data`, and
synchronizes the environment-managed superadmin. `seed_reference_data` creates only currencies and
platform settings. Never put `seed_demo` in a deployed startup command: it is an explicit local/private
QA command and may create temporary, non-approved legal templates.

Use the direct server commands below only for emergency or diagnostic work.

From the relevant environment app directory on the server:

```bash
docker compose \
  --project-name banxum_staging \
  --env-file infra/deploy/.env \
  -f infra/deploy/docker-compose.yml \
  up -d --build
```

For production, use `--project-name banxum_prod`.

Health check:

```bash
curl -fsS http://127.0.0.1:8081/api/v1/health/
curl -fsS http://127.0.0.1:8082/api/v1/health/
```

Public check after DNS/TLS:

```bash
curl -fsS https://staging.example.com/api/v1/health/
curl -fsS https://banxum.example.com/api/v1/health/
```

Logs:

```bash
docker compose --project-name banxum_staging -f infra/deploy/docker-compose.yml logs -f backend
docker compose --project-name banxum_prod -f infra/deploy/docker-compose.yml logs -f backend
```

## Postgres Readiness And Hardening Checks

Staging and production each run their own PostgreSQL container and volume through the isolated
Compose project. Confirm the target environment has a healthy Postgres before running migrations or
smoke checks:

```bash
docker compose \
  --project-name banxum_staging \
  --env-file infra/deploy/.env \
  -f infra/deploy/docker-compose.yml \
  ps postgres
```

The full test suite must be run against PostgreSQL before first production money movement and after
any migration or financial-service change. Use CI, a local disposable Postgres container, or a staging
test database. Do not run `pytest` against the production database or any database containing real
client data.

Local/disposable Postgres commands:

```bash
docker compose up -d postgres redis
make migration-check-postgres
make test-backend-postgres
make test-postgres-hardening
```

If the disposable database uses non-default credentials, override:

```bash
POSTGRES_TEST_DATABASE_URL=postgres://user:password@host:5432/dbname make test-backend-postgres
POSTGRES_TEST_DATABASE_URL=postgres://user:password@host:5432/dbname make test-postgres-hardening
```

The focused hardening pack verifies production-engine behavior that SQLite cannot prove:

- DB-level append-only triggers reject raw SQL mutation.
- Financial idempotency/concurrency collapses duplicate lender-deposit declarations into one bank
  operation, journal entry, and balance lot.

CI also runs with PostgreSQL 16 and Redis. `MIGRATION_CHECK_DATABASE_URL` is set to Postgres in CI so
the migration drift gate uses the production database engine.

## PostgreSQL Backups

Backups must be environment-scoped, encrypted off-host, and monitored. The backup helper acquires a
per-environment lock, creates a compressed custom-format `pg_dump`, validates it with `pg_restore
--list`, writes a SHA-256 checksum, uploads both files with S3 server-side encryption, and retains a
short local recovery window. It never touches another Compose project.

Example production environment file consumed by the cron wrapper (store outside Git):

```env
BANXUM_APP_DIR=/opt/banxum/production/app
BANXUM_ENV_FILE=/opt/banxum/production/app/infra/deploy/.env
BANXUM_COMPOSE_PROJECT=banxum_prod
BANXUM_BACKUP_DIR=/opt/banxum/production/backups
BANXUM_BACKUP_S3_URI=s3://REPLACE-WITH-PRIVATE-ZURICH-BUCKET/production/postgres
BANXUM_BACKUP_KMS_KEY_ID=REPLACE-WITH-KMS-KEY-ID
BANXUM_BACKUP_REQUIRE_OFFSITE=true
BANXUM_BACKUP_LOCAL_RETENTION_DAYS=7
BANXUM_BACKUP_MAX_AGE_HOURS=30
```

Run once manually and verify the destination before installing cron:

```bash
set -a; source /etc/banxum/production-backup.env; set +a
/opt/banxum/production/app/infra/deploy/backup_postgres.sh
/opt/banxum/production/app/infra/deploy/check_backup_freshness.sh
```

Recommended schedule (02:30 Europe/Zurich plus freshness monitoring):

```cron
30 2 * * * set -a; . /etc/banxum/production-backup.env; set +a; /opt/banxum/production/app/infra/deploy/backup_postgres.sh >> /var/log/banxum-production-backup.log 2>&1
15 8 * * * set -a; . /etc/banxum/production-backup.env; set +a; /opt/banxum/production/app/infra/deploy/check_backup_freshness.sh >> /var/log/banxum-production-backup-monitor.log 2>&1
```

Use distinct staging paths, prefixes, and credentials. Configure S3 lifecycle expiration at 62 days.
A successful dump is not a completed backup program: before real money, restore a selected archive
into a disposable PostgreSQL database, run integrity counts/checks, document the result, and alert on
any backup or freshness-check non-zero exit.

## Scheduled Jobs And Monitoring

Default scheduled jobs are run by the backend management command:

```bash
docker compose \
  --project-name banxum_staging \
  --env-file infra/deploy/.env \
  -f infra/deploy/docker-compose.yml \
  exec -T backend .venv/bin/python backend/manage.py run_scheduled_jobs
```

Use `--job <name>` to run a subset, and `--force` only for an explicit operator-triggered one-off.
In staging and production, `SCHEDULED_JOBS_ACTOR_EMAIL` must point to a dedicated active scheduler
service admin account, not a human admin account.

Monitoring should call the read-only check command and alert on any non-zero exit:

```bash
docker compose \
  --project-name banxum_staging \
  --env-file infra/deploy/.env \
  -f infra/deploy/docker-compose.yml \
  exec -T backend .venv/bin/python backend/manage.py check_scheduled_jobs
```

The monitor fails when it finds:

- a scheduled-job run still marked `failed`; or
- a `running` scheduled-job run older than `SCHEDULED_JOBS_RUNNING_TIMEOUT_MINUTES`.

Example cron shape for the current shared-server launch, using only BANXUM project names and paths:

```cron
*/5 * * * * cd /opt/banxum/staging/app && docker compose --project-name banxum_staging --env-file infra/deploy/.env -f infra/deploy/docker-compose.yml exec -T backend .venv/bin/python backend/manage.py run_scheduled_jobs --job email_outbox_dispatch >> /var/log/banxum-staging-jobs.log 2>&1
10 6 * * * cd /opt/banxum/staging/app && docker compose --project-name banxum_staging --env-file infra/deploy/.env -f infra/deploy/docker-compose.yml exec -T backend .venv/bin/python backend/manage.py run_scheduled_jobs >> /var/log/banxum-staging-jobs.log 2>&1
*/15 * * * * cd /opt/banxum/staging/app && docker compose --project-name banxum_staging --env-file infra/deploy/.env -f infra/deploy/docker-compose.yml exec -T backend .venv/bin/python backend/manage.py check_scheduled_jobs >> /var/log/banxum-staging-job-monitor.log 2>&1
```

Use equivalent production paths and the `banxum_prod` project name for production. Do not install
global cron tasks that run Docker cleanup, stop unrelated containers, or touch the trading-bot
project.

Stop one BANXUM environment:

```bash
docker compose --project-name banxum_staging -f infra/deploy/docker-compose.yml down
```

Do not add `-v` unless deliberately deleting that environment's database volumes.

## QA Development Mode

QA development mode is a temporary superadmin-only staging/local tool for end-to-end testing of
time-based workflows. It must never be enabled in production.

Enable it only in a non-production environment by setting:

```env
QA_DEV_MODE_ALLOWED=true
QA_DEV_MODE_SNAPSHOT_DIR=/opt/banxum/staging/qa-snapshots
QA_DEV_MODE_MAX_ADVANCE_DAYS=120
```

The admin console exposes the controls under `/admin` -> `QA mode` for superadmins only. The backend
also enforces superadmin-only access and rejects the feature when `ENVIRONMENT=production` /
`IS_PRODUCTION=true`, even if the env flag is set incorrectly.

Behavior:

- Enabling QA mode creates a Django database fixture snapshot before any QA-time changes are made.
- While QA mode is enabled, the platform's `now_utc()` helper returns the simulated QA time.
- Advancing time is day-based. For each crossed Europe/Zurich business date, the system runs the
  daily scheduled jobs: balance ageing and penalty charging, loan servicing status scan, primary
  funding-expiry scan, reconciliation-break task sync, and due email dispatch.
- Reverting restores the database snapshot captured at QA-mode entry and clears the simulated clock.
  Sessions are part of database state and should be expected to reset; the operator may need to sign
  in again.

Important limits:

- QA mode restores database state, not file/object storage. Uploaded files, generated files already
  written to disk, and external provider side effects are not rolled back by the DB snapshot.
- Do not use QA mode against real customer data, real-money provider flows, or production
  credentials.
- Do not schedule normal crons against the same environment while a manual QA time-travel run is in
  progress; the QA panel already invokes the scheduled-job service for crossed business dates.
