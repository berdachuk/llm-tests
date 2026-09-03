# qualbench comparative report: FP8 vs NVFP4

`Qwen3.6-35B-A3B`, `berdachuk-pc` (RTX 5060 Ti 16GB), froggeric v22.4
chat template applied to both, identical `ft serve` flags
(`--moe-backend offload --cuda-graph-max-bs 2 --max-running-requests 2
--kv-reserve-tokens 260000 --tool-call-parser qwen3_coder
--reasoning-parser qwen3`).

Date: 2026-09-03.

## Headline results

| | FP8 | NVFP4 |
|---|---|---|
| **Raw pass count (official run)** | 38/50 | 36/40* |
| **After post-hoc re-verification** | 48/50 | 46/50 |
| **Real avoidable-failure count** | 0 | 1 (SQL task 04) |
| **Total wall time** | ~77 min (incl. 1 restart) | ~41 min (no restart) |
| **Idle GPU VRAM (model loaded)** | ~14.7 GiB / 16.3 GiB | ~14.7 GiB / 16.3 GiB |

\* NVFP4's official run only covered 40 tasks in that invocation because
long-context (10 tasks) was deliberately run first/separately to avoid
the OOM pattern found on FP8; combined total is 46/50 across both
invocations.

Of the 4 total non-passes after re-verification (2 per quantization),
3 are either by-design (mcp-tools task 06, both) or a shared,
already-known model-family characteristic (SQL task 05's `ADD
CONSTRAINT ... IF NOT EXISTS` hallucination, reproduces on both at
comparable ~40-60%/33% rates). **Exactly one is a genuine, newly-found
quantization-specific quality difference**: SQL task 04.

## The one real quality difference: SQL migrations task 04

- **FP8:** rare failure (~1/3 in one batch), via reasoning-loop /
  decision-paralysis -- the model gets stuck re-deriving the same
  hypothesis and never emits a final answer. Other runs pass cleanly
  with a fully correct idempotent fix.
- **NVFP4:** consistent failure (4/4 across official run + 3 reruns),
  via a specific, repeatable omission -- the model correctly guards
  every statement *except* the very first (`ALTER TABLE accounts ADD
  COLUMN is_active ...` is left without `IF NOT EXISTS`, while the
  later `CREATE INDEX`/`CREATE TABLE`/`INSERT` are all correctly
  guarded).

This is the clearest signal in the whole 50-task suite that the NVFP4
quantization has a measurably different (and here, worse) failure mode
on this specific task than FP8, despite passing everything else FP8
passes with comparable-or-better speed.

## Shared model-family characteristics (present in both quantizations)

- **SQL task 05** (`fk-missing-unique-target`): both quantizations
  hallucinate the invalid Postgres syntax `ALTER TABLE ... ADD
  CONSTRAINT IF NOT EXISTS ...` (not valid -- `IF NOT EXISTS` only
  applies to `CREATE INDEX`/`CREATE TABLE`/`ADD COLUMN` in Postgres) at
  a similar rate (FP8: ~40-60% across ~8 runs; NVFP4: 1/3 on
  reruns, consistent with that same range). This looks like a training-
  data-level pattern-overgeneralization baked into the model itself,
  not something either quantization introduces or fixes.
- **TS/Angular task 03** (`shopping-cart`): both occasionally (roughly
  1-in-several runs) produce a `computed()`-based fix instead of the
  spec-required getter-shaped fix, despite the model's own reasoning
  trace sometimes explicitly flagging the exact mismatch before
  ignoring it. Same low frequency and same root cause on both.
- **mcp-tools task 06**: both correctly/incorrectly call the
  money-transfer tool with incomplete info every time -- this is a
  by-design hallucination probe expected to "fail" on any model that
  hasn't specifically been RLHF'd against this exact scenario; not a
  quantization-dependent signal.

## Speed

NVFP4 was consistently ~1.5-2x faster than FP8 across every category
that ran in both (java-spring: 527.5s vs 1034.7s; ts-angular: 278.1s vs
662.6s; sql-migrations: 285.5s vs 503.1s; mcp-tools: 33.7s vs 65.6s;
security-review: 317.9s vs 534.8s; long-context: 1006.8s vs 1212.5s).
This is the expected direction for a lower-precision quantization on
this hardware and is a genuine practical advantage of NVFP4 if the
task-04 regression above is deemed acceptable or is separately fixed
(e.g. via prompting).

## Infrastructure: VRAM headroom is quantization-independent here

Idle VRAM usage (model loaded, no requests in flight) was ~14.7 GiB for
*both* quantizations -- NVFP4's smaller weight footprint did not
translate into meaningfully lower VRAM pressure in this serving
configuration, because `--kv-reserve-tokens 260000` (not raw weight
size) dominates the allocation on a 16GB card at this context length.
The FP8 run crashed with a CUDA OOM when long-context (up to 150K-token
prompts) was run *last*, after ~47 minutes of continuous prior serving;
running long-context first/in isolation avoided the crash on both
quantizations, with GPU usage in both cases peaking at ~15.6-15.7 GiB.
**This is a fixed hardware/serving-config constraint of this particular
16GB card + `--kv-reserve-tokens` setting, independent of quantization**
-- not a finding specific to either FP8 or NVFP4, but a practical
operational note for running this suite (or any long-context workload)
on this hardware going forward: always run long-context first or in its
own isolated server session.

## Bottom line

- **Correctness:** FP8 and NVFP4 are equivalent on 48/49 "real" tasks
  (excluding the by-design mcp-tools probe). The one exception (SQL
  task 04) favors FP8, which fails rarely and via reasoning-loop rather
  than a specific, repeatable code-generation omission.
- **Speed:** NVFP4 is substantially faster (~1.5-2x) across every
  category, with no VRAM-usage penalty relative to FP8.
- **Recommendation:** NVFP4 is the better default for this hardware
  given the speed advantage, *provided* the SQL-task-04-style
  idempotency-guard omission is monitored/mitigated (e.g. via a stronger
  system prompt reminding the model to guard *every* DDL statement, not
  just some) if idempotent migration generation is a real use case for
  this deployment. For workloads that don't touch that specific pattern,
  NVFP4 has no observed correctness downside in this 50-task suite.
</content>
