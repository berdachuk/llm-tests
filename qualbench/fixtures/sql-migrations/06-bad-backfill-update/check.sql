-- 1. Orders with a real discount code get the correct percent.
SELECT
    'discount_codes_backfilled_correctly' AS check_name,
    (
        (SELECT discount_percent FROM orders WHERE customer_name = 'Alice') = 10
        AND (SELECT discount_percent FROM orders WHERE customer_name = 'Carla') = 50
        AND (SELECT discount_percent FROM orders WHERE customer_name = 'Evan') = 25
    ) AS check_result;

-- 2. Orders with NO discount code stay at 0.
SELECT
    'no_discount_orders_stay_zero' AS check_name,
    (
        (SELECT discount_percent FROM orders WHERE customer_name = 'Bob') = 0
        AND (SELECT discount_percent FROM orders WHERE customer_name = 'Dana') = 0
    ) AS check_result;

-- 3. No order ended up with a discount_percent that doesn't correspond
-- to any real discount code AND isn't 0 (catches "last row wins" style
-- cross-join corruption landing on some plausible-looking value).
SELECT
    'no_orphaned_percent_values' AS check_name,
    (NOT EXISTS (
        SELECT 1 FROM orders o
        WHERE o.discount_percent <> 0
          AND NOT EXISTS (
              SELECT 1 FROM discount_codes dc
              WHERE dc.code = o.discount_code AND dc.percent = o.discount_percent
          )
    )) AS check_result;
