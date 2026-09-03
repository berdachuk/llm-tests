# qualbench

A 50-task quality/regression eval comparing **FP8 vs NVFP4** quantizations
of `Qwen3.6-35B-A3B` on the local desktop (`berdachuk-pc`, RTX 5060 Ti
16GB), across 6 categories. Each category is model-in-the-loop: a fixed
prompt is sent to a live server, the response is extracted, and a
deterministic check (compiler/test-runner/regex/schema) decides pass/fail
-- no LLM-judge fallback has been needed so far.

Last updated: 2026-09-03.

## Status: COMPLETE. FP8 (48/50) and NVFP4 (46/50) both run on the 5060 Ti, one real quantization-specific quality difference found. See `results/comparative-report-20260903.md` for the full comparative writeup. **Bonus: full 50-task FP8 confirmation run on the remote RTX 4090 (192.168.0.88) -- 46/50, 0 real avoidable failures, no new findings** (see `results/run-4090-fp8-final-20260903.md`).

## Layout

```
fixtures/
  java-spring/       10 tasks -- planted bugs in a Spring/Java class, fix
                      must make its existing JUnit test class pass (mvn).
    base/             the Spring project itself.
    check.py          model-in-the-loop harness.
    tasks.json        task manifest for check.py.
  ts-angular/         8 tasks -- planted bugs in an Angular file, fix must
                      make its existing spec pass (ng test / vitest).
    base/             the Angular app itself.
    check.py          model-in-the-loop harness.
    tasks.json        task manifest for check.py.
  sql-migrations/     6 tasks -- planted bugs in a Postgres migration
                      script, fix must apply cleanly + pass check.sql.
    NN-*/              seed.sql, up.sql (buggy), up.fixed.sql (reference),
                       check.sql, README.md per task.
    verify.sh          generic dry-run+validate runner (no model calls).
    check.py           model-in-the-loop wrapper around verify.sh.
    tasks.json          task manifest for check.py.
  mcp-tools/          8 tasks -- given a tool-call schema + user request,
                      the model must emit the right tool call (or none).
  security-review/    8 tasks -- planted vulnerabilities (SQLi, SSRF,
                      hardcoded secrets, etc.), model must name the issue;
                      graded by regex recall against required phrasings.
  long-context/       10 tasks -- needle-in-haystack retrieval at 8K/64K/
                      150K tokens x position 10%/50%/90%, plus 2 tasks
                      with decoy markers.
harness/
  run_all.py          unified runner: shells out to each category's own
                      check.py --all, parses PASS/FAIL lines, writes a
                      combined report to results/.
results/              aggregated run reports (JSON + Markdown per run),
                      plus findings.md (detailed reproduced-failure log).
```

All qualbench content (fixtures, harnesses, `base/` app projects, results)
now lives as ordinary tracked files inside the main `llm-tests` git repo
-- there are no nested git repositories under `qualbench/` anymore.

## Comparative results (2026-09-03): FP8 48/50, NVFP4 46/50

**One real, newly-found quantization-specific quality difference:** SQL
task 04 (`non-idempotent-migration`) fails consistently on NVFP4 (4/4
across the official run + 3 reruns, via a specific repeatable
omission -- guards every statement except the first `ADD COLUMN`), but
only rarely on FP8 (~1/3, via an unrelated reasoning-loop mechanism).
Everything else that differs between the two is either by-design
(mcp-tools task 06) or a shared model-family characteristic that
reproduces at comparable rates on both quantizations (SQL task 05's
`ADD CONSTRAINT ... IF NOT EXISTS` hallucination, TS task 03's
computed()-vs-getter inconsistency).

NVFP4 is consistently ~1.5-2x faster than FP8 across every category,
with no VRAM-usage penalty (`--kv-reserve-tokens`, not weight size,
dominates VRAM allocation on this card at this context length).

**Full details:** `results/comparative-report-20260903.md` (bottom-line
recommendation + full analysis), `results/run-fp8-final-20260903.md` +
`results/run-nvfp4-final-20260903.md` (per-run reports), and
`results/findings.md` (every individual finding, reproduced and
root-caused).

## FP8 run (2026-09-03) -- 48/50

| Category | Pass | Total | Notes |
|---|---|---|---|
| Java/Spring bugfix | 10 | 10 | Stable. |
| TS/Angular bugfix | 8 | 8 | Stable in this run (task 03 `shopping-cart` has a known ~1/5 non-determinism, see `results/findings.md`). |
| SQL migrations | 5 | 6 | Task 04 failed: known non-deterministic reasoning-loop finding, see `results/findings.md`. |
| MCP/tool-call | 7 | 8 | Task 06 is an intentional hallucination probe, *expected* to fail every run -- not a real finding. |
| Security review | 8 | 8 | Stable. |
| Long-context retrieval | 10 | 10 | **Retry run** after an FP8 server OOM crash mid-suite -- see incident note below and `results/findings.md`. |

**Real avoidable-failure count: 0/50.** Both non-passes are expected
(one by design, one a previously-documented low-frequency model
inconsistency), not new findings.

See `results/run-fp8-final-20260903.md` for the full consolidated report
and `results/findings.md` for detailed, reproduced failure analyses
(exact bad output extracted, root cause, whether it recurs).

### Infrastructure incident: FP8 server OOM during long-context

Running all 6 categories back-to-back in one continuous server session
(~47 min) left too little free VRAM on the 16GB card by the time
long-context's larger prompts (up to 150K tokens) were reached --
the server crashed with a genuine `torch.OutOfMemoryError` in the
scheduler process. Restarting the server fresh and re-running
long-context in isolation passed 10/10 cleanly, with GPU memory holding
at ~15.6-15.7 of 16.3 GiB throughout. See `results/findings.md` for full
details.

## NVFP4 run (2026-09-03) -- 46/50

Chat template was found stock/unpatched on the NVFP4 model directory;
patched with the same froggeric v22.4 template used for FP8 (byte-
identical original templates confirmed via diff, so this was a safe
like-for-like fix) before running.

Long-context was deliberately run **first**, immediately after a fresh
server start, to avoid the FP8 OOM pattern above -- this worked, no
crash, whole 50-task suite completed in one server session (no restart
needed).

| Category | Pass | Total | Notes |
|---|---|---|---|
| Java/Spring bugfix | 10 | 10 | Stable, ~2x faster than FP8. |
| TS/Angular bugfix | 7/8 official, 8/8 on rerun | 8 | Task 03 failed once, 3/3 pass on rerun -- known non-determinism, not new. |
| SQL migrations | 4/6 official; task 04 confirmed 0/4, task 05 confirmed 2/3 on rerun | 6 | **Task 04 is a new, NVFP4-specific finding** (see below). Task 05 matches FP8's already-known finding. |
| MCP/tool-call | 7 | 8 | Task 06 by design, expected. |
| Security review | 8 | 8 | Stable. |
| Long-context retrieval | 10 | 10 | No OOM (run first, see above). |

**New finding -- SQL task 04 (`non-idempotent-migration`) is
NVFP4-specific:** the model consistently (4/4) guards every statement
except the very first `ALTER TABLE accounts ADD COLUMN is_active ...`,
so the second application of the migration fails immediately. FP8 fails
here rarely (~1/3) and via an unrelated mechanism (reasoning-loop
non-termination). This is the clearest quantization-specific quality
difference found in the whole suite -- see `results/findings.md` for
full detail.

See `results/run-nvfp4-final-20260903.md` for the full consolidated
NVFP4 report.

## Environment (as of last check, 2026-09-03)

- Server: `http://127.0.0.1:8000`, model id `qwen3.6-35b-a3b`. Both FP8
  and NVFP4 model directories confirmed healthy at various points in
  this session (only one is loaded at a time; switching requires a
  server restart with a different `--model-path`).
- Docker `qualbench-pg` (Postgres 18-alpine, port 15432): running, healthy.
  Does **not** survive a host reboot (`--rm` flag) -- restart with:
  ```
  docker run --rm -d --name qualbench-pg -e POSTGRES_PASSWORD=qualbench \
    -e POSTGRES_DB=qualbench -p 15432:5432 postgres:18-alpine
  ```
- RAM: ~13-46Gi available out of 62Gi depending on category (long-context
  is the heaviest); swap stayed under ~2Gi of 63Gi throughout both runs --
  acceptable headroom.
- GPU: RTX 5060 Ti, 16.3 GiB total. Model + reserved KV cache alone uses
  ~14.7 GiB at idle **for both quantizations** (NVFP4's smaller weights
  didn't reduce VRAM pressure here -- `--kv-reserve-tokens 260000`
  dominates the allocation); long-context tasks push usage to
  ~15.6-15.7 GiB on both. **Very little headroom on this card -- always
  run long-context first or in isolation**, regardless of quantization.
- Both FP8 and NVFP4 chat templates are now patched to froggeric v22.4
  (`chat_template.jinja`, with `.orig` backups kept alongside).
- Remote RTX 4090 (`192.168.0.88:8000`, FP8, froggeric v22.4,
  `--kv-reserve-tokens 300000`): healthy, used for the 4090 confirmation
  run. No OOM, no restart needed across the full suite.
- **Harness note:** the `long-context` category imports `tiktoken` (via
  `gen_prompt.py`). Run the harness with the repo venv python
  (`.venv/bin/python`), not the system python, or that category silently
  runs 0/0 tasks.

## Test plan: COMPLETE

1. ~~Write the unified qualbench runner~~ -- done: `harness/run_all.py`.
2. ~~Run the full 50-task suite against FP8~~ -- done, 48/50.
3. ~~Check/patch the NVFP4 chat template~~ -- done, was stock/unpatched,
   now froggeric v22.4.
4. ~~Run the full 50-task suite against NVFP4~~ -- done, 46/50 (long-
   context run first to avoid the FP8 OOM pattern -- worked).
5. ~~Produce a comparative report~~ -- done, see
   `results/comparative-report-20260903.md`.
6. ~~Run the full 50-task suite against the remote RTX 4090 (FP8)~~ --
   done, 46/50, 0 real avoidable failures, no new findings
   (`results/run-4090-fp8-final-20260903.md`). Long-context passed 10/10
   with no OOM and no restart (24.5 GiB VRAM absorbs the
   sustained-serving pressure that OOM'd the 16 GB card).

No further qualbench work planned unless new findings warrant
follow-up (e.g. investigating whether a stronger system prompt
mitigates NVFP4's SQL task 04 regression).

## Design notes for future task authors

- **Non-determinism at temperature=0 is real and expected** on this
  offloaded-MoE serving setup (expert-routing/batching effects). A single
  failing run on a task that has a correct reference solution is not
  automatically a fixture bug -- rerun 2-3x before concluding it's a
  reproducible model issue (see `results/findings.md` for the
  investigation pattern to follow: re-run, inspect the actual extracted
  code/SQL, confirm root cause, decide whether it recurs).
- **Don't retry-until-pass in the official scoring run.** Flaky/borderline
  behavior is itself a quality signal worth reporting, consistent with
  how MCP task 06 is treated (an intentional, expected failure).
- Every bugfix-style category (`java-spring`, `ts-angular`) strips
  `// BUG:` / `-- BUG:` hint comments before sending code to the model, so
  the model can't just read the answer off the page.
- Every `check.py` falls back to `reasoning_content` when `content` is
  empty/whitespace (reasoning-heavy models sometimes emit the entire
  answer as reasoning if `max_tokens` is tight), and uses
  `reasoning_effort: "low"` with a generous `max_tokens` (4000-6000) to
  avoid truncation mid-answer.
