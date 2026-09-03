# qualbench run: nvfp4 (FINAL, consolidated)

- Server: `http://127.0.0.1:8000`
- Model: `qwen3.6-35b-a3b` (Qwen3.6-35B-A3B-NVFP4, froggeric v22.4 chat
  template patched in this session -- previously stock/unpatched)
- Source runs:
  - `run-nvfp4-longctx-20260903-113841` (long-context, run first/isolated
    to avoid the FP8 OOM pattern seen in the FP8 run)
  - `run-nvfp4-20260903-120623` (remaining 5 categories, same server
    session, no crash this time)
- Total wall time: 1006.8s + 1442.7s = 2449.5s (~41 min), no restart
  needed
- **Total: 46/50 passed**

| Category | Pass | Total | Wall (s) | Notes |
|---|---|---|---|---|
| java-spring | 10 | 10 | 527.5 | ~2x faster than FP8 (1034.7s) |
| ts-angular | 7 | 8 | 278.1 | task 03 failed here; re-verified 3/3 pass on rerun -- known ~1-in-several non-determinism, not new |
| sql-migrations | 4 | 6 | 285.5 | tasks 04 and 05 failed -- see findings below, one is a **new** reproducible NVFP4 regression |
| mcp-tools | 7 | 8 | 33.7 | task 06 by-design hallucination probe, expected every run |
| security-review | 8 | 8 | 317.9 | |
| long-context | 10 | 10 | 1006.8 | run first/isolated; no OOM this time (see note below) |

## Post-hoc verification of official-run failures

Following the qualbench protocol (never treat a single failing run as a
finding without re-running 2-3x and inspecting the actual output), each
failure from the official run was re-run 3 additional times against the
same (still-alive, uncrashed) server:

- **ts-angular 03 (`shopping-cart`)**: 3/3 pass on rerun. Matches the
  already-documented FP8 finding (computed()-vs-getter inconsistency,
  low frequency). Not new, not NVFP4-specific.
- **sql-migrations 04 (`non-idempotent-migration`)**: **4/4 fail**
  (official run + 3 reruns), always with the same root cause -- the
  model's fix correctly adds `IF NOT EXISTS` guards to `CREATE INDEX`
  and `CREATE TABLE` but leaves the very first statement,
  `ALTER TABLE accounts ADD COLUMN is_active ...`, unguarded, so the
  second application of the migration fails immediately on that first
  line. **This is a new, highly reproducible NVFP4-specific pattern**,
  distinct from FP8's occasional reasoning-loop non-termination on the
  same task. See `findings.md` for full detail.
- **sql-migrations 05 (`fk-missing-unique-target`)**: 2/3 pass on
  rerun (1/3 fail with the exact `ALTER TABLE ... ADD CONSTRAINT IF NOT
  EXISTS ...` invalid-Postgres-syntax hallucination). This matches the
  already-documented FP8 finding almost exactly (FP8: ~40-60% failure
  rate on this task, same root cause). **Confirmed to reproduce on
  NVFP4 at a comparable rate** -- not FP8-specific.

Real, newly-confirmed NVFP4 regression count: **1** (SQL task 04's
consistent missing-idempotency-guard-on-first-statement pattern).

## Long-context: no OOM this time

Unlike the FP8 run (which crashed with a CUDA OOM when long-context ran
last, after ~47 minutes of prior serving), the NVFP4 run had
long-context run *first*, immediately after a fresh server start, and
completed cleanly with no crash. GPU usage during long-context peaked at
~15.7 GiB out of 16.3 GiB total -- essentially identical to FP8's
memory footprint (idle usage on both was ~14.7 GiB; the NVFP4-quantized
weights did **not** meaningfully reduce VRAM pressure here, since
`--kv-reserve-tokens 260000` dominates the allocation regardless of
weight precision). This confirms the OOM risk is a fixed hardware/
serving-config constraint independent of quantization, and the
run-long-context-first mitigation was necessary and sufficient for
NVFP4 too.

## Task-level detail

### java-spring (10/10)
- [PASS] 01-pagination-calculator (42.1s)
- [PASS] 02-discount-calculator (50.1s)
- [PASS] 03-inventory-counter (53.8s)
- [PASS] 04-date-range-overlap (44.7s)
- [PASS] 05-csv-field-parser (55.1s)
- [PASS] 06-moving-average (49.4s)
- [PASS] 07-money (80.3s)
- [PASS] 08-retrying-operation (58.0s)
- [PASS] 09-request-id-generator (54.1s)
- [PASS] 10-lru-cache (39.6s)

### ts-angular (7/8, official run; 8/8 confirmed on rerun)
- [PASS] 01-price-formatter (33.7s)
- [PASS] 02-search-service (52.2s)
- [FAIL] 03-shopping-cart (19.2s) -- 3/3 pass on rerun, known non-determinism
- [PASS] 04-password-match-validator (39.6s)
- [PASS] 05-ticker-component (30.8s)
- [PASS] 06-todo-list-component (41.8s)
- [PASS] 07-counter-display-component (27.5s)
- [PASS] 08-batch-processor (32.5s)

### sql-migrations (4/6, official run)
- [PASS] 01-add-column-not-null (6.7s)
- [PASS] 02-unique-constraint-dupes (48.2s)
- [PASS] 03-rename-column-view (51.8s)
- [FAIL] 04-non-idempotent-migration (72.3s) -- 4/4 fail on rerun, **new reproducible NVFP4 finding**
- [FAIL] 05-fk-missing-unique-target (65.7s) -- 2/3 pass on rerun, matches known FP8 finding
- [PASS] 06-bad-backfill-update (40.7s)

### mcp-tools (7/8)
- [PASS] 01-single-tool-required-args
- [PASS] 02-enum-selection
- [PASS] 03-numeric-coercion
- [PASS] 04-nested-object-args
- [PASS] 05-tool-disambiguation
- [FAIL] 06-missing-info-no-premature-call -- by design, always expected to fail
- [PASS] 07-multi-step-context-carry
- [PASS] 08-array-argument

### security-review (8/8)
- [PASS] 01-sql-injection
- [PASS] 02-hardcoded-secret
- [PASS] 03-path-traversal
- [PASS] 04-insecure-deserialization
- [PASS] 05-weak-crypto-hash
- [PASS] 06-ssrf
- [PASS] 07-broken-access-control
- [PASS] 08-command-injection

### long-context (10/10)
- [PASS] 01-8k-pos10 (44.2s)
- [PASS] 02-8k-pos50 (36.0s)
- [PASS] 03-8k-pos90 (38.4s)
- [PASS] 04-64k-pos10 (90.3s)
- [PASS] 05-64k-pos50 (79.8s)
- [PASS] 06-64k-pos90 (76.9s)
- [PASS] 07-150k-pos10 (178.4s)
- [PASS] 08-150k-pos50 (186.1s)
- [PASS] 09-distractor-64k (89.8s)
- [PASS] 10-distractor-150k (186.3s)
</content>
