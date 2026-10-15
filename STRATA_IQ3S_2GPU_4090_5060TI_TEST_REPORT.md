# Strata IQ3_S — dual-GPU тест на RTX 4090 + RTX 5060 Ti (192.168.0.88)

> Дата прогона: **2026-10-15** (UTC ~08:48–09:37)  
> Предыдущий single-GPU отчёт: [`STRATA_IQ3S_4090_TEST_REPORT.md`](STRATA_IQ3S_4090_TEST_REPORT.md)  
> Сравнение: [`STRATA_VS_FREETOKEN_4090_COMPARE.md`](STRATA_VS_FREETOKEN_4090_COMPARE.md)  
> Артефакты на хосте: `/mnt/data/strata/runs/20261015-iq3s-2gpu/`  
> Локальная копия: `strata-results/20261015-iq3s-2gpu/`

---

## 1. Executive summary

| Пункт | Результат |
|---|---|
| Engine | Strata **v0.1.44.1** |
| Model | `qwen3.8-flash-next-iq3_s` / IQ3_S + vision mmproj |
| GPUs | **GPU0 RTX 4090 24 GB** + **GPU1 RTX 5060 Ti 16 GB** (layer split) |
| Split (auto) | card order **1,0**; layers **0–2 @ CUDA0 (5060 Ti)**, **3–47 @ CUDA1 (4090)** + head/MTP |
| Bind / monitor | `0.0.0.0:8080` — UI: http://192.168.0.88:8080/ |
| Context limit | **262144** |
| Smoke chat | **PASS** (`pong`) |
| Vision smoke | **PASS** (`Black`) |
| agentbench fast | **49 passed / 6 failed / 3 skipped** (~83 s) |
| qualbench-50 text | **50/50** за **966.2 s** |
| Context matrix | A–D OK; E **3/3** (mid flake → retry); raw F 262K → HTTP 400; calibrated F ~**248K 3/3** |

**Вердикт:** качество qualbench то же (**50/50**), что на 1×4090, но **wall time хуже** (966 vs **685–711 s**, ~**1.36×**). Prefill на длинном контексте ~**1.25–1.6× медленнее** 1×4090. Layer split на этой паре карт **не ускоряет** text suite / long-context.

**Прод после окна:** вернулись на **1×4090** без `layer_split` — [`STRATA_88_PRODUCTION.md`](STRATA_88_PRODUCTION.md).

---

## 2. Конфигурация

```text
./setup.sh --yes --family qwen --model IQ3_S --context 262144 --vision yes \
  --gpus 0,1 --layer-split auto \
  --data-dir /mnt/data/strata-data --host 0.0.0.0 --port 8080 --setup --no-start
```

Config: `strata-iq3_s.json` → `"gpu": [0, 1], "layer_split": "auto"`.

| | Idle | Loaded (steady) |
|---|---|---|
| GPU0 4090 used | ~40 MiB | ~**23.4–23.5 GiB** |
| GPU1 5060 Ti used | ~15 MiB | ~**8.5–11.3 GiB** |
| Host RAM | — | ~**60–61 GiB** |
| Matrix VRAM sum | — | ~**35.3–35.4 GiB** (обе карты) |

LAN `:8080`: `scripts/open-strata-8080.sh`.

---

## 3. agentbench (fast subset)

```text
AGENTBENCH_URL=http://127.0.0.1:18081
AGENTBENCH_MODEL=qwen3.8-flash-next-iq3_s
pytest agentbench/tests -m "not slow and not concurrency"
→ 49 passed, 6 failed, 3 skipped (~83 s)
```

| Тест | Причина |
|---|---|
| `test_models_endpoint_reports_full_context` | `meta.n_ctx`, нет `max_model_len` |
| `test_messages_count_tokens` | **401** |
| `test_full_bugfix_loop…` | tool loop без финального `content` |
| `test_inline_think_off…` / `tool_choice=required` | XPASS(strict) / иное vs FT xfail |
| `test_grep_style_result_with_word_error…` | лишний tool_call |

Артефакт: `strata-results/20261015-iq3s-2gpu/agentbench-smoke.txt`.

---

## 4. Qualbench-50 (text)

Источник: [`qualbench/results/run-strata-iq3s-2gpu-full50-20261015-121142.md`](qualbench/results/run-strata-iq3s-2gpu-full50-20261015-121142.md).

| Category | Pass | Wall 2× (s) | Wall 1× (s) |
|---|---:|---:|---:|
| java-spring | 10/10 | 95.5 | 83 |
| ts-angular | 8/8 | 60.6 | 62 |
| sql-migrations | 6/6 | 48.2 | 61 |
| mcp-tools | 8/8 | 23.5 | 15 |
| security-review | 8/8 | 108.1 | 93 |
| long-context | 10/10 | **630.3** | **397** |
| **Total** | **50/50** | **966.2** | **711** |

150K tasks: ~122–135 s (1×: ~77–98 s).

---

## 5. Context matrix

CSV: `strata-results/20261015-iq3s-2gpu/matrix.csv` (+ `matrix-f-calib.json`).

### 5.1 Latency tiers (cold rep=0)

| Tier | Prompt tok | TTFT 2× (s) | Prefill 2× | Decode 2× | Prefill 1× (ref) |
|---|---:|---:|---:|---:|---:|
| A ~1K | 1251 | 3.18 | 400 | 44 | 376 |
| B ~4K | 5229 | 6.46 | **817** | 47 | **1437** |
| C ~32K | 42513 | 34.0 | **1252** | 51 | **1903** |
| D ~65K | 85101 | 41.1 | **1275** | 54 | **1931** |

Warm rep=1: TTFT ~0.09–0.13 s (KV hit).

### 5.2 Needle E (~170K) / F (~248K)

| Cell | Result | Prefill tok/s | Notes |
|---|---|---:|---|
| E pos 0.1 | **PASS** | 1293 | |
| E pos 0.5 | flake empty → **PASS retry** | 1283 | first: empty stream / `pt=0` |
| E pos 0.9 | **PASS** | 1293 | |
| F raw 262K ×3 | **HTTP 400** | — | как на 1× |
| F calib ~248K ×3 | **3/3 PASS** | ~**1264** | aim words 190810; max_tokens=256 |

1×4090 ref: E prefill ~2050–2075; F calib ~1990–2003; F also raw-400 then calib 3/3.

**Итог matrix:** потолок тот же (~248K needle OK; raw 262K filler → 400). Prefill на 2×GPU стабильно ниже (~60–65% от 1× на C–F).

---

## 6. Выводы

1. **2×GPU layer split работает** (monitor `:8080`, обе карты под нагрузкой).
2. **Qualbench score 50/50** — паритет с 1×; **скорость хуже** (особенно long-context).
3. **Context ceiling паритетен** 1× (~248K calib, 150K qualbench).
4. Для qualbench / long-context на этом хосте предпочтительнее **Strata 1×4090**; GPU1 лучше оставить под ASR/embeddings.
5. agentbench fails — те же классы API-расхождений (+1 fail vs 1×).

---

## 7. Файлы

| Путь | Содержимое |
|---|---|
| `/mnt/data/strata/runs/20261015-iq3s-2gpu/` | server, matrix*, F-calib, cells, api-key |
| `llm-tests/strata-results/20261015-iq3s-2gpu/` | локальная копия |
| `qualbench/results/run-strata-iq3s-2gpu-full50-20261015-121142.*` | qualbench |
| `STRATA_88_ACTIVE_STACK.md` | текущий стек |
