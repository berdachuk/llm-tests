-- BUG: none of these statements guard against already having been run.
-- Re-running this script a second time fails at the very first statement
-- with "ERROR: column "is_active" of relation "accounts" already
-- exists" -- and even if that were fixed, CREATE TABLE / CREATE INDEX /
-- the INSERTs below would each independently fail or duplicate rows on a
-- second run too.
ALTER TABLE accounts ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT true;

CREATE INDEX idx_accounts_is_active ON accounts (is_active);

CREATE TABLE account_tiers (
    name TEXT PRIMARY KEY
);

INSERT INTO account_tiers (name) VALUES ('free'), ('pro'), ('enterprise');
