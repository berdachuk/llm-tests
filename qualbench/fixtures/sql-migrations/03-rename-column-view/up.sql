-- BUG: implements the "rename" as DROP COLUMN + ADD COLUMN instead of
-- ALTER TABLE ... RENAME COLUMN. Because low_stock_products depends on
-- the qty column, dropping it fails outright:
--   ERROR: cannot drop column qty of table products because other
--   objects depend on it
--   DETAIL: view low_stock_products depends on column qty of table products
-- (If someone "fixed" this by adding CASCADE, it would silently DROP the
-- low_stock_products view entirely instead of preserving it under the new
-- column name -- an even worse outcome.)
ALTER TABLE products DROP COLUMN qty;
ALTER TABLE products ADD COLUMN quantity_in_stock INTEGER NOT NULL DEFAULT 0;
