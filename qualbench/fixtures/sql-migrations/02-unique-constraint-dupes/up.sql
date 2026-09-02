-- BUG: adds a UNIQUE constraint directly against existing data that
-- already contains a duplicate email ('alice@example.com' appears twice,
-- for user ids 1 and 3). PostgreSQL validates the constraint against all
-- current rows at ADD-CONSTRAINT time, so this fails immediately with:
--   ERROR: could not create unique index "users_email_key"
--   DETAIL: Key (email)=(alice@example.com) is duplicated.
ALTER TABLE users ADD CONSTRAINT users_email_key UNIQUE (email);
