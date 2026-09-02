-- Deterministic post-migration checks. Each SELECT must return exactly
-- one row with check_result = true, or verify.sh reports failure.

-- 1. Column exists, is NOT NULL, and has a DEFAULT.
SELECT
    'column_not_null_with_default' AS check_name,
    (is_nullable = 'NO' AND column_default IS NOT NULL) AS check_result
FROM information_schema.columns
WHERE table_name = 'orders' AND column_name = 'shipping_status';

-- 2. No existing rows were left with a NULL/garbage status -- all must
-- have a real, non-empty value.
SELECT
    'all_existing_rows_backfilled' AS check_name,
    (COUNT(*) = 0) AS check_result
FROM orders
WHERE shipping_status IS NULL OR shipping_status = '';

-- 3. A newly inserted row that doesn't specify shipping_status gets
-- 'pending' as the default.
INSERT INTO orders (customer_name, total_cents) VALUES ('Dana', 1200);
SELECT
    'new_row_defaults_to_pending' AS check_name,
    (shipping_status = 'pending') AS check_result
FROM orders
WHERE customer_name = 'Dana';
