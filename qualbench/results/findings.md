# qualbench findings log (FP8, pre-unified-runner exploratory runs)

Server: `http://127.0.0.1:8000`, model `qwen3.6-35b-a3b`
(`Qwen3.6-35B-A3B-FP8`, froggeric v22.4 chat template, `ft serve` with
`--moe-backend offload --cuda-graph-max-bs 2 --max-running-requests 2`).

These are exploratory runs made while building each category's harness,
before the unified runner existed. All findings below were reproduced by
re-running the specific task 2-3+ times and inspecting the actual
extracted code/SQL from the model's response (not just the pass/fail
line), to separate "genuine model issue" from "harness extraction bug".

Recorded here so they aren't lost before the official FP8-vs-NVFP4 run
happens through the (not yet built) unified runner.

## TS/Angular -- task 03 (`shopping-cart`)

**Bug:** `total` is computed once at construction instead of reactively.
Idiomatic Angular fixes: either wrap it in `computed()` (returns a
`Signal<number>`, must be called as `cart.total()`) or convert it to a
plain `get total()` getter (accessed as `cart.total`, recomputes on every
read). The spec accesses `cart.total` as a **plain value**, so only the
getter-shaped fix is actually compatible with it -- this was verified
deliberately (see below) and is intentional test design, not a fixture
bug.

**Observed:** Out of ~5 runs at `temperature=0`, one run produced a
`computed()`-based fix (fails: `Signal` object is not `1000`), the rest
produced the getter form (passes). The model's own reasoning trace in the
failing run *explicitly* raised and discussed this exact mismatch
("Wait, if `total` is a signal, `cart.total` would be a signal object...")
before ultimately committing to `computed()` anyway -- i.e. it identified
the risk and then ignored it. Root cause is model
inconsistency/non-determinism under the offload-batching serving setup,
not ambiguity in the task.

**Verification performed:** manually confirmed both a `computed()`-based
fix (fails against the original spec) and a getter-based fix (passes
against the original spec) by directly editing `shopping-cart.ts` in
`base/` and running `ng test --include=...` for each, then restoring the
original file via `git checkout`.

**Disposition:** kept as-is (spec unchanged). Treated as a real,
low-frequency (~1/5 runs observed) FP8 quality signal for this task.

## SQL migrations -- task 02 (`unique-constraint-dupes`)

**Bug:** `ALTER TABLE users ADD CONSTRAINT ... UNIQUE (email)` against
data that already has a duplicate email; must disambiguate duplicates
first (reference fix appends a suffix to non-earliest duplicates) without
deleting any rows, then add the constraint.

**Observed failure (reproduced):** model wrote an `UPDATE ... FROM
duplicates WHERE ...` self-join to disambiguate, using an **ambiguous
column reference**:
```sql
UPDATE users SET email = email || '_' || id
FROM duplicates
WHERE duplicates.id = users.id AND duplicates.rn > 1;
```
Postgres rejects this: `ERROR: column reference "email" is ambiguous`
(exists in both `users` and the `duplicates` CTE). Correct version needs
`users.email` / `users.id` qualification on the left-hand side.

**Frequency:** 2/3 pass in one batch of repeated single-shot runs; other
batches passed 3/3. Roughly 60-100% pass rate across observed runs --
borderline/flaky rather than deterministic failure.

**Disposition:** real, reproducible SQL-correctness gap (self-join
ambiguity), not a harness bug -- confirmed by extracting and reading the
actual candidate SQL with `--keep-scratch`.

## SQL migrations -- task 03 (`rename-column-view`)

**Bug:** a view depends on the column being renamed; naive
`ALTER TABLE ... RENAME COLUMN` + touching the view breaks, because
Postgres actually propagates a column rename into dependent views
automatically -- no view edit is needed at all (reference fix is a single
`RENAME COLUMN` statement).

**Observed failure (reproduced):** model correctly used
`ALTER TABLE products RENAME COLUMN qty TO quantity_in_stock;` (the right
fix on its own) but then *unnecessarily* also emitted:
```sql
CREATE OR REPLACE VIEW low_stock_products AS
    SELECT id, name, quantity_in_stock ...
```
Postgres rejects `CREATE OR REPLACE VIEW` when it would change an
existing view's output column name (`qty` -> `quantity_in_stock`) in
place, requiring `ALTER VIEW ... RENAME COLUMN` instead. The model over-
engineered a fix that was already complete after the first statement.

**Frequency:** 2/3 pass in repeated runs.

**Disposition:** real correctness gap -- over-application of a fix beyond
what's needed, breaking an otherwise-correct first statement.

## SQL migrations -- task 04 (`non-idempotent-migration`)

**Observed failure (reproduced once, not fully reproducible):** in one
run, the model's reasoning entered a long unresolved loop -- repeatedly
re-deriving and re-rejecting the same hypothesis ("is the bug the missing
DEFAULT? no, DEFAULT is present... maybe it's idempotency... wait...")
for the entire visible transcript without ever emitting a final `sql`
code block, exhausting the response before producing an answer. Other
runs on the same task correctly produced the idempotent fix (`IF NOT
EXISTS` on `ADD COLUMN`/`CREATE INDEX`/`CREATE TABLE` + `ON CONFLICT DO
NOTHING` on the insert) and passed cleanly, including the two-apply
idempotency check.

**Frequency:** 1/3 in one repeated batch; other individual re-runs passed.

**Disposition:** real finding -- reasoning-loop / decision-paralysis
failure mode under this serving setup, worth tracking if it recurs at
higher frequency in the official run. Not a harness bug (confirmed the
harness's `max_tokens`/`reasoning_effort` settings match the other
passing categories).

## SQL migrations -- task 05 (`fk-missing-unique-target`)

**Bug:** FK references a column with no unique constraint; reference fix
adds `UNIQUE (code)` to the target table before adding the FK.

**Observed failure (reproduced, consistent root cause across occurrences):**
model correctly identifies the missing-unique-constraint root cause, but
sometimes guards it with invalid syntax:
```sql
ALTER TABLE warehouses ADD CONSTRAINT IF NOT EXISTS warehouses_code_unique UNIQUE (code);
```
`ADD CONSTRAINT ... IF NOT EXISTS` **does not exist** in Postgres --
`IF NOT EXISTS` is only supported for `CREATE INDEX`, `CREATE TABLE`, and
`ADD COLUMN`, not `ADD CONSTRAINT`. The model appears to over-generalize
the idempotency-guard pattern from other statement types.

**Frequency:** roughly 40-60% failure rate across ~8 repeated single-shot
runs during harness development -- the single most unstable task found
so far. Every observed failure had this exact same root cause (never a
different bug).

**Disposition:** the most notable finding overall -- a specific,
reproducible Postgres-syntax hallucination pattern (`ADD CONSTRAINT ...
IF NOT EXISTS`) that recurs at a materially higher rate than any other
single-run flakiness observed elsewhere in the suite. Worth specifically
calling out in the final FP8-vs-NVFP4 report and checking whether NVFP4
shows the same pattern.

## Categories with no findings (stable across all observed runs)

- **Java/Spring** (10/10, including the `InventoryCounter` concurrency
  race -- correctly fixed every observed run).
- **Security review** (8/8).
- **Long-context retrieval** (10/10, including both distractor tasks --
  model correctly ignores decoy markers even when the decoy's own note
  text points at it).
- **MCP/tool-call** (7/8 by design; task 06 is an intentional hallucination
  probe and is expected to fail every run -- not tracked here as a
  "finding" since it's the task's designed purpose, see
  `fixtures/mcp-tools/README.md`).
