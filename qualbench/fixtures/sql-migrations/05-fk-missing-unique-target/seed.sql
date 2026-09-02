CREATE TABLE warehouses (
    id SERIAL PRIMARY KEY,
    code TEXT NOT NULL,  -- intended to be a unique business code, but no
                         -- constraint currently enforces that
    city TEXT NOT NULL
);

INSERT INTO warehouses (code, city) VALUES
    ('WH-EAST', 'Boston'),
    ('WH-WEST', 'Seattle');

CREATE TABLE shipments (
    id SERIAL PRIMARY KEY,
    tracking_number TEXT NOT NULL
);
