# Task 01: Add a NOT NULL column to a populated table

`seed.sql` creates an `orders` table and inserts several existing rows.

`up.sql` is a pending migration meant to add a `shipping_status` column
that every order must have (`NOT NULL`), to support a new shipment
tracking feature.

**Your task:** Review `up.sql`. If it has a problem that will prevent it
from applying cleanly to the table created/populated by `seed.sql`, fix
`up.sql` so that:
1. It applies successfully against the existing data (no error).
2. Every existing row ends up with a valid, sensible `shipping_status`
   value (not simply left NULL -- the column must remain `NOT NULL`).
3. Going forward, inserting a new order without specifying
   `shipping_status` should default it to `'pending'`.

Run `./verify.sh` to check your fix.
