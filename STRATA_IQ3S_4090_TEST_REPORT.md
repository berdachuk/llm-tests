# Strata IQ3_S — полный тест на RTX 4090 24 GB (192.168.0.88)

> Дата прогона: **2026-10-15** (UTC ~07:15–07:47)  
> План: [`STRATA_QWEN38_FLASH_NEXT_4090_PLAN.md`](STRATA_QWEN38_FLASH_NEXT_4090_PLAN.md)  
> Артефакты на хосте: `/mnt/data/strata/runs/20261015-iq3s-full/`  
> Локальная копия CSV: `strata-results/20261015-iq3s-full/`

---

## 1. Executive summary

| Пункт | Результат |
|---|---|
| Engine | Strata **v0.1.44.1** (`296b59d2`) — обновлён с устаревшего локального main |
| Model | `qwen3.8-flash-next-iq3_s` / IQ3_S + vision mmproj |
| GPU | RTX 4090 (GPU0), ~**23970 MiB** used / **114 MiB** free |
| RAM | ~**62 GiB** used under load (experts ~47 GiB lock + KV stream) |
| Context limit | **262144** |
| Smoke chat | **PASS** (`pong`) |
| Vision smoke | **PASS** (1×1 PNG → «Black») |
| Context matrix A–E | **PASS** (latency + needle@131K all positions) |
| Context matrix F (~248K) | **PASS** after calibration + `max_tokens≥256` (naive 262K filler → HTTP 400) |
| agentbench fast | **50 passed / 5 failed / 3 skipped** |

**Вердикт:** IQ3_S на 4090 стабилен до ~248K prompt tokens с needle recall; заявленный native max 262K достижим по prefill, но нужно оставлять запас под chat template / generation. Prefill ~**1.9–2.1k tok/s** на длинных промптах; decode ~**50–150 tok/s** (зависит от длины ответа / draft accept).

### Production follow-up (same day)

| Пункт | Результат |
|---|---|
| Cutover | Bifrost `llm-88` → Strata `:8080`; FreeToken off |
| Model id | **`qwen3.8-flash-next-iq3_s`** (compat `qwen3.6-35b-a3b` retired) |
| Autostart | user units + linger; firewall oneshot **без** Docker / без `Before=` |
| Qualbench-50 morning | **50/50** / **711 s** |
| Qualbench-50 prod re-check | **50/50** / **685 s** — [`run-strata-iq3s-prod-full50-20261015-135743.md`](qualbench/results/run-strata-iq3s-prod-full50-20261015-135743.md) |
| Runbook | [`STRATA_88_PRODUCTION.md`](STRATA_88_PRODUCTION.md) |

---

## 2. Окружение и подготовка

### 2.1. FreeToken

Перед тестом FreeToken остановлен; снимок restore:

- `/mnt/data/strata/FREETOKEN_RESTORE.md`
- `llm-tests/FREETOKEN_88_RESTORE.md`

GPU0 был свободен (~43 MiB) до старта Strata.

### 2.2. Обновление Strata

| | |
|---|---|
| Было | `99f3dbd` (локальный main, **behind origin на ~2174**) |
| Стало | `origin/main` = **v0.1.44.1** `296b59d2` |
| Setup | `./setup.sh --yes --family qwen --model IQ3_S --context 262144 --vision yes --gpu 0 --data-dir /mnt/data/strata-data --host 0.0.0.0 --api-key … --port 8080 --setup --no-start` |
| Веса | уже на диске; engine + vision пересобраны |

Конфиг: `strata-iq3_s.json` — `--max-context 262144 --kv int8 --kv-resident 32768 --expert-cache auto --spec 4 --mtp … --pool-workers 15 --vram-reserve-mib 700`.

### 2.3. Сеть

Сервер слушает `0.0.0.0:8080`, но с bench-машины прямой TCP на `:8080` таймаутился (firewall без sudo). Тесты шли:

- matrix / smoke / vision — **на хосте** `127.0.0.1:8080`
- agentbench — через **SSH tunnel** `127.0.0.1:18080 → 127.0.0.1:8080`

Хост имеет два LAN IP: `192.168.0.88` (wifi) и `192.168.0.175` (ethernet).

API key: файл `$RUN/api-key.txt` (не коммитить).

---

## 3. Smoke

### 3.1. Text

Запрос: «Say only: pong», `max_tokens=256`.

| Метрика | Значение |
|---|---|
| content | `pong` |
| finish_reason | `stop` |
| prompt_tokens | 56 |
| completion_tokens | 27 (часть — reasoning) |
| prompt_per_second | ~132 |
| predicted_per_second | ~106 |

Замечание: при `max_tokens=16` ответ часто уходит в `finish_reason=length` с пустым `content` (reasoning съедает бюджет). Для коротких smoke нужен запас tokens или `reasoning_effort=none` / `enable_thinking=false`.

### 3.2. Vision

1×1 PNG data-URL: «What color…? One word.» → **`Black`**, finish `stop`, ~188 prompt tok/s, ~134 decode tok/s.

---

## 4. Context matrix (IQ3_S)

Engine держался на **context_limit=262144**; менялась только длина промпта.

Колонки: cold = первый запрос (rep=0), warm = повтор того же промпта (prefix cache).

### 4.1. Latency tiers A–D (без needle)

| Tier | Target | Actual prompt tok | Cold TTFT s | Cold prefill t/s | Cold decode t/s | Warm TTFT s | OK |
|---|---:|---:|---:|---:|---:|---:|---|
| A | 1 024 | 1 251 | 3.38 | 376 | 52 | 0.09 | yes |
| B | 4 096 | 5 229 | 3.69 | 1437 | 55 | 0.10 | yes |
| C | 32 768 | 42 513 | 22.4 | 1903 | 58 | 0.12 | yes |
| D | 65 536 | 85 101 | 27.2 | 1931 | 61 | 0.14 | yes |

### 4.2. Long-context needle E (131K target → ~170K actual)

| Needle pos | prompt_tokens | TTFT s | prefill t/s | decode t/s | total s | needle | OK |
|---:|---:|---:|---:|---:|---:|---|---|
| 10% | 170 356 | 77.7 | 2076 | 75 | 82.3 | yes | yes |
| 50% | 170 357 | 75.0 | 2055 | 89 | 75.2 | yes | yes |
| 90% | 170 357 | 75.0 | 2055 | 123 | 75.1 | yes | yes |

### 4.3. Native-max F

| Попытка | Actual prompt | Результат |
|---|---:|---|
| Наивный filler «target=262144» | (rejected) | **HTTP 400** — промпт + template > n_ctx |
| Калибровка ~248K (×3 позиции) | ~248 155 | Prefill OK (~78 s, ~1990–2000 t/s). Needle: mid **yes**; 10%/90% сначала **no** (`finish=length`, max_tokens=64) |
| Retry 10%/90% с max_tokens=256 | ~248 114 | Needle **yes** / **yes**, finish `stop` |

Итого F (калиброванный ~248K):

| Needle pos | prompt_tokens | TTFT s | prefill t/s | decode t/s | needle (final) |
|---:|---:|---:|---:|---:|---|
| 10% | 248 114 | 77.6 | 2003 | 142 | **yes** |
| 50% | 248 154 | 78.8 | 1985 | 110 | **yes** |
| 90% | 248 115 | 78.7 | 1985 | 154 | **yes** |

**Практический потолок промпта на этой конфигурации:** ~**248K** токенов модели (оставляя запас до 262144). «Забить ровно 262144 filler-слов» нельзя — нужен запас на спецтокены/template/ответ.

---

## 5. agentbench (fast subset)

```text
AGENTBENCH_URL=http://127.0.0.1:18080  # SSH tunnel
AGENTBENCH_MODEL=qwen3.8-flash-next-iq3_s
pytest agentbench/tests -m "not slow and not concurrency"
→ 50 passed, 5 failed, 3 skipped, 8 deselected (~63 s)
```

### 5.1. Failures (кратко)

| Тест | Причина |
|---|---|
| `test_models_endpoint_reports_full_context` | Strata отдаёт `meta.n_ctx=262144`, не `max_model_len` (ожидание FreeToken) |
| `test_messages_count_tokens` | `401` на `/v1/messages/count_tokens` (эндпоинт/auth) |
| `test_full_bugfix_loop…` | агент продолжил tool_calls без финального `content` |
| `test_inline_think_off…` / `tool_choice=required` | были `xfail` под FreeToken; на Strata поведение иное → `XPASS`/`fail` при `xfail_strict` |

Протоколы chat/completions, responses, messages, tool calling, streaming, reasoning effort — в основном зелёные.

---

## 6. Ресурсы под нагрузкой

| | Idle (после stop FT) | Strata loaded / matrix |
|---|---|---|
| GPU0 used | ~43 MiB | **23970 MiB** |
| GPU0 free | ~24 041 MiB | **114 MiB** |
| GPU1 | ~3709 MiB (ASR/embed) | без изменений |
| Host RAM used | — | ~**62 GiB** |

KV streaming on: KV в RAM (~3.6 GB на 262K по логу setup), expert cache в VRAM (~14.7 GiB).

---

## 7. Выводы и рекомендации

1. **IQ3_S + Strata v0.1.44.1 на 4090** — рабочий baseline для long-context agent/RAG до ~**250K** prompt tokens.
2. Prefill масштабируется хорошо (~2k tok/s на 40K–250K); TTFT на 170K–248K ≈ **75–80 s** cold.
3. Warm/prefix-cache даёт TTFT **<0.15 s** на повтор того же промпта (A–D).
4. Для smoke/коротких ответов: не жать `max_tokens` (reasoning иначе ест бюджет) или явно глушить thinking.
5. Needle@F требует достаточного `max_tokens` (256 оказалось достаточно vs 64).
6. С bench-LAN открыть `:8080` в firewall (нужен sudo) или всегда tunnel.
7. После окна: **восстановить FreeToken** по `FREETOKEN_RESTORE.md` (`enable` engine + start daemon/engine).

---

## 8. Файлы

| Путь | Содержимое |
|---|---|
| `/mnt/data/strata/runs/20261015-iq3s-full/matrix.csv` | полная матрица |
| `…/smoke-short.json`, `smoke-vision.json` | smoke |
| `…/agentbench-smoke.txt` | сводка agentbench |
| `…/setup.log`, `server.out`, `strata-iq3_s.log` | логи |
| `llm-tests/strata-results/20261015-iq3s-full/` | локальная копия ключевых артефактов |

---

## 9. Команды повтора (кратко)

```bash
ssh berda@192.168.0.88
cd /mnt/data/strata/Strata
./run-iq3_s.sh   # или setup.sh после --setup

# bench host:
ssh -fN -L 127.0.0.1:18080:127.0.0.1:8080 berda@192.168.0.88
export AGENTBENCH_URL=http://127.0.0.1:18080
export AGENTBENCH_MODEL=qwen3.8-flash-next-iq3_s
export AGENTBENCH_API_KEY=$(ssh berda@192.168.0.88 'cat /mnt/data/strata/runs/20261015-iq3s-full/api-key.txt')
pytest agentbench/tests -m "not slow and not concurrency"
```
