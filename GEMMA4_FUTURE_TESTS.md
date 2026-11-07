# Gemma-4 QAT — saved settings for future tests (.175)

After 2026-11-07 paper/main-track experiments, production `:8080` returned to
**Strata IQ3_S**. Cutover assets are kept on disk for a fast re-test.

## Canonical archive on .175

`/mnt/data/gemma4-kaggle/archive-for-future-tests/LATEST/`

Contains: systemd user units (12B/31B), `serve_gemma4.py` / `.sh`, Strata bak,
nvidia-guard snippet, README with enable/disable recipes.

Live serve tree (not removed): `/mnt/data/gemma4-kaggle/{bin,api-key.env,logs,runs}`.

## Models

| HF / local | Served id | Practical ctx on 4090 |
|---|---|---|
| `google/gemma-4-12B-it-qat-w4a16-ct` | `gemma-4-12b-it-qat` (+ alias `qwen3.8-flash-next-iq3_s`) | **131072** |
| `google/gemma-4-31B-it-qat-w4a16-ct` | `gemma-4-31b-it-qat` | **~3072** (not for agents) |

## Docs in this repo

| File | What |
|---|---|
| [GEMMA4_12B_QAT_DOWNLOAD.md](GEMMA4_12B_QAT_DOWNLOAD.md) | HF download |
| [GEMMA4_12B_QAT_CUTOVER.md](GEMMA4_12B_QAT_CUTOVER.md) | 12B :8080 cutover |
| [GEMMA4_12B_QAT_FULL_SUITE.md](GEMMA4_12B_QAT_FULL_SUITE.md) | suite + wall ~46 |
| [GEMMA4_31B_QAT_DOWNLOAD.md](GEMMA4_31B_QAT_DOWNLOAD.md) | 31B download |
| [GEMMA4_31B_QAT_CUTOVER.md](GEMMA4_31B_QAT_CUTOVER.md) | 31B cutover |
| [GEMMA4_31B_QAT_FULL_SUITE.md](GEMMA4_31B_QAT_FULL_SUITE.md) | 31B suite |

## Quick re-cutover (12B)

On `berda@192.168.0.175` follow `archive-for-future-tests/LATEST/README.md`.
GPU1 stacks (8002–8006) stay up; only GPU0 / `:8080` swaps.

## Restore Strata (prod)

Disable both `gemma4-*-qat` units → unmask/restore `strata-iq3_s.service` →
`enable --now` → reboot optional → smoke `:8080` + GPU1 + public Bifrost.
