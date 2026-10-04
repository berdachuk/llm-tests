# FreeToken models for 192.168.0.88 (RTX 4090)

Какие checkpoint’ы из
[FreeToken `docs/models.md`](https://github.com/FlashML-org/FreeToken/blob/main/docs/models.md)
реально подходят под железо `.88`, и куда ставить
[`nvidia/Qwen3.8-Flash-Next-NVFP4`](https://huggingface.co/nvidia/Qwen3.8-Flash-Next-NVFP4).

Связанные runbook’и:
[`FREETOKEN_QWEN36_SERVE.md`](FREETOKEN_QWEN36_SERVE.md),
[`FREETOKEN_QWEN38_SERVE.md`](FREETOKEN_QWEN38_SERVE.md),
[`STRATA_QWEN38_FLASH_NEXT_4090_PLAN.md`](STRATA_QWEN38_FLASH_NEXT_4090_PLAN.md).

---

## 0. Hardware envelope

| Ресурс | Факт |
|---|---|
| Host | `ssh berda@192.168.0.88` |
| GPU0 | RTX 4090 **24 GB** (primary FreeToken) |
| GPU1 | RTX 5060 Ti **16 GB** (optional second serve) |
| RAM | **125 GiB** usable |
| Disk | `/mnt/data` NVMe |
| Engine | FreeToken (`ft serve` / `ft daemon`), MoE: `--moe-strategy offload` / `hybrid` |
| Current daily | `Qwen3.6-35B-A3B-FP8` on `:8000` |

Правило fit:

- **MoE** → experts в host RAM + hot cache на GPU → упираемся в **RAM**.
- **Dense** → всё в VRAM → упираемся в **24 GB** и убиваем длинный KV.
- **Qwen3.8-Flash-Next** → дополнительно **~47.7 GiB PLE n-gram pinned в RAM**
  ([models.md Notes](https://github.com/FlashML-org/FreeToken/blob/main/docs/models.md)).

---

## 1. Рекомендуемые модели (daily / A/B)

| Prio | Checkpoint | Fit | Зачем |
|---|---|---|---|
| **1** | [`Qwen/Qwen3.6-35B-A3B-FP8`](https://huggingface.co/Qwen/Qwen3.6-35B-A3B-FP8) | ✅ proven | Daily baseline: offload ~31 GB experts, 262K, concurrency 4 |
| **2** | [`nvidia/Qwen3.6-35B-A3B-NVFP4`](https://huggingface.co/nvidia/Qwen3.6-35B-A3B-NVFP4) | ✅ | Тот же класс, меньше footprint → больше KV/cache; на 5060 Ti часто лучше FP8 |
| **3** | [`Qwen/Qwen3-VL-30B-A3B-Instruct`](https://huggingface.co/Qwen/Qwen3-VL-30B-A3B-Instruct) | ✅ | Vision MoE того же envelope; text-only: `--text-model-only` |
| **4** | [`openai/gpt-oss-120b`](https://huggingface.co/openai/gpt-oss-120b) | ✅ | Сильный coding A/B; типично ~60–90 GB RAM |
| **5** | [`openai/gpt-oss-20b`](https://huggingface.co/openai/gpt-oss-20b), [`google/gemma-4-12B-it`](https://huggingface.co/google/gemma-4-12B-it), [`Qwen/Qwen3-VL-8B-Instruct`](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct) | ✅ | Лёгкие / dual-serve на **5060 Ti** |
| **6** | [`nvidia/Gemma-4-26B-A4B-NVFP4`](https://huggingface.co/nvidia/Gemma-4-26B-A4B-NVFP4), [`RedHatAI/Muse-Glimmer-30B-NVFP4`](https://huggingface.co/RedHatAI/Muse-Glimmer-30B-NVFP4) | ✅ likely | Mid MoE альтернативы 35B-A3B |

Опционально того же класса (мало смысла апгрейда):
`Qwen3.5-35B-A3B-FP8`, `Qwen3-30B-A3B`.

---

## 2. Spotlight: Qwen3.8-Flash-Next-NVFP4

| | |
|---|---|
| HF | **[`nvidia/Qwen3.8-Flash-Next-NVFP4`](https://huggingface.co/nvidia/Qwen3.8-Flash-Next-NVFP4)** |
| Также в models.md | [`RadixArk/Qwen3.8-Flash-Next-NVFP4`](https://huggingface.co/RadixArk/Qwen3.8-Flash-Next-NVFP4), [`Qwen/Qwen3.8-Flash-Next-FP8`](https://huggingface.co/Qwen/Qwen3.8-Flash-Next-FP8) |
| Arch | 125B MoE / ~6B active + 51B n-gram (PLE) + MTP |
| Quant | **NVFP4** (ModelOpt) — реалистичный FreeToken-путь на consumer GPU |
| PLE | **~47.7 GiB pinned в host RAM** (не убрать) |
| Fit на .88 | ⚠️ **маргинально** при 125 GiB: PLE ≈48 GB + experts + OS/KV |
| FP8 sibling | ❌ `Qwen3.8-Flash-Next-FP8` (~173 GiB weights) — не для 125 GB |

### Когда брать FreeToken NVFP4 vs Strata

| Цель | Выбор |
|---|---|
| Full-ish quality Flash-Next + OpenAI API + concurrency | FreeToken **[`nvidia/Qwen3.8-Flash-Next-NVFP4`](https://huggingface.co/nvidia/Qwen3.8-Flash-Next-NVFP4)** (experiment window) |
| Max context / single-user / меньше RAM pressure (n-gram на SSD) | **Strata** GGUF IQ3_S / Q2_0 — см. [`STRATA_QWEN38_FLASH_NEXT_4090_PLAN.md`](STRATA_QWEN38_FLASH_NEXT_4090_PLAN.md) |
| Daily agents без риска OOM | Оставить **35B-A3B-FP8** |

Ожидаемый decode (чужие отчёты, не .88): NVFP4 Flash-Next на 5090+~136 GB ≈ **42–65 t/s**.
На 4090 + 125 GB — ожидаемо ниже и с риском нехватки RAM; нужен свой smoke.

### Предлагаемые пути на диске

```text
/mnt/data/berda-models/models/Qwen3.8-Flash-Next-NVFP4/   # hf download target
/mnt/data/freetoken-runs/YYYYMMDD-flash-next-nvfp4/       # NOTES, nvidia-smi, curls
```

### Download (когда решите качать)

```bash
ssh berda@192.168.0.88
mkdir -p /mnt/data/berda-models/models
hf download nvidia/Qwen3.8-Flash-Next-NVFP4 \
  --local-dir /mnt/data/berda-models/models/Qwen3.8-Flash-Next-NVFP4
```

### Serve sketch (после stop текущего `:8000`)

```bash
source ~/freetoken/activate.sh
# optional once: ft bench bw
ft serve \
  --model /mnt/data/berda-models/models/Qwen3.8-Flash-Next-NVFP4 \
  --moe-strategy offload \
  --moe-cache-auto \
  --host 0.0.0.0 --port 8000 \
  --served-model-name qwen3.8-flash-next-nvfp4 \
  --reasoning-parser qwen3 \
  --tool-call-parser qwen3_coder \
  --max-running-requests 1 \
  --kv-reserve-tokens 65536
```

Замечания:

- Стартовать с **`max-running-requests 1`**, пока не подтверждён RAM/VRAM envelope.
- На Ada 4090 NVFP4 backend может уйти в Triton; при сбоях смотреть `--nvfp4-backend triton`.
- Перед serve: `free -h` — желательно **≥100 GiB available** после stop 35B.
- После эксперимента — restore
  [`FREETOKEN_QWEN36_SERVE.md`](FREETOKEN_QWEN36_SERVE.md).

### Smoke checklist

- [ ] Download complete, disk size logged
- [ ] FreeToken 35B stopped; ≥100 GiB RAM free
- [ ] `ft serve` reaches ready; `nvidia-smi` + `free -h` captured
- [ ] Short chat decode tok/s
- [ ] Prefill @ 8K / 32K (и выше, если KV позволяет)
- [ ] Optional: agentbench smoke subset
- [ ] Restore 35B-A3B-FP8

---

## 3. Маргинально / короткий контекст

| Checkpoint | Вердикт |
|---|---|
| [`nvidia/Qwen3.8-27B-NVFP4`](https://huggingface.co/nvidia/Qwen3.8-27B-NVFP4) | Уже меряли: ~22 GB weights → KV **~5.6K** — не daily |
| [`nvidia/Qwen3.6-27B-NVFP4`](https://huggingface.co/nvidia/Qwen3.6-27B-NVFP4) | Тот же dense story |
| [`nvidia/Gemma-4-31B-IT-NVFP4`](https://huggingface.co/nvidia/Gemma-4-31B-IT-NVFP4) | Dense: короткий ctx only |
| [`nvidia/MiniMax-M2.5-NVFP4`](https://huggingface.co/nvidia/MiniMax-M2.5-NVFP4) | ~229B: на 125 GB на грани / скорее нет |

---

## 4. Не брать на .88 (не хватает RAM)

| Checkpoint | Почему |
|---|---|
| [`Qwen/Qwen3.8-Flash-Next-FP8`](https://huggingface.co/Qwen/Qwen3.8-Flash-Next-FP8) | ~173 GiB + PLE ~48 GiB |
| [`deepseek-ai/DeepSeek-V4-Flash-0731`](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731) | Практика ~156–192 GB RAM |
| [`nvidia/GLM-5.2-NVFP4`](https://huggingface.co/nvidia/GLM-5.2-NVFP4), [`nvidia/GLM-4.7-NVFP4`](https://huggingface.co/nvidia/GLM-4.7-NVFP4), [`RedHatAI/GLM-5.3-Flash-NVFP4`](https://huggingface.co/RedHatAI/GLM-5.3-Flash-NVFP4) | Часто 200–256 GB+ |
| [`nvidia/MiniMax-M3-NVFP4`](https://huggingface.co/nvidia/MiniMax-M3-NVFP4) | Крупнее M2.5 |

---

## 5. Практическая раскладка

| Слот | Модель | Порт |
|---|---|---|
| Daily FreeToken | `Qwen3.6-35B-A3B-FP8` | `:8000` GPU0 |
| FreeToken A/B (окно) | **`nvidia/Qwen3.8-Flash-Next-NVFP4`** или `gpt-oss-120b` / `35B-A3B-NVFP4` | `:8000` GPU0 (stop daily) |
| Flash-Next max-ctx personal | Strata IQ3_S / Q2_0 | `:8080` GPU0 (отдельное окно) |
| Sidekick | gpt-oss-20b / VL-8B / Gemma-12B | `:8081` GPU1 |

**Итог:** для FreeToken на .88 лучший daily — **35B-A3B-FP8**.
Для Flash-Next в FreeToken брать именно
**[`nvidia/Qwen3.8-Flash-Next-NVFP4`](https://huggingface.co/nvidia/Qwen3.8-Flash-Next-NVFP4)**
(не FP8), как experiment с жёстким RAM budget; для устойчивого Flash-Next на этой машине параллельно держать Strata-план.
