# Task 03: Rename a column that a view depends on

`seed.sql` creates a `products` table with a poorly-named `qty` column,
plus a reporting view `low_stock_products` that references `qty`.

`up.sql` is a pending migration meant to rename `qty` to the clearer
`quantity_in_stock`, as part of a larger cleanup.

**Your task:** Review `up.sql`. Renaming a column that a dependent view
references requires updating the view's definition too, or the view will
either break or (worse, depending on how it's done) silently keep
referencing stale/wrong state. Fix `up.sql` so that:
1. The column is renamed to `quantity_in_stock`.
2. The `low_stock_products` view still exists afterward and still
   correctly reports products with fewer than 10 units in stock, using
   the NEW column name.

Run `./verify.sh` to check your fix.
