CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_name TEXT NOT NULL,
    total_cents INTEGER NOT NULL
);

INSERT INTO orders (customer_name, total_cents) VALUES
    ('Alice', 1999),
    ('Bob', 4550),
    ('Carla', 750);
