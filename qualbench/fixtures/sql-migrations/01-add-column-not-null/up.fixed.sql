-- Reference fix: provide a DEFAULT so existing rows are backfilled
-- automatically and atomically as part of the ALTER TABLE, and so future
-- inserts that omit shipping_status default to 'pending' too.
ALTER TABLE orders ADD COLUMN shipping_status TEXT NOT NULL DEFAULT 'pending';
