# Improvement Plan: `llm-tests` (agentbench + qualbench)

> Written 2026-09-05. Sources: direct review of this repo, plus the
> evidence-backed insight logs of the sibling Java/Spring-AI benchmark agents
> (`bitgn-ecom1-spring-ai/docs/agent-quality-and-speed-insights.md`,
> `bitgn-pac1-spring-ai/docs/agent-quality-and-speed-insights.md`). Those logs
> are the product of ~20 full benchmark runs and dozens of A/B experiments;
> the practices below are the ones that measurably paid off there and are
> directly transferable to this Python suite.

## 1. Current state (verified)

Two independent subsystems, no shared code/config/runner:

| | agentbench | qualbench |
|---|---|---|
| Runner | pytest (`pytest.ini`, `testpaths = agentbench/tests`) | `harness/run_all.py` (subprocesses per-category `check.py --all`) |
| Tests | 66 pytest tests, 9 modules, 3 wire protocols (OpenAI chat, Responses, Anthropic) | 50 tasks, 6 categories, deterministic graders (mvn / ng test / verify.sh / jsonschema / regex) |
| Markers | `slow`, `concurrency`, `streaming`, `tool_calling`, `reasoning`, `openai`, `responses`, `anthropic` | none (not pytest) |
| Config | `agentbench/settings.py` + `.env` + CLI flags — excellent | hardcoded defaults in `run_all.py` / `check.py` |
| Artifacts | none (results recorded by hand in `TEST_RESULTS.md`) | `results/run-<tag>-<ts>.{json,md}` per run |
| Server | live FreeToken/OpenAI-compatible endpoint | same |

Already good and worth keeping: the env-driven settings layer with
reasoning-budget-aware `max_tokens` defaults (agentbench), the fail-fast
`_server_reachable` autouse fixture, the opt-in `slow`/`concurrency` gating,
deterministic no-LLM-judge grading in qualbench, and the gitignore hygiene
(`secrets/`, `node_modules/`, `target/` are all untracked).

## 2. The transferable lessons (from the Java/Spring-AI projects)

1. **Deterministic gates beat LLM-as-judge.** ECOM1 measured LLM judging at
   0% lift, 32% false negatives, ~24 s/call and removed it. qualbench already
   follows this — keep it that way; never add an LLM-judge fallback.
2. **A run that "finishes" is not a run that is correct.** PAC1's 43/43 DONE
   run had all scores sealed server-side; "DONE" was reachability, not
   correctness. Same here: a PASS line from a grader is only as good as the
   grader's ability to fail loudly.
3. **Run-to-run variance is real and must be measured before trusting a
   single run.** ECOM1: the same unchanged code scored 49/55 and 43/55 on
   identical setups (±6 tasks on a 55-task board). Any effect smaller than
   the variance is unmeasurable by single runs.
4. **A hypothesis with no positive control is untested, not confirmed.**
   ECOM1's availability family failed 0/130 while its single-ref siblings
   passed 22/22 — the contrast localized the defect. Conversely, a grader
   with no clean-code case cannot measure false positives.
5. **Log the decision, not just the verdict.** ECOM1: `tool_result` events
   were never logged, so three "fixes" went unverified; logging the decision
   exposed two root causes on the first run. A short-circuiting grader reports
   *a* defect, never the defect count.
6. **Reports are read-only artifacts.** ECOM1: overwriting completed reports
   with fresh partial runs loses data. Hand-maintained summaries drift.
7. **Long runs must be detached** (`setsid nohup … &`, verify `pid == pgid ==
   sid`), or a caller-side timeout kills the whole process group.
8. **Every LLM client needs a read/call timeout** — local models drop idle
   sockets during long generations; without one a run hangs silently.
9. **The silent-failure lesson:** a graph will not tell you it lied; it shows
   you all-green. The question per task is *"could this have passed by
   mistake?"*, not "did it pass?".

## 3. Findings and recommendations (prioritized)

### P0 — Correctness risks

**F1. qualbench graders never check `finish_reason` — silent truncation is
invisible.**
`mcp-tools/check.py` sends `max_tokens: 1024` with **no `reasoning_effort`**
and grades `message.content` only; the other five graders set
`reasoning_effort: "low"` but none checks `finish_reason`. The agentbench
suite already documents the trap (settings.py:121-130): a reasoning model can
spend the whole budget on `reasoning_content` and return empty `content` with
`finish_reason: "length"`. A truncated-but-parseable answer then grades PASS
or FAIL for the wrong reason, and the run report cannot tell.
Fix:
- Add `reasoning_effort: "low"` to `mcp-tools/check.py` (parity with the
  other five).
- In every `check.py`, treat `finish_reason == "length"` as a distinct
  failure reason (`"truncated: finish_reason=length"`), and fall back to
  `reasoning_content` where the other graders already do (java-spring,
  ts-angular, sql-migrations, security-review, long-context do; mcp-tools
  does not — add the same fallback).

**F2. Per-task failure reasons and model outputs are not persisted.**
`run_all.py` parses only `[PASS]/[FAIL]` lines; the `reasons` each `check.py`
prints go to stdout and are echoed, but never land in the JSON report, and
the model's extracted fix/SQL is discarded. ECOM1 lesson 5: the decision must
be logged. Today, forensics on a failed task require a full re-run.
Fix:
- Have each `check.py` emit a machine-readable per-task block (e.g.
  `[REASON] <task> <json>` lines or a `--json` mode) and have `run_all.py`
  capture reasons + the extracted candidate (code/SQL) into the run JSON.
- This also enables **offline replay**: re-run `mvn test` / `ng test` /
  `verify.sh` on a saved candidate without a model call — the ECOM1 pattern
  of a deterministic offline corpus testable in seconds, not a 90-minute run.

**F3. No preflight health check in qualbench.**
agentbench fails fast via `_server_reachable`; `run_all.py` with a dead
server burns 6 category timeouts (~30+ min) before reporting anything.
Fix: `GET /v1/models` (and verify the requested model id is served) before
the first category; exit with a clear message otherwise.

### P1 — Measurement methodology

**F4. No repeat-baseline; single runs are treated as truth.**
`TEST_RESULTS.md` and `results/` record one run per configuration. ECOM1
lesson 3: variance must be measured by repeating the *unchanged* baseline
before any change is validated. qualbench's prompts are fixed (unlike ECOM1's
randomized instances), so per-task diffs *are* attributable — but model
non-determinism at `temperature=0` still exists (TS task 03 evidence in
`results/findings.md`).
Fix:
- Establish a repeat-baseline protocol: run the unchanged suite N times
  (N≥3) on the reference config, record the pass-rate spread, and require any
  claimed improvement to exceed that spread.
- Track per-task pass *rates* across runs (a `results/trends.json` or a
  `history/` dir), not just per-run totals. The structural-failure set —
  tasks failing in *every* run — is the actionable signal (ECOM1).

**F5. No negative controls in security-review.**
All 8 security-review tasks have planted vulnerabilities; there is no
clean-code case, so the false-positive rate is unmeasured. ECOM1 lesson 4.
Fix: add 2-3 clean-code tasks (expected verdict: no issue named) and grade
them with the same regex recall. This is the qualbench analog of PAC1's
`DegenerateGreenDetector`.

**F6. Run provenance is incomplete.**
Run JSON records url/model/timestamps but not: git commit of the suite,
server/FreeToken version, chat-template version, or GPU/quantization. ECOM1:
"scores are only comparable within a model" — and here even the model id is
ambiguous across quantizations of the same checkpoint.
Fix: `run_all.py` should record `git rev-parse HEAD`, the server's
`/v1/models` payload (context length, template version if exposed), and a
free-form `notes` field. agentbench's `TEST_RESULTS.md` entries should carry
the same.

### P2 — Structure, CI, hygiene

**F7. qualbench is not pytest.** No markers, no xfail, no gating, no
`--collect-only`, no CI integration. Two options:
- (a) Wrap each category as a pytest module (thin adapter calling the
  existing `check.py` logic in-process), gaining markers (`slow` for
  long-context), `xfail` for the by-design probes (mcp-tools 06), and one
  `pytest` entry point for both suites; or
- (b) keep `run_all.py` but add a `--json` mode, a manifest, and a
  `--categories`-aware preflight (F3).
Recommend (a) — it unifies the two subsystems and makes the by-design
probes explicit instead of a footnote in a README.

**F8. No CI config.** There is no GitHub Actions/GitLab CI file. Even a
minimal pipeline helps: `pytest agentbench/tests -m "not slow and not
concurrency"` against a local mock (see F9) + `run_all.py --categories
sql-migrations` (the only category with a fully offline deterministic
runner) + `ruff check`.

**F9. agentbench has no offline layer.** All 66 tests hit the live server;
there is no way to run the protocol/tool-calling tests without the GPU box.
The Java projects solve this with `StubAgentFacade`/`StubTaskRunner`
implementing the `AgentFacade` interface. The Python analog: a
`RecordingClient` that replays captured JSONL responses (one file per test
scenario, recorded once against the live server, replayed in CI). This is
the single highest-leverage addition for CI and for regression-testing
client-side parsing changes.

**F10. `xfail_strict` is not set.** `test_reasoning.py:168` and
`test_tool_calling.py:118` use `@pytest.mark.xfail`; without
`xfail_strict = true` in `pytest.ini`, a test that unexpectedly *passes* is
silently reported as XPASS instead of failing the run. ECOM1 lesson: a fix
that cannot fail loudly will be mistaken for a partial success.

**F11. No lint/format config.** No ruff/black config, no `pre-commit`.
ECOM1's `write-less-code` pass (11 duplicated `medianXxx` methods collapsed
into one) is the cautionary tale. Add `ruff` (lint + format) with a minimal
config; the codebase is small (5.2k LOC) so this is a one-time pass.

**F12. Long-context ordering dependency.** `TEST_RESULTS.md` notes
long-context is stable "when run first/in isolation" (OOM otherwise). The
runner should either document/order this explicitly or isolate the category
(separate process, which `run_all.py` already does per category — verify the
OOM was a pre-unified-runner artifact and note the current behavior).

**F13. Scratch scripts at repo root.** `gen_256k_prompt.py` (791 LOC) and
`check_applied.py` (139 LOC) are one-off tooling. Move to `tools/` (or
`qualbench/fixtures/long-context/` for the prompt generator) so the repo
root reads as: `agentbench/`, `qualbench/`, `pytest.ini`, `README.md`.

**F14. Secrets.** `secrets/` is correctly gitignored, but two plaintext
passwords live in the repo tree. Fine for a private box; if this repo ever
moves to a shared remote, move them to env vars / a secrets manager and
delete the files. (Also: `secrets/password73.txt` — same treatment.)

### P3 — Nice-to-haves

- **F15. Trend report.** Replace hand-maintained `TEST_RESULTS.md` with a
  generated `results/trends.md` (per-task pass rates, per-config totals,
  structural-failure set) — ECOM1's `familyCounters`-as-report-columns
  pattern, minus the family counters.
- **F16. Detached-run wrapper.** A `scripts/run-qualbench.sh` using
  `setsid nohup … &` with exit-status recording (ECOM1: `rc > 128` ⇒ killed
  by signal) for the ~77-minute full runs.
- **F17. A/B control protocol.** Before any future change to a grader or
  prompt, run the unchanged baseline and the change on the same server/model
  back-to-back (ECOM1: five ranked fixes produced an identical 44/55).

## 4. Target structure (after the plan)

```
llm-tests/
  pytest.ini                 # + xfail_strict = true
  pyproject.toml             # ruff config, project metadata
  agentbench/
    client.py                # + RecordingClient (replay mode)
    tests/                   # unchanged, now runnable offline via replay
  qualbench/
    harness/run_all.py       # + preflight, --json reasons, provenance, replay
    fixtures/…               # + security-review clean-code controls
    results/                 # + trends.md, history/
  tools/                     # gen_256k_prompt.py, check_applied.py moved here
  scripts/run-qualbench.sh   # setsid wrapper
  .github/workflows/ci.yml   # lint + offline agentbench + sql-migrations
```

## 5. Suggested order of work

1. **F1 + F2** (grader correctness + persisted reasons/outputs) — small,
   high value; unblocks everything else.
2. **F3 + F6** (preflight + provenance) — small.
3. **F10 + F11** (xfail_strict, ruff) — mechanical.
4. **F9** (RecordingClient replay) — medium; enables CI.
5. **F7 + F8** (pytest integration + CI) — medium.
6. **F4 + F5 + F15** (repeat-baseline, negative controls, trends) — ongoing
   methodology; start the baseline now so future changes have a yardstick.
7. **F12–F14, F16–F17** — hygiene and wrappers, as convenient.
