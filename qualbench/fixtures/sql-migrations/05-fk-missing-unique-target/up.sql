-- BUG: adds a foreign key referencing warehouses.code, but code has no
-- UNIQUE constraint or index (and isn't the primary key). PostgreSQL
-- rejects this outright with:
--   ERROR: there is no unique constraint matching given keys for
--   referenced table "warehouses"
ALTER TABLE shipments ADD COLUMN warehouse_code TEXT;

ALTER TABLE shipments
    ADD CONSTRAINT fk_shipments_warehouse_code
    FOREIGN KEY (warehouse_code) REFERENCES warehouses (code);
