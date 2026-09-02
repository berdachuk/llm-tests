CREATE TABLE discount_codes (
    code TEXT PRIMARY KEY,
    percent INTEGER NOT NULL
);

INSERT INTO discount_codes (code, percent) VALUES
    ('SAVE10', 10),
    ('SAVE25', 25),
    ('VIP50', 50);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_name TEXT NOT NULL,
    discount_code TEXT REFERENCES discount_codes (code),
    discount_percent INTEGER NOT NULL DEFAULT 0
);

INSERT INTO orders (customer_name, discount_code) VALUES
    ('Alice', 'SAVE10'),
    ('Bob', NULL),
    ('Carla', 'VIP50'),
    ('Dana', NULL),
    ('Evan', 'SAVE25');
