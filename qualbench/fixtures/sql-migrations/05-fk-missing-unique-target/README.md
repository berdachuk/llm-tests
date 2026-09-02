# Task 05: Foreign key referencing a non-unique target column

`seed.sql` creates a `warehouses` table (with a `code` column that is
NOT currently unique) and an empty `shipments` table.

`up.sql` is a pending migration meant to add a foreign key from
`shipments.warehouse_code` to `warehouses.code`, so shipments can be
linked to the warehouse that handles them.

**Your task:** Review `up.sql`. A FOREIGN KEY can only reference a column
(or column set) on the target table that is guaranteed unique -- i.e. a
PRIMARY KEY or a column with a UNIQUE constraint/index. Fix `up.sql` so
that the foreign key can actually be created, without silently allowing
`warehouses.code` to contain duplicates going forward (that would defeat
the purpose of linking shipments to a single specific warehouse).

Run `./verify.sh` to check your fix.
