-- BUG: this UPDATE...FROM is missing the join condition linking
-- orders.discount_code to discount_codes.code. Without a WHERE clause
-- connecting them, PostgreSQL performs an implicit cross join -- every
-- row in `orders` gets updated once per row in `discount_codes`, and the
-- FINAL value each order ends up with is effectively whichever
-- discount_codes row happened to be processed last (undefined by row
-- order, but deterministically wrong). This affects EVERY order,
-- including the ones that used no discount code at all (discount_code
-- IS NULL), which should have stayed at 0.
UPDATE orders
SET discount_percent = discount_codes.percent
FROM discount_codes;
