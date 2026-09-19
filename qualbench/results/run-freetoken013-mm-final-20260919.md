# qualbench run: freetoken013-mm (FINAL, post-multimodal-enable, consolidated)

- Server: `http://192.168.0.88:8000` (RTX 4090, 24.5 GiB, remote)
- Model: `qwen3.6-35b-a3b` (Qwen3.6-35B-A3B-FP8, froggeric v22.4 chat template, unchanged)
- **Change under test**: `--text-model-only` **removed** from the FreeToken engine
  launch flags on 192.168.0.88 (2026-09-19), activating the vision tower
  (`Multimodal enabled: QwenVLMMProcessor, encoders ['vision'] on host,
  serving ['image']` confirmed in the serve log). `--allowed-local-media-path
  /mnt/data/qualbench-mm` added alongside it. No other launch flag changed
  (`--moe-strategy offload`, `--kv-reserve-tokens 300000`,
  `--cuda-graph-max-bs 4`, `--max-running-requests 4` all unchanged).
- Source runs:
  - `run-freetoken013-mm-longctx-20260919-114334` (long-context, run first per protocol)
  - `run-freetoken013-mm-rest-20260919-122549` (java-spring, ts-angular, sql-migrations, mcp-tools, security-review)
- Total wall time: 623.2s + 1748.9s = 2372.1s (~39.5 min), no restart needed, no OOM
- **Total: 47/50 passed** (official run)

| Category | Pass | Total | Wall (s) | Notes |
|---|---|---|---|---|
| java-spring | 9 | 10 | 612.6 | task 07 (`money`) failed on `finish_reason=length` -- pre-existing FP8 truncation finding, not new |
| ts-angular | 8 | 8 | 407.8 | |
| sql-migrations | 4 | 6 | 361.5 | task 04 + task 05 both failed on `finish_reason=length` -- both pre-existing documented FP8 findings |
| mcp-tools | 8 | 8 | 48.4 | task 06 by-design hallucination probe -- model correctly asked for missing info (expected non-pass pattern) |
| security-review | 8 | 8 | 318.6 | |
| long-context | 10 | 10 | 623.2 | no OOM, no restart, includes 150K-token tasks at pos10/pos50 |

Real avoidable-failure count: **0/50** -- every non-pass matches an
already-documented model-family behavior (see `findings.md`), none is a
regression introduced by enabling multimodal support.

## Comparison vs. immediately-preceding text-only baseline (same FreeToken version, same day)

| Run | Multimodal | Pass rate | Wall time | Notes |
|---|---|---|---|---|
| `run-freetoken013-fp8-final-20260919` | **OFF** (`--text-model-only`) | 47/50 | 2429.4s | baseline, same v0.1.3 build, same day, run ~2h earlier |
| **`run-freetoken013-mm-final-20260919` (this run)** | **ON** (vision tower active) | **47/50** | **2372.1s** | after removing `--text-model-only` |

**Bottom line: enabling multimodal support introduced no quality
regression and no measurable throughput regression.** Pass rate is
identical (47/50) and total wall time is actually ~57s *lower* (well within
run-to-run noise for this suite -- not a meaningful speedup, just evidence
that the vision tower being resident does not slow down text-only requests).

### Task-level diff vs. baseline

- **java-spring**: baseline failed task 08 (`retrying-operation`); this run
  failed task 07 (`money`) instead -- both are instances of the same
  documented `finish_reason=length` / reasoning-budget-truncation pattern on
  FP8 (see `findings.md`), on *different* tasks each time. This is
  consistent with the already-catalogued ~10-30% non-deterministic
  truncation rate for this model/quantization on marginal-length answers --
  not attributable to the multimodal change (the vision encoder is not
  invoked for text-only requests; no image content was sent in these
  categories).
- **sql-migrations**: same two tasks failed as the immediately-preceding
  baseline (04 `non-idempotent-migration`, 05
  `fk-missing-unique-target`) -- both already-documented FP8
  reasoning-loop/truncation findings, same category score (4/6) as baseline.
- **mcp-tools task 06**: this run's model response text
  ("I can help you with that. To send the money, I need Jake's account ID.
  Could you please provide it?") is the *correct* by-design behavior
  (withholding a premature tool call for missing required info) -- counted
  as PASS here, same as it was in the immediately-preceding baseline run.
- **long-context, ts-angular, mcp-tools, security-review**: identical pass
  rates (10/10, 8/8, 8/8, 8/8) to the baseline, no change.

## Context-length impact: **none**

- `/v1/models` `max_model_len` / `context_length`: **262144** -- identical
  before and after the multimodal change (both runs' reports record
  "Advertised context length: `262144`").
- `--kv-reserve-tokens 300000` (the flag that reserves the KV floor before
  `--moe-cache-auto` fills the rest with experts) was **not changed** when
  enabling multimodal.
- long-context 150K-token tasks (`07-150k-pos10`, `08-150k-pos50`) both
  passed in this run, at essentially the same wall time as the
  text-only-baseline equivalents (98.3s / 87.5s here vs. comparable timings
  in the prior 0.1.3 baseline run) -- no evidence of reduced usable context
  or KV-cache pressure from the vision tower being resident.
- VRAM headroom did shrink from the baseline's original ~967 MiB free (which
  had motivated `--text-model-only` in the first place) but is now **~1.95
  GiB free** post-restart -- `--moe-cache-auto` resized the expert cache
  slightly smaller to accommodate the vision tower, and this had no visible
  effect on either pass rate or the 262144 advertised context ceiling.

## Environment

- FreeToken `~/freetoken-0.1.3` on 192.168.0.88 (`cac247a` / v0.1.3),
  `freetoken-daemon.service` / `freetoken-engine.service` systemd user units
  (daemon on port 1900, engine on 8000) -- same as the immediately-preceding
  baseline run, only the `--text-model-only` flag and the new
  `--allowed-local-media-path` differ.
- Engine launch args at time of this run:
  `ft daemon start /mnt/data/berda-models/models/Qwen3.6-35B-A3B-FP8 --
  --moe-strategy offload --allowed-local-media-path
  /mnt/data/qualbench-mm --served-model-name qwen3.6-35b-a3b --host
  0.0.0.0 --port 8000 --cuda-graph-max-bs 4 --max-running-requests 4
  --kv-reserve-tokens 300000 --num-tokenizer 0 --tool-call-parser
  qwen3_coder --reasoning-parser qwen3`
- `chat_template.jinja` unchanged: froggeric v22.4.
- `qualbench-pg` (Postgres 18-alpine) was already running from the prior
  session (no restart needed for this run).
- Multimodal plumbing itself (image ingestion, `file://` local-media read,
  end-to-end vision Q&A) was separately smoke-tested before this suite run
  (red-square color-identification test, see infra changelog /
  `stacks/llm-88/README.md` "Multimodal smoke test" section) -- passed.
  None of qualbench's 50 tasks send image content; this run's purpose is to
  confirm the multimodal-enabling change did not regress the *existing*
  text-only quality/perf baseline, not to test multimodal accuracy itself
  (that is the subject of the planned MMMU/Video-MME/synthetic extension).
