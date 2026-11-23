#!/usr/bin/env bash
# IP of Webby-Soft SRL. One-time post-deploy maintenance for the private production test site.

set -euo pipefail

app_dir=/opt/banxum/production/app
project=banxum_prod
env_file=infra/deploy/.env
compose_file=infra/deploy/docker-compose.yml
deploy_backup=/opt/banxum/production/backups/banxum_prod-postgres-20261123T112357Z.dump

cd "$app_dir"

test -s "$deploy_backup"
test -s "${deploy_backup}.sha256"
echo "deploy_backup_status=present_and_checksummed"
echo "deploy_backup_path=$deploy_backup"
echo "deploy_offsite_copy_status=not_configured"

current_cron=$(crontab -l 2>/dev/null || true)
old_line=$(
  printf '%s\n' "$current_cron" \
    | grep '/opt/banxum/production/app' \
    | grep -- '--job email_outbox_dispatch' \
    | head -1
)
if [ -z "$old_line" ]; then
  echo "production_email_cron_status=missing" >&2
  exit 2
fi
echo "production_cron_old=$old_line"
if printf '%s\n' "$old_line" | grep -q -- '--job assisted_recovery_links'; then
  updated_cron=$current_cron
else
  updated_cron=$(printf '%s\n' "$current_cron" | sed \
    '/\/opt\/banxum\/production\/app/ { /--job email_outbox_dispatch/ s/--job email_outbox_dispatch/--job email_outbox_dispatch --job assisted_recovery_links/; }')
  printf '%s\n' "$updated_cron" | crontab -
fi
new_line=$(
  crontab -l \
    | grep '/opt/banxum/production/app' \
    | grep -- '--job email_outbox_dispatch' \
    | head -1
)
echo "production_cron_new=$new_line"
printf '%s\n' "$new_line" | grep -q -- '--job assisted_recovery_links'

preview=$(python3 infra/deploy/reset_qa_environment.py \
  --environment production --allow-production)
echo "production_reset_preview=$preview"
confirmation=$(printf '%s' "$preview" | python3 -c \
  'import json,sys; print(json.load(sys.stdin)["confirmation"])')
actor_email=$(python3 - "$app_dir/infra/deploy/.env" <<'PYTHON'
from pathlib import Path
import sys

for raw_line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    name, value = line.split("=", 1)
    if name.strip() != "GARANTA_SUPERADMIN_EMAIL":
        continue
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    if not value:
        raise SystemExit("GARANTA_SUPERADMIN_EMAIL is empty")
    print(value)
    break
else:
    raise SystemExit("GARANTA_SUPERADMIN_EMAIL is missing")
PYTHON
)
reset_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
python3 infra/deploy/reset_qa_environment.py \
  --environment production --allow-production --execute \
  --actor-email "$actor_email" --run-id "$reset_id" --confirm "$confirmation"
echo "production_reset_status=passed"

compose=(
  docker compose --project-name "$project" --env-file "$env_file"
  -f "$compose_file"
)
"${compose[@]}" exec -T backend .venv/bin/python backend/manage.py \
  run_scheduled_jobs --job balance_ageing_scan --dry-run
echo "production_balance_ageing_dry_run_status=passed"
"${compose[@]}" exec -T backend .venv/bin/python backend/manage.py \
  run_scheduled_jobs --force
echo "production_all_scheduled_jobs_status=passed"
"${compose[@]}" exec -T backend .venv/bin/python backend/manage.py check_scheduled_jobs
echo "production_scheduled_job_monitor_status=passed"

curl -fsS https://nxnarena.com/api/v1/health/ >/dev/null
echo "external_production_health=passed"
