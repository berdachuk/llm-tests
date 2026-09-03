# Test results: qualbench FP8 vs NVFP4 (2026-09-03)

Summary of the `qualbench` 50-task quality/regression eval, comparing
**FP8 vs NVFP4** quantizations of `Qwen3.6-35B-A3B` on the local desktop
(`berdachuk-pc`, RTX 5060 Ti 16GB), across 6 categories: Java/Spring
bugfix, TS/Angular bugfix, SQL migrations, MCP/tool-call, security review,
and long-context retrieval. See [`qualbench/README.md`](qualbench/README.md)
for the suite's full design and layout.

Full detail lives in `qualbench/results/`:
- [`comparative-report-20260903.md`](qualbench/results/comparative-report-20260903.md) -- the full FP8-vs-NVFP4 writeup
- [`run-fp8-final-20260903.md`](qualbench/results/run-fp8-final-20260903.md) / [`run-nvfp4-final-20260903.md`](qualbench/results/run-nvfp4-final-20260903.md) -- per-quantization consolidated run reports
- [`findings.md`](qualbench/results/findings.md) -- every individual finding, reproduced and root-caused

## Headline results

| | FP8 | NVFP4 |
|---|---|---|
| **Pass rate** | 48/50 | 46/50 |
| **Real avoidable-failure count** | 0 | 1 (SQL task 04) |
| **Total wall time** | ~77 min (incl. 1 server restart) | ~41 min (no restart) |
| **Idle GPU VRAM (model loaded)** | ~14.7 GiB / 16.3 GiB | ~14.7 GiB / 16.3 GiB |

## Per-category pass rate

| Category | FP8 | NVFP4 | Notes |
|---|---|---|---|
| Java/Spring bugfix | 10/10 | 10/10 | Stable on both; NVFP4 ~2x faster. |
| TS/Angular bugfix | 8/8 | 8/8 (7/8 official run, 8/8 confirmed on rerun) | Task 03 `shopping-cart`: known low-frequency `computed()`-vs-getter non-determinism on both. |
| SQL migrations | 5/6 | 4/6 | See "Key finding" below -- one real quantization-specific difference (task 04). |
| MCP/tool-call | 7/8 | 7/8 | Task 06 is a by-design hallucination probe, expected to fail every run on both. |
| Security review | 8/8 | 8/8 | Stable on both. |
| Long-context retrieval | 10/10 | 10/10 | Stable on both **when run first/in isolation** -- see OOM note below. |

## Key finding: SQL task 04 is a real, quantization-specific regression

`sql-migrations/04-non-idempotent-migration` asks the model to make a
Postgres migration script idempotent (safe to re-run without error).

- **FP8** fails here rarely (~1/3 in one repeated batch) via a
  reasoning-loop / decision-paralysis failure mode -- the model gets
  stuck re-deriving the same hypothesis and never emits a final answer.
  Other FP8 runs pass cleanly with a fully correct fix.
- **NVFP4** fails here consistently (4/4 across the official run + 3
  dedicated reruns), via a specific, repeatable omission: it correctly
  guards every later statement (`CREATE INDEX`, `CREATE TABLE`, the
  `INSERT`) but leaves the very first statement,
  `ALTER TABLE accounts ADD COLUMN is_active ...`, without an
  `IF NOT EXISTS` guard, so the second run fails immediately on that
  first line.

This is the clearest, most reproducible quality difference found
between the two quantizations across the whole 50-task suite.

## Shared model-family characteristics (present on both quantizations)

- **SQL task 05** (`fk-missing-unique-target`): both quantizations
  hallucinate the invalid Postgres syntax
  `ALTER TABLE ... ADD CONSTRAINT IF NOT EXISTS ...` (not valid --
  `IF NOT EXISTS` only applies to `CREATE INDEX`/`CREATE TABLE`/
  `ADD COLUMN` in Postgres) at a comparable rate (FP8 ~40-60% across ~8
  runs; NVFP4 ~1/3 on reruns). Looks like a training-data-level
  pattern-overgeneralization baked into the model itself, not introduced
  or fixed by either quantization.
- **TS/Angular task 03** (`shopping-cart`): both occasionally (roughly
  1-in-several runs) produce a `computed()`-based fix instead of the
  spec-required getter-shaped fix. Same low frequency, same root cause,
  on both.
- **mcp-tools task 06**: an intentional hallucination probe (incomplete
  info, model still calls a money-transfer tool) -- expected to "fail"
  on both quantizations by design, not a real finding.

## Speed

NVFP4 was consistently ~1.5-2x faster than FP8 across every category:

| Category | FP8 (s) | NVFP4 (s) |
|---|---|---|
| java-spring | 1034.7 | 527.5 |
| ts-angular | 662.6 | 278.1 |
| sql-migrations | 503.1 | 285.5 |
| mcp-tools | 65.6 | 33.7 |
| security-review | 534.8 | 317.9 |
| long-context | 1212.5 | 1006.8 |

## Infrastructure note: long-context OOM risk (quantization-independent)

Running all 6 categories back-to-back in one continuous server session
left too little free VRAM by the time long-context's largest prompts
(up to 150K tokens) were reached, and the **FP8** server crashed with a
genuine CUDA `OutOfMemoryError` on the first official attempt. Idle GPU
VRAM (model loaded, no requests) was ~14.7 GiB on *both* quantizations --
NVFP4's smaller weights did not reduce VRAM pressure here, because
`--kv-reserve-tokens 260000` (not weight size) dominates the allocation
on this 16GB card. Mitigation (running long-context first, immediately
after a fresh server restart, rather than last) worked cleanly on both
quantizations, with GPU usage peaking at ~15.6-15.7 GiB in both cases.
This is a fixed hardware/serving-config constraint, not a quantization
difference -- always run long-context first or in its own isolated
server session on this hardware.

## Bottom line / recommendation

- **Correctness:** FP8 and NVFP4 are equivalent on every task except
  SQL task 04, which favors FP8 (fails rarely, via an unrelated
  mechanism) over NVFP4 (fails consistently, via a specific repeatable
  omission).
- **Speed:** NVFP4 is substantially faster (~1.5-2x) with no VRAM
  penalty.
- **Recommendation:** NVFP4 is the better default for this hardware
  given the speed advantage, provided the SQL-task-04-style
  idempotency-guard omission is monitored or mitigated (e.g. a stronger
  system-prompt reminder to guard *every* DDL statement) if idempotent
  migration generation is a real use case for this deployment.

## Environment

- Model: `Qwen3.6-35B-A3B`, both quantizations served with froggeric
  v22.4 chat template patched over the stock template.
- Server: `ft serve --moe-backend offload --cuda-graph-max-bs 2
  --max-running-requests 2 --kv-reserve-tokens 260000
  --tool-call-parser qwen3_coder --reasoning-parser qwen3`, on
  `http://127.0.0.1:8000`.
- Hardware: `berdachuk-pc`, RTX 5060 Ti 16GB.
- Supporting infra: Docker `qualbench-pg` (Postgres 18-alpine) for the
  SQL migrations category.
</content>
