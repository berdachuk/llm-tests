#!/usr/bin/env bash
# Generic dry-run + validation harness for a qualbench SQL migration task.
#
# Usage: ./verify.sh <task-dir> [up-file]
#   task-dir  Path to a task directory containing seed.sql, check.sql, and
#             either up.sql (the candidate migration, default) or an
#             explicitly named migration file to test.
#   up-file   Optional filename (relative to task-dir) of the migration to
#             apply instead of up.sql -- e.g. "up.fixed.sql" to confirm the
#             reference solution passes.
#
# Exit code 0 = migration applied AND every check_result was true.
# Exit code 1 = migration failed to apply, or at least one check failed.
#
# Each run gets a fresh, isolated database inside the qualbench-pg
# container (started separately -- see README at the repo root), so tasks
# never interfere with each other and can be re-run repeatedly.

set -uo pipefail

TASK_DIR="${1:?usage: verify.sh <task-dir> [up-file]}"
UP_FILE="${2:-up.sql}"
PGHOST="${QUALBENCH_PGHOST:-127.0.0.1}"
PGPORT="${QUALBENCH_PGPORT:-15432}"
PGUSER="${QUALBENCH_PGUSER:-postgres}"
export PGPASSWORD="${QUALBENCH_PGPASSWORD:-qualbench}"

DB_NAME="qualbench_$(basename "$TASK_DIR" | tr '-' '_')_$$"

cleanup() {
  psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -v ON_ERROR_STOP=1 \
    -c "DROP DATABASE IF EXISTS \"${DB_NAME}\";" >/dev/null 2>&1
}
trap cleanup EXIT

echo "== Task: $TASK_DIR =="
echo "== Migration file: $UP_FILE =="

psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d postgres -v ON_ERROR_STOP=1 \
  -c "CREATE DATABASE \"${DB_NAME}\";" || { echo "FAIL: could not create scratch database"; exit 1; }

echo "-- Applying seed.sql --"
if ! psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$DB_NAME" -v ON_ERROR_STOP=1 \
    -f "$TASK_DIR/seed.sql"; then
  echo "FAIL: seed.sql itself failed to apply (fixture bug, not a candidate failure)"
  exit 1
fi

echo "-- Applying $UP_FILE (dry-run of the migration under test) --"
if ! psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$DB_NAME" -v ON_ERROR_STOP=1 \
    -f "$TASK_DIR/$UP_FILE"; then
  echo "FAIL: $UP_FILE did not apply cleanly"
  exit 1
fi

if [ -f "$TASK_DIR/RUN_TWICE" ]; then
  echo "-- Re-applying $UP_FILE a second time (idempotency check) --"
  if ! psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$DB_NAME" -v ON_ERROR_STOP=1 \
      -f "$TASK_DIR/$UP_FILE"; then
    echo "FAIL: $UP_FILE did not apply cleanly on a second run (not idempotent)"
    exit 1
  fi
fi

echo "-- Running check.sql --"
RESULTS="$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$DB_NAME" -v ON_ERROR_STOP=1 \
  -q -t -A -F'|' -f "$TASK_DIR/check.sql")"
STATUS=$?

if [ "$STATUS" -ne 0 ]; then
  echo "FAIL: check.sql itself errored"
  exit 1
fi

echo "$RESULTS"

FAILED=0
while IFS='|' read -r name result; do
  [ -z "$name" ] && continue
  if [ "$result" != "t" ]; then
    echo "FAIL: check '$name' returned '$result' (expected 't')"
    FAILED=1
  fi
done <<< "$RESULTS"

if [ "$FAILED" -eq 0 ]; then
  echo "PASS: all checks succeeded"
  exit 0
else
  exit 1
fi
