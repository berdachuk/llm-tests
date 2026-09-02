# Task 04: Make a migration safe to re-run (idempotent)

`seed.sql` creates a base `accounts` table.

`up.sql` is a migration meant to add an `is_active` flag column and a
supporting index, then seed a new lookup table `account_tiers`.

Migration tooling sometimes re-applies the same "up" script more than
once (e.g. after a partial failure, a bad deploy retry, or manual
re-running during an incident). **Your task:** Review `up.sql`. Fix it so
that running it TWICE in a row against the same database succeeds both
times with no errors and leaves the database in the same correct end
state either way (idempotent), while still doing all of the following
after the first run:
1. `accounts` has an `is_active BOOLEAN NOT NULL DEFAULT true` column.
2. An index exists on `accounts.is_active`.
3. `account_tiers` exists and contains exactly the rows `('free')`,
   `('pro')`, `('enterprise')` (no duplicates, even after a second run).

Run `./verify.sh` to check your fix (it runs the migration twice).
