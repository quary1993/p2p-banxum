#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${BANXUM_APP_DIR:-$(pwd)}"
COMPOSE_FILE="${BANXUM_COMPOSE_FILE:-$APP_DIR/infra/deploy/docker-compose.yml}"
ENV_FILE="${BANXUM_ENV_FILE:-$APP_DIR/infra/deploy/.env}"
PROJECT_NAME="${BANXUM_COMPOSE_PROJECT:?Set BANXUM_COMPOSE_PROJECT to banxum_staging or banxum_prod}"
BACKUP_DIR="${BANXUM_BACKUP_DIR:?Set BANXUM_BACKUP_DIR to a BANXUM-only directory}"
S3_URI="${BANXUM_BACKUP_S3_URI:-}"
KMS_KEY_ID="${BANXUM_BACKUP_KMS_KEY_ID:-}"
REQUIRE_OFFSITE="${BANXUM_BACKUP_REQUIRE_OFFSITE:-false}"
RETENTION_DAYS="${BANXUM_BACKUP_LOCAL_RETENTION_DAYS:-7}"

if [[ "$REQUIRE_OFFSITE" == "true" && -z "$S3_URI" ]]; then
  echo "BANXUM_BACKUP_S3_URI is required when BANXUM_BACKUP_REQUIRE_OFFSITE=true" >&2
  exit 2
fi
if [[ ! -f "$COMPOSE_FILE" || ! -f "$ENV_FILE" ]]; then
  echo "Compose or environment file was not found for $PROJECT_NAME" >&2
  exit 2
fi

install -d -m 0700 "$BACKUP_DIR"
exec 9>"$BACKUP_DIR/.backup.lock"
if ! flock -n 9; then
  echo "Another BANXUM PostgreSQL backup is already running" >&2
  exit 3
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
base_name="${PROJECT_NAME}-postgres-${timestamp}.dump"
temporary_path="$BACKUP_DIR/.${base_name}.partial"
final_path="$BACKUP_DIR/$base_name"
checksum_path="${final_path}.sha256"

cleanup() {
  rm -f "$temporary_path"
}
trap cleanup EXIT

compose=(docker compose --project-name "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE")
"${compose[@]}" exec -T postgres sh -c \
  'pg_dump --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --format=custom --compress=9' \
  > "$temporary_path"

if [[ ! -s "$temporary_path" ]]; then
  echo "PostgreSQL backup was empty" >&2
  exit 4
fi

# Validate the custom-format archive before publishing or retaining it.
"${compose[@]}" exec -T postgres pg_restore --list >/dev/null < "$temporary_path"
chmod 0600 "$temporary_path"
mv "$temporary_path" "$final_path"
sha256sum "$final_path" > "$checksum_path"
chmod 0600 "$checksum_path"

if [[ -n "$S3_URI" ]]; then
  upload_args=(--only-show-errors --sse AES256)
  if [[ -n "$KMS_KEY_ID" ]]; then
    upload_args=(--only-show-errors --sse aws:kms --sse-kms-key-id "$KMS_KEY_ID")
  fi
  aws s3 cp "$final_path" "${S3_URI%/}/$base_name" "${upload_args[@]}"
  aws s3 cp "$checksum_path" "${S3_URI%/}/${base_name}.sha256" "${upload_args[@]}"
fi

find "$BACKUP_DIR" -maxdepth 1 -type f \
  \( -name "${PROJECT_NAME}-postgres-*.dump" -o -name "${PROJECT_NAME}-postgres-*.dump.sha256" \) \
  -mtime "+$RETENTION_DAYS" -delete

echo "Created and validated $final_path"
if [[ -n "$S3_URI" ]]; then
  echo "Uploaded encrypted backup to ${S3_URI%/}/$base_name"
else
  echo "No off-host upload configured; this local backup alone does not satisfy the production go-live gate" >&2
fi
