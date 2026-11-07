# Gemma-4 31B QAT — full LLM suite (`.175`)

Date: **2026-11-07**. Artifacts: `strata-results/20261107-gemma4-qat/`.  
Serve: vLLM **0.25.1** on `:8080` (`gemma4-31b-qat.service`), GPU0 only.  
Model: `google/gemma-4-31B-it-qat-w4a16-ct` → served id **`gemma-4-31b-it-qat`**.

## Verdict

Suite completed against the temporary Gemma cutover. Strong on MCP / security / Java; limited by **3072** context (no long-context tasks) and empty `content` when clients send `reasoning_effort`. GPU1 stacks stayed healthy.

| Suite | Result |
|---|---|
| Smoke `/v1/models` + chat `pong` | **PASS** |
| agentbench fast | **44 passed / 10 failed / 11 skipped / 1 xfailed** (~72 s) |
| agentbench concurrency | **3/3** |
| qualbench (runnable) | **37/40** (~6.5 min coding+security+mcp; sql retry after PG up) |
| long-context | **0/0** (tasks skipped: advertised `max_model_len=3072` < 8K) |
| Strata Monitor / 40K–248K matrix | **N/A** (vLLM, not Strata) |

Equivalent vs classic 50-task frame: **37/50** if the 10 long-context tasks count as unavailable/fail.

## Serve config (at suite time)

- `max-model-len=3072`, `gpu-memory-utilization=0.98`, `max-num-seqs=1`, `enforce-eager`
- `--enable-auto-tool-choice --tool-call-parser gemma4`
- Alias: `qwen3.8-flash-next-iq3_s` still routed to same weights
- Auth: Strata API key (nginx `/v1/` unchanged)

## Agentbench (fast)

Fails (mostly contract / reasoning, not basic chat):

- `/v1/messages/count_tokens` missing
- `reasoning_effort` levels → empty `content` (tokens go to reasoning channel)
- a few agentic / multi-turn tool edge cases
- one bugfix “no final summary” flake-style fail

Concurrency (`MAX_RUNNING=1`): **3 passed**.

Logs: `strata-results/20261107-gemma4-qat/agentbench-fast.txt`, `agentbench-concurrency.txt`.

## Qualbench

Primary report: [`qualbench/results/run-gemma4-31b-qat-full50-final-20261107-120339.md`](qualbench/results/run-gemma4-31b-qat-full50-final-20261107-120339.md)  
SQL retry (after `qualbench-pg` on `:15432`): [`…sql-retry-20261107-120413.md`](qualbench/results/run-gemma4-31b-qat-sql-retry-20261107-120413.md)

| Category | Pass | Notes |
|---|---|---|
| java-spring | **10/10** | |
| ts-angular | **7/8** | `03-shopping-cart` |
| sql-migrations | **4/6** | retry; 2 quality fails (`01`, `02`) |
| mcp-tools | **8/8** | |
| security-review | **8/8** | |
| long-context | **0/0** | skipped by harness (ctx) |

**Harness notes for this model:** default qualbench `max_tokens` 4k–6k exceeds 3072 ctx → HTTP 400; `reasoning_effort: low` yields empty `content`. Suite run used temporary checker overrides (`max_tokens=1536`, no `reasoning_effort`); fixtures restored after.

## Isolation check

| Endpoint | Status after suite |
|---|---|
| `:8002` speaches | 200 |
| `:8004` embedding | 200 |
| `:8006` frida | 200 |
| GPU1 VRAM | ~8356 MiB (unchanged) |

## Compare

| Stack | Qualbench | Context |
|---|---|---|
| Strata IQ3_S (prod) | **50/50** @ ~600 s | 262K |
| Maya GLM-5.3-Flash | **41/50** | 32K |
| **Gemma-4 31B QAT** | **37/40** runnable (~**37/50**) | **3072** |
