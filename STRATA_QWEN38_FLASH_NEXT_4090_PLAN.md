# Plan: Strata + Qwen3.8-Flash-Next на RTX 4090 (192.168.0.88)

Цель: поднять **Strata** с **максимальным контекстом** на **RTX 4090 24 GB**,
прогнать матрицу размеров контекста, затем вернуть **FreeToken**
(`qwen3.6-35b-a3b` на `:8000`).

Хост: `ssh berda@192.168.0.88` (`llm-server`).  
Связанные runbook’и: [`FREETOKEN_QWEN36_SERVE.md`](FREETOKEN_QWEN36_SERVE.md),
[`TEST_RESULTS.md`](TEST_RESULTS.md).

---

## 0. Целевой профиль

| Параметр | Выбор | Почему |
|---|---|---|
| Engine | [Strata](https://github.com/Niko1221/Strata) (latest) | готовый MoE offload + OpenAI/Anthropic API |
| Model family | `qwen` (оригинал Flash-Next) | полный набор экспертов; Coder/Swift — отдельный проход позже |
| Quant | **IQ3_S** (primary, сейчас качается) | при 125 GB RAM — лучшее качество; ≈ full на lab scores |
| Quant ladder (потом) | **Q2_0 → IQ2_XS → IQ3_XXS** | speed→quality ladder для той же context matrix; см. §9 |
| GPU | **CUDA device 0 = RTX 4090** (`--gpu 0`) | 24 GB → большой expert cache; 5060 Ti не трогаем |
| Context (ceiling) | **262144** (native max) | trained window модели; 384K/512K — только как optional experimental pass |
| KV | default streaming from 64K (`--kv-resident 32768`) | больше experts в VRAM на длинном контексте |
| KV optional A/B | `--kv q4_0` и/или `--kv k8v4` | меньше KV → больше experts / выше decode на 128K–262K |
| Vision | `yes` (отдельный smoke) | checkpoint multimodal; text-baseline не ломает |
| Bind | `0.0.0.0:8080` + API key | доступ с bench-машины; не конфликтовать с FreeToken `:8000` |
| Data dir | `/mnt/data/strata-data` | модели/packs на NVMe data-диск (~1.1T free) |
| Install dir | `/mnt/data/strata/Strata` | код engine отдельно от весов |

**Не делать в первом прогоне:** Experimental Speed Projection (off),
Unsloth UD-Q4_K_XL (слишком медленный decode), multi-GPU split с 5060 Ti
(усложняет baseline; peer-cache — follow-up).

---

## 1. Inventory сервера (уже проверено 2026-10-03)

| Ресурс | Факт | Вердикт |
|---|---|---|
| OS | Ubuntu 24.04.5 | OK |
| CPU | i9-14900KF, 32 thr, AVX2 | OK |
| RAM | 125 GiB | OK для IQ3_S @ 262K |
| GPU0 | RTX 4090 24564 MiB, driver 595 | OK (≥580) |
| GPU1 | RTX 5060 Ti 16311 MiB | не используем в этом плане |
| Disk `/mnt/data` | ~1.1T free | OK (≥80–120 GB нужно) |
| FreeToken сейчас | `:8000`, PID через daemon, ~23 GB на 4090 | **нужна временная остановка** |
| Другие порты | `:1234` llmster, `:11434` Ollama | не трогаем |
| Strata port | `:8080` (свободен) | OK |

Ожидаемый footprint IQ3_S: ~55 GB experts в RAM + ~29 GB n-gram на SSD +
KV (~13.7 KB/token в RAM при streaming) + GPU hot path / expert cache.

Грубая оценка KV в RAM при streaming:  
`262144 × 13.7 KB ≈ 3.5 GB` — при 125 GB RAM запас большой.

---

## 2. Окно работ и коммуникация

1. Выбрать maintenance window (оценка wall-clock):
   - install + download IQ3_S: **40–90 мин** (зависит от HF);
   - first load: **2–5 мин**;
   - context matrix (см. §7): **2–4 ч**;
   - optional IQ2_XS download: +40–70 мин;
   - restore FreeToken: **5–15 мин** до ready.
2. Перед stop FreeToken предупредить, кто бьёт в `http://192.168.0.88:8000`
   (Cursor/agents/qualbench).
3. Вести лог сессии: `/mnt/data/strata/runs/YYYYMMDD-hhmm/` (команды, curl, nvidia-smi, результаты).

Структура артефактов:

```text
/mnt/data/strata/
  Strata/                 # git clone
  runs/
    20261003-strata-ctx/
      NOTES.md
      preflight.txt
      matrix.csv
      agentbench-smoke.txt
      nvidia-smi-*.txt
/mnt/data/strata-data/    # models/, packs/, mtp/ (Strata --data-dir)
```

---

## 3. Preflight (до остановки FreeToken)

На `192.168.0.88`:

```bash
ssh berda@192.168.0.88

mkdir -p /mnt/data/strata/runs/$(date +%Y%m%d)-strata-ctx
RUN=/mnt/data/strata/runs/$(date +%Y%m%d)-strata-ctx
echo "RUN=$RUN" | tee "$RUN/NOTES.md"

{
  date -Is
  hostname
  free -h
  nvidia-smi
  df -h / /mnt/data
  ss -lntp | grep -E '8000|8080|1900|1234|11434' || true
  curl -sS http://127.0.0.1:8000/v1/models | python3 -m json.tool | head -40
  /home/berda/freetoken-0.1.3/.venv/bin/ft daemon status || true
  curl -sS http://127.0.0.1:1900/engine/status || true
  systemctl --user status freetoken-daemon.service freetoken-engine.service --no-pager
} | tee "$RUN/preflight.txt"
```

Критерии «можно останавливать FreeToken»:

- `/v1/models` отвечает (чтобы зафиксировать baseline до stop);
- нет чужого долгого qualbench/agentbench на `:8000`;
- на `/mnt/data` ≥ **120 GB** free.

---

## 4. Временная остановка FreeToken

Цель: полностью освободить **GPU0 VRAM** и порт `:8000`, не потеряв конфиг автозапуска.

### 4.1. Stop engine + не дать systemd сразу поднять снова

```bash
# 1) Остановить engine через daemon API
/home/berda/freetoken-0.1.3/.venv/bin/ft daemon stop

# 2) Остановить user units (engine oneshot + на всякий случай проверить daemon)
systemctl --user stop freetoken-engine.service

# Опционально на время окна — не автостартовать engine после reboot:
# systemctl --user disable freetoken-engine.service
# (daemon можно оставить running — он лёгкий и не занимает GPU)

# 3) Если serve всё ещё жив (adopted / orphan) — принудительно
pgrep -af 'freetoken|ft serve' || true
# только если процесс ещё держит GPU/порт:
# /home/berda/freetoken-0.1.3/.venv/bin/ft daemon stop --force
```

### 4.2. Verify GPU free

```bash
nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/v1/models || echo '8000 down (expected)'
ss -lntp | grep 8000 || echo 'port 8000 free'
```

**Pass:** GPU0 `memory.used` ≪ 1–2 GiB (desktop/idle), `:8000` не слушает.  
GPU1 (5060 Ti) может оставаться с мелким idle footprint — ок.

### 4.3. Rollback-заметка (заполнить в NOTES.md)

Записать до stop:

- model path: `/mnt/data/berda-models/models/Qwen3.6-35B-A3B-FP8`
- served name: `qwen3.6-35b-a3b`
- flags из `~/.local/state/freetoken/serve.json` / `freetoken-engine.service`
- был ли multimodal path (`--allowed-local-media-path /mnt/data/qualbench-mm`)

---

## 5. Установка Strata (один раз)

```bash
sudo mkdir -p /mnt/data/strata /mnt/data/strata-data
sudo chown berda:berda /mnt/data/strata /mnt/data/strata-data

cd /mnt/data/strata
git clone https://github.com/Niko1221/Strata.git
cd Strata
git log -1 --oneline | tee -a "$RUN/NOTES.md"

# Если HF медленный:
# export HF_ENDPOINT=https://hf-mirror.com
# export HF_TOKEN=...   # только если понадобится auth
```

### 5.1. Setup: IQ3_S + max native context на 4090

```bash
cd /mnt/data/strata/Strata

./setup.sh \
  --yes \
  --family qwen \
  --model IQ3_S \
  --context 262144 \
  --vision yes \
  --gpu 0 \
  --data-dir /mnt/data/strata-data \
  --host 0.0.0.0 \
  --api-key "$(openssl rand -hex 16)" \
  --port 8080
```

Сохранить выданный API key в `$RUN/NOTES.md` (и в локальный secret store bench-машины; **не коммитить**).

Первый старт: UI/API на `http://192.168.0.88:8080`.  
PC может «подвиснуть» 1–3 минуты — не убивать процесс.

### 5.2. Post-install health

```bash
export STRATA_KEY='<from NOTES>'
curl -sS -H "Authorization: Bearer $STRATA_KEY" \
  http://127.0.0.1:8080/v1/models | python3 -m json.tool | tee "$RUN/strata-models.json"

curl -sS -H "Authorization: Bearer $STRATA_KEY" \
  'http://127.0.0.1:8080/props' | python3 -m json.tool | tee "$RUN/strata-props.json"

nvidia-smi | tee "$RUN/nvidia-smi-after-load.txt"
free -h | tee -a "$RUN/nvidia-smi-after-load.txt"
```

**Pass:**

- model listed, context limit = **262144** (или выбранный);
- short completion работает (см. §6);
- GPU0 занят hot path + expert cache; RAM +35–60 GB vs idle.

### 5.3. Optional: calibrate (после первого успешного short chat)

```bash
./setup.sh --calibrate   # ~5–10 мин, NVIDIA-only; запомнить в NOTES
```

Делать **до** длинной matrix, чтобы все context sizes шли на одном tuned profile.

---

## 6. Smoke (context не важен)

```bash
export STRATA_URL=http://127.0.0.1:8080
export STRATA_KEY='...'

# short chat
curl -sS "$STRATA_URL/v1/chat/completions" \
  -H "Authorization: Bearer $STRATA_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "strata",
    "messages": [{"role":"user","content":"Reply with exactly: pong"}],
    "max_tokens": 16,
    "temperature": 0
  }' | tee "$RUN/smoke-short.json"
```

С bench-машины (`projects-llm-test/llm-tests`):

```bash
# agentbench fast subset against Strata
AGENTBENCH_URL=http://192.168.0.88:8080 \
AGENTBENCH_MODEL=strata \
AGENTBENCH_API_KEY="$STRATA_KEY" \
pytest agentbench/tests -q -m "not slow and not concurrency" \
  | tee "$RUN/agentbench-smoke.txt"
```

> Если agentbench ещё не умеет Bearer key из env — прокинуть через client/settings
> или `Authorization` header в клиенте; зафиксировать патч отдельно, не смешивать
> с matrix.

---

## 7. Матрица контекстов (основной тест)

### 7.1. Стратегия

Один fixed quant (**IQ3_S**), один GPU (**4090**), меняем **размер промпта / заявленный context**.

| Tier | Prompt size (tokens) | Зачем | Ожидание (порядок, по README/DETAILS) |
|---|---:|---|---|
| A | 1 024 | decode baseline | высокий tok/s |
| B | 4 096 | короткий agent turn | prefill ~несколько секунд |
| C | 32 768 | типичный coding-agent prompt | prefill ~десятки секунд |
| D | 65 536 | граница KV streaming | сравнить resident vs stream |
| E | 131 072 | long agent / multi-file | prefill минуты |
| F | **262 144** | native max | worst-case prefill; needle@10/50/90% |
| G (optional) | 384 000 / 512 000 | experimental rope | только если F стабилен |

Для каждой строки матрицы: **N=3** итерации (warmup 1 не в статистику, если время жмёт — хотя бы N=1 + повторить fails).

Метрики в `matrix.csv`:

```text
ts,quant,context_limit,prompt_tokens,gen_tokens,ttft_s,prefill_tps,decode_tps,total_s,finish_reason,vram_used_mib,ram_used_gib,ok,notes
```

### 7.2. Генератор промпта

Использовать существующий `gen_256k_prompt.py` или простой needle:

```bash
# пример: needle-in-haystack на целевой длине
# needle id уникален на run; позиция 10% / 50% / 90% для tier E/F
```

Требования к промпту:

- измеренный tokenizer length ≈ target (±2%);
- вшитый needle `SECRET=<uuid>` на позиции P∈{0.1, 0.5, 0.9} для E/F;
- вопрос в конце: «What is SECRET?»;
- `max_tokens` небольшой (64–256), `temperature=0`, reasoning **low/off** для latency-матрицы.

Отдельный quality pass (§8) — с нормальным reasoning.

### 7.3. Протокол одного прогона

```bash
# псевдокод одного cell
# 1) nvidia-smi snapshot before
# 2) POST /v1/chat/completions with timed curl / python client
# 3) record TTFT (time to first token) if streaming; else total_s + usage
# 4) check finish_reason != length; check needle recall for E/F
# 5) nvidia-smi / free -h after
# 6) cooldown 15–30s между итерациями
```

Streaming рекомендуется для TTFT:

```bash
curl -N -sS "$STRATA_URL/v1/chat/completions" \
  -H "Authorization: Bearer $STRATA_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "strata",
    "stream": true,
    "messages": [{"role":"user","content": "..."}],
    "max_tokens": 128,
    "temperature": 0
  }'
```

### 7.4. Порядок выполнения (чтобы ловить OOM рано)

1. A → B → C (sanity)  
2. D (streaming boundary)  
3. E  
4. F (max) — **только если E стабилен**  
5. Optional G  
6. На F: 3 needle позиции (10/50/90%) × 1–2 repeats  
7. Optional: повторить C/E/F с `--kv q4_0`, затем с `--kv k8v4`  
   (переконфиг через `./setup.sh --setup --context 262144 --kv q4_0 --yes`  
   или правка `strata-*.json` + restart; каждый KV mode — отдельный `$RUN` subdir)

### 7.5. Критерии pass/fail по ячейке

| Условие | Результат |
|---|---|
| HTTP 200, `finish_reason` ∈ {stop, end_turn, …} не `length` при малом max_tokens | OK |
| Engine crash / reconnect / empty content | FAIL — логировать `strata-*.log` |
| Needle не найден на E/F | FAIL quality (отдельно от perf) |
| RAM >95% / OOM killer | STOP matrix, уменьшить context или quant |
| Prefill > 15 мин на F | отметить как impractical для agents; не abort всей matrix |

### 7.6. Переключение context limit без полной переустановки

Для сравнения **заявленного** limit vs фактического prompt:

```bash
# новый profile / перезапись config
./setup.sh --setup --model IQ3_S --context 131072 --vision yes --gpu 0 \
  --data-dir /mnt/data/strata-data --host 0.0.0.0 --api-key "$STRATA_KEY" --port 8080 --yes
```

Веса не качаются повторно. Между context limits — всегда health + short smoke.

Рекомендация: держать engine на **262144** весь matrix и лишь менять **длину промпта**.
Так сравнивается prefill/decode vs filled context, а не разные compile/config.
Отдельный `--context 32768` имеет смысл только если хотите замерить
«короткий KV budget → больше expert cache».

---

## 8. Quality smoke на выбранных context sizes

Не полный qualbench 50 (долго + single-request engine). Минимум:

| Suite | Когда | Команда (с bench host) |
|---|---|---|
| agentbench fast | после smoke | см. §6 |
| qualbench `mcp-tools` | после C (32K) ok | `run_all.py --categories mcp-tools --url http://192.168.0.88:8080 --model strata --tag strata-iq3s` |
| qualbench `long-context` | после E/F | `--categories long-context` (сверить лимиты фикстур 8K/64K/150K с живым context) |
| multimodal smoke | optional | 1–2 image prompts через `/v1/chat/completions` |

Обязательно логировать:

- `finish_reason`
- reasoning tokens vs content (если видны в API)
- wall time / task

Сравнивать не с абсолютом «47/50 FreeToken», а с **тем же subset на FreeToken**
до/после окна (или с сохранёнными отчётами `qualbench/results/`).

---

## 9. Очередь докачки quant’ов (после IQ3_S)

**Статус ladder:**

| # | Model | Download | Status |
|---|---|---:|---|
| 0 | **IQ3_S** | ~84 GB | ✅ done (`/mnt/data/strata-data/models/IQ3_S`, 2026-10-03) |
| 1 | **Q2_0** | ~66 GB | ✅ done (`models/Q2_0`, 2026-10-03) |
| 2 | **IQ2_XS** | ~68 GB | 🔄 **in progress** (`runs/*-download-IQ2_XS`) |
| 3 | **IQ3_XXS** | ~76 GB | ⏳ after IQ2_XS |

Цель — полный ladder оригинального Flash-Next на диске для A/B
скорости/качества на тех же context tiers.

| # | Model | Download (ориентир) | RAM use (ориентир) | Зачем |
|---|---|---:|---:|---|
| 0 | **IQ3_S** | ~84 GB | ~50 GB | primary / best quality |
| 1 | **Q2_0** | ~66 GB | ~34 GB | самый быстрый decode |
| 2 | **IQ2_XS** | ~68 GB | ~36 GB | recommended balance |
| 3 | **IQ3_XXS** | ~76 GB | ~43 GB | почти IQ3_S, чуть быстрее |

Shard 2 (n-gram ~29 GB) и vision encoder у оригинального `qwen` family
**шарятся** между размерами — setup не качает их повторно. Дополнительный
диск сверх IQ3_S: примерно **+110–140 GB** на три shard-1 (не полные 66+68+76).

Места на `/mnt/data` хватает (≥1T free на момент плана).

### 9.1. Когда запускать

1. IQ3_S setup завершился (`--no-start` exit 0; файлы в
   `/mnt/data/strata-data/models/IQ3_S/` без `.part`).
2. Желательно **до** окна stop FreeToken / matrix — качать можно параллельно
   с живым FreeToken (GPU не нужен).
3. Качать **последовательно** (один `./setup.sh --setup` за раз), чтобы не
   душить HF и диск.

### 9.2. Команды (фон, без старта сервера)

```bash
ssh berda@192.168.0.88
cd /mnt/data/strata/Strata
RUN=/mnt/data/strata/runs/$(date +%Y%m%d)-download-ladder
mkdir -p "$RUN"

# Последовательная докачка (один setup за раз). Можно завернуть в nohup снаружи.
for MODEL in Q2_0 IQ2_XS IQ3_XXS; do
  LOG="$RUN/setup-$MODEL.log"
  echo "=== $(date -Is) start $MODEL ===" | tee -a "$RUN/NOTES.md"
  ./setup.sh \
    --setup \
    --yes \
    --family qwen \
    --model "$MODEL" \
    --context 262144 \
    --vision yes \
    --gpu 0 \
    --data-dir /mnt/data/strata-data \
    --no-start \
    >"$LOG" 2>&1 < /dev/null \
    || { echo "FAIL $MODEL" | tee -a "$RUN/NOTES.md"; break; }
  echo "=== $(date -Is) done $MODEL ===" | tee -a "$RUN/NOTES.md"
done
```

Фон всей очереди: обернуть цикл выше в скрипт
`$RUN/ladder.sh`, затем:

```bash
setsid nohup bash "$RUN/ladder.sh" >"$RUN/ladder.out" 2>&1 < /dev/null &
echo $! > "$RUN/ladder.pid"
```

Одноразовая команда на один размер (если удобнее вручную):

```bash
./setup.sh --setup --yes --family qwen --model Q2_0 \
  --context 262144 --vision yes --gpu 0 \
  --data-dir /mnt/data/strata-data --no-start
# затем то же для IQ2_XS и IQ3_XXS
```

### 9.3. Verify после каждого размера

```bash
ls -lah /mnt/data/strata-data/models/Q2_0 \
        /mnt/data/strata-data/models/IQ2_XS \
        /mnt/data/strata-data/models/IQ3_XXS \
        /mnt/data/strata-data/models/IQ3_S
du -sh /mnt/data/strata-data/models/*
# не должно остаться *.part
find /mnt/data/strata-data/models -name '*.part'
```

### 9.4. Как использовать в matrix

Порядок бенчей (после restore/stop FreeToken окна или в отдельном окне):

1. **IQ3_S** — полная matrix A→F (primary).
2. **Q2_0** — только C / E / F (speed ceiling).
3. **IQ2_XS** — только C / E / F (balance).
4. **IQ3_XXS** — только C / E / F (почти-IQ3_S latency).

Переключение без повторного download:

```bash
./setup.sh --setup --yes --family qwen --model Q2_0 \
  --context 262144 --vision yes --gpu 0 \
  --data-dir /mnt/data/strata-data \
  --host 0.0.0.0 --api-key "$STRATA_KEY" --port 8080
# или run-q2_0.sh / run-iq2_xs.sh / run-iq3_xxs.sh / run-iq3_s.sh
```

Колонка `quant=` в `matrix.csv`: `IQ3_S` | `Q2_0` | `IQ2_XS` | `IQ3_XXS`.

---

## 10. Восстановление FreeToken (обязательный финал)

### 10.1. Stop Strata

```bash
# закрыть setup/run window или убить serve-процесс Strata
pgrep -af 'strata|llama-server|setup.sh' || true
# штатно: Ctrl+C в сессии ./setup.sh / run-*.sh
# убедиться что :8080 свободен
ss -lntp | grep 8080 || echo '8080 free'
nvidia-smi
```

### 10.2. Start FreeToken снова

Если units только stop’нуты:

```bash
systemctl --user start freetoken-daemon.service
systemctl --user start freetoken-engine.service

# если engine unit — oneshot и модель поднимает daemon:
/home/berda/freetoken-0.1.3/.venv/bin/ft daemon start \
  /mnt/data/berda-models/models/Qwen3.6-35B-A3B-FP8 -- \
  --moe-strategy offload \
  --allowed-local-media-path /mnt/data/qualbench-mm \
  --served-model-name qwen3.6-35b-a3b \
  --host 0.0.0.0 \
  --port 8000 \
  --cuda-graph-max-bs 4 \
  --max-running-requests 4 \
  --kv-reserve-tokens 300000 \
  --num-tokenizer 0 \
  --tool-call-parser qwen3_coder \
  --reasoning-parser qwen3
```

Если `freetoken-engine.service` был `disable` на время окна — `systemctl --user enable --now freetoken-engine.service`.

Альтернатива (как в runbook §5): `source ~/freetoken/activate.sh` + `setsid nohup ft serve ...`
— использовать **только если** daemon-path не поднимает engine; не запускать оба сразу
(bind conflict на `:8000`).

### 10.3. Verify FreeToken back

```bash
# ждать ready (может занять несколько минут)
for i in $(seq 1 60); do
  curl -sf http://127.0.0.1:8000/v1/models && break
  sleep 5
done
curl -sS http://127.0.0.1:8000/v1/models | python3 -m json.tool | head -40
nvidia-smi
```

**Pass:** `id=qwen3.6-35b-a3b`, `context_length=262144`, GPU0 снова ~loaded.

Короткий regression (с bench host):

```bash
AGENTBENCH_URL=http://192.168.0.88:8000 \
AGENTBENCH_MODEL=qwen3.6-35b-a3b \
pytest agentbench/tests/test_basic_compat.py -q
```

---

## 11. Чеклист исполнения (копипаст)

- [ ] Preflight записан (`$RUN/preflight.txt`)
- [ ] Stakeholders предупреждены про downtime `:8000`
- [ ] `ft daemon stop` + `systemctl --user stop freetoken-engine.service`
- [ ] GPU0 VRAM свободна, `:8000` down
- [ ] `git clone` Strata → `/mnt/data/strata/Strata`
- [ ] `./setup.sh` IQ3_S / context **262144** / GPU0 / data-dir / host 0.0.0.0 + api-key
- [ ] `/v1/models` + short smoke OK
- [ ] Optional `--calibrate`
- [ ] Matrix tiers A→F записаны в `matrix.csv`
- [ ] Needle 10/50/90% на 128K и 262K
- [ ] Optional KV A/B (`q4_0`, `k8v4`) на C/E/F
- [ ] Optional agentbench smoke + qualbench subset
- [ ] **Потом:** докачать ladder `Q2_0` → `IQ2_XS` → `IQ3_XXS` (`--setup --no-start`, §9)
- [ ] **Потом:** C/E/F matrix на каждом ladder quant
- [ ] Strata остановлен, GPU0 свободен
- [ ] FreeToken поднят, `/v1/models` OK
- [ ] agentbench basic compat на FreeToken зелёный
- [ ] NOTES.md + результаты скопированы/закоммичены (без API key)

---

## 12. Риски и митигации

| Риск | Митигация |
|---|---|
| FreeToken не поднимается после окна | хранить точные flags из `serve.json` / unit; fallback `nohup ft serve` из `FREETOKEN_QWEN36_SERVE.md` §5 |
| OOM на 262K IQ3_S | маловероятно при 125 GB; если случится — снизить до 128K или IQ2_XS; включить `--kv q4_0` |
| HF download обрыв | `--data-dir` сохраняет partial; просто перезапустить `./setup.sh` |
| Порт/API key утечка в LAN | обязательный `--api-key`; не светить key в git |
| Путаница портов | FreeToken `:8000`, Strata `:8080` — bench URL менять явно |
| Strata single-request | не гонять concurrency agentbench; matrix строго serial |
| Долгий prefill «завис» | смотреть Monitor/log; не kill раньше 2× ожидаемого времени tier |
| systemd снова поднял FreeToken во время теста | `stop` engine unit; при повторных сюрпризах — `disable` на окно |

---

## 13. Definition of done

1. Есть `matrix.csv` для IQ3_S на 4090 с tiers **A–F** (хотя бы N=1, лучше N=3).  
2. Зафиксированы TTFT/prefill/decode + VRAM/RAM на каждом tier.  
3. Needle recall на **128K и 262K** (3 позиции) записан.  
4. FreeToken снова обслуживает `qwen3.6-35b-a3b` на `:8000` с basic compat green.  
5. Краткий SUMMARY в `$RUN/NOTES.md`: какой max context practical для coding agents на этом хосте.

---

## 14. Follow-ups (вне этого плана)

- **Докачка quant ladder:** Q2_0 (идёт) → IQ2_XS → IQ3_XXS — см. §9.  
- **Bonsai-2 27B:** [`BONSAI2_27B_4090_DOWNLOAD_PLAN.md`](BONSAI2_27B_4090_DOWNLOAD_PLAN.md)
  — `Ternary-Bonsai-2-27B-gguf` PQ2_0 + mmproj; Prism runtime; prefer GPU1 `:8081`.  
- IQ3_S vs FreeToken Qwen3.6-35B-A3B на одинаковом qualbench subset.  
- Strata на GPU1 (5060 Ti) **параллельно** с FreeToken на 4090.  
- `--gpus 0,1` / `--peer-device` для expert cache.  
- Swift 1.5 / Coder семейства.  
- Постоянный systemd user unit для Strata (только если решим держать вместо FreeToken).
