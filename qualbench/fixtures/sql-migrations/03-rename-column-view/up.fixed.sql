-- Reference fix: use RENAME COLUMN, which PostgreSQL propagates
-- automatically into dependent view definitions -- no need to touch the
-- view at all, and its column list (still named "qty" for external
-- consumers) and semantics are fully preserved.
ALTER TABLE products RENAME COLUMN qty TO quantity_in_stock;
