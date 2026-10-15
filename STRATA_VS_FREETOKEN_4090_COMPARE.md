# Strata IQ3_S vs FreeToken на RTX 4090 (`.88`)

> Сравнение **не apples-to-apples по модели**: разные семейства и кванты.  
> Цель — сопоставить **рабочий прод-стек FreeToken** с **прогоном Strata IQ3_S** на том же железе (GPU0 4090, 125 GB RAM).

| | **FreeToken** (baseline) | **Strata IQ3_S** (этот прогон) |
|---|---|---|
| Дата | 2026-09-19 (v0.1.3 + MM) | **2026-10-15** |
| Engine | FreeToken **0.1.3** | Strata **v0.1.44.1** |
| Model | `qwen3.6-35b-a3b` = Qwen3.6-35B-A3B-**FP8** | `qwen3.8-flash-next-iq3_s` = Flash-Next **IQ3_S** |
| Port | `:8000` | `:8080` |
| Context advertise | **262144** (`max_model_len`) | **262144** (`meta.n_ctx`) |
| Vision | ON (+~0.5 GiB VRAM) | ON (mmproj BF16) |
| Источники | [`run-freetoken013-mm-final-20260919.md`](qualbench/results/run-freetoken013-mm-final-20260919.md), [`FREETOKEN_QWEN36_SERVE.md`](FREETOKEN_QWEN36_SERVE.md), [`TEST_RESULTS.md`](TEST_RESULTS.md) | [`STRATA_IQ3S_4090_TEST_REPORT.md`](STRATA_IQ3S_4090_TEST_REPORT.md), `strata-results/20261015-iq3s-full/` |

---

## 1. Железо / footprint

| Метрика | FreeToken FP8 | Strata IQ3_S |
|---|---|---|
| GPU0 VRAM used | ~**23.1–23.7 GiB** (почти полный 24 GB) | ~**23.4 GiB** (23970 MiB) |
| GPU0 free | ~0.2–1.0 GiB | ~**114 MiB** |
| Host RAM under load | MoE offload (experts в RAM; типично десятки GiB) | ~**62 GiB** (experts ~47 GiB + KV stream) |
| KV strategy | `--kv-reserve-tokens 300000` (пол в VRAM до expert cache) | KV **streaming в RAM**, `--kv-resident 32768` |
| Concurrent requests | max **4** | по умолчанию **1** (batching off) |

Оба упираются в потолок 4090. FreeToken оставляет чуть больше «воздуха» под concurrent KV; Strata IQ3_S агрессивнее заполняет VRAM expert cache + почти нулевой free.

---

## 2. Совместимость API / agentbench

Одинаковый фильтр: `pytest agentbench/tests -m "not slow and not concurrency"`.

| | FreeToken (документированный профиль) | Strata 2026-10-15 |
|---|---|---|
| Быстрый agentbench | Зелёный core (chat/tools/stream); suite заточен под FT | **50 passed / 5 failed / 3 skipped** |
| `/v1/models` context field | `max_model_len` / `context_length` | `meta.n_ctx` (тест FT падает) |
| `/v1/messages/count_tokens` | поддерживается | **401** в этом прогоне |
| `tool_choice=required` | documented gap (xfail) | иное поведение → strict fail |
| Inline `<\|think_off\|>` | documented FT parser gap (xfail) | иное → strict fail |
| Chat template checks | froggeric path | skipped (нет `AGENTBENCH_TEMPLATE_PATH`) |
| Agentic bugfix final summary | обычно OK на FT | 1 fail (tool_calls без final content) |

**Вывод:** для coding-agents FreeToken сейчас **более «притёрт»** к agentbench/Bifrost (поле context, count_tokens, ожидаемые xfail). Strata закрывает основные протоколы (chat/responses/messages/tools/stream), но 5 fails — в основном **контракт API / тест-ожидания FT**, не полный отказ качества.

---

## 3. Качество (qualbench / long-context)

| Suite | FreeToken | Strata |
|---|---|---|
| qualbench 50 (text) | **47/50** (MM-on, 0 avoidable regressions) | **не гонялся** в этом окне |
| long-context category | **10/10**, вкл. **150K** pos10/pos50 (~87–98 s/task) | своя matrix: needle **E ~170K** 3/3, **F ~248K** 3/3 (после калибровки) |
| Vision smoke | color ID OK (runbook) | 1×1 PNG → «Black» OK |
| Full MMMU / Video-MME | есть отдельные прогоны на FT | не гонялись |

Честное сравнение quality на одинаковых 50 задачах **пока невозможно** — нужен qualbench на Strata. По long-context retrieval Strata показал needle recall выше типичного qualbench ceiling (150K → **248K**).

---

## 4. Производительность (ориентиры)

| Метрика | FreeToken (runbook / longctx) | Strata IQ3_S (matrix) |
|---|---|---|
| Decode tok/s | типично **40–80** | **~50–150** (короткие ответы / draft) |
| Prefill tok/s | до ~**1500** (runbook) | **~1900–2100** на 40K–250K cold |
| TTFT ~40K prompt | — | ~**22 s** cold |
| TTFT ~85K | — | ~**27 s** cold |
| TTFT ~170K | ~87–98 s wall на 150K tasks (qualbench, с генерацией) | ~**75–82 s** TTFT needle |
| TTFT ~248K | native 262K не отдельно бенчили в matrix | ~**78 s** TTFT |
| Warm prefix cache | есть | TTFT **&lt;0.15 s** на повтор A–D |

Strata выглядит **быстрее на prefill** длинных промптов в этом прогоне; decode сопоставим/чуть выше на коротких генерациях (с MTP/spec). Абсолютные цифры зависят от длины ответа и reasoning.

---

## 5. Context ceiling (практика)

| | FreeToken | Strata IQ3_S |
|---|---|---|
| Advertised | 262144 | 262144 |
| Verified in suite | 150K tasks pass; full 262K «не независимо верифицирован» как single needle matrix | **~248K** prompt + needle OK; сырой filler на 262K → **HTTP 400** (template overhead) |
| Risk | мало free VRAM при больших concurrent | мало free VRAM; single-flight по умолчанию |

---

## 6. Когда что брать

| Сценарий | Рекомендация |
|---|---|
| Прод Bifrost / coding agents / qualbench-паритет | **FreeToken** `qwen3.6-35b-a3b` |
| Макс. однопользовательский long-context / Flash-Next quality ladder | **Strata IQ3_S** (и дальше Q2_0 / IQ2_XS A/B) |
| Multimodal image в agent path | оба умеют; FT уже вшит в serve unit + qualbench-mm |
| Несколько параллельных запросов | **FreeToken** (max 4); Strata — включать parallel осознанно |

---

## 7. Ограничения сравнения

1. **Разные модели** (3.6-35B-A3B FP8 vs 3.8-Flash-Next IQ3_S) — главная оговорка.
2. Strata **без** полного qualbench-50 в этом окне.
3. agentbench на Strata гонялся через SSH tunnel; FT — напрямую `:8000`.
4. FreeToken сейчас **остановлен** (restore: `FREETOKEN_88_RESTORE.md`); цифры FT — из сентябрьских артефактов, не side-by-side в один день.

---

## 8. Следующие шаги (если добивать паритет)

1. Поднять FreeToken обратно → тот же agentbench filter → таблица fail-by-fail.
2. Прогнать `qualbench` categories `mcp-tools` + `long-context` на Strata (как в плане §8).
3. Опционально: короткий decode A/B на одинаковом 4K prompt (одинаковый `max_tokens`, thinking off) для чистого tok/s.
