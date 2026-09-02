# SQL / Migration Review fixtures

6 self-contained Postgres migration-review tasks. Each task directory
contains:

- `seed.sql` -- base schema + data, applied first.
- `up.sql` -- the buggy migration under review/repair.
- `up.fixed.sql` -- reference solution (used to validate the fixture
  itself; not shown to the model under test).
- `check.sql` -- deterministic post-migration assertions. Every SELECT
  must return a single `check_result = t` row.
- `README.md` -- the task prompt.
- `RUN_TWICE` (only in task 04) -- marker file telling `verify.sh` to
  apply the migration a second time before running checks (idempotency
  test).

## Prerequisites

A scratch Postgres instance reachable at `127.0.0.1:15432`, user
`postgres`, password `qualbench`. Start one with:

```bash
docker run --rm -d --name qualbench-pg \
  -e POSTGRES_PASSWORD=qualbench -e POSTGRES_DB=qualbench \
  -p 15432:5432 postgres:18-alpine
```

(The system-installed Postgres on this machine requires an interactive
sudo password for the `postgres` role, so fixtures use an isolated Docker
container instead. This also keeps every verify.sh run fully isolated
via a fresh scratch database per invocation.)

## Running

```bash
./verify.sh <task-dir> [migration-file]
```

- `migration-file` defaults to `up.sql`. Pass `up.fixed.sql` to confirm
  the reference solution passes, or the candidate's proposed fix file.
- Exit code 0 = migration applied and all checks passed.
- Exit code 1 = migration failed to apply, or at least one check failed.

Each invocation creates and drops its own uniquely-named scratch
database, so tasks/runs never interfere with each other.
