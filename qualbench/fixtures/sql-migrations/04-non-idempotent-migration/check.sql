-- 1. is_active column exists correctly.
SELECT
    'is_active_column_correct' AS check_name,
    (EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'accounts' AND column_name = 'is_active'
          AND is_nullable = 'NO' AND data_type = 'boolean'
    )) AS check_result;

-- 2. Index on is_active exists (exactly one, not duplicated).
SELECT
    'index_exists_exactly_once' AS check_name,
    (COUNT(*) = 1) AS check_result
FROM pg_indexes
WHERE tablename = 'accounts' AND indexdef ILIKE '%is_active%';

-- 3. account_tiers has exactly the 3 expected rows, no duplicates from
-- the second run.
SELECT
    'account_tiers_has_no_dupes' AS check_name,
    (
        (SELECT COUNT(*) FROM account_tiers) = 3
        AND (SELECT COUNT(DISTINCT name) FROM account_tiers) = 3
    ) AS check_result;

-- 4. Original accounts rows were untouched by the re-run (no duplicated
-- accounts, still exactly 2).
SELECT
    'accounts_row_count_unchanged' AS check_name,
    (COUNT(*) = 2) AS check_result
FROM accounts;
