-- 1. warehouses.code now has a UNIQUE constraint (or PK) backing it.
SELECT
    'warehouses_code_is_unique' AS check_name,
    (EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'warehouses'::regclass
          AND contype IN ('u', 'p')
          AND conkey = ARRAY[(
              SELECT attnum FROM pg_attribute
              WHERE attrelid = 'warehouses'::regclass AND attname = 'code'
          )]
    )) AS check_result;

-- 2. The foreign key from shipments.warehouse_code to warehouses.code
-- exists.
SELECT
    'fk_exists' AS check_name,
    (EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'shipments'::regclass AND contype = 'f'
    )) AS check_result;

-- 3. Inserting a shipment with a valid warehouse_code works.
INSERT INTO shipments (tracking_number, warehouse_code) VALUES ('TRACK-1', 'WH-EAST');
SELECT
    'valid_fk_insert_succeeds' AS check_name,
    (COUNT(*) = 1) AS check_result
FROM shipments
WHERE tracking_number = 'TRACK-1';

-- 4. Inserting a shipment with a NON-existent warehouse_code is rejected.
DO $$
BEGIN
    BEGIN
        INSERT INTO shipments (tracking_number, warehouse_code) VALUES ('TRACK-2', 'WH-NORTH');
        RAISE EXCEPTION 'expected foreign_key_violation but insert succeeded';
    EXCEPTION WHEN foreign_key_violation THEN
        NULL; -- expected
    END;
END $$;

SELECT
    'invalid_fk_insert_rejected' AS check_name,
    (COUNT(*) = 0) AS check_result
FROM shipments
WHERE tracking_number = 'TRACK-2';
