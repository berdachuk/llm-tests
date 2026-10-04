# Plan: Ternary-Bonsai-2-27B на berdachuk-pc (192.168.0.73)

Коллекция: [prism-ml/bonsai-2](https://huggingface.co/collections/prism-ml/bonsai-2).  
Хост: **этот компьютер** — `berdachuk-pc` / `192.168.0.73` (user `berdachuk`).

Связано: план для сервера 88 —
[`BONSAI2_27B_4090_DOWNLOAD_PLAN.md`](BONSAI2_27B_4090_DOWNLOAD_PLAN.md)
(тот же вес, другой host/GPU/порт).

---

## Inventory (проверено 2026-10-04)

| Ресурс | Факт | Вердикт |
|---|---|---|
| Host | berdachuk-pc, 192.168.0.73 | OK |
| OS | Ubuntu (локальный desktop) | OK |
| CPU | i5-13400, 16 threads | OK (AVX2) |
| RAM | **62 GiB** (~45 GiB available) | OK (модели ~6–8 GB resident) |
| GPU | **RTX 5060 Ti 16 GB**, driver 595.91.07 | OK (≥8–12 GB нужно) |
| Disk `/` | 916G, **89G free (90%)** | тесно — не сюда |
| Disk `/mnt/nvme1n1p1` | 938G, **130G free** | **✅ data dir** |
| Disk `/mnt/data_sdb1` | 469G, 61G free | запасной |
| Ports | `:8080` занят; `:11434` Ollama | Bonsai → **`:8081`** |

GPU idle footprint сейчас ~0.7 GB — карта свободна для serve.

---

## Выбор модели из серии

| Repo в коллекции | Формат | Вердикт для .73 |
|---|---|---|
| **[prism-ml/Ternary-Bonsai-2-27B-gguf](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf)** | GGUF PTQ1_0 / PQ2_0 | **✅ primary** — Linux CUDA |
| prism-ml/Ternary-Bonsai-2-27B-mlx-2bit | MLX 2-bit | ❌ Mac only |
| prism-ml/Ternary-Bonsai-2-27B-gguf-dev | GGUF dev | ❌ не нужен |
| Ternary Bonsai 2 WebGPU Kernels | browser | ❌ не серверный serve |

Base: **Qwen3.8-27B** dense hybrid-attention (~75% linear). Context **262K**.  
Apache-2.0. Claim ~98% FP16 @ ~6–7 GB.

### Packing для 5060 Ti 16GB

| Pack | Size | 256K context (ориентир) | Рекомендация |
|---|---:|---|---|
| **PQ2_0** | 7.21 GB | ~12.2 GB VRAM @ q4_0 KV | **✅ качать первым** (default Bonsai-demo, быстрее prefill) |
| **PTQ1_0** | 5.95 GB | ~11.0 GB VRAM @ q4_0 KV | optional A/B / запас VRAM |
| mmproj Q8_0 | 0.63 GB | +VRAM только при image | **да** |

Оба packing комфортно влезают в **16 GB** даже на полном 256K с q4_0 KV.  
С f16 KV на 256K PQ2_0 будет туго (~16 GB) — для max-context serve предпочитать
**q4_0 / calibrated KV** (см. Bonsai-demo `KV-CACHE.md` / `BONSAI_KV4=1`).

**Итого к скачиванию:** `PQ2_0` + `mmproj` (~8 GB). Optional: `PTQ1_0` (+6 GB).

---

## Runtime (обязательно)

Не работает в stock llama.cpp / Ollama / LM Studio / Strata / FreeToken.

Нужен [Bonsai-demo](https://github.com/PrismML-Eng/Bonsai-demo) /
[PrismML-Eng/llama.cpp](https://github.com/PrismML-Eng/llama.cpp).

Порт: **`:8081`** (`:8080` уже занят на этой машине).

---

## Пути

```text
/mnt/nvme1n1p1/bonsai/
  Bonsai-demo/          # git clone
  models/               # если download вручную через hf
  runs/YYYYMMDD-*/      # логи
```

Не класть на `/` (осталось ~89G, диск на 90%).

---

## Когда качать

- Download **можно сейчас** — GPU не нужен; ~8 GB, минуты–десятки минут.
- Не параллелить с тяжёлым HF на 88, если общий канал узкий (локальный
  download с HF независим от 88, но WAN один).
- Serve — в любой момент; не требует stop сервисов на `:8080`/Ollama, если
  VRAM хватает (~12 GB peak на 256K). Если `:8080` уже держит большую модель
  на GPU — сначала проверить `nvidia-smi`.

---

## Команды скачивания (запланировано — не запускать без OK)

### Вариант A — Bonsai-demo setup (предпочтительно)

```bash
# на berdachuk-pc (уже здесь)
mkdir -p /mnt/nvme1n1p1/bonsai/runs/$(date +%Y%m%d)-download
cd /mnt/nvme1n1p1/bonsai
git clone --depth 1 https://github.com/PrismML-Eng/Bonsai-demo.git
cd Bonsai-demo

# default = Bonsai 2 27B PQ2_0 (+ mmproj). Сверить ./setup.sh --help / AGENTS.md
setsid nohup ./setup.sh \
  > /mnt/nvme1n1p1/bonsai/runs/$(date +%Y%m%d)-download/setup.log \
  2>&1 < /dev/null &
echo $! > /mnt/nvme1n1p1/bonsai/runs/$(date +%Y%m%d)-download/setup.pid
```

### Вариант B — только веса с HF

```bash
mkdir -p /mnt/nvme1n1p1/bonsai/models
hf download prism-ml/Ternary-Bonsai-2-27B-gguf \
  --include '*PQ2_0*' '*mmproj*' \
  --local-dir /mnt/nvme1n1p1/bonsai/models/Ternary-Bonsai-2-27B-gguf
```

Бинарники всё равно через Bonsai-demo.

---

## Serve после download

```bash
cd /mnt/nvme1n1p1/bonsai/Bonsai-demo
# сверить актуальные env в scripts/start_llama_server.sh / AGENTS.md
CUDA_VISIBLE_DEVICES=0 \
BONSAI_PORT=8081 \
./scripts/start_llama_server.sh
# API: http://192.168.0.73:8081/v1  или http://127.0.0.1:8081/v1
```

Для длинного context на 16GB:

- предпочитать q4_0 / `BONSAI_KV4=1` (если demo поддерживает);
- при vision + длинном контексте: `BONSAI_MMPROJ_CPU=1` (projector в RAM).

Sampling (thinking): `temperature=1.0`, `top_p=0.95`, `top_k=20`, `min_p=0.05`.  
Effort: default `xhigh`; для latency — `medium` (`low` ≈ xhigh).  
`max_tokens` ≥ 16384.

---

## Тесты

| Тест | Цель |
|---|---|
| `/health` + short chat | alive |
| agentbench fast против `:8081` | wire-compat |
| qualbench `mcp-tools` | tools |
| vision smoke (mmproj) | multimodal |
| context 32K / 128K / 256K | practical max на 16GB |

Сравнивать с FreeToken/Strata на 88 осознанно: это **27B dense ternary**, не
125B MoE и не 35B-A3B FP8.

---

## Чеклист

- [ ] Место на `/mnt/nvme1n1p1` ≥ 20 GB free
- [ ] `git clone` Bonsai-demo
- [ ] Download **PQ2_0** + **mmproj**
- [ ] Optional PTQ1_0
- [ ] Serve на `:8081`, GPU VRAM OK (`nvidia-smi`)
- [ ] Smoke + agentbench subset
- [ ] NOTES: tok/s, TTFT @ 32K/128K/256K на 5060 Ti

---

## Статус

| Item | Status |
|---|---|
| Выбор | **Ternary-Bonsai-2-27B-gguf / PQ2_0 (+ mmproj)** |
| Fit на 5060 Ti 16GB / 62GB RAM | **да** (256K с q4_0 KV) |
| Data dir | `/mnt/nvme1n1p1/bonsai/` |
| Download | **запланировано, не запущено** |
| Port | `:8081` |

Дата плана: 2026-10-04.
