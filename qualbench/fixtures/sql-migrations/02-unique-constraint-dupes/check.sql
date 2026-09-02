-- 1. All 4 original rows still exist -- no data was deleted.
SELECT
    'no_rows_deleted' AS check_name,
    (COUNT(*) = 4) AS check_result
FROM users;

-- 2. The UNIQUE constraint now exists on email.
SELECT
    'unique_constraint_exists' AS check_name,
    (COUNT(*) = 1) AS check_result
FROM pg_constraint
WHERE conrelid = 'users'::regclass AND contype = 'u';

-- 3. Inserting a new row with an email that is already in use fails.
-- We test this via a DO block that catches the expected unique_violation
-- and reports success only if the exception was actually raised.
DO $$
BEGIN
    BEGIN
        INSERT INTO users (email) VALUES ('bob@example.com');
        RAISE EXCEPTION 'expected unique_violation but insert succeeded';
    EXCEPTION WHEN unique_violation THEN
        NULL; -- expected
    END;
END $$;

SELECT
    'duplicate_insert_rejected' AS check_name,
    (COUNT(*) = 1) AS check_result
FROM users
WHERE email = 'bob@example.com';
