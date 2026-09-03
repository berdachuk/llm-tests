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
- **Long-context retrieval** (10/10, including both distractor tasks --
  model correctly ignores decoy markers even when the decoy's own note
  text points at it).
- **MCP/tool-call** (7/8 by design; task 06 is an intentional hallucination
  probe and is expected to fail every run -- not tracked here as a
  "finding" since it's the task's designed purpose, see
  `fixtures/mcp-tools/README.md`).

## Fixture robustness gap (not a model finding) -- security-review task 07

After the unified runner (`harness/run_all.py`) was built and re-run
against the full security-review category, task 07
(`broken-access-control`) failed on its first re-verification, having
originally passed 8/8. Investigation:

- The model's fix was substantively correct every time: query the invoice
  repository by *both* invoice ID and the authenticated user's ID (a
  textbook ownership check), e.g. "Query the repository using both the
  invoice ID and the authenticated user's ID" / `findByInvoiceIdAndOwnerId(...)`.
- `expected.json`'s required-phrase group 2 only recognized a fixed set
  of phrasings (`"belongs to.*(user|customer)"`, `"owns? the invoice"`,
  etc.) and didn't anticipate this equally-valid paraphrase describing
  the *mechanism* (querying by two IDs together) rather than naming the
  concept ("ownership") directly.
- **This was a fixture gap, not a model regression** -- broadened the
  regex group to also match `"invoice.*(and|with).*(user|owner).*id"` /
  `"(user|owner).*id.*and.*invoice"`, re-verified 8/8 passes cleanly
  afterward. Kept the check strict (still requires the two-ID-together
  concept, not just any mention of "invoice" and "id" separately).

This is a useful reminder that regex-recall grading for the
security-review category may need occasional broadening as new valid
phrasings are observed across runs -- treat any single-task security-
review failure as "investigate the actual response first" before
assuming it's a genuine model quality regression.

## Infrastructure incident (not a model or fixture finding) -- FP8 server OOM during official run

During the official full 50-task FP8 run (java-spring -> ts-angular ->
sql-migrations -> mcp-tools -> security-review -> long-context, all
in one continuous server session), the long-context category failed
0/10: task 01 hit the harness's 600s timeout and every task after it got
`Connection refused`.

**Root cause (confirmed via `~/qwen36_35b_serve.log`):** genuine
`torch.OutOfMemoryError: CUDA out of memory` inside the FreeToken
scheduler subprocess, raised in the linear-attention "gated delta rule"
kernel (`chunk_gated_delta_rule_fwd_h`) while allocating a 128 MiB
tensor. At the moment of the crash the process already held 14.46 GiB of
the RTX 5060 Ti's 16.3 GiB capacity -- after ~47 minutes of continuous
serving across the first 5 categories, there wasn't enough headroom left
for the long-context tasks' larger activation buffers (some prompts are
up to ~150k tokens). The scheduler subprocess died; the API server
correctly detected the dead worker and shut itself down cleanly (no
zombie process, no leftover GPU allocation once the process exited --
confirmed via `nvidia-smi` after kill, only ~970 MiB desktop/X11 usage
remained).

**Resolution:** restarted the FP8 server fresh, verified healthy via a
real `/v1/chat/completions` round trip (not just `/v1/models`), then
re-ran *only* the long-context category in isolation. It passed 10/10
cleanly, including both 150k-token tasks, with GPU memory holding
steady around 15.6-15.7 GiB throughout -- i.e. right at the edge of the
card's capacity, but stable when long-context runs against a freshly-
loaded server rather than one that has already served ~2000s of prior
traffic across other categories.

**Disposition:** hardware/infrastructure constraint specific to this
16 GB card under the offload-MoE serving configuration, not a model
quality issue or fixture bug. **Actionable for the NVFP4 run:** run
long-context either first (right after server start) or as its own
isolated invocation, rather than last in a single long continuous
session, to avoid the same OOM. Since NVFP4 quantization should use
less VRAM for weights than FP8, this specific crash may not reproduce
on NVFP4 at all -- worth explicitly noting in the comparative report
either way.

See `results/run-fp8-final-20260903.md` for the consolidated final FP8
report (48/50, combining the two runs across the restart).

## NVFP4 -- SQL migrations task 04 (`non-idempotent-migration`) -- new, NVFP4-specific finding

Unlike FP8 (which showed an occasional reasoning-loop non-termination on
this task, ~1/3 frequency, other runs passing cleanly), the NVFP4
quantization shows a **different and much more consistent** failure
mode on the same task: **4/4 fail** across the official run + 3
dedicated reruns, always with the identical root cause.

**Observed pattern:** the model's fix correctly recognizes and guards
the later statements against re-application --
`CREATE INDEX ... ON accounts (is_active)` becomes idempotent (or is
otherwise handled), and `CREATE TABLE account_tiers` / the `INSERT`
seed get proper `IF NOT EXISTS` / `ON CONFLICT DO NOTHING` guards -- but
consistently leaves the **very first statement** unguarded:
```sql
ALTER TABLE accounts ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT true;
```
with no `ADD COLUMN IF NOT EXISTS`. Since this is the first line of the
migration, the second application fails immediately with
`ERROR: column "is_active" of relation "accounts" already exists`,
before any of the (correctly-guarded) later statements even get a
chance to run.

**Frequency:** 4/4 (official run + 3 reruns), all with the exact same
root cause -- this task is currently the single most reliably-failing
task in the entire 50-task suite for NVFP4.

**Disposition:** a genuine, highly reproducible NVFP4-specific quality
regression relative to FP8 on this exact task. FP8 fails here rarely and
via a different mechanism (decision-paralysis / non-termination); NVFP4
fails here consistently and via a specific omission (forgetting to guard
only the first of several statements needing idempotency guards, despite
correctly guarding the rest). Worth flagging prominently in the
comparative report as the clearest quality difference found between the
two quantizations.

## NVFP4 -- SQL migrations task 05 (`fk-missing-unique-target`) -- confirms FP8 finding, not FP8-specific

Re-ran 3x after the official run's failure. Result: 2/3 pass, 1/3 fail
with the exact same invalid-Postgres-syntax hallucination already
documented for FP8 above (`ALTER TABLE ... ADD CONSTRAINT IF NOT EXISTS
...`, which does not exist in Postgres). Frequency is comparable to
FP8's ~40-60% failure rate on this task. **This confirms the finding is
a model-family characteristic that persists across both quantizations,
not an FP8-specific artifact.**

## NVFP4 -- long-context OOM risk

Running long-context first (immediately after a fresh server restart)
rather than last avoided any OOM crash on NVFP4, matching the mitigation
already established for FP8. GPU usage during NVFP4 long-context peaked
at ~15.7 of 16.3 GiB -- essentially identical to FP8's footprint. The
NVFP4-quantized weights did not meaningfully reduce VRAM pressure in
this configuration, most likely because `--kv-reserve-tokens 260000`
(not model-weight size) is the dominant allocation. The OOM risk is
therefore a fixed hardware/serving-config constraint independent of
quantization -- run long-context first (or in isolation) for any future
run of either quantization on this card.

See `results/run-nvfp4-final-20260903.md` for the consolidated final
NVFP4 report (46/50).
