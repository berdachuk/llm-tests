# Strata IQ3_S — matrix: 1×4090 vs 4090+5060 Ti (`layer-split auto`)

Одинаковый quant IQ3_S, context advertise 262144, vision ON, `--kv-resident 32768`, `--spec 4` + MTP.  
Разница: **solo GPU0** vs **`--layer-split auto`** на GPU0+GPU1.

| | **1 GPU** (4090) | **2 GPU** (4090 + 5060 Ti) |
|---|---|---|
| Дата | 2026-10-15 ~07:23 UTC | 2026-10-15 ~09:12 UTC |
| Config | `gpu: 0` (без layer-split) | `gpu: [0,1]`, `layer_split: auto` |
| VRAM used (сумма) | ~**23.4 GiB** (только 4090) | ~**35.4 GiB** (≈24.0 + ≈11.3) |
| Артефакты | `strata-results/20261015-iq3s-full/matrix.csv` | `strata-results/20261015-iq3s-2gpu/matrix.csv` |

> Cold = rep=0 (первый проход). Warm = rep=1 (тот же промпт).  
> Prefill/decode — из harness `prefill_tps` / `decode_tps` (короткий gen на A–D → decode шумный).

---

## Prefill / TTFT (cold)

| Tier | prompt tok | **1GPU** TTFT s | **1GPU** prefill t/s | **2GPU** TTFT s | **2GPU** prefill t/s | Δ prefill |
|---|---:|---:|---:|---:|---:|---:|
| A ~1K | 1 251 | 3.38 | **376** | 3.18 | **400** | +6% |
| B ~4K | 5 229 | 3.69 | **1437** | 6.46 | **817** | **−43%** |
| C ~32K | 42 513 | 22.4 | **1903** | 34.0 | **1252** | **−34%** |
| D ~64K | 85 101 | 27.2 | **1931** | 41.1 | **1275** | **−34%** |
| E ~170K (pos10%) | 170 356 | 77.7 | **2076** | 61.0 | **1293** | **−38%** |
| E ~170K (pos90%) | 170 357 | 75.0 | **2055** | 75.0 | **1293** | **−37%** |
| F ~248K (calib, 1GPU only) | ~248 115 | ~78 | **~1990** | — | не калибровали | — |

На длинных промптах (B–E) **одна 4090 быстрее по prefill ~1.3–1.6×**.  
2GPU даёт чуть лучше только на крошечном A (~1K); дальше PCIe/pipeline layer-split съедает выигрыш.

Интересный outlier: E pos10% TTFT на 2GPU **короче** (61 s vs 78 s) при **меньшем** prefill t/s — в CSV у 2GPU `total_s=132` (длинный decode/thinking), у 1GPU `total=82`. Сравнивать лучше **prefill_tps**, не голый TTFT.

Warm TTFT (A–D): оба **~0.09–0.14 s** — prefix cache паритетен.

---

## Decode (cold, tok/s)

| Tier | **1GPU** | **2GPU** | Δ |
|---|---:|---:|---:|
| A | 52 | 44 | −15% |
| B | 55 | 47 | −15% |
| C | 58 | 51 | −12% |
| D | 61 | 54 | −11% |
| E pos10% | 75 | 77 | ≈0 |
| E pos90% | 123 | 95 | −23% |
| F calib (1GPU) | 110–154 | — | — |

На коротких ответах A–D decode у 2GPU **на ~10–15% ниже**. На E сопоставимо / чуть хуже. Для длинных ответов см. также live `/v1/status` на 2GPU: ~**63 tok/s** predicted на большом prompt — в том же диапазоне, что solo.

---

## Correctness (matrix)

| | 1GPU | 2GPU |
|---|---|---|
| A–D | 4/4 | 4/4 |
| E needles | **3/3** | **2/3** (pos50% fail: `pt=0` / empty в CSV) |
| F naive 262K | HTTP 400 | HTTP 400 |
| F calib ~248K | **3/3** after max_tokens=256 | не гоняли |

---

## Вывод

1. **Prefill:** 1×4090 ≈ **1.9–2.1k tok/s** на 40K–170K; 2GPU layer-split ≈ **1.25–1.3k tok/s** (−**34–38%**).
2. **Decode:** 2GPU не ускоряет solo-stream; обычно **−10–15%** vs 1GPU на этом matrix.
3. Layer-split на 4090+5060 Ti здесь **не про скорость одного запроса**, а про VRAM/expert cache / возможность держать больше state (сумма ~35 GiB vs 24). Для max single-user long-context throughput — **оставить одну 4090**.
4. 2GPU matrix оборвался на F без калибровки; E mid flake — имеет смысл перепрогнать E/F на 2GPU отдельно, если нужен паритет correctness.

Команды прогонов: `runs/.../run_matrix.py` на хосте; CSV выше.
