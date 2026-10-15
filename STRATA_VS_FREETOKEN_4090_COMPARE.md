# Strata IQ3_S vs FreeToken на RTX 4090 (`.88`)

> Сравнение **не apples-to-apples по модели**: разные семейства и кванты.  
> Цель — сопоставить **бывший прод FreeToken** с **Strata IQ3_S** на том же железе.  
> **Прод сейчас:** Strata **1×4090** на `:8080` (Bifrost `llm-88/qwen3.8-flash-next-iq3_s`). FreeToken выключен.

| | **FreeToken** (baseline) | **Strata 1×4090** (prod) | **Strata 2×GPU** (test window) |
|---|---|---|---|
| Дата | 2026-09-19 (v0.1.3 + MM) | **2026-10-15** | **2026-10-15** |
| Engine | FreeToken **0.1.3** | Strata **v0.1.44.1** | Strata **v0.1.44.1** |
| Model | `qwen3.6-35b-a3b` FP8 | Flash-Next **IQ3_S** (`qwen3.8-flash-next-iq3_s`) | Flash-Next **IQ3_S** |
| GPUs | GPU0 4090 | GPU0 4090 | **GPU0+1**, `layer_split=auto` (card order **1,0**) |
| Port | `:8000` (off) | `:8080` | `:8080` (LAN monitor) |
| Context | **262144** | **262144** (практика ~**248K**) | **262144** |
| Vision | ON | ON | ON (smoke PASS) |
| Отчёты | [`run-freetoken013-mm-final-20260919.md`](qualbench/results/run-freetoken013-mm-final-20260919.md) | [`STRATA_IQ3S_4090_TEST_REPORT.md`](STRATA_IQ3S_4090_TEST_REPORT.md), morning [`…113238.md`](qualbench/results/run-strata-iq3s-full50-20261015-113238.md), prod [`…prod…135743.md`](qualbench/results/run-strata-iq3s-prod-full50-20261015-135743.md) | [`STRATA_IQ3S_2GPU_4090_5060TI_TEST_REPORT.md`](STRATA_IQ3S_2GPU_4090_5060TI_TEST_REPORT.md), [`…121142.md`](qualbench/results/run-strata-iq3s-2gpu-full50-20261015-121142.md) |

---

## 1. Железо / footprint

| Метрика | FreeToken FP8 | Strata 1×4090 | Strata 2×GPU |
|---|---|---|---|
| GPU0 4090 used | ~**23.1–23.7 GiB** | ~**23.4 GiB** | ~**23.4–23.5 GiB** |
| GPU1 5060 Ti used | ASR/embed (отд.) | idle / ASR restore | ~**8.5–11.3 GiB** (layers 0–2) |
| Host RAM under load | MoE offload | ~**62 GiB** | ~**60–61 GiB** |
| KV strategy | `--kv-reserve-tokens 300000` | KV stream + `--kv-resident 32768` | same |
| Concurrent requests | max **4** | **1** | **1** |

2×GPU split (auto): layers **0–2 @ 5060 Ti**, **3–47 + head/MTP @ 4090**.

---

## 2. Совместимость API / agentbench

| | FreeToken | Strata 1×4090 | Strata 2×GPU |
|---|---|---|---|
| agentbench fast | зелёный core (suite под FT) | **50 pass / 5 fail / 3 skip** | **49 pass / 6 fail / 3 skip** |
| context field | `max_model_len` | `meta.n_ctx` | `meta.n_ctx` |
| `count_tokens` | OK | **401** | **401** |
| qualbench mcp-tools | **8/8** | **8/8** | **8/8** |

**Вывод:** API-расхождения Strata vs FreeToken те же на 1× и 2×. Layer split не чинит контракт.

---

## 3. Качество — полный qualbench-50 (text)

| Category | FreeToken | Strata 1×4090 | Strata 2×GPU | Wall FT → 1× → 2× |
|---|---|---|---|---|
| **Total** | **47/50** | **50/50** | **50/50** | **2372 → 711 → 966 s** |
| java-spring | 9/10 | **10/10** | **10/10** | 613 → 83 → 95.5 |
| ts-angular | 8/8 | **8/8** | **8/8** | 408 → 62 → 60.6 |
| sql-migrations | 4/6 | **6/6** | **6/6** | 362 → 61 → 48.2 |
| mcp-tools | 8/8 | **8/8** | **8/8** | 48 → 15 → 23.5 |
| security-review | 8/8 | **8/8** | **8/8** | 319 → 93 → 108.1 |
| long-context | 10/10 | **10/10** | **10/10** | 623 → **397** → **630** |

FT fails: java `07-money`, sql `04`+`05`. На обоих Strata — **0/50** avoidable fails.

**Прод re-check** (после reboot, тот же id, LAN `:8080`): снова **50/50** за **685 s**
([`run-strata-iq3s-prod-full50-20261015-135743.md`](qualbench/results/run-strata-iq3s-prod-full50-20261015-135743.md)) —
категории: java 79 / ts 54 / sql 44 / mcp 15 / security 95 / long-context **398** s.

**Вывод:** score одинаковый (**50/50**). **Скорость лучше у 1×4090** (~685–711 s). 2×GPU ~**1.36× медленнее** 1×, в основном из‑за long-context. Оба Strata быстрее FreeToken (~3.3–3.5× / ~2.5×).

---

## 4. Производительность

| Метрика | FreeToken | Strata 1×4090 | Strata 2×GPU |
|---|---|---|---|
| Full qualbench-50 wall | **~2372 s** | **685–711 s** | **966 s** |
| long-context category | **623 s** | **397–398 s** | **630 s** |
| 150K task wall | ~87–98 s | ~**77–98 s** | ~**122–135 s** |
| Prefill ~32–65K (cold, matrix) | до ~1500 | ~**1900–1930** | ~**1250–1275** |
| Prefill ~170–248K | — | ~**1990–2075** | ~**1260–1295** |
| Prefill short Monitor prompt | — | ~**100–400** (нормально) | — |
| Decode (matrix / answers) | **40–80** | **~50–150** | **~45–145** |

---

## 5. Context ceiling

| | FreeToken | Strata 1×4090 | Strata 2×GPU |
|---|---|---|---|
| Advertised | 262144 | 262144 | 262144 |
| Practical prompt (OpenCode) | — | **248000** | — |
| qualbench verified | **150K** | **150K** | **150K** |
| Needle ~170K (E) | — | **3/3** | **3/3** (1 flake mid → retry OK) |
| Needle ~248K (F calib) | — | **3/3** | **3/3** |
| Raw filler 262K | — | HTTP **400** | HTTP **400** |
| Risk | concurrent KV | мало free VRAM | PCIe split → ниже prefill |

---

## 6. Когда что брать

| Сценарий | Рекомендация |
|---|---|
| Прод Bifrost / OpenCode / chat | **Strata 1×4090** (`qwen3.8-flash-next-iq3_s`) |
| Qualbench text quality / speed | **Strata 1×4090** (50/50, ~685–711 s) |
| Long-context агенты на этом хосте | **Strata 1×4090** (2× split замедляет) |
| Занять обе карты под один LLM | 2×GPU работает, score паритетен, но **не ускоряет** |
| Параллельные запросы (max 4) | только если вернуть **FreeToken** |
| GPU1 под ASR/embeddings | не отдавать под layer split |

---

## 7. Ограничения

1. Разные модели (3.6-35B-A3B FP8 vs 3.8-Flash-Next IQ3_S).
2. FT сентябрь / Strata октябрь — не один день.
3. FreeToken остановлен; прод на Strata (`STRATA_88_PRODUCTION.md`).
4. Multimodal suite на Strata не гонялся (только vision smoke).
5. agentbench: часть fails из‑за контракта API Strata vs suite под FreeToken.

---

## 8. Следующие шаги

1. ~~Полный text qualbench-50 на 1× и 2×~~ — done.
2. ~~Context matrix 2× (A–F + calib)~~ — done.
3. ~~Прод cutover Bifrost + autostart после reboot~~ — done.
4. ~~Прод re-check qualbench-50~~ — **50/50 @ 685 s**.
5. agentbench fail-by-fail vs поднятый FreeToken (опционально).
6. Confirm ASR/embed Docker на GPU1 после reboot, если нужен.
