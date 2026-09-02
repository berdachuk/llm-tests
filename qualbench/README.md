# qualbench

A 50-task quality/regression eval comparing **FP8 vs NVFP4** quantizations
of `Qwen3.6-35B-A3B` on the local desktop (`berdachuk-pc`, RTX 5060 Ti
16GB), across 6 categories. Each category is model-in-the-loop: a fixed
prompt is sent to a live server, the response is extracted, and a
deterministic check (compiler/test-runner/regex/schema) decides pass/fail
-- no LLM-judge fallback has been needed so far.

Last updated: 2026-09-02.

## Status: fixtures + per-category harnesses complete (50/50 tasks written and verified). Unified runner not yet built. No NVFP4 run yet.

## Layout

```
fixtures/
  java-spring/       10 tasks -- planted bugs in a Spring/Java class, fix
                      must make its existing JUnit test class pass (mvn).
    base/             the Spring project itself (own nested git repo).
    check.py          model-in-the-loop harness (own nested git repo).
    tasks.json        task manifest for check.py.
  ts-angular/         8 tasks -- planted bugs in an Angular file, fix must
                      make its existing spec pass (ng test / vitest).
    base/             the Angular app itself (own nested git repo).
    check.py          model-in-the-loop harness (own nested git repo).
    tasks.json        task manifest for check.py.
  sql-migrations/     6 tasks -- planted bugs in a Postgres migration
                      script, fix must apply cleanly + pass check.sql.
                      Own nested git repo (fixtures + harness together).
    NN-*/              seed.sql, up.sql (buggy), up.fixed.sql (reference),
                       check.sql, README.md per task.
    verify.sh          generic dry-run+validate runner (no model calls).
    check.py           model-in-the-loop wrapper around verify.sh.
    tasks.json          task manifest for check.py.
  mcp-tools/          8 tasks -- given a tool-call schema + user request,
                      the model must emit the right tool call (or none).
                      Own nested git repo.
  security-review/    8 tasks -- planted vulnerabilities (SQLi, SSRF,
                      hardcoded secrets, etc.), model must name the issue;
                      graded by regex recall against required phrasings.
                      Own nested git repo.
  long-context/       10 tasks -- needle-in-haystack retrieval at 8K/64K/
                      150K tokens x position 10%/50%/90%, plus 2 tasks
                      with decoy markers. Own nested git repo.
harness/              (empty) -- unified runner across all 6 categories,
                      not yet written.
results/              (empty) -- aggregated run reports land here once the
                      unified runner exists.
```

Each `fixtures/<category>/` is its **own separate git repository** (not a
submodule, just an independent `git init`), following the pattern
established when the Java/TS `base/` app fixtures were first built. This
top-level `qualbench/` directory is also its own separate git repo,
tracking only files that live directly under it (this README, `results/`,
`harness/`) -- it does not attempt to absorb the nested per-category repos.

## Results so far (single-run pass counts against the live FP8 server)

| Category | Tasks | Pass rate (1 run) | Notes |
|---|---|---|---|
| Java/Spring bugfix | 10 | 10/10 | Stable. |
| TS/Angular bugfix | 8 | 8/8 | Task 03 (`shopping-cart`) showed one transient failure across repeated runs -- see `results/findings.md`. |
| SQL migrations | 6 | 4/6 (varies 1-3/3 per task on repeat runs) | Tasks 02, 03, 04, 05 have real, reproducible FP8 quality issues at temp=0. See `results/findings.md`. |
| MCP/tool-call | 8 | 7/8 (by design) | Task 06 is an intentional hallucination probe (model wrongly calls a money-transfer tool with incomplete info) and is *expected* to fail -- this is scored as a real finding, not a fixture bug. |
| Security review | 8 | 8/8 | Stable across repeated checks. |
| Long-context retrieval | 10 | 10/10 | Stable; model correctly rejects decoy markers even when the decoy's own note explicitly points to it. |

**Total: 50/50 tasks written, individually verified against the live FP8
server at least once; 4 categories fully stable, 2 categories (TS, SQL)
show genuine model non-determinism / correctness gaps worth reporting.**

See `results/findings.md` for the detailed, reproduced failure analyses
(exact bad output extracted, root cause, whether it recurs).

## Environment (as of last check, 2026-09-02)

- FP8 server: `http://127.0.0.1:8000`, model id `qwen3.6-35b-a3b`, healthy.
- Docker `qualbench-pg` (Postgres 18-alpine, port 15432): running, healthy.
  Does **not** survive a host reboot (`--rm` flag) -- restart with:
  ```
  docker run --rm -d --name qualbench-pg -e POSTGRES_PASSWORD=qualbench \
    -e POSTGRES_DB=qualbench -p 15432:5432 postgres:18-alpine
  ```
- RAM: 42Gi used / 4.4Gi free / 20Gi available out of 62Gi. Swap: ~1.3MiB
  of 64Gi used (excellent headroom for the full run).
- NVFP4 model / chat template: **not yet checked or patched**. Must run
  the same froggeric-template verification workflow used for FP8 before
  the NVFP4 leg of the comparison.

## Test plan / remaining work

1. **Write the unified qualbench runner** (`harness/run_all.py` or
   similar) that invokes each category's `check.py --all` (and the SQL
   category's `check.py`, which wraps `verify.sh`), captures pass/fail +
   timing for all 50 tasks in one pass, and writes a report to
   `results/`. This is the main remaining piece of infrastructure.
2. **Re-verify RAM/swap headroom** immediately before the full run (state
   drifts across long sessions; last verified figures are above).
3. **Check/patch the NVFP4 chat template**: locate
   `~/llm_models/Qwen3.6-35B-A3B-NVFP4/chat_template.jinja`, run the same
   `check_applied.py` + froggeric-template workflow already used for the
   FP8 model directory, patch if the vendor template is still in place.
4. **Run the full 50-task suite against FP8** via the unified runner.
   Expect ~75-90 minutes based on measured per-task timings (average
   ~90s/task across categories already exercised).
5. **Stop FP8, start NVFP4** with the same serving flags (`ft serve`,
   same `--tool-call-parser`/`--reasoning-parser`/etc.), confirm healthy.
6. **Run the full 50-task suite against NVFP4** via the unified runner.
7. **Produce a comparative report**: pass rate per category, timing, and
   peak RAM/VRAM + swap usage, FP8 vs NVFP4. Call out any category where
   NVFP4 regresses relative to FP8's already-known findings (e.g. does
   NVFP4 also hallucinate `ADD CONSTRAINT ... IF NOT EXISTS`, or is that
   FP8-specific?).

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
