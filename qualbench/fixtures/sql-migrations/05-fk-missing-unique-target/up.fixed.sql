-- Reference fix: add a UNIQUE constraint on warehouses.code FIRST (this
-- also protects against future duplicate codes), then the foreign key can
-- be created successfully.
ALTER TABLE warehouses ADD CONSTRAINT warehouses_code_key UNIQUE (code);

ALTER TABLE shipments ADD COLUMN warehouse_code TEXT;

ALTER TABLE shipments
    ADD CONSTRAINT fk_shipments_warehouse_code
    FOREIGN KEY (warehouse_code) REFERENCES warehouses (code);
