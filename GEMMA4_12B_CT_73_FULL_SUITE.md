# Gemma-4 12B QAT-CT — full LLM suite (`.73`)

Date: **2026-11-11**. Artifacts: `strata-results/20261111-gemma4-12b-ct-73/`.  
Serve: vLLM **0.31.0** on `192.168.0.73:8012`, RTX 5060 Ti 16 GiB.  
Model: `google/gemma-4-12B-it-qat-w4a16-ct` → served id **`gemma-4-12B-it-qat-w4a16-ct`**.

## Verdict

On desktop `.73` with **`max_model_len=131072`**, qualbench lands at **42/50** (same headline as the 2026-11-07 `.175` 4090 cutover). Agentbench is strong once `--enable-auto-tool-choice --tool-call-parser gemma4` is on (**53 passed / 1 failed**). Without the tool parser, tool tests mostly 400.

| Suite | Result |
|---|---|
| Smoke `/v1/models` + chat `pong` | **PASS** (`max_model_len=131072`) |
| agentbench fast (w/ tool+reasoning parsers) | **53 passed / 1 failed / 11 skipped / 1 xfailed** (~160 s) |
| agentbench concurrency (`MAX_RUNNING=1`) | **3/3** |
| qualbench-50 (combined) | **42/50** |
| long-context | **7/10** (3× 150k → HTTP 400 over ctx) |

## Serve config (at suite time)

- `max-model-len=131072`, util `0.90`, `max-num-seqs=1`, `enforce-eager`, fp8 KV, text-only
- `--enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4`
- Qualbench: temporary strip of `reasoning_effort` (Gemma pollutes `content` with think text)

## Qualbench (combined)

Primary: [`qualbench/results/run-gemma4-12b-ct-73-full50-20261111-161809.md`](qualbench/results/run-gemma4-12b-ct-73-full50-20261111-161809.md) (**35/42**, ts-angular **0/0** — Node not on PATH).  
TS retry with nvm Node: [`…ts-retry-20261111-162025.md`](qualbench/results/run-gemma4-12b-ct-73-ts-retry-20261111-162025.md) (**7/8**).

| Category | Pass | Notes |
|---|---|---|
| java-spring | **8/10** | fails `03`, `08` (compile) |
| ts-angular | **7/8** | `03-shopping-cart` (retry) |
| sql-migrations | **4/6** | `02`, `03` |
| mcp-tools | **8/8** | needs tool-parser |
| security-review | **8/8** | |
| long-context | **7/10** | 150k tasks rejected (ctx 131072) |
| **Total** | **42/50** | |

## Agentbench

Single fail: `TestInlineThinkTags::test_inline_think_off_tag_content_is_not_swallowed_into_reasoning` (FreeToken/Qwen-oriented inline tag; not applicable to Gemma/vLLM the same way).

## Speed probe (warm `:8012`)

| Probe | Prompt | Completion | Wall | Rough rate |
|---|---:|---:|---:|---|
| Warm pong | 18 | 2 | 0.11 s | — |
| Short decode | 25 | 96 | 3.24 s | ~**30** tok/s decode |
| Mid prefill (~1.8k) | 1820 | 2 | 1.11 s | ~**1.6k** tok/s prefill |

Artifact: `strata-results/20261111-gemma4-12b-ct-73/speed-probe.json`.

## Compare vs `.175` 12B (2026-11-07)

| | `.175` 4090 | `.73` 5060 Ti (this run) |
|---|---|---|
| qualbench | **42/50** | **42/50** |
| peak short decode | ~**51** t/s | ~**30** t/s |
| ctx | 131072 | 131072 |
| agentbench tools | mostly OK w/ parser | **53/1** w/ parser |

## Runtime note

Live process was restarted mid-suite to add tool/reasoning parsers (required for mcp/agentbench tools). `serve.sh` updated to include them by default. System unit install uses sudo (see `gemma4-12b.service`).
