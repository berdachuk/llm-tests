# Task 06: Backfill UPDATE with a wrong/missing join condition

`seed.sql` creates an `orders` table and a `discount_codes` table, and
inserts several orders, only SOME of which used a discount code
(tracked via `orders.discount_code`, which is NULL for orders that used
no discount).

`up.sql` is a pending "backfill" migration meant to populate a new
`orders.discount_percent` column by looking up each order's discount
code in `discount_codes` -- but only for orders that actually used a
discount code. Orders with no discount code must be left at 0.

**Your task:** Review `up.sql`. It applies without any SQL error, but
that does NOT mean it's correct -- run it and check whether it actually
computes the right values. Fix it so that:
1. Every order that used a real discount code gets that code's correct
   `discount_percent`.
2. Every order that used NO discount code (`discount_code IS NULL`) ends
   up with `discount_percent = 0`, not some other/wrong value.
3. No order's discount_percent is populated from the WRONG discount code.

Run `./verify.sh` to check your fix. (This migration "succeeds" with no
error even in its buggy form -- read the check output carefully, this is
a silent logic bug, not a crash.)
