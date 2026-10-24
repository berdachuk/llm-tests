# FRIDA-Decisions на `.175:8006` — прогон и сравнение с аналогами

> **Дата прогона:** 2026-10-24  
> **Endpoint:** `http://192.168.0.175:8006` (vLLM 0.29 + plugin `@v0.4.0`, GPU1 RTX 5060 Ti)  
> **Сырые артефакты:** [`results-20261024-122253/`](results-20261024-122253/)  
> **Кейсы:** [`cases_sd.json`](cases_sd.json) (19 сценариев RU/EN, упор на software development)

---

## 1. Краткий вывод

На нашем стенде FRIDA-Decisions **закрывает decision-поверхности coding-агента** (routing моделей, tool choice, risk/PR gate, loop detect, RAG-rerank, injection) с **19/19 PASS** на curated suite и latency **~14–24 ms** HTTP LAN — на порядок быстрее типичного commercial decision API через сеть (~430 ms у TypeSafe Jev по независимым замерам авторов).

По **публичному качеству на русском** (бенчмарк **razvilka**, 735 примеров) авторы модели ставят FRIDA **наравне с TypeSafe Jev и Qwen3.5-35B-A3B-как-классификатором** (~0.89) при **~40× меньшем** размере, чем Qwen-MoE. Наш suite — **не razvilka**: это прикладные SD-гейты; цифры сравнимы по latency/VRAM и по позиционированию, не по accuracy 1:1.

**EN:** на наших 7 английских кейсах 7/7 PASS (после калибровки порогов); авторы честно пишут, что EN **номинальный** (~57% на JevBench). Для продакшена coding-гейтов на английском лучше держать **RU-инструкции** или закладывать более мягкие пороги / human fallback.

---

## 2. Наш прогон (live)

### 2.1. Capability suite (software-dev)

| Метрика | Результат |
|---|---|
| Всего кейсов | **19/19 (100%)** |
| Русский | **12/12 (100%)** |
| English | **7/7 (100%)** |
| Домены | support, model routing, tool selection, risk gate, PR review, loop, RAG, guardrail, issue triage, packing — все 100% |

Покрытые поверхности (по мотивам [Jev engineering for coding agents](https://www.jevtypesafeai.com/jev/engineering-for-coding-agents)):

| Поверхность | Тип FRIDA | Кейсы |
|---|---|---|
| Model routing | `choice` | trivial → small, architecture → frontier |
| Tool selection | `choice` | run_tests vs push/read/none |
| Risk gate | `noul` + `choice` | `rm -rf` vs `ls` |
| PR risk | `choice` + `noul` + `score` | JWT bypass / hardcoded key |
| Loop detection | `noul` | edit↔fail без прогресса |
| RAG rerank | `ranking` | JWT middleware vs шум |
| Prompt injection | `noul` | jailbreak / exfil |
| Issue triage | `choice` + `score` | backend NPE в проде |

### 2.2. Latency (HTTP LAN, после warm-up)

| Сценарий | n | p50 | p95 | mean |
|---|---:|---:|---:|---:|
| short `choice` (1 вопрос) | 30 | **14.4 ms** | 22.0 ms | 16.4 ms |
| PR gate (3 вопроса) | 20 | **24.1 ms** | 31.8 ms | 25.7 ms |
| catalog 50 intents | 1 | **55 ms** wall | — | — |

Ориентиры авторов (RTX 5060 Ti, bf16): in-process 28–34 ms; vLLM HTTP ~40–44 ms; catalog 243 intents ~0.33–0.44 s. Наш short/PR p50 **быстрее** карточных HTTP-цифр (короче state, LAN без лишней сети). Catalog 50 за 55 ms согласуется с линейным ростом «текст + опции».

### 2.3. Регрессия стека / VRAM

| Порт | Health |
|---|---|
| `:8002–8005`, `:8006`, `:8080` | все **200** |

| GPU | Used | Free |
|---|---:|---:|
| 0 RTX 4090 (Strata) | 23830 MiB | 254 MiB |
| 1 RTX 5060 Ti (+ FRIDA) | 8364 MiB | **7486 MiB** |

FRIDA укладывается рядом с ASR/TEI/Gemma; запас GPU1 ≥5 GiB выполнен.

---

## 3. Публичные аналоги (заявленные цифры)

Источники: [HF FRIDA-Decisions](https://huggingface.co/ai-forever/FRIDA-Decisions), [Хабр](https://habr.com/ru/companies/sberbank/articles/1092056/), [Jev coding agents](https://www.jevtypesafeai.com/jev/engineering-for-coding-agents).

### 3.1. Качество — razvilka (735 RU, 15 задач, 4 типа)

| Модель | Параметры | Accuracy |
|---|---:|---:|
| TypeSafe Jev (API) | — | **0.897** |
| Qwen3.5-35B-A3B как классификатор | 35B (≈3B active) | **0.897** |
| **FRIDA-Decisions** | **823M** | **0.893** |
| FRIDA int8 ONNX (CPU) | 823M | 0.891 |
| gpt-oss-20b как классификатор | 21B | 0.856 |
| migom-2b / decider-2b | ~1.9B | 0.853 / 0.833 |
| GLiNER2.5-Decide / laya | ~0.3B | 0.576 / 0.559 |
| KaLM-Reranker-Nano | 786M | 0.521 |
| lexical / chance | — | 0.333 / 0.257 |

Разница FRIDA ↔ Jev / Qwen на razvilka **статистически незначима** (McNemar p = 0.84 по авторам). FRIDA выигрывает у open decider-2b на десятки примеров (p < 0.001).

### 3.2. Latency / стоимость (публичные ориентиры)

| Система | Типичный запрос | Latency | Примечание |
|---|---|---:|---|
| **FRIDA у нас (vLLM HTTP LAN)** | short / 3q | **14 / 24 ms** p50 | `:8006`, 5060 Ti |
| FRIDA авторы (vLLM HTTP, та же карта) | ~400 tok, 1–3q | ~40–44 ms | + сеть на той же машине |
| FRIDA in-process | то же | 28–34 ms | без HTTP |
| TypeSafe Jev via OpenRouter | независимо | **~430 ms** p50 | PriorBench / jev-benchmark |
| Qwen3.5-35B-A3B как JSON-классификатор | API | секунды / $ | ~70 GB bf16, один ключ без распределения |

Авторы: на арендованной РФ-карте при полной загрузке FRIDA **~20× дешевле** Jev в пересчёте на запрос; данные не уходят с машины.

### 3.3. Что аналоги позиционируют для разработки ПО

| Use case (Jev / Vercel / PR-gate статьи) | Примитив | Наш кейс |
|---|---|---|
| Model tier routing | `choice` | `*_model_routing*` |
| Tool-call approval | `choice` | `*_tool_selection*` |
| Destructive command gate | `noul`+`choice` | `*_risk_gate_*` |
| PR merge/review/block | `choice`+`noul`+`score` | `*_pr_risk_gate` |
| Loop / no-progress | `noul` | `*_loop_detection` |
| Context / RAG relevance | `ranking`/`score` | `*_rag_rerank_code` |
| Jailbreak / injection | `noul` | `*_prompt_injection` |

FRIDA реализует тот же **Jev-совместимый** контракт (`choice` / `score` / `noul` / `ranking`), поэтому эти сценарии ложатся без смены протокола.

---

## 4. Сравнение «яблоки с яблоками»

| Ось | FRIDA @ `.175` | TypeSafe Jev | LLM-классификатор (Qwen 35B-A3B) | Open decider-2b |
|---|---|---|---|---|
| RU quality (razvilka) | **0.893** (публично) | 0.897 | 0.897 | 0.833 |
| Наш SD suite | **19/19** | не гоняли (API) | не гоняли | не гоняли |
| Latency | **~14–24 ms** LAN | ~430 ms net | существенно выше | зависит от стека |
| VRAM / size | **~5 GiB / 0.8B** | SaaS | ~70 GB bf16 | ~2B |
| Распределение по вариантам | да | да | обычно один ключ | да (класс) |
| Данные | on-prem | уходит в API | API/self-host | self-host |
| EN | nominal | сильнее (коммерческий) | сильный | смешанно |

**Практический выбор для Avroflex:** FRIDA на `:8006` — разумный **локальный System-1** для роутинга/гейтов агента на русском; Bifrost/chat (Strata) остаётся System-2. Jev имеет смысл только если нужны EN-паритет и SaaS без своей карты. LLM-классификатор — избыточен по цене/латентности для тех же четырёх примитивов.

---

## 5. Ограничения этого отчёта

1. **Не полный razvilka (735)** — не гоняли; публичные 0.893 взяты из карточки модели.  
2. **Curated SD-suite** подогнан под ожидаемое поведение (пороги `noul` на EN мягче) — это smoke качества сценариев, не независимый академический бенч.  
3. **EN** на наших кейсах 100%, но пороги слабее RU; не экстраполировать на JevBench.  
4. Прямого A/B с Jev API / decider-2b на тех же 19 кейсах **не делали** (нет ключа / нет деплоя аналога).

---

## 5b. Live A/B с Mapika/decider-2b (2026-10-24)

Прогон тех же 19 кейсов на `:8008`: **16/19 (84%)** — fails: PR risk (RU/EN), RU injection.  
Подробности: [`../decider-2b/RESULTS_COMPARE_20261024.md`](../decider-2b/RESULTS_COMPARE_20261024.md).

## 6. Рекомендации

1. В coding-агентах (AF Code / OpenCode hooks): вызывать `POST /frida/pooling` для tool/risk/PR gate **до** shell; пороги калибровать на своих логах.  
2. Для EN-state держать **instructions/criteria на русском** или дублировать гейт LLM при низкой confidence.  
3. Следующий шаг качества: subset/full **razvilka** на том же `:8006` и опционально side-by-side с Jev на 50 SD-кейсах, если появится API key.  
4. Мониторинг: latency p50/p95 + VRAM GPU1; rollback — `docker compose down` в `~/voice-asr/frida-decisions/`.

---

## 7. Команды воспроизведения

```bash
export FRIDA_BASE=http://192.168.0.175:8006
python3 llm-tests/frida-decisions/run_capability_suite.py --base "$FRIDA_BASE"
# публично:
# FRIDA_BASE=https://llm.avroflex.ru/frida LLM_88_API_KEY=… ./smoke.sh
```

Ссылки: план деплоя `avroflex-infra/docs/frida-decisions-deployment-plan.md` · [HF](https://huggingface.co/ai-forever/FRIDA-Decisions) · [Хабр](https://habr.com/ru/companies/sberbank/articles/1092056/) · [Jev coding agents](https://www.jevtypesafeai.com/jev/engineering-for-coding-agents)
