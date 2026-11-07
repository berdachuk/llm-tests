# Gemma-4 12B QAT download — .175

Allowed competition model for [Gemma 4 Developer Agent](https://www.kaggle.com/competitions/gemma-4-developer-agent) (one of four QAT variants).

| Field | Value |
|---|---|
| HF repo | `google/gemma-4-12B-it-qat-w4a16-ct` |
| Local dir | `/mnt/data/berda-models/huggingface/google/gemma-4-12B-it-qat-w4a16-ct` |
| `model.safetensors` | **9.56 GiB** (10264229896 bytes) — verified |
| Started | 2026-11-07T04:15:20-05:00 |
| Finished | 2026-11-07T04:27:03-05:00 (`exit=0`) |
| Duration | ~11.7 min |
| Log | `/mnt/data/berda-models/huggingface/logs/gemma4-12b-qat-download-20261107-041520.log` |
| HF CLI venv | `/mnt/data/berda-models/huggingface/.venv-hf` |
| HF user | `sberdachuk` |
| Follow-up | cutover → [`GEMMA4_12B_QAT_CUTOVER.md`](GEMMA4_12B_QAT_CUTOVER.md) |

## Why 12B

31B QAT on 24 GB only fits **`max-model-len≈3072`** — not usable for agent work (want ≥32K, prefer 128K). 12B weights ~10.3 GB leave room for **32K–128K** on the same 4090.
