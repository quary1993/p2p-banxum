#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_NAME="${BANXUM_COMPOSE_PROJECT:?Set BANXUM_COMPOSE_PROJECT to banxum_staging or banxum_prod}"
BACKUP_DIR="${BANXUM_BACKUP_DIR:?Set BANXUM_BACKUP_DIR to a BANXUM-only directory}"
MAX_AGE_HOURS="${BANXUM_BACKUP_MAX_AGE_HOURS:-30}"

latest_path="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name "${PROJECT_NAME}-postgres-*.dump" -print0 2>/dev/null \
  | xargs -0 -r ls -1t \
  | head -n 1)"

if [[ -z "$latest_path" ]]; then
  echo "No PostgreSQL backup found for $PROJECT_NAME in $BACKUP_DIR" >&2
  exit 1
fi
if [[ ! -f "${latest_path}.sha256" ]]; then
  echo "Backup checksum is missing for $latest_path" >&2
  exit 1
fi

sha256sum --check "${latest_path}.sha256" >/dev/null
modified_epoch="$(stat -c %Y "$latest_path")"
now_epoch="$(date +%s)"
age_seconds="$((now_epoch - modified_epoch))"
max_age_seconds="$((MAX_AGE_HOURS * 3600))"

if (( age_seconds > max_age_seconds )); then
  echo "Latest PostgreSQL backup for $PROJECT_NAME is older than ${MAX_AGE_HOURS}h: $latest_path" >&2
  exit 1
fi

echo "Latest PostgreSQL backup is fresh and checksum-valid: $latest_path"
