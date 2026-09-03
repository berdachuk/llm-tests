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

## Real memory footprint: measured, not estimated

All figures below are read directly from `ft serve` startup logs and
`nvidia-smi`/`free -h` on `berdachuk-pc`, not calculated or assumed.

### VRAM: KV cache scaling and steady-state/peak usage

KV cache size scales linearly with `--kv-reserve-tokens`, confirmed
across every tested reservation point on this card:

| `--kv-reserve-tokens` | KV cache size (measured) | GiB per 1M tokens |
|---:|---:|---:|
| 8,192 (default floor) | 0.16 GiB | ~19.5 |
| 120,051 | 2.29 GiB | ~19.1 |
| 260,029 (selected/validated) | 4.96 GiB | ~19.1 |
| 300,000 | 5.72 GiB | ~19.1 |

At ~1.907x10^-5 GiB/token, reserving the model's full native
262,144-token context would cost only ~5.0 GiB of KV cache by itself.
KV cache is *not* the binding constraint on this card -- core weights
and the GPU-resident MoE expert cache already consume nearly the whole
16.3 GiB before a single KV token is reserved:

| VRAM state (FP8 and NVFP4, both at the 260K config) | Size |
|---|---:|
| Free VRAM before model load (desktop already using the rest) | 14.24-14.51 GiB of 16.3 GiB total |
| Free VRAM after full init, before CUDA graph capture | 1.16-1.18 GiB |
| Free VRAM after CUDA graph capture | 1.07-1.15 GiB |
| **Steady-state VRAM used (idle, no requests in flight)** | **~14.7-14.75 GiB of 16.3 GiB** |
| **Peak VRAM during an actual 150K-token long-context request** | **~15.6-15.7 GiB of 16.3 GiB** |

At peak, only **~0.6-0.7 GiB of margin** remains on this 16.3 GiB card --
which is exactly the margin that ran out during the FP8 run's OOM
incident above, after ~47 minutes of continuous prior serving. This
VRAM profile is identical between FP8 and NVFP4: `--kv-reserve-tokens`
dominates the allocation, not weight precision.

### System RAM: the MoE expert pool is the real quantization-dependent cost

NVFP4's smaller weight footprint does not reduce VRAM pressure (above),
but it does substantially reduce the **host RAM** cost of the MoE
expert pool that lives outside VRAM. Measured directly from server
startup logs:

| Quantization | Expert pool size (RAM) | Idle desktop RAM already in use | Total system RAM in this box |
|---|---:|---:|---:|
| FP8 | 31.4 GB | ~14 GiB of 62 GiB | 64 GiB (62 GiB usable) + 64 GiB swap |
| NVFP4 | 21.8 GB | ~14 GiB of 62 GiB | 64 GiB (62 GiB usable) + 64 GiB swap |

The OS and background processes alone use ~14 GiB before any model
loads. Add the FP8 expert pool and **~45 GB is committed before the
server handles a single request** (vs. ~35 GB for NVFP4) -- this is why
64 GB, not 32 GB, was the correct RAM target for this hardware.

### Minimum / recommended / maximum-tested memory requirements

| | VRAM | System RAM |
|---|---|---|
| **Minimum to load the server at all** (default 8,330-token effective context, no tuning) | ~14.3 GiB free -- nearly the whole 16.3 GiB card; weights + MoE cache dominate even at minimal context, not KV cache | 31.4 GB (FP8) / 21.8 GB (NVFP4) for the expert pool, plus OS overhead -- 64 GB was the tested floor |
| **Recommended: validated for 92K+ single requests** (`--kv-reserve-tokens 260000`) | ~14.7-14.75 GiB steady state, up to ~15.6-15.7 GiB under an actual long prompt, out of 16.3 GiB total | Same 64 GB box; raising KV reservation has no RAM cost -- that cost is VRAM-only |
| **Maximum verified in this test** | 92,436-token single request confirmed end-to-end (throughput benchmark); 150K-token prompts confirmed to pass in isolation (qualbench long-context category); full 262,144-token native context was **not** independently verified | Not applicable -- RAM cost is fixed by quantization choice, not by KV reservation |

**Takeaway:** on a 16 GB consumer card, VRAM is the scarce resource at
every context size, not just at the maximum -- the "minimum" and
"recommended" VRAM requirements are much closer together than the raw
KV-cache math alone would suggest, because weights and the MoE expert
cache already claim nearly the whole card. System RAM, by contrast, is
fixed per quantization (31.4 GB vs. 21.8 GB) regardless of context-window
target, so it's the quantization choice -- not the context goal -- that
sets the RAM floor.

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
- Supporting infra: Docker `qualbench-pg` (Postgres 18-alpine) for the
  SQL migrations category.

### Hardware (`berdachuk-pc`)

| Component | Specification |
|---|---|
| CPU | Intel Core i5-13400, 10 cores / 16 threads, up to 4.6 GHz |
| RAM | 64 GiB total (62 GiB usable), 64 GiB swap |
| GPU | NVIDIA GeForce RTX 5060 Ti, 16.3 GiB (16,311 MiB) VRAM, compute capability 12.0 (Blackwell) |
| OS | Ubuntu 24.04.4 LTS, kernel 6.8.0-138-generic |
| NVIDIA stack | Driver 595.84, CUDA 13.3 |
| Model checkpoints on disk | FP8: ~35 GB, NVFP4: ~22 GB |

This is a live desktop, not a headless server -- the compositor and
desktop session keep ~14 GiB of RAM and part of the GPU's VRAM
occupied even at idle, which is why the memory figures above are
reported as measured values rather than theoretical card/RAM totals.
</content>
