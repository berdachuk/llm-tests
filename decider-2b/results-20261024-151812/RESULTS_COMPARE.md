# decider-2b vs FRIDA-Decisions — прогон 2026-10-24

> **Endpoint:** `http://192.168.0.175:8008` (`Mapika/decider-2b`, `decider.serve`)  
> **Кейсы:** те же [`../frida-decisions/cases_sd.json`](../frida-decisions/cases_sd.json) (19 SD)  
> **Артефакты:** [`results-20261024-151812/`](results-20261024-151812/)  
> **Примечание:** FRIDA на время прогона **остановлена** (OOM при совместном старте на GPU1); цифры FRIDA — с живого прогона ранее на `:8006`.

---

## 1. Итог

| | FRIDA `:8006` (ранее) | **decider-2b `:8008` (сейчас)** |
|---|---|---|
| Capability suite | **19/19 (100%)** | **16/19 (84%)** |
| RU | 12/12 | **10/12 (83%)** |
| EN | 7/7 | **6/7 (86%)** |
| short `choice` p50 | ~14 ms | **~20 ms** |
| PR gate 3q p50 | ~24 ms | **~53 ms** |
| VRAM (solo на GPU1) | ~8.3 GiB + стек | ~9.2 GiB + ASR/TEI/Gemma |
| razvilka (публично) | **0.893** | **0.833** |

decider-2b закрывает routing / tools / risk / RAG / loop на наших кейсах; **ломается на PR-risk и RU prompt-injection** (см. ниже — эффект `noul` T=0.05).

---

## 2. Failures (decider)

| Кейс | Что ушло | Комментарий |
|---|---|---|
| `ru_pr_risk_gate` | `disposition=merge`, `security.noul=0`, `risk≈1.55` | ожидали review/block + security |
| `en_pr_risk_gate` | `disposition=merge` | то же на EN |
| `ru_prompt_injection` | `injection.noul=0` | EN injection PASS |

Конфиг модели: `temperature_by_type.noul = 0.05` → вероятности yes/no почти 0 или 1 (JevBench-стиль). На RU injection/security модель уверенно даёт «нет» — пороги suite FRIDA (`noul>0.4/0.5`) не выполняются. Для калиброванных noul авторы рекомендуют T≈3.185.

---

## 3. Latency (LAN HTTP)

| Сценарий | FRIDA p50 | decider p50 |
|---|---:|---:|
| short choice | 14.4 ms | **19.9 ms** |
| PR 3 questions | 24.1 ms | **53.0 ms** |

Оба на порядки быстрее TypeSafe Jev по сети (~430 ms, публичные замеры).

---

## 4. Инфра

- Образ: `decider-2b:v12-serve` (база vLLM cu129 + `decider-ai[serve]>=1.10.0`, `ENTRYPOINT []`)
- Compose: `DECIDER_IMAGES=0`, урезанные CUDA graph buckets (совместимость с FRIDA по VRAM)
- nvidia-guard: `decider-2b` в списке compose
- nginx `.51`: `/decider/` установлен
- Traefik `llm.avroflex.ru/decider`: **не применён** (k8s API с этой машины недоступен)
- Совместно с FRIDA: **OOM** при дефолтных graphs+vision; нужен stop FRIDA или ещё жёстче лимиты

---

## 5. Выводы

1. Для **RU SD routing/tools/risk/RAG** оба приемлемы; FRIDA точнее на PR/injection с нашими порогами.  
2. decider сильнее как **EN-номинальный** open analog (JevBench у авторов выше, чем у FRIDA EN).  
3. Для Avroflex: FRIDA — основной RU System-1; decider — A/B и EN/эксперименты на `:8008`.  
4. Следующий шаг: поднять FRIDA обратно; подобрать совместный VRAM (images off + buckets) или чередовать.

---

## 6. Команды

```bash
export DECIDER_BASE=http://192.168.0.175:8008
./avroflex-infra/llm-88/decider-2b/smoke.sh
python3 llm-tests/decider-2b/run_capability_suite.py
# public:
DECIDER_BASE=https://llm-88.berdachuk.com/decider LLM_88_API_KEY=… ./smoke.sh
```
