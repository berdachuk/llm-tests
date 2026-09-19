# qualbench run: freetoken013-fp8 (FINAL, consolidated)

- Server: `http://192.168.0.88:8000` (RTX 4090, 24.5 GiB, remote)
- Model: `qwen3.6-35b-a3b` (Qwen3.6-35B-A3B-FP8, froggeric v22.4 chat template, unchanged)
- **FreeToken upgraded**: `af71ba4` (v0.1.2-28-gaf71ba4, 2026-09-03) -> `cac247a`
  (**v0.1.3 release**, 2026-09-15) on 192.168.0.88. Same model checkpoint,
  same chat template, same launch flags (`--moe-strategy offload`
  replaces the old `--moe-backend offload` name internally but is
  functionally the same knob; `--text-model-only` added), same
  `--kv-reserve-tokens 300000` / `--cuda-graph-max-bs 4` /
  `--max-running-requests 4` config, now served via the systemd
  daemon/engine units instead of a manual `nohup`.
- Source runs:
  - `run-freetoken013-longctx-20260919-102544` (long-context, run first per protocol)
  - `run-freetoken013-rest-20260919-105950` (java-spring, ts-angular, sql-migrations, mcp-tools, security-review)
- Total wall time: 633.1s + 1796.3s = 2429.4s (~40.5 min), no restart needed, no OOM
- **Total: 47/50 passed** (official run)

| Category | Pass | Total | Wall (s) | Notes |
|---|---|---|---|---|
| java-spring | 9 | 10 | 608.8 | task 08 failed once; 2/3 pass on targeted rerun -- low-frequency non-determinism, not new |
| ts-angular | 8 | 8 | 421.5 | |
| sql-migrations | 4 | 6 | 374.9 | task 02 (ambiguous-column flakiness) + task 04 (reasoning-loop truncation) -- both pre-existing documented FP8 findings |
| mcp-tools | 8 | 8 | 46.6 | task 06 by-design hallucination probe passed this run (model correctly refused) |
| security-review | 8 | 8 | 344.5 | |
| long-context | 10 | 10 | 633.1 | no OOM, no restart |

Real avoidable-failure count: **0/50** -- every non-pass matches an
already-documented model-family behavior (see below), none is a
regression introduced by the FreeToken 0.1.2 -> 0.1.3 upgrade.

## Comparison vs. previous Qwen3.6-35B-A3B-FP8 runs on this same 4090

| Run | FreeToken ver | Pass rate | Notes |
|---|---|---|---|
| `run-4090-fp8-final-20260903` | v0.1.2 (af71ba4) | 46/50 | official baseline confirmation run |
| `run-4090-fp8-full-20260905-195732` | v0.1.2 (af71ba4) | 42/50 | sql-migrations 0/6 -- Postgres (`qualbench-pg`) was down/unreachable that run, all 6 failed on `verify.sh` connection, not a model issue |
| `run-4090-fp8-sql-retry-20260905-200656` | v0.1.2 (af71ba4) | 4/6 (sql only) | sql retry after restarting `qualbench-pg` -- same category score (4/6) as today's run |
| **`freetoken013-fp8` (this run)** | **v0.1.3 (cac247a)** | **47/50** | **today, after the 0.88 FreeToken upgrade** |

**Bottom line: the FreeToken 0.1.2 -> 0.1.3 upgrade introduced no
regressions and no new findings.** Model quality on this 50-task suite is
statistically indistinguishable from the pre-upgrade baseline -- every
non-pass in today's run reproduces a failure mode already catalogued in
`findings.md` for this exact model/quantization:

- **java-spring 08 (`retrying-operation`)**: new task index to fail (the
  earlier baseline saw task 09 flake instead), but the *same class* of
  low-frequency non-determinism -- 2/3 pass on immediate rerun against
  the same live server. Not a version-specific regression; this fixture
  has now shown transient failures on two different tasks (09 previously,
  08 today) at a similar (~10-30%) rate, consistent with documented
  offload-batching non-determinism, not the FreeToken version.
- **sql-migrations 02 (`unique-constraint-dupes`)**: matches the
  documented "ambiguous column reference in self-join" finding
  (~60-100% pass rate across observed runs, i.e. genuinely flaky at the
  model level, not host-specific).
- **sql-migrations 04 (`non-idempotent-migration`)**: matches the
  documented FP8 reasoning-loop / `finish_reason=length` truncation
  finding (fails intermittently on FP8, unlike the NVFP4-specific
  omission bug).
- **mcp-tools 06**: by-design hallucination probe; this run happened to
  pass (model correctly withheld the premature tool call), which is a
  positive outcome, not a finding.

No infrastructure changes were needed beyond restarting the
`qualbench-pg` Postgres container (it does not survive reboots, `--rm`
flag) before the sql-migrations category.

## Environment

- FreeToken repo now lives at `~/freetoken-0.1.3` on 192.168.0.88 (git
  worktree of `~/freetoken`, commit `cac247a` / release `v0.1.3`),
  managed by the `freetoken-daemon.service` / `freetoken-engine.service`
  systemd user units (daemon supervisor on port 1900, engine on 8000).
- Engine launch args (from `systemctl --user cat freetoken-engine.service`):
  `ft daemon start /mnt/data/berda-models/models/Qwen3.6-35B-A3B-FP8 --
  --moe-strategy offload --text-model-only --served-model-name
  qwen3.6-35b-a3b --host 0.0.0.0 --port 8000 --cuda-graph-max-bs 4
  --max-running-requests 4 --kv-reserve-tokens 300000 --num-tokenizer 0
  --tool-call-parser qwen3_coder --reasoning-parser qwen3`
- `chat_template.jinja` unchanged: froggeric v22.4, md5
  `e904fed1e909c364b0a4473f713d6932`, `.orig` backup intact.
- `qualbench-pg` (Postgres 18-alpine) restarted fresh for this run (not
  running when the session started; the container does not survive
  reboots).
</content>
