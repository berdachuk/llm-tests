-- Reference fix: join discount_codes to orders on the actual matching
-- key, and restrict to orders that actually have a discount_code -- so
-- NULL-discount orders are correctly left untouched at their default 0.
UPDATE orders
SET discount_percent = discount_codes.percent
FROM discount_codes
WHERE orders.discount_code = discount_codes.code;
