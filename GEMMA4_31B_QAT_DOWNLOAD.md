# Gemma-4 31B QAT download (Phase A) — .175

Competition model for [Gemma 4 Developer Agent / Paper Track](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper).

| Field | Value |
|---|---|
| HF repo | `google/gemma-4-31B-it-qat-w4a16-ct` |
| Local dir | `/mnt/data/berda-models/huggingface/google/gemma-4-31B-it-qat-w4a16-ct` |
| `model.safetensors` | **23.265 GB** (23265352448 bytes) |
| Started | 2026-11-07T02:28:52-05:00 |
| Finished | 2026-11-07T02:59:29-05:00 (`exit=0`) |
| Duration | ~30.6 min |
| Log | `/mnt/data/berda-models/huggingface/logs/gemma4-31b-qat-download-20261107-022852.log` |
| HF CLI venv | `/mnt/data/berda-models/huggingface/.venv-hf` |
| HF user | `sberdachuk` |
| Strata | left **running** (not stopped) |

Sidecars present: `config.json`, `tokenizer.json`, `tokenizer_config.json`, `generation_config.json`, `processor_config.json`, `chat_template.jinja`, `README.md`.

## Phase B (deferred — needs explicit go)

1. Stop Strata (free RTX 4090 / GPU0).
2. Serve local path with vLLM (compressed-tensors W4A16; short `max-model-len` for 24 GB).
3. Smoke `/v1/models` + short completion.
4. Paper experiments → restore Strata IQ3_S + Monitor smoke.
