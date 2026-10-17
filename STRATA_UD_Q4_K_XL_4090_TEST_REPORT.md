# Strata UD-Q4_K_XL — полный тест на RTX 4090 24 GB (`.175`)

> Дата прогона: **2026-10-17**  
> План: [`STRATA_UD_Q4_K_XL_PLAN.md`](STRATA_UD_Q4_K_XL_PLAN.md)  
> Артефакты на хосте: `/mnt/data/strata/runs/20261017-ud-q4_k_xl/`  
> Локальная копия: `strata-results/20261017-ud-q4_k_xl/`  
> Откат IQ3_S: [`STRATA_IQ3S_RESTORE_SNAPSHOT.md`](STRATA_IQ3S_RESTORE_SNAPSHOT.md)

---

## 1. Executive summary

| Пункт | Результат |
|---|---|
| Engine | Strata **v0.1.44.1** |
| Model | `qwen3.8-flash-next-ud-q4_k_xl` / Unsloth **UD-Q4_K_XL** + vision mmproj |
| GPU | RTX 4090 (GPU0), ~**23974 MiB** used |
| RAM | ~**88 GiB** used under load (full resident experts, no `--resident-budget`) |
| Context limit | **262144** (practical prompt ~**248K**) |
| Smoke chat | **PASS** (`pong`) |
| Vision smoke | **PASS** (1×1 PNG → «Black», `enable_thinking=false`) |
| Context matrix A–E | **PASS** (incl. needle@~170K all positions) |
| Context matrix F (~248K) | **PASS** after calibration (`target=190810`, `max_tokens=256`) |
| agentbench fast | **50 passed / 5 failed / 3 skipped** (~96 s) |
| agentbench slow | **5/5 passed** (~338 s) |
| Qualbench-50 | **48/50** (sql 4/6 after Postgres up; first run 44/50 with PG down) |

**Вердикт:** UD-Q4_K_XL на 1×4090 с полным resident pack стабилен до ~248K с needle recall. Prefill на длинных промптах ~**1.2–1.3k tok/s** (ниже IQ3_S ~2.0k); decode short-reply ~**40–100 tok/s**. Host RAM выше IQ3_S (~88 vs ~62 GiB). Qualbench text чуть ниже IQ3_S (48/50 vs 50/50) из‑за 2 SQL fails при живом Postgres.

### Production cutover (same day)

| Пункт | Результат |
|---|---|
| systemd | `strata-ud-q4_k_xl` **active**; `strata-iq3_s` disabled |
| Model id | **`qwen3.8-flash-next-ud-q4_k_xl`** / `llm-88/qwen3.8-flash-next-ud-q4_k_xl` |
| Public `llm-88.berdachuk.com/v1/models` | serves Q4 id (nginx→Strata) |
| OpenCode | default `llm-88-local/qwen3.8-flash-next-ud-q4_k_xl`, limit **248000** |
| Runbook | [`STRATA_88_PRODUCTION.md`](STRATA_88_PRODUCTION.md) |

---

## 2. Smoke

### 2.1. Text

| Метрика | Значение |
|---|---|
| content | `pong` |
| finish_reason | `stop` |
| prompt / completion | 57 / 28 (с reasoning) |
| prompt_per_second | ~68 |
| predicted_per_second | ~52 |

Артефакт: `strata-results/20261017-ud-q4_k_xl/smoke-short.json`.

### 2.2. Vision

1×1 black PNG data-URL + `chat_template_kwargs.enable_thinking=false` → **`Black`**, finish `stop`.  
Артефакт: `smoke-vision.json`.

---

## 3. Context matrix (UD-Q4_K_XL)

CSV: `strata-results/20261017-ud-q4_k_xl/matrix.csv` (+ `matrix-f-calib.json`).

| Tier | Target | Actual prompt (typ.) | Result | Prefill t/s (cold) | Notes |
|---|---:|---:|---|---:|---|
| A | 1 024 | ~1 251 | PASS | ~217 | decode ~41 |
| B | 4 096 | ~5 229 | PASS | ~859 | |
| C | 32 768 | ~42 513 | PASS | ~1 162 | |
| D | 65 536 | ~85 101 | PASS | ~1 199 | |
| E | 131 072 | ~170 355 | PASS needle 3/3 | ~1 285–1 293 | pos 0.1/0.5/0.9 |
| F naive | 262 144 | — | HTTP 400 | — | same as IQ3_S filler overshoot |
| F calib | 190 810 | ~248 017 | PASS needle 3/3 | ~1 249 | `max_tokens=256` |

VRAM во всех ячейках ~**23974 MiB**. RAM ~**87–88 GiB**.

---

## 4. agentbench

```text
AGENTBENCH_URL=http://192.168.0.175:8080
AGENTBENCH_MODEL=qwen3.8-flash-next-ud-q4_k_xl
AGENTBENCH_API_KEY=<strata key>
```

| Suite | Result | Wall | Artifact |
|---|---|---|---|
| fast (`not slow and not concurrency`) | **50 pass / 5 fail / 3 skip** | 96 s | `agentbench-smoke.txt` |
| slow | **5/5** | 338 s | `agentbench-slow.txt` |

Fails (same shape as IQ3_S-era contract/edge cases): models full-context report, count_tokens, one inline-think off case, `tool_choice=required`, grep-result-with-word-`error`.

---

## 5. Qualbench-50

Первый полный прогон без Docker Postgres → sql **0/6** (инфра), остальные категории **44/44** → reported **44/50** / **1137 s**:  
[`qualbench/results/run-strata-ud-q4-full50-20261017-212452.md`](qualbench/results/run-strata-ud-q4-full50-20261017-212452.md).

Retry sql с `qualbench-pg` на `:15432` → **4/6**:  
[`qualbench/results/run-strata-ud-q4-sql-retry-20261017-214920.md`](qualbench/results/run-strata-ud-q4-sql-retry-20261017-214920.md).

**Сводный score с живым Postgres: 48/50** (java 10 + ts 8 + sql 4 + mcp 8 + security 8 + long 10).

| Category | Pass | Wall (s) |
|---|---|---|
| java-spring | 10/10 | 122 |
| ts-angular | 8/8 | 78 |
| sql-migrations | 4/6 | 57 (retry) |
| mcp-tools | 8/8 | 23 |
| security-review | 8/8 | 170 |
| long-context | 10/10 | 694 |

---

## 6. Reproduce

```bash
export STRATA_URL=http://192.168.0.175:8080
export STRATA_KEY=$(ssh berda@192.168.0.175 'cat /mnt/data/strata/runs/20261015-iq3s-full/api-key.txt')
export STRATA_MODEL=qwen3.8-flash-next-ud-q4_k_xl

# agentbench
AGENTBENCH_URL=$STRATA_URL AGENTBENCH_MODEL=$STRATA_MODEL AGENTBENCH_API_KEY=$STRATA_KEY \
  .venv/bin/pytest agentbench/tests -q -m "not slow and not concurrency"

# qualbench (need docker qualbench-pg on :15432)
QUALBENCH_API_KEY=$STRATA_KEY .venv/bin/python3 qualbench/harness/run_all.py \
  --url "$STRATA_URL" --model "$STRATA_MODEL" --tag strata-ud-q4-full50

# matrix — on host
ssh berda@192.168.0.175
# see /mnt/data/strata/runs/20261017-ud-q4_k_xl/run_matrix.py + run_matrix_f_calib.py
```

Compare vs IQ3_S: [`STRATA_IQ3S_VS_UD_Q4_COMPARE.md`](STRATA_IQ3S_VS_UD_Q4_COMPARE.md).
