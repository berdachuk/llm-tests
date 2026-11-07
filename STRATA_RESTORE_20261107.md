# Strata IQ3_S restore after Gemma cutover — 2026-11-07

## Saved for future Gemma tests

On `.175`: `/mnt/data/gemma4-kaggle/archive-for-future-tests/LATEST/`  
Repo index: [`GEMMA4_FUTURE_TESTS.md`](GEMMA4_FUTURE_TESTS.md)

Units `gemma4-12b-qat` / `gemma4-31b-qat` left **disabled** (files kept). Models stay on disk.

## Restore actions

1. `systemctl --user disable --now gemma4-12b-qat gemma4-31b-qat`
2. `unmask` + restore `strata-iq3_s.service` from `bak-gemma4-cutover`
3. `enable --now strata-iq3_s`
4. Reboot `.175`
5. Smoke all LLM / ASR / embedding stacks

## Post-reboot smoke

| Endpoint | Result |
|---|---|
| `:8080` `/v1/models` | **PASS** — `qwen3.8-flash-next-iq3_s`, `n_ctx/max=262144` |
| `:8080` chat `pong` | **PASS** (`content=pong`; thinking-off also OK) |
| `https://llm-88.berdachuk.com` chat | **PASS** (`pong` with `enable_thinking=false`) |
| `:8002` speaches | **PASS** (docs 200, whisper model listed) |
| `:8003` gigaam | **PASS** (`/health` ok) |
| `:8004` Qwen3 embedding | **PASS** (POST `/v1/embeddings` dim 1024) |
| `:8005` embeddinggemma-2 | **PASS** (embeddings dim 768) |
| `:8006` frida | **PASS** (healthy; `/v1/models` + openapi) |
| GPU0 / GPU1 VRAM | ~23640 / ~8356 MiB |

`gemma4-*-qat`: disabled / inactive. `strata-iq3_s`: **enabled + active**.
nvidia-guard falls through to Strata when Gemma units are not enabled.
