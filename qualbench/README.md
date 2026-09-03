# qualbench

A 50-task quality/regression eval comparing **FP8 vs NVFP4** quantizations
of `Qwen3.6-35B-A3B` on the local desktop (`berdachuk-pc`, RTX 5060 Ti
16GB), across 6 categories. Each category is model-in-the-loop: a fixed
prompt is sent to a live server, the response is extracted, and a
deterministic check (compiler/test-runner/regex/schema) decides pass/fail
-- no LLM-judge fallback has been needed so far.

Last updated: 2026-09-03.

## Status: official full 50-task FP8 run complete (48/50 -- both non-passes are known/expected, see below). Unified runner built. NVFP4 run not yet started.

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

## Official FP8 run (2026-09-03) -- 48/50

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
details. **For the NVFP4 run, run long-context first (or in its own
isolated invocation) to avoid the same risk.**

## Environment (as of last check, 2026-09-03)

- FP8 server: `http://127.0.0.1:8000`, model id `qwen3.6-35b-a3b`, healthy
  (restarted once after the OOM incident above).
- Docker `qualbench-pg` (Postgres 18-alpine, port 15432): running, healthy.
  Does **not** survive a host reboot (`--rm` flag) -- restart with:
  ```
  docker run --rm -d --name qualbench-pg -e POSTGRES_PASSWORD=qualbench \
    -e POSTGRES_DB=qualbench -p 15432:5432 postgres:18-alpine
  ```
- RAM: ~13-46Gi available out of 62Gi depending on category (long-context
  is the heaviest); swap stayed under ~2Gi of 63Gi throughout the run --
  acceptable headroom.
- GPU: RTX 5060 Ti, 16.3 GiB total. Model + reserved KV cache alone uses
  ~14.5-15 GiB at idle; long-context tasks push usage to ~15.6-15.7 GiB.
  **Very little headroom -- this is the binding constraint**, see OOM
  incident above.
- NVFP4 model / chat template: **not yet checked or patched**. Must run
  the same froggeric-template verification workflow used for FP8 before
  the NVFP4 leg of the comparison.

## Test plan / remaining work

1. ~~Write the unified qualbench runner~~ -- done: `harness/run_all.py`.
2. ~~Run the full 50-task suite against FP8~~ -- done, 48/50, see above.
3. **Check/patch the NVFP4 chat template**: locate
   `~/llm_models/Qwen3.6-35B-A3B-NVFP4/chat_template.jinja`, run the same
   `check_applied.py` + froggeric-template workflow already used for the
   FP8 model directory, patch if the vendor template is still in place.
4. **Stop FP8, start NVFP4** with the same serving flags (`ft serve`,
   same `--tool-call-parser`/`--reasoning-parser`/etc.), confirm healthy
   via a real `/v1/chat/completions` round trip (not just `/v1/models`).
5. **Run the full 50-task suite against NVFP4** via the unified runner --
   run long-context first or in isolation to avoid the FP8 OOM pattern.
6. **Produce a comparative report**: pass rate per category, timing, and
   peak RAM/VRAM + swap usage, FP8 vs NVFP4. Specifically check whether
   NVFP4 reproduces FP8's known findings (SQL task 05's `ADD CONSTRAINT
   ... IF NOT EXISTS` hallucination, TS task 03's computed()-vs-getter
   inconsistency, SQL task 04's reasoning-loop non-termination) and
   whether NVFP4 (using less VRAM for weights) avoids the long-context
   OOM risk seen on FP8.

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
