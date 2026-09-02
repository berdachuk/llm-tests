# Task 02: Add a UNIQUE constraint to a column with existing duplicates

`seed.sql` creates a `users` table with an `email` column and inserts
several rows, including two rows that accidentally share the same email
address (a pre-existing data quality problem).

`up.sql` is a pending migration meant to enforce that emails are unique
going forward.

**Your task:** Review `up.sql`. Fix it so that:
1. The migration applies successfully despite the existing duplicate.
2. After migration, `email` has an enforced UNIQUE constraint (verified by
   attempting -- and failing -- to insert a second row with an
   already-used email).
3. No user rows are silently deleted to "fix" the duplicate -- both
   original rows for the duplicated email must still exist afterward, but
   the migration must ensure the STORED values that will be constrained
   are actually unique (e.g. by disambiguating the duplicate in a
   non-destructive way), OR provide a corrective step that a real DBA
   would take. Do not silently drop data.

Run `./verify.sh` to check your fix.
