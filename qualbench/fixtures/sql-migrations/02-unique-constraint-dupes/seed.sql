CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL
);

INSERT INTO users (id, email) VALUES
    (1, 'alice@example.com'),
    (2, 'bob@example.com'),
    (3, 'alice@example.com'),  -- accidental duplicate of row 1's email
    (4, 'carla@example.com');
