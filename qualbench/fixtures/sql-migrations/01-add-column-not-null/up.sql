-- BUG: adds a NOT NULL column with no DEFAULT to a table that already has
-- rows. PostgreSQL must backfill every existing row with a value for the
-- new NOT NULL column at the moment it's added -- without a DEFAULT (or a
-- separate backfill step), this fails immediately with:
--   ERROR: column "shipping_status" contains null values
ALTER TABLE orders ADD COLUMN shipping_status TEXT NOT NULL;
