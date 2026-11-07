# Temporary Gemma-4 12B QAT cutover (.175 :8080)

Replaces **Gemma-4 31B QAT** (and still keeps Strata IQ3_S masked) on **GPU0 only**.
GPU1 stacks stay on nvidia-guard compose.

## Why switch 31B → 12B

31B W4A16 fits the 4090 only at **`max-model-len≈3072`** — not efficient for real agent / OpenCode work (need ≥**32K**, prefer **128K**). 12B is an **allowed** competition QAT variant and leaves ~13 GB for KV.

## Live path

```
Client → https://llm.avroflex.ru/v1  (Bifrost)
       → llm-88 → https://llm-88.berdachuk.com/v1
       → nginx .51 → http://192.168.0.175:8080  (vLLM Gemma 12B)
```

| Item | Value |
|---|---|
| Unit | `gemma4-12b-qat.service` (user; **disabled** after restore 2026-11-07) |
| Previous | `gemma4-31b-qat.service` **disabled** |
| Strata | **restored** on `:8080` (see [`STRATA_RESTORE_20261107.md`](STRATA_RESTORE_20261107.md); archive [`GEMMA4_FUTURE_TESTS.md`](GEMMA4_FUTURE_TESTS.md)) |
| Model path | `/mnt/data/berda-models/huggingface/google/gemma-4-12B-it-qat-w4a16-ct` |
| Served ids | `gemma-4-12b-it-qat` + alias `qwen3.8-flash-next-iq3_s` |
| Context | **`max-model-len=131072`** (live; smoke OK) |
| Util | `0.95`, `max-num-seqs=1`, tool-parser `gemma4` |
| VRAM GPU0 | ~**23239** MiB / 24564 |
| Auth | same Strata API key |
| Smoke | `/v1/models` + chat `pong` on both ids — **PASS** (2026-11-07) |

## nvidia-guard

Prefer `gemma4-12b-qat` when enabled; else fall back to `gemma4-31b-qat`; else Strata.
Backup: `/usr/local/sbin/restart-gpu-services.sh.bak-pre-gemma4-12b-*`.

## Roll back to 31B

```bash
systemctl --user disable --now gemma4-12b-qat.service
systemctl --user enable --now gemma4-31b-qat.service
# note: restore serve defaults / GEMMA4_* if 31B unit still expects 3072 via env
```

## Restore Strata

Same as 31B cutover: disable Gemma unit(s), unmask `strata-iq3_s.service`, restore bak, `enable --now`.
