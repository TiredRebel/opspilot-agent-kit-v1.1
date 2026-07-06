#!/usr/bin/env bash
# P6-2: proves the dump/restore cycle scripts/backup.sh relies on actually works, against a
# throwaway scratch database — needs no cloud credentials, only the local postgres container.
# Not part of `make test` (touches a real, if scratch, Postgres via docker exec) — run manually:
#   bash scripts/test_backup_restore.sh
set -euo pipefail

POSTGRES_USER="${POSTGRES_USER:-opspilot}"
POSTGRES_DB="${POSTGRES_DB:-opspilot}"
SCRATCH_DB="opspilot_restore_test"
CONTAINER="opspilot-agent-kit-v11-postgres-1"
DUMP_FILE="/tmp/opspilot-restore-test.sql.gz"

cleanup() {
  docker exec "$CONTAINER" psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$SCRATCH_DB\" WITH (FORCE);" >/dev/null
  rm -f "$DUMP_FILE"
}
trap cleanup EXIT

echo "1. Row counts in source ($POSTGRES_DB):"
source_counts=$(docker exec "$CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tA -c "
  SELECT 'kb_documents=' || (SELECT COUNT(*) FROM kb_documents)
      || ' kb_chunks=' || (SELECT COUNT(*) FROM kb_chunks);
")
echo "   $source_counts"

echo "2. Dumping $POSTGRES_DB..."
docker exec "$CONTAINER" pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" | gzip > "$DUMP_FILE"
echo "   $(du -h "$DUMP_FILE" | cut -f1) written to $DUMP_FILE"

echo "3. Creating scratch database $SCRATCH_DB..."
docker exec "$CONTAINER" psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$SCRATCH_DB\" WITH (FORCE);" >/dev/null
docker exec "$CONTAINER" psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE \"$SCRATCH_DB\";" >/dev/null

echo "4. Restoring dump into $SCRATCH_DB..."
gunzip -c "$DUMP_FILE" | docker exec -i "$CONTAINER" psql -U "$POSTGRES_USER" -d "$SCRATCH_DB" >/dev/null

echo "5. Row counts in restored ($SCRATCH_DB):"
restored_counts=$(docker exec "$CONTAINER" psql -U "$POSTGRES_USER" -d "$SCRATCH_DB" -tA -c "
  SELECT 'kb_documents=' || (SELECT COUNT(*) FROM kb_documents)
      || ' kb_chunks=' || (SELECT COUNT(*) FROM kb_chunks);
")
echo "   $restored_counts"

if [ "$source_counts" = "$restored_counts" ]; then
  echo "PASS: restored row counts match the source exactly."
  exit 0
else
  echo "FAIL: row counts differ (source: $source_counts, restored: $restored_counts)."
  exit 1
fi
