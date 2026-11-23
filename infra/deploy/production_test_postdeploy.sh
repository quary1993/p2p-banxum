#!/usr/bin/env bash
# IP of Webby-Soft SRL. One-time post-deploy maintenance for the private production test site.

set -euo pipefail

app_dir=/opt/banxum/production/app
project=banxum_prod
env_file=infra/deploy/.env
compose_file=infra/deploy/docker-compose.yml
backup_dir=/opt/banxum/production/backups

cd "$app_dir"

deploy_backup=$(find "$backup_dir" -maxdepth 1 -type f \
  -name 'banxum_prod-postgres-*.dump' -print | sort | tail -1)
test -n "$deploy_backup"
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
    | head -1 \
    || true
)
echo "production_cron_old=${old_line:-missing}"
updated_cron=$current_cron
if [ -n "$old_line" ]; then
  if ! printf '%s\n' "$old_line" | grep -q -- '--job assisted_recovery_links'; then
    updated_cron=$(printf '%s\n' "$updated_cron" | sed \
      '/\/opt\/banxum\/production\/app/ { /--job email_outbox_dispatch/ s/--job email_outbox_dispatch/--job email_outbox_dispatch --job assisted_recovery_links/; }')
  fi
else
  updated_cron="${updated_cron}${updated_cron:+$'\n'}*/5 * * * * cd /opt/banxum/production/app && docker compose --project-name banxum_prod --env-file infra/deploy/.env -f infra/deploy/docker-compose.yml exec -T backend .venv/bin/python backend/manage.py run_scheduled_jobs --job email_outbox_dispatch --job assisted_recovery_links >> /var/log/banxum-production-jobs.log 2>&1"
fi

funding_line='*/5 * * * * cd /opt/banxum/production/app && docker compose --project-name banxum_prod --env-file infra/deploy/.env -f infra/deploy/docker-compose.yml exec -T backend .venv/bin/python backend/manage.py run_scheduled_jobs --job primary_funding_expiry_scan --job originator_opportunity_lifecycle_scan >> /var/log/banxum-production-jobs.log 2>&1'
daily_line='10 0 * * * cd /opt/banxum/production/app && docker compose --project-name banxum_prod --env-file infra/deploy/.env -f infra/deploy/docker-compose.yml exec -T backend .venv/bin/python backend/manage.py run_scheduled_jobs >> /var/log/banxum-production-jobs.log 2>&1'
monitor_line='*/15 * * * * cd /opt/banxum/production/app && docker compose --project-name banxum_prod --env-file infra/deploy/.env -f infra/deploy/docker-compose.yml exec -T backend .venv/bin/python backend/manage.py check_scheduled_jobs >> /var/log/banxum-production-job-monitor.log 2>&1'
for required_line in "$funding_line" "$daily_line" "$monitor_line"; do
  marker=$(printf '%s\n' "$required_line" | sed 's/^.*manage.py /manage.py /; s/ >>.*$//')
  if ! printf '%s\n' "$updated_cron" | grep -Fq -- "$marker"; then
    updated_cron="${updated_cron}${updated_cron:+$'\n'}${required_line}"
  fi
done
printf '%s\n' "$updated_cron" | crontab -
new_line=$(
  crontab -l \
    | grep '/opt/banxum/production/app' \
    | grep -- '--job email_outbox_dispatch' \
    | head -1
)
echo "production_cron_new=$new_line"
printf '%s\n' "$new_line" | grep -q -- '--job assisted_recovery_links'

echo "production_reset_status=already_completed_not_repeated"

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
