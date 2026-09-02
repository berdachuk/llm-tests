-- Reference fix: non-destructively disambiguate the duplicate BEFORE
-- adding the constraint, by appending a suffix derived from the row's own
-- id to every row that isn't the earliest (lowest-id) holder of a given
-- email. No rows are deleted; only the conflicting duplicate's email
-- value is corrected to something clearly flagged for manual follow-up.
UPDATE users u
SET email = u.email || '+dup' || u.id || '@qualbench.invalid'
WHERE u.id NOT IN (
    SELECT MIN(id) FROM users GROUP BY email
);

ALTER TABLE users ADD CONSTRAINT users_email_key UNIQUE (email);
