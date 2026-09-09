#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_NAME="${BANXUM_COMPOSE_PROJECT:?Set BANXUM_COMPOSE_PROJECT to banxum_staging or banxum_prod}"
BACKUP_DIR="${BANXUM_BACKUP_DIR:?Set BANXUM_BACKUP_DIR to a BANXUM-only directory}"
MAX_AGE_HOURS="${BANXUM_BACKUP_MAX_AGE_HOURS:-30}"
REQUIRE_OFFSITE="${BANXUM_BACKUP_REQUIRE_OFFSITE:-false}"
S3_URI="${BANXUM_BACKUP_S3_URI:-}"

if [[ "$REQUIRE_OFFSITE" == "true" && "$S3_URI" != s3://* ]]; then
  echo "A valid BANXUM_BACKUP_S3_URI is required for off-site verification" >&2
  exit 1
fi

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

if [[ "$REQUIRE_OFFSITE" == "true" || -n "$S3_URI" ]]; then
  expected_uri="${S3_URI%/}/$(basename "$latest_path")"
  if [[ ! -f "${latest_path}.offsite" ]] || [[ "$(<"${latest_path}.offsite")" != "$expected_uri" ]]; then
    echo "Off-site upload was not completed for $latest_path" >&2
    exit 1
  fi
  object_path="${expected_uri#s3://}"
  bucket="${object_path%%/*}"
  key="${object_path#*/}"
  remote_size="$(aws s3api head-object --bucket "$bucket" --key "$key" --query ContentLength --output text)"
  if [[ "$remote_size" != "$(stat -c %s "$latest_path")" ]]; then
    echo "Off-site backup size does not match $latest_path" >&2
    exit 1
  fi
  remote_checksum="$(aws s3 cp "${expected_uri}.sha256" - --only-show-errors)"
  if [[ "$remote_checksum" != "$(<"${latest_path}.sha256")" ]]; then
    echo "Off-site backup checksum evidence does not match $latest_path" >&2
    exit 1
  fi
fi

echo "Latest PostgreSQL backup is fresh and checksum-valid (off-site required=$REQUIRE_OFFSITE): $latest_path"
