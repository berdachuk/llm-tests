# Gemma-4 12B QAT — full LLM suite (`.175`)

Date: **2026-11-07**. Artifacts: `strata-results/20261107-gemma4-12b-qat/`.  
Serve: vLLM **0.25.1** on `:8080` (`gemma4-12b-qat.service`), GPU0 only.  
Model: `google/gemma-4-12B-it-qat-w4a16-ct` → served id **`gemma-4-12b-it-qat`**.

## Verdict

Replacing 31B with the allowed **12B** QAT unlocks **`max_model_len=131072`** on the same 4090. Qualbench **42/50** (incl. long-context **7/10**); measured short decode ~**51** tok/s, mid/8k prefill ~**5.2k–6.5k** tok/s, stream TTFT ~**55** ms. Still behind Strata IQ3_S on score/context class, but now past the ≥32K / ~128K practical floor that 31B could not meet.

| Suite | Result |
|---|---|
| Smoke `/v1/models` + chat `pong` | **PASS** (`max_model_len=131072`) |
| agentbench fast | **46 passed / 8 failed / 11 skipped / 1 xfailed** (~68 s) |
| agentbench concurrency | **3/3** |
| qualbench-50 | **42/50** @ **460.5 s** |
| long-context | **7/10** |
| Strata Monitor / 40K–248K matrix | **N/A** (vLLM, not Strata) |

## Serve config (at suite time)

- `max-model-len=131072`, `gpu-memory-utilization=0.95`, `max-num-seqs=1`, `enforce-eager`
- `--enable-auto-tool-choice --tool-call-parser gemma4`
- Alias: `qwen3.8-flash-next-iq3_s`
- Auth: Strata API key

## Agentbench (fast)

Fails (mostly contract / reasoning):

- `/v1/messages/count_tokens` missing
- `reasoning_effort` levels → empty `content` / empty reasoning channel
- inline think-off / one multi-turn tool round-trip

Concurrency (`MAX_RUNNING=1`): **3 passed**.

## Qualbench

Report: [`qualbench/results/run-gemma4-12b-qat-full50-20261107-125922.md`](qualbench/results/run-gemma4-12b-qat-full50-20261107-125922.md)

| Category | Pass | Notes |
|---|---|---|
| java-spring | **8/10** | fails `03`, `08` (compile) |
| ts-angular | **7/8** | `03-shopping-cart` |
| sql-migrations | **4/6** | `02`, `03` |
| mcp-tools | **8/8** | |
| security-review | **8/8** | |
| long-context | **7/10** | now runnable (was 0/0 on 31B @ 3072) |

Harness: temporary strip of `reasoning_effort` in checkers (Gemma empties `content`); restored after run.

## Speed probe (live `:8080`, warm)

| Probe | Prompt | Completion | Wall | Rate |
|---|---:|---:|---:|---|
| Short decode | 31 | 111 | 2.18 s | ~**51** tok/s decode |
| Mid prefill | 1820 | 2 | 0.35 s | ~**5.2k** tok/s prefill |
| ~7k prefill | 7020 | 2 | 1.08 s | ~**6.5k** tok/s prefill |
| Stream short | — | — | — | TTFT ~**55** ms |

Artifact: `strata-results/20261107-gemma4-12b-qat/speed-probe.json`.

## Coding-session wall (measured)

Same formula as Strata UI (**output_sum / Σ request duration**). Synthetic
proxy with growing context + substantial patches (not a 2 h OpenCode log).

| Session | n | Prompt range | Out sum | Σ dur | Wall tok/s |
|---|---:|---|---:|---:|---:|
| Strata IQ3_S real UI (ref) | 351 | 357–108945 | 319588 | 7351 s | **≈ 43.5** |
| Gemma 12B gen-heavy v2 | 20 | 1297–68819 | 10072 | 217 s | **≈ 46.4** |
| Gemma 12B long-ctx ≥20K | 12 | — | — | — | **≈ 43.8** |
| Gemma 12B ack-heavy v1 | 24 | 774–61704 | 1637 | 168 s | **≈ 9.8** |

Artifacts: `coding-wall-session.json`, `coding-wall-session-v2.json`.
Peak decode still ~**51** vs Strata ~**90–180**; wall can look tied when both
are prefill-taxed on patch-heavy work.

## Isolation

GPU1 VRAM stayed ~8356 MiB; ports 8002–8006 listening.

## Compare vs Strata IQ3_S

| Axis | Strata IQ3_S | Gemma-4 12B QAT | Verdict |
|---|---|---|---|
| Qualbench | **50/50** @ ~600 s | **42/50** @ **461 s** | **Strata** (−8 on Gemma) |
| Peak decode | ~**90–180** t/s | ~**51** t/s | **Strata** (~2–3×) |
| Coding wall | UI **~43.5** | proxy **~46** (gen-heavy) | **~tie** when prefill-taxed |
| Prefill (mid) | ~1.9–4.6k class | ~**5.2–6.5k** | competitive |
| Context | ~**248K** practical | **131072** | **Strata** ceiling; both ≥32K/128K bar |
| Role | prod Bifrost / OpenCode | Kaggle-legal experiment | restore Strata for prod |

Also vs Maya **41/50** @ 32K and Gemma-31B ~**37/50** @ **3072** (context-killed).
