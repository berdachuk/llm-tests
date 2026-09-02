CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    qty INTEGER NOT NULL
);

INSERT INTO products (name, qty) VALUES
    ('Widget', 3),
    ('Gadget', 25),
    ('Gizmo', 0);

CREATE VIEW low_stock_products AS
    SELECT id, name, qty
    FROM products
    WHERE qty < 10;
