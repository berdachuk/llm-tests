# Эксперимент: gpu-unlock на RTX 4090 vs Strata IQ3_S (`.175`)

> **Статус:** выполнен **2026-10-31** — см. [`GPU_UNLOCK_4090_STRATA_REPORT.md`](GPU_UNLOCK_4090_STRATA_REPORT.md) (**neutral**, rollback OK).  
> **План:** Cursor `gpu_unlock_strata_exp`  
> **Цель:** A/B locked vs unlocked tensor-rate; обязательный откат cmdline.

## Scope

- Unlock only `0000:01:00.0` (4090 AD102). Not 5060 Ti.
- Metrics: Monitor, decode probe, matrix A–E + F-calib, qualbench-50 (unlocked); locked baseline + post-rollback smoke.
- Run dir: `/mnt/data/strata/runs/20261031-gpu-unlock/`
- Local mirror: `strata-results/20261031-gpu-unlock/`

## Outcome (short)

| Gate | Result |
|---|---|
| Unlock journal on 4090 | **PASS** (`SS0=0x88888888`) |
| Prefill C/E ≥ +15% | **FAIL** (~0–1%) |
| Qualbench wall ≤ −10% | **FAIL** (645 s ≈ 644 s baseline) |
| Rollback (no `targets=`) | **PASS** — Strata `PONG`, no `unlocked` |

**Prod:** packages may stay installed; GRUB **without** `gpu_unlock.targets`.

## Rollback

Remove `gpu_unlock.targets=…` from GRUB → `update-grub` → reboot. Packages may remain; without targets module is inert.
