CREATE TABLE accounts (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

INSERT INTO accounts (name) VALUES ('Acme Corp'), ('Globex');
