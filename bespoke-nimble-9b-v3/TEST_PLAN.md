# План теста: Bespoke-Nimble-9B-v3 (аналог FRIDA / decider-2b)

> **Дата:** 2026-10-24  
> **Статус:** ✅ прогон выполнен (research-only, CC BY-NC) — см. [`RESULTS_COMPARE_20261024.md`](RESULTS_COMPARE_20261024.md)  
> **Модель:** [`bespokelabs/Bespoke-Nimble-9B-v3`](https://huggingface.co/bespokelabs/Bespoke-Nimble-9B-v3)  
> **Код / recipe:** [bespokelabsai/nimble](https://github.com/bespokelabsai/nimble)  
> **Результат suite:** **19/19**; latency ~1.0 s / ~3.2 s (short / PR 3q)  
> **Образец прогонов:** FRIDA `:8006`, decider-2b `:8008`, Nimble `:8009`  
> **IaC:** `avroflex-infra/llm-88/bespoke-nimble-9b-v3/`

---

## 1. Цель

Прогнать **тот же SD capability suite** (`frida-decisions/cases_sd.json`, 19 кейсов RU/EN) против Nimble-v3 и сравнить side-by-side с FRIDA и decider-2b:

| Ось | FRIDA | decider-2b | **Nimble-v3** |
|---|---|---|---|
| Live suite | 19/19 | 16/19 | **19/19** |
| razvilka / Decision Index | 0.893 (razvilka) | 0.833 (razvilka) | **DI 0.2.1 = 56.88** (авторы) |
| Размер | 0.8B encoder | 2B | **9B + LoRA** на Qwen3.5-9B |
| Лицензия | MIT | Apache-2.0 | **CC BY-NC 4.0** (не коммерция) |

**Важно для Avroflex:** v3 под **CC BY-NC** — тест/research OK; прод/клиентский billing — **нельзя** без другой лицензии. Для продакшена смотреть v4 API или другую open-модель.

---

## 2. Что такое модель

- Jev-style / System One: `state` + typed questions → вероятности по опциям, **без генерации текста**.
- LoRA на `Qwen/Qwen3.5-9B`; scorer читает логиты candidate tokens → softmax.
- Типы: choice (enum), noul (bool); score через ordered levels / expected value из probs (как в recipe).
- Контекст: до ~8k tokens/вопрос в поздних релизах; train часто до 2k.
- Inference: `CudaCandidateScorer` / `ParallelScorer` (см. README nimble); опционально Ollama `nimble` (исторически v2).
- v3 (2026-10-06): #1 open &lt;25B на Decision Index на момент релиза (по авторам); v4 уже сильнее на API.

---

## 3. Железо и порт

| | Значение |
|---|---|
| Host | `192.168.0.175`, **GPU1** RTX 5060 Ti 16 GiB |
| Порт | **`:8009`** (8006=FRIDA, 8007=Nemotron бронь, 8008=decider-2b) |
| Bind | `192.168.0.175` only |
| HF cache | `/mnt/data/berda-models/huggingface` |

### VRAM (оценка)

| Режим | Ориентир | На 5060 Ti 16 GiB |
|---|---:|---|
| BF16 full | ~18–19 GiB | ❌ |
| **Q8_0** (как в старом плане) | ~10–11 GiB | ✅ exclusive |
| Q4_K_M | ~6–7 GiB | ✅; качество проверить |

**Режим теста:** **exclusive GPU1** — stop Speaches / GigaAM / TEI / EmbeddingGemma / FRIDA / decider на время load+suite (как в старом Nimble-плане). GPU0 Strata **не трогать**.

После load: free ≥ **2 GiB**.

---

## 4. Топология теста (минимум LAN)

```text
Тестер
  └─ POST http://192.168.0.175:8009/v1/systemone   # или /v1/score → адаптер
       → Docker/Ollama/CudaScorer wrapper
       → GPU1 exclusive

Опционально позже:
  nginx .51 /nimble/ → :8009
  Traefik llm.avroflex.ru/nimble  (только если лицензия позволит прод)
```

Публичный path **не обязателен** для DoD теста; достаточно LAN + отчёт.

---

## 5. API и адаптер кейсов

Upstream schema Nimble (enum / boolean fields) ≠ FRIDA `questions` 1:1, но близко к TypeSafe `/v1/systemone`.

| FRIDA / cases_sd | Nimble | Действие адаптера |
|---|---|---|
| `choice` + `criteria` map | enum field | ключи → choices |
| `noul` + true/false criteria | boolean | map |
| `score` + levels list | ordered enum / expected score | map levels → choices; expect по score/choice |
| `ranking` | нет | **remap → choice** (как у decider) |

Артефакты кода (создать при имплементации):

```text
llm-tests/bespoke-nimble-9b-v3/
  TEST_PLAN.md                 # этот файл
  run_capability_suite.py      # POST systemone + remap ranking
  # --cases ../frida-decisions/cases_sd.json
  results-YYYYMMDD-HHMMSS/
  RESULTS_COMPARE_YYYYMMDD.md  # колонка vs FRIDA / decider
```

IaC (при деплое): `avroflex-infra/llm-88/bespoke-nimble-9b-v3/` — Dockerfile/compose/smoke по образцу decider, порт 8009.

---

## 6. Этапы прогона

### Этап 0 — Legal / scope

- [x] Зафиксировать: прогон **research-only** (CC BY-NC).
- [x] Не включать в Bifrost prod allowlist без legal OK.

### Этап 1 — Веса и runtime

- [x] Pre-seed HF: `Qwen/Qwen3.5-9B` + `bespokelabs/Bespoke-Nimble-9B-v3` (LoRA) в `/mnt/data/berda-models/huggingface`.
- [x] Runtime: **CudaCandidateScorer** + FastAPI `/v1/systemone` (`device_map` + 12 GiB GPU budget).
- [x] Не chat-completions decode.

### Этап 2 — Exclusive up

- [x] `docker compose stop` для: speaches, gigaam, embedding, embeddinggemma-2, frida-decisions, decider-2b.
- [x] Up nimble `:8009`; `/health` 200; free ≥2 GiB (~5.4 GiB free).
- [x] Smoke: choice + noul + score.

### Этап 3 — Capability suite (как FRIDA/decider)

- [x] `python3 run_capability_suite.py --base http://192.168.0.175:8009` → **19/19**
- [x] Отчёт: total / RU / EN / by domain / failures.
- [x] Latency: short n=20; PR 3q n=15 (catalog 50 — skip; latency уже ~1 s/field).
- [x] Гейты мягкие: 100% без `--gate`.

### Этап 4 — Сравнение

См. [`RESULTS_COMPARE_20261024.md`](RESULTS_COMPARE_20261024.md):

| Метрика | FRIDA | decider-2b | Nimble-v3 |
|---|---|---|---|
| suite pass | 19/19 | 16/19 | **19/19** |
| RU / EN | 12/12 / 7/7 | 10/12 / 6/7 | **12/12 / 7/7** |
| p50 short / 3q | 14 / 24 ms | 20 / 53 ms | **1009 / 3162 ms** |
| VRAM | ~8 GiB | ~9 GiB | ~10.4 GiB + offload |
| License | MIT | Apache-2.0 | CC BY-NC |

Ожидаемые риски fails (гипотезы до прогона):

- PR / injection с порогами FRIDA на `noul` — как у decider при extreme T.
- Ranking только через remap → choice.
- EN может быть сильнее FRIDA (Qwen3.5 base); RU — проверить отдельно.

### Этап 5 — Tear-down

- [x] `docker compose down` nimble.
- [x] Поднять обратно ASR/TEI/Gemma (FRIDA/decider оставлены stopped).
- [x] Regression health `:8002–8005`, `:8080`.

---

## 7. DoD теста

- [x] LAN smoke choice/noul/score на `:8009`
- [x] Capability 19 кейсов прогнаны; markdown отчёт с колонкой vs FRIDA/decider
- [x] Latency p50/p95 записаны
- [x] VRAM snapshot + exclusive список остановленных сервисов
- [x] Явная пометка **CC BY-NC / research-only** в отчёте
- [x] Стек GPU1 восстановлен после теста

**Вне скоупа этого плана:** Bifrost prod provider, Traefik public, Decision Index full suite, обучение, v4 API.

---

## 8. Команды (черновик)

```bash
# Exclusive
for d in speaches gigaam embedding embeddinggemma-2 frida-decisions decider-2b; do
  ssh berda@192.168.0.175 "cd ~/voice-asr/$d && docker compose stop"
done

# After wrapper exists:
export NIMBLE_BASE=http://192.168.0.175:8009
./smoke.sh
python3 llm-tests/bespoke-nimble-9b-v3/run_capability_suite.py --base "$NIMBLE_BASE"

# Restore
ssh berda@192.168.0.175 'sudo /usr/local/sbin/restart-gpu-services.sh'  # или compose up по проектам
```

---

## 9. Связанные документы

| Документ | Роль |
|---|---|
| [HF Bespoke-Nimble-9B-v3](https://huggingface.co/bespokelabs/Bespoke-Nimble-9B-v3) | веса v3, DI 56.88 |
| [github.com/bespokelabsai/nimble](https://github.com/bespokelabsai/nimble) | scorers, data, recipe |
| `avroflex-infra/docs/bespoke-nimble-9b-deployment-plan.md` | старый exclusive deploy (обновить → v3 / `:8009`) |
| `frida-decisions/cases_sd.json` | единый набор кейсов |
| `decider-2b/RESEARCH_EMBEDDINGGEMMA2_LOCAL_JEV.md` | альтернатива на эмбеддингах |

---

## 10. Рекомендация порядка работ

1. Сначала закрыть A/B FRIDA↔decider (отчёты уже есть; FRIDA/decider сейчас stopped).  
2. Отдельное окно exclusive GPU1 под Nimble-v3 Q8 + этот TEST_PLAN.  
3. По результатам: если suite ≥ decider и latency приемлема — оставить research endpoint; в прод Avroflex **не** ставить из‑за NC license.
