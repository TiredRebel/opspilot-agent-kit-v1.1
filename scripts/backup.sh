#!/usr/bin/env bash
# P6-2: nightly pg_dump -> gzip -> upload to object storage via rclone.
#
# rclone (not gsutil/aws-cli) so this script doesn't hard-couple to one cloud — point
# RCLONE_REMOTE at whatever remote you've configured (`rclone config`) for S3, GCS, B2, etc.
# The pg_dump/gzip/restore portions need no cloud credentials and are covered by
# scripts/test_backup_restore.sh; the actual rclone upload/download is not exercised by that test.
#
# Cron (documented, not installed by this script):
#   0 3 * * * /path/to/opspilot/scripts/backup.sh >> /var/log/opspilot-backup.log 2>&1
set -euo pipefail

POSTGRES_USER="${POSTGRES_USER:-opspilot}"
POSTGRES_DB="${POSTGRES_DB:-opspilot}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
RCLONE_REMOTE="${RCLONE_REMOTE:-opspilot-backups:opspilot/db}"
BACKUP_DIR="${BACKUP_DIR:-/tmp/opspilot-backups}"

mkdir -p "$BACKUP_DIR"
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
dump_file="$BACKUP_DIR/opspilot-$timestamp.sql.gz"

echo "Dumping $POSTGRES_DB (as $POSTGRES_USER) to $dump_file..."
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" | gzip > "$dump_file"

size=$(du -h "$dump_file" | cut -f1)
echo "Dump complete: $dump_file ($size)"

if command -v rclone >/dev/null 2>&1; then
  echo "Uploading to $RCLONE_REMOTE ..."
  rclone copy "$dump_file" "$RCLONE_REMOTE"
  echo "Upload complete."
else
  echo "rclone not installed — skipping upload. Dump kept locally at $dump_file." >&2
fi

# Keep the last 14 local dumps; rely on the object-storage lifecycle policy (configure separately)
# for longer retention.
find "$BACKUP_DIR" -name 'opspilot-*.sql.gz' -mtime +14 -delete

echo "Done."
