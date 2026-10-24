# Исследование: локальный Jev-подобный decision на EmbeddingGemma-2

> **Дата:** 2026-10-24  
> **Контекст:** A/B FRIDA-Decisions (`:8006`) / Mapika/decider-2b (`:8008`, докачка весов)  
> **Источник подхода:** [Pavel Agurov — Local Jev with 0.5B](https://www.linkedin.com/pulse/local-jev-05b-pavel-agurov-ncqte/)  
> **Кандидат базы у нас:** [`google/embeddinggemma-2`](https://huggingface.co/google/embeddinggemma-2) на `192.168.0.175:8005`  
> **Статус:** предложение (не реализовано)

---

## 1. Вопрос

Можно ли реализовать decision-модель класса System One / Jev (`choice` / `score` / `noul`, опционально `ranking`) **по идее Agurov**, но на **EmbeddingGemma-2**, которая уже крутится на GPU1 рядом с ASR/TEI/FRIDA?

---

## 2. Что делает Agurov (кратко)

База — **causal Instruct LM** (`Qwen/Qwen2.5-0.5B-Instruct`), не эмбеддер.

| Режим | Механика | Результат у автора |
|---|---|---|
| Prompt + structured output | генерация JSON/enum | 2.5–4.6 с/пример, 2 метки ок, 3+ плохо |
| **Simple Jev** | один forward; softmax по логитам букв `A`/`B`/… | 2–5× быстрее; 2 метки ок; 3–10 классов развал |
| **Jev + h-layer** | линейный слой на last hidden state (init из `lm_head` букв), CE на ~200 примерах/класс | 91–99.6% на 3–10 метках; фиксированный набор меток |

Смысл: убрать генерацию, оставить один проход и калибруемые вероятности по опциям.

Родственная open-реализация полного System One на маленьком Qwen: [jaredpalmer/kev-0.5b](https://huggingface.co/jaredpalmer/kev-0.5b) (LoRA + pointer head, `/v1/systemone`) — это уже не «промпт+логиты букв», а отдельная архитектура ближе к TypeSafe/FRIDA.

---

## 3. Чем EmbeddingGemma-2 отличается

| | Agurov / Kev / decider | EmbeddingGemma-2 @ `:8005` |
|---|---|---|
| Тип | causal LM (+ head) | encoder → dense vector |
| Выход | логиты токенов / pointer | **768-d** embedding |
| API у нас | — | `POST /v1/embeddings` |
| VRAM (ордер) | 0.5B–2B decision | ~2.5–4 GiB, уже live |
| Мультимодальность | отдельно (SmolVLM у Agurov) | text + image уже в стеке |

**Следствие:** шаг «взять логиты букв A/B» **непереносим**. Нет `lm_head` / next-token prediction.

---

## 4. Вывод по возможности

| Вопрос | Ответ |
|---|---|
| Скопировать Agurov Test 4 (letter logits) на EmbeddingGemma-2? | **Нет** |
| Сделать **аналог** локального Jev на эмбеддингах? | **Да** |
| Заменить FRIDA / decider-2b на динамических criteria (coding gates)? | **Нет** без отдельного тяжёлого обучения |
| Имеет смысл как тонкий System-1 для **фиксированных** каталогов / RAG? | **Да** |

Философски EmbeddingGemma-2 ближе к **FRIDA / KaLM-reranker** (encoder decisions), чем к causal «letter Jev» Agurov.

Публичный ориентир: чистый reranker/embedding path на razvilka у авторов FRIDA слабый (KaLM-Reranker-Nano **0.521** vs FRIDA **0.893**). Zero-shot cosine на EmbeddingGemma-2, скорее всего, тоже не догонит FRIDA без обучения.

---

## 5. Предлагаемые варианты реализации

### Вариант A — Cosine / bi-encoder System One (прототип, zero-shot)

**Идея:** для каждого вопроса:

1. `q = emb(state + instructions)` (или отдельно state / question);
2. для каждого ключа в `criteria`: `c_i = emb(text_i)`;
3. scores = cosine(`q`, `c_i`) → softmax → `choice` / ранжирование;
4. `noul`: два критерия `true`/`false` или порог на similarity;
5. `score`: уровни шкалы как опции → взвешенное среднее индекса.

**Плюсы:** критерии в JSON как у Jev; без дообучения; можно повесить на живой `:8005`; latency = 1 + K embed-calls (или batch).  
**Минусы:** качество на сложных SD-гейтах слабее FRIDA; калибровка вероятностей условная.

**Контракт:** тонкий сервис `POST /v1/systemone` → внутри только вызовы EmbeddingGemma-2.

### Вариант B — Probe / h-layer (аналог Test 5 Agurov)

**Идея:** заморозить EmbeddingGemma-2; на 768-d обучить маленький линейный (или MLP) классификатор под **фиксированный** набор меток (интенты, tier routing, tool allowlist).

**Плюсы:** быстро инференс; на своих данных может быть сильно; обучение минуты–часы.  
**Минусы:** новый набор labels = переобучение; не «criteria в запросе».

Подходит для: каталог агентов / intents support / model-tier на известном enum.

### Вариант C — Полный decision (LoRA + pointer), база = Gemma/Qwen Instruct

**Идея:** как Kev / FRIDA / decider — не обёртка над `:8005`. EmbeddingGemma-2 здесь только «сосед по GPU», не backbone.

**Плюсы:** настоящий динамический System One.  
**Минусы:** отдельный проект обучения; дублирует FRIDA/decider, которые уже закрывают задачу.

**Не предлагаем сейчас**, пока live FRIDA + decider-2b A/B не закрыт.

---

## 6. Рекомендация для Avroflex

```text
System-2 (Strata / Bifrost chat)
        ▲
        │ low confidence / hard
System-1a  FRIDA :8006  /  decider :8008     ← динамические criteria, SD gates
System-1b  EmbeddingGemma-2 :8005 + thin     ← RAG + опционально fixed catalog (A/B)
```

1. **Оставить** FRIDA (и после A/B — decider) как основной typed-decision path.  
2. **Не** пытаться эмулировать letter-logits Agurov на EmbeddingGemma-2.  
3. **Опциональный прототип:** вариант **A** (cosine System One) поверх `:8005` + прогон того же `cases_sd.json` (с ожидаемо более низким pass-rate) для честного сравнения в отчёте.  
4. Если на внутренних логах появятся стабильные enum-каталоги — вариант **B** (probe) точечно.

---

## 7. Минимальный план прототипа A (если решим делать)

| Шаг | Действие |
|---|---|
| 1 | Сервис `llm-88/embedding-systemone/` (FastAPI): Jev JSON in → batch embed на `:8005` → answers out |
| 2 | Порт LAN, например `:8009` (не трогать 8007 Nemotron / 8008 decider) |
| 3 | Адаптер `cases_sd.json` → тот же expect, что у decider suite |
| 4 | Строка в `RESULTS_COMPARE_*.md`: FRIDA vs decider vs emb-cosine |
| 5 | DoD прототипа: latency + pass-rate; без публичного Traefik, пока нет win |

Оценка усилий: **0.5–1 день** на прототип A; обучение B — отдельно после появления размеченного каталога.

---

## 8. Риски и ограничения

- Zero-shot embedding decisions **систематически** слабее encoder-decision моделей с обучением под choice/noul/score (FRIDA).  
- Softmax по cosine ≠ калибровка Jev; пороги для risk/injection gates нужно подбирать отдельно.  
- Batch на `:8005` делит GPU1 с ASR/TEI/FRIDA/decider — следить за VRAM и latency.  
- Русский: EmbeddingGemma-2 мультиязычна, но SD-кейсы калибровались под FRIDA RU-first — ожидать асимметрию RU/EN.

---

## 9. Ссылки

- [Local Jev with 0.5B — Pavel Agurov](https://www.linkedin.com/pulse/local-jev-05b-pavel-agurov-ncqte/)  
- [jaredpalmer/kev-0.5b](https://huggingface.co/jaredpalmer/kev-0.5b) (полный System One на 0.5B)  
- [google/embeddinggemma-2](https://huggingface.co/google/embeddinggemma-2)  
- Live: [`docs/embeddinggemma-2-deployment-plan.md`](../../../projects-avroflex/avroflex-infra/docs/embeddinggemma-2-deployment-plan.md)  
- Сравнение FRIDA: [`../frida-decisions/RESULTS_COMPARE_20261024.md`](../frida-decisions/RESULTS_COMPARE_20261024.md)  
- Деплой decider: `avroflex-infra/docs/decider-2b-deployment-plan.md`
