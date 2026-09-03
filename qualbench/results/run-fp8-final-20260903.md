# qualbench run: fp8 (FINAL, consolidated)

- Server: `http://127.0.0.1:8000`
- Model: `qwen3.6-35b-a3b` (Qwen3.6-35B-A3B-FP8, froggeric v22.4 chat template)
- Source runs:
  - `run-fp8-20260903-101540` (categories 1-5, plus long-context which OOM'd)
  - `run-fp8-longctx-retry-20260903-104858` (long-context re-run on a freshly
    restarted server, see "Infrastructure incident" below)
- Total wall time: 3401.5s + 1212.5s = 4614.0s (~77 min), including one
  server restart
- **Total: 48/50 passed**

| Category | Pass | Total | Wall (s) | Notes |
|---|---|---|---|---|
| java-spring | 10 | 10 | 1034.7 | |
| ts-angular | 8 | 8 | 662.6 | |
| sql-migrations | 5 | 6 | 503.1 | task 04 failed: known non-deterministic reasoning-loop finding (see findings.md) |
| mcp-tools | 7 | 8 | 65.6 | task 06 failed: by-design hallucination probe, expected every run |
| security-review | 8 | 8 | 534.8 | |
| long-context | 10 | 10 | 1212.5 | **retry run**, after infra incident on first attempt |

Real avoidable-failure count: **0/50**. Both non-passes are expected/known
(one by design, one a previously-documented low-frequency model
inconsistency) — not new findings.

## Infrastructure incident: FP8 server OOM during long-context (first attempt)

On the first attempt, the long-context category failed 0/10: the first
task (`01-8k-pos10`) hit the harness's 600s read-timeout, and every
subsequent task got `Connection refused` — the server process had crashed.

**Root cause (confirmed from `~/qwen36_35b_serve.log`):** a genuine
`torch.OutOfMemoryError: CUDA out of memory` inside the scheduler process,
raised in the linear-attention "gated delta rule" kernel
(`chunk_gated_delta_rule_fwd_h`) while allocating a 128 MiB tensor. At the
time of the crash the process already held 14.46 GiB of the RTX 5060 Ti's
16.3 GiB (15.46 GiB reported capacity), leaving no room for the long
prompt's activation buffers. The backend scheduler subprocess died, the
API server detected the dead worker and shut itself down cleanly (no
zombie process, no leftover GPU allocation once torch's process exited).

This occurred after java-spring, ts-angular, sql-migrations, mcp-tools,
and security-review had already run back-to-back in the same server
process (~47 minutes of continuous serving) before long-context started.

**Resolution and verification:** killed the crashed process, confirmed
GPU was clean (only ~970 MiB from desktop/X11, no leftover CUDA
allocation), restarted the FP8 server fresh, verified healthy via a real
`/v1/chat/completions` round trip, then re-ran **only** the long-context
category. It passed 10/10, including both 150k-token tasks, with GPU
memory holding steady around 15.6-15.7 GiB throughout (i.e. right at the
edge of the 16.3 GiB card, but stable when long-context is run against a
freshly-loaded server rather than one that's already served ~2000s of
prior traffic).

**Disposition:** infrastructure/hardware constraint of the local RTX 5060
Ti 16GB card under this offload-MoE serving configuration, not a model
quality issue and not a fixture bug. Long-context tasks (up to 150k
tokens) need close-to-maximal free VRAM; running the full 50-task suite
in one continuous server session leaves too little headroom by the time
long-context is reached. **Actionable follow-up for the NVFP4 run:**
either (a) run long-context first/immediately after a fresh server
start, or (b) restart the server between categories, or (c) run
long-context as its own isolated invocation as was done here. Given
NVFP4 quantization uses less VRAM than FP8 for the model weights, this
specific OOM may not reproduce on NVFP4 — worth explicitly checking as
part of the comparative report.

## Task-level detail

### java-spring (10/10)
- [PASS] 01-pagination-calculator (54.5s)
- [PASS] 02-discount-calculator (94.2s)
- [PASS] 03-inventory-counter (102.0s)
- [PASS] 04-date-range-overlap (110.0s)
- [PASS] 05-csv-field-parser (92.8s)
- [PASS] 06-moving-average (84.4s)
- [PASS] 07-money (151.3s)
- [PASS] 08-retrying-operation (122.7s)
- [PASS] 09-request-id-generator (143.0s)
- [PASS] 10-lru-cache (79.7s)

### ts-angular (8/8)
- [PASS] 01-price-formatter (66.0s)
- [PASS] 02-search-service (72.5s)
- [PASS] 03-shopping-cart (137.4s)
- [PASS] 04-password-match-validator (99.7s)
- [PASS] 05-ticker-component (52.5s)
- [PASS] 06-todo-list-component (96.1s)
- [PASS] 07-counter-display-component (61.1s)
- [PASS] 08-batch-processor (76.3s)

### sql-migrations (5/6)
- [PASS] 01-add-column-not-null (50.7s)
- [PASS] 02-unique-constraint-dupes (49.2s)
- [PASS] 03-rename-column-view (65.6s)
- [FAIL] 04-non-idempotent-migration (147.3s) -- known non-deterministic finding, see findings.md
- [PASS] 05-fk-missing-unique-target (64.9s)
- [PASS] 06-bad-backfill-update (125.4s)

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

### long-context (10/10, retry run)
- [PASS] 01-8k-pos10 (87.6s)
- [PASS] 02-8k-pos50 (73.4s)
- [PASS] 03-8k-pos90 (90.6s)
- [PASS] 04-64k-pos10 (75.4s)
- [PASS] 05-64k-pos50 (117.3s)
- [PASS] 06-64k-pos90 (104.9s)
- [PASS] 07-150k-pos10 (164.0s)
- [PASS] 08-150k-pos50 (178.6s)
- [PASS] 09-distractor-64k (115.1s)
- [PASS] 10-distractor-150k (204.9s)
</content>
</invoke>
