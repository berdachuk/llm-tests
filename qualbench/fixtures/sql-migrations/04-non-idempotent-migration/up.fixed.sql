-- Reference fix: every DDL statement uses an IF (NOT) EXISTS guard, and
-- the seed-data insert uses ON CONFLICT DO NOTHING against the primary
-- key so re-running never duplicates rows.
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true;

CREATE INDEX IF NOT EXISTS idx_accounts_is_active ON accounts (is_active);

CREATE TABLE IF NOT EXISTS account_tiers (
    name TEXT PRIMARY KEY
);

INSERT INTO account_tiers (name) VALUES ('free'), ('pro'), ('enterprise')
ON CONFLICT (name) DO NOTHING;
