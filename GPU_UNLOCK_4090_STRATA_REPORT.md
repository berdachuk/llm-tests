# gpu-unlock on RTX 4090 vs Strata IQ3_S — report (`.175`)

Date: **2026-10-31**. Run: `/mnt/data/strata/runs/20261031-gpu-unlock/`  
Local: `strata-results/20261031-gpu-unlock/`.  
Plan: [`GPU_UNLOCK_4090_STRATA_EXPERIMENT.md`](GPU_UNLOCK_4090_STRATA_EXPERIMENT.md).

## Verdict

**Neutral — no meaningful Strata IQ3_S speedup.** Unlock on Ada 4090 succeeded
(`SS0=0x88888888`, `SS1=0x8`). Prefill deltas are noise (**~0–1%**). Decode and
qualbench wall unchanged. **Rollback proved:** cmdline without
`gpu_unlock.targets`, no `unlocked` line, Strata `PONG` OK.

Hypothesis from README (quantized GGUF / memory-bound path ≈ 0–15%, decode 0%)
**confirmed** for this stack.

| Gate | Result |
|---|---|
| Unlock journal `unlocked` on `0000:01:00.0` | **PASS** |
| 5060 Ti untouched | **PASS** (not in recipe; not targeted) |
| Prefill C/E ≥ +15% | **FAIL** (≈ 0–1%) |
| Qualbench wall ≤ −10% | **FAIL** (645 s vs ~644 s baseline) |
| Rollback (no targets → no unlock) | **PASS** |

## Setup

| Item | Value |
|---|---|
| Package | `gpu-unlock-dkms` / `gpu-unlock-firmware` **2.0.0** |
| Target | `gpu_unlock.targets=0000:01:00.0` only |
| Kernel | `7.0.0-38-generic`, `nvidia-595-open` |
| Strata | v0.2.7.1 / 0.1.53, `qwen3.8-flash-next-iq3_s` |
| After experiment | packages **installed**, cmdline **without** targets (inert) |

## Monitor

| Cell | Locked prefill / decode | Unlocked prefill / decode | Δ prefill |
|---|---|---|---|
| warm ~26K | **1767** / 117 | **1769** / 95 | ~0% |
| reuse ~13K | **1716** / 144 | **1716** / 122 | ~0% |
| decode probe 256 tok | 155 / **128** | 119 / **114** | n/a (decode flat/noise) |

## Matrix (cold rep=0)

| Tier | Locked prefill | Unlocked prefill | Δ |
|---|---:|---:|---:|
| B ~5K | 1431 | 1429 | ~0% |
| C ~42K | 1920 | 1927 | +0.3% |
| D ~85K | 1942 | 1952 | +0.5% |
| E ~170K (mean of 3 pos) | ~2073 | ~2090 | ~+0.8% |

F raw 262K → 400 both sides. F-calib ~248K needles **3/3** both sides.

## Qualbench-50 (unlocked)

[`qualbench/results/run-strata-iq3s-gpu-unlock-full50-20261031-142156.md`](qualbench/results/run-strata-iq3s-gpu-unlock-full50-20261031-142156.md)

- **48/50** @ **645.1 s** (sql 5/6, security 7/8 — flaky vs prior 50/50; not a speed signal)
- Prior locked recheck **50/50** @ **644 s** (2026-10-30)

Wall time essentially identical.

## Rollback proof

1. Removed `gpu_unlock.targets=0000:01:00.0` from GRUB → `update-grub` → reboot.
2. Cmdline: `quiet splash` only (no targets).
3. Journal: module loads/taints, **no** `gpu_unlock: unlocked`.
4. Strata up; Monitor warm prefill **1775**; chat **`PONG`**.

Re-enable later: add targets back to GRUB + reboot (packages already present).

## Recommendation

Do **not** leave unlock enabled for Strata IQ3_S prod — no benefit, Ada experimental
path + kernel taint. Keep packages installed with cmdline off for future non-IQ3
experiments (BF16 fine-tune / SD) if desired.
