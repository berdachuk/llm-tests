# Bespoke-Nimble-9B-v3 vs FRIDA / decider-2b — прогон 2026-10-24

> **License: CC BY-NC 4.0 — research-only.** Не для коммерческого / клиентского billing Avroflex.  
> **Endpoint:** `http://192.168.0.175:8009` (`CudaCandidateScorer` + FastAPI `/v1/systemone`)  
> **Кейсы:** те же [`../frida-decisions/cases_sd.json`](../frida-decisions/cases_sd.json) (19 SD)  
> **Артефакты:** [`results-cap-20261024-155717/`](results-cap-20261024-155717/)  
> **Режим:** exclusive GPU1 (ASR/TEI/Gemma/FRIDA/decider остановлены на время теста)

---

## 1. Итог

| | FRIDA `:8006` (ранее) | decider-2b `:8008` | **Nimble-v3 `:8009`** |
|---|---|---|---|
| Capability suite | **19/19 (100%)** | **16/19 (84%)** | **19/19 (100%)** |
| RU | 12/12 | 10/12 (83%) | **12/12** |
| EN | 7/7 | 6/7 (86%) | **7/7** |
| short `choice` p50 | ~14 ms | ~20 ms | **~1009 ms** |
| PR gate 3q p50 | ~24 ms | ~53 ms | **~3162 ms** |
| VRAM (exclusive GPU1) | ~4–8 GiB | ~4–9 GiB | **~10.4 GiB** (+ host offload) |
| License | MIT | Apache-2.0 | **CC BY-NC 4.0** |
| razvilka / DI (публично) | 0.893 | 0.833 | DI 0.2.1 ≈ 56.88 (авторы) |

Nimble-v3 **закрывает весь SD suite** (включая PR-risk и RU injection, где падал decider), но **на 1–2 порядка медленнее** FRIDA/decider: 9B + independent full-prompt prefill на поле + CPU offload на 16 GiB.

---

## 2. Failures

Нет (19/19 PASS).

---

## 3. Latency (LAN HTTP, exclusive GPU1)

| Сценарий | FRIDA p50 | decider p50 | **Nimble-v3 p50 / p95** |
|---|---:|---:|---:|
| short choice (n=20) | 14.4 ms | 19.9 ms | **1008.5 / 1015.4 ms** |
| PR 3 questions (n=15) | 24.1 ms | 53.0 ms | **3161.6 / 3197.2 ms** |

Источник: [`results-cap-20261024-155717/latency.json`](results-cap-20261024-155717/latency.json).

---

## 4. Инфра

- Образ: `bespoke-nimble-9b-v3:research` (база `vllm/vllm-openai:v0.29.0-cu129`, `PYTHONPATH=/opt/nimble`, transformers 5.17 / peft 0.21)
- Merge LoRA → `/mnt/data/berda-models/huggingface/nimble-9b-v3-merged`; `schema_config` refreshed под текущий `encoding_contract`
- Load: `device_map=auto`, `NIMBLE_MAX_GPU_MEMORY=12GiB` (overflow → host RAM)
- Публичный nginx/Traefik/Bifrost: **не** делали (NC)

---

## 5. Выводы

1. По **качеству** на наших SD-гейтах Nimble-v3 = FRIDA (19/19) и лучше decider (закрыл PR/injection).  
2. По **latency / VRAM** FRIDA и decider остаются рабочими System-1 для Avroflex.  
3. **Прод Avroflex с Nimble-v3 нельзя** без другой лицензии (CC BY-NC). Research LAN-only.  
4. После теста: `docker compose down` nimble; поднять ASR/TEI/Gemma обратно.

---

## 6. Команды

```bash
export NIMBLE_BASE=http://192.168.0.175:8009
~/voice-asr/bespoke-nimble-9b-v3/smoke.sh
python3 llm-tests/bespoke-nimble-9b-v3/run_capability_suite.py
```
