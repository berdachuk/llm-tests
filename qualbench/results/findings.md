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

## RTX 4090 (192.168.0.88) -- FP8 full-suite confirmation run

Full 50-task suite re-run against the remote RTX 4090 server
(`http://192.168.0.88:8000`, FP8, froggeric v22.4 template,
`--kv-reserve-tokens 300000`). Result: **46/50**, real avoidable-failure
count **0/50** -- every non-pass is a previously documented finding:

- **java-spring 09** (`request-id-generator`): 1 fail in official run,
  3/3 pass on rerun -- known low-frequency non-determinism.
- **ts-angular 03** (`shopping-cart`): 1 fail in official run, 1/3 pass
  on rerun -- the known `computed()`-vs-getter inconsistency, same
  pattern and frequency as on the 5060 Ti (both quantizations).
- **sql-migrations 05** (`fk-missing-unique-target`): 1 fail in official
  run, 2/3 pass on rerun -- the known `ADD CONSTRAINT IF NOT EXISTS`
  invalid-Postgres-syntax hallucination (~40-60% rate on FP8).
- **mcp-tools 06**: by-design hallucination probe, expected every run.

**Notable:** `sql-migrations/04-non-idempotent-migration` -- the task
that is a reproducible NVFP4-specific regression on the 5060 Ti (4/4
fail) and a rare FP8 reasoning-loop failure there (~1/3) -- **passed** on
the 4090 FP8 run. Consistent with FP8's documented occasional-failure
behavior; does not change the NVFP4-specific finding.

**Infrastructure:** no OOM, no restart needed on the 4090 (24.5 GiB
VRAM absorbs the sustained-serving memory pressure that OOM'd the 16 GB
5060 Ti). Long-context passed 10/10 including both 150K-token tasks.
Harness note: long-context requires `tiktoken` (via `gen_prompt.py`);
run the harness with the repo venv python (`.venv/bin/python`), not the
system python, or that category silently runs 0/0 tasks.

See `results/run-4090-fp8-final-20260903.md` for the consolidated report
(46/50).

---

## Multimodal (vision) category -- initial calibration, 2026-09-19

New opt-in `multimodal` category, run against the vision-enabled FP8
build on the 4090 (`192.168.0.88:8000`). Findings from bringing it up:

### 1. Token budget dominates vision-reasoning results (harness bug, fixed)

This was the single biggest confound in the whole exercise, and it took
three attempts to size correctly.

| run | `max_tokens` | accuracy | truncated | wrong answers | accuracy over answered |
|---|---|---|---|---|---|
| 1 | 1024->2048 | 35/60 = 58.3% | **21** | **4** | 89.7% |
| 2 | 4096 | 40/60 = 66.7% | 12 | 8 | 83.3% |
| probe | 16384 | -- | 0 of 4 retried | -- | those items scored correct |
| 3 | 16384 | **48/60 = 80.0%** | 4 | 8 | 85.7% |

All four domain buckets clear their thresholds at the final setting:
`charts 14/16 (87.5%)`, `photos 11/16 (68.8%)`, `screen-captures 11/12
(91.7%)`, `diagrams 12/16 (75.0%)`; chance floor 26.0%, so the lift is
54 points.

Direct evidence, re-running the four items that truncated in *both*
runs 1 and 2 at a 16384 budget:

| item | completion tokens used | result at 16384 |
|---|---|---|
| `charts-11-materials` | 9390 | correct (`A`) |
| `diagrams-05-computer_science` | 10421 | correct (`D`) |
| `diagrams-07-electronics` | 9427 | correct (`A`) |
| `diagrams-03-art_theory` | 4353 | **wrong** (`D` vs `A`) |

Three of the four were *never* reasoning failures -- the model simply
needed ~10k tokens to finish analysing a real MMMU diagram. Only the
fourth is a genuine miss. Every truncation therefore converts directly
into a phantom wrong answer that understates the model.

Note the perverse effect at 4096: accuracy rose (58.3% -> 66.7%) while
the number of *genuine* wrong answers also rose (4 -> 8). The first
figure was flattered by the small answered denominator; the second is
the more trustworthy signal. This is precisely why `variance_report.py`
reports `accuracy over answered items` and the truncation count next to
the headline number, and why the checker classifies
`finish_reason=length` as a plumbing failure rather than a wrong answer.

Note also that the *wrong-answer* count is stable at 8 from 4096
onwards. Raising the budget recovered truncated items but produced no
new wrong answers -- it revealed the model's real capability rather than
inflating it.

Default raised to **16384**. Cost: a few items take minutes instead of
seconds; one item needed 10.4k tokens and 293s. The alternative is
scoring the model wrong for failing to finish inside a budget we picked
arbitrarily, which corrupts exactly the number the suite exists to
produce.

Residual truncations at 16384: **4 items** (`charts-05`,
`photos-04`, `diagrams-06`, `diagrams-08`), each burning 300-500s
before giving up. These are genuine reasoning loops, not a budget
problem -- the opposite conclusion from the earlier ones, and worth
distinguishing. Raising the budget further would cost enormous wall time
for diminishing returns; they are left as-is and counted honestly as
plumbing failures.

**Run-config guard added.** Because runs 1-3 used different budgets,
aggregating them reported a 21.7% "spread" that was entirely a
configuration difference, not model noise. Records now embed their
config, and `variance_report.py` refuses to present a spread as
variance without warning when the supplied runs disagree.

The lesson generalizes: for any vision-reasoning eval, **check the
truncation count before reading the accuracy number**.

### 2. Grading bug found by probing -- hedged multiple-choice answers

The first implementation credited any reply whose first character matched
the expected letter. That scored replies like `"Both B and C"` and
`"B or C"` as **correct**, silently inflating multiple-choice accuracy
for answers that decline to commit. Fixed via
`mm_common.resolve_choice_letter`, which detects multiple distinct
in-range option letters and refuses credit. Regression tests added.

### 3. Fixture bug found in the synthetic smoke set -- ambiguous ground truth

`smoke/chart-02` asks which series rises most from Jan to Mar. The
generator produced **a tie**: B rises 20->30 and C rises 28->38, both
+10. Ground truth claimed `B`, so the model's `C` was scored wrong. Both
answers are defensible, so the item now accepts either
(`answer_any_of`). Worth stating plainly: this was a bug in *our*
fixture, not a model failure, and it was only visible because the
variance report separates wrong answers from other outcomes.

Confirmed end-to-end after the fix: a smoke-suite rerun scored the item
`correct` and the whole synthetic suite went from 14/16 to **15/16 =
93.8%** (the one missing item, `counting-04`, truncated after 356s -- a
plumbing failure, correctly not scored as a wrong answer).

### 4. Run-to-run instability is ~2%, measured with two same-config runs

The first cross-run comparison looked alarming: **7 items flipped**
between runs 1 and 2, suggesting 11.7% nondeterminism. Inspecting them
showed every single one had an **empty answer on one side** -- i.e. a
truncation, not a changed opinion.

Fix: `variance_report.py` now excludes any item where a run failed for a
plumbing reason from the flakiness count, and reports those separately
as `unmeasurable`.

Across runs 1-3 (mixed budgets -- useful only for the plumbing
correction, not as a variance figure):

```
60 repeated items: 34 always correct, 3 always wrong, 0 flipped (0.0%)
23 items EXCLUDED (a run was truncated/errored, so the comparison is void)
per-run accuracy: 58.3%, 66.7%, 80.0%
```

Run 4 then repeated run 3 at the **identical 16384 configuration**, the
only comparison that actually measures model variance. Run 3's header
predates config embedding, but the config is provable from the data:
run 3 has correct answers that used 15,900 completion tokens, which no
smaller budget could produce. (The guard still labels it unverifiable
because it only reads headers -- conservative by design.)

```
same config (runs 3+4): 53 measurable items
  45 always correct, 7 always wrong, 1 flipped (1.9%)
  7 items EXCLUDED (one run truncated them)
  accuracy: 80.0% vs 78.3% (spread 1.7%)
```

**~2% flakiness on a proper same-config sample**, replacing the earlier
0%-on-a-mixed-budget-sample figure. The single flip was
`diagrams-09-history` (C -> A). This is still a notable contrast with
the *text* categories on this same FP8 build, where `findings.md`
documents ~10-30% nondeterminism on long reasoning tasks -- vision
answers here are short (a single option letter), so there is far less
room for a reasoning loop to send the answer somewhere different.

Two caveats, both material:

1. The per-run accuracy *spread* of 21.7% above runs 1-3 is **not model
   variance** -- those runs used different token budgets. A dedicated
   run-config comparison now detects and labels this (see item 1).
2. Flakiness is measured only over items that neither run truncated.
   The excluded seven cluster at the 16k-token boundary, so the hardest
   items are the least covered by this stability claim.

### 5. Per-domain spread is large

Definitive per-domain results at the correct budget (run 3):

| domain | accuracy |
|---|---|
| screen-captures | 11/12 = 91.7% |
| charts | 14/16 = 87.5% |
| diagrams | 12/16 = 75.0% |
| photos | 11/16 = 68.8% |

Spread: range 22.9%, stdev 9.2%. The earlier picture was distorted by
truncation in two different directions: charts *rose* from 62.5% to
87.5% once their items were allowed to finish, while diagrams recovered
only partially because several of its truncated items turned out to be
genuinely wrong rather than merely unfinished.

Notably **photos is now the weakest bucket**, not diagrams -- the
opposite of what the truncated runs suggested. That looks like a real
capability signal (medical/histology imagery, agricultural photos,
geography) rather than a budget or formatting artifact.

The same-config repeat (run 4) preserved the ordering -- charts 93.8%,
screen-captures 91.7%, diagrams 68.8%, photos 62.5% -- with photos
landing exactly on its 60% threshold. Photos is the bucket to watch:
it is the only domain whose verdict could plausibly flip on a rerun.

A single flat pass threshold would be useless here, hence the
per-domain thresholds in `thresholds.json`.

Treat this as a relative ordering, not absolute capability: several
samples per subject means individual subject scores (many 0/1 or 1/1)
carry almost no information.

### 6. Caveat on comparing to published MMMU numbers

This suite scores a **60-item stratified subset** of the MMMU
*validation* split with its own prompt and answer parser. Published MMMU
scores use the full 900-item validation split (or the withheld 10.5k test
split) with the official harness. These are different measurements and
the numbers are **not** directly comparable. `public_benchmarks.json`
ships with unsourced placeholders deliberately marked `UNVERIFIED`; the
dashboard refuses to present them as fact.

Only the `validation` split is used, because it is the only split whose
answers are public and therefore locally gradeable. MMMU's `test` answers
are withheld.
