# Plan: Ternary-Bonsai-2-27B на 192.168.0.88

Коллекция: [prism-ml/bonsai-2](https://huggingface.co/collections/prism-ml/bonsai-2).  
Хост: `ssh berda@192.168.0.88` (RTX 4090 24GB + RTX 5060 Ti 16GB, 125GB RAM).

Связано: [`STRATA_QWEN38_FLASH_NEXT_4090_PLAN.md`](STRATA_QWEN38_FLASH_NEXT_4090_PLAN.md)
(Strata ladder качается отдельно; **не смешивать runtime**).  
Тот же вес на desktop `.73`: [`BONSAI2_27B_73_DOWNLOAD_PLAN.md`](BONSAI2_27B_73_DOWNLOAD_PLAN.md).

---

## Выбор модели из серии

| Repo в коллекции | Формат | Вердикт для 88 |
|---|---|---|
| **[prism-ml/Ternary-Bonsai-2-27B-gguf](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf)** | GGUF PTQ1_0 / PQ2_0 | **✅ primary** — Linux CUDA, OpenAI API через Prism llama.cpp |
| prism-ml/Ternary-Bonsai-2-27B-mlx-2bit | MLX 2-bit | ❌ Mac only |
| prism-ml/Ternary-Bonsai-2-27B-gguf-dev | GGUF dev | ❌ не нужен для prod/bench |
| Ternary Bonsai 2 WebGPU Kernels | browser demo | ❌ не серверный serve |

Base: **Qwen3.8-27B** (dense hybrid-attention), не MoE Flash-Next.  
Context: **262K**. License: Apache-2.0. Claim: ~98% FP16 intelligence @ ~6–7 GB.

### Какой packing качать

| Pack | Size | Зачем | Рекомендация |
|---|---:|---|---|
| **PQ2_0** | 7.21 GB | быстрее prefill; **default Bonsai-demo** | **качать первым** |
| **PTQ1_0** | 5.95 GB | самый маленький (1.75 bpw) | optional A/B / 5060 Ti dual-serve |
| mmproj Q8_0 | 0.63 GB | vision | **да**, для multimodal smoke |

На **4090 24GB** оба packing спокойно держат **256K** context (при q4_0 KV —
~11–12 GB; с f16 KV тоже влезает с запасом). На **5060 Ti 16GB** — тоже OK
для PQ2_0 @ 256K с q4_0 KV.

**Итого к скачиванию:** `PQ2_0` + `mmproj` (~8 GB). Optional позже: `PTQ1_0`.

---

## Критическое ограничение runtime

Эти GGUF **не грузятся** в:

- stock llama.cpp / Ollama / LM Studio (стандартный GGUF runtime)
- **Strata**
- **FreeToken**

Нужен [PrismML-Eng/llama.cpp](https://github.com/PrismML-Eng/llama.cpp) fork /
[Bonsai-demo](https://github.com/PrismML-Eng/Bonsai-demo) (`./setup.sh` тянет
правильные бинарники). Типы `PTQ1_0` / `PQ2_0` + Hadamard path только там.

Порт: **не** `:8000` (FreeToken) и желательно не конфликтовать со Strata `:8080`
→ использовать **`:8081`** (или `:8090`).

---

## Когда качать

1. **Сейчас можно параллельно** с Strata Q2_0 download — разные каталоги, HF
   bandwidth поделится; если HF начнёт throttle — отложить до конца Strata Q2_0.
2. Serve/bench — **отдельное окно**: либо на **GPU1 (5060 Ti)** рядом с FreeToken
   на 4090, либо временно вместо FreeToken на 4090.

Предпочтительный serve-профиль для тестов без downtime FreeToken:

| Role | GPU | Port | Model |
|---|---|---|---|
| FreeToken (baseline) | GPU0 4090 | `:8000` | qwen3.6-35b-a3b |
| Bonsai-2 | GPU1 5060 Ti | `:8081` | Ternary-Bonsai-2-27B PQ2_0 |

---

## Пути на диске

```text
/mnt/data/bonsai/
  Bonsai-demo/          # git clone PrismML-Eng/Bonsai-demo
  models/               # GGUF + mmproj (или то, что кладёт setup.sh)
  runs/YYYYMMDD-*/      # логи download / serve
```

Места: ~8–15 GB (PQ2_0 + mmproj [+ PTQ1_0]). На `/mnt/data` хватает.

---

## Команды скачивания (запланировано — ещё не запущено)

### Вариант A — официальный demo setup (предпочтительно)

```bash
ssh berda@192.168.0.88
mkdir -p /mnt/data/bonsai/runs/$(date +%Y%m%d)-download
cd /mnt/data/bonsai
git clone --depth 1 https://github.com/PrismML-Eng/Bonsai-demo.git
cd Bonsai-demo

# По умолчанию demo тянет Bonsai 2 27B PQ2_0 (+ mmproj).
# Уточнить флаги в ./setup.sh --help / AGENTS.md перед запуском
# (BONSAI_MODEL / format env — сверить актуальную доки).
setsid nohup ./setup.sh > /mnt/data/bonsai/runs/$(date +%Y%m%d)-download/setup.log \
  2>&1 < /dev/null &
echo $! > /mnt/data/bonsai/runs/$(date +%Y%m%d)-download/setup.pid
```

`./setup.sh` обычно **только install+download**, без авто-start сервера
(start отдельно: `./scripts/start_llama_server.sh`).

### Вариант B — прямой HF download весов

```bash
mkdir -p /mnt/data/bonsai/models
# нужен huggingface-cli / hf
hf download prism-ml/Ternary-Bonsai-2-27B-gguf \
  --include '*PQ2_0*' '*mmproj*' \
  --local-dir /mnt/data/bonsai/models/Ternary-Bonsai-2-27B-gguf
# optional:
# hf download prism-ml/Ternary-Bonsai-2-27B-gguf \
#   --include '*PTQ1_0*' \
#   --local-dir /mnt/data/bonsai/models/Ternary-Bonsai-2-27B-gguf
```

Бинарники всё равно ставить через Bonsai-demo / Prism fork.

---

## Serve (после download; отдельно от Strata window)

```bash
cd /mnt/data/bonsai/Bonsai-demo
# пример — сверить актуальные флаги в scripts/start_llama_server.sh / AGENTS.md
CUDA_VISIBLE_DEVICES=1 \
BONSAI_PORT=8081 \
./scripts/start_llama_server.sh
# API: http://192.168.0.88:8081/v1
```

Sampling (thinking default): `temperature=1.0`, `top_p=0.95`, `top_k=20`,
`min_p=0.05`. Reasoning effort: default `xhigh`; для latency — `medium`
(`low` не поддерживается → ведёт себя как xhigh).  
Generous `max_tokens` (≥16384) — модель думает до ответа.

---

## Тесты после подъёма

| Тест | Зачем |
|---|---|
| `/v1/models` + short chat | alive |
| agentbench fast (`not slow and not concurrency`) | wire-compat |
| qualbench `mcp-tools` | tool-calling |
| optional vision smoke (mmproj) | multimodal |
| context smoke 32K / 128K / 262K | hybrid-attn longctx vs Strata MoE |

Сравнивать с FreeToken Qwen3.6-35B-A3B и с Strata Flash-Next **на одинаковых
subset’ах**, помня что это другой класс модели (27B dense ternary vs 125B MoE).

---

## Чеклист

- [ ] Strata Q2_0 download не конфликтует / завершён или HF ок с двумя потоками
- [ ] `git clone` Bonsai-demo → `/mnt/data/bonsai/Bonsai-demo`
- [ ] Download **PQ2_0** + **mmproj** (~8 GB)
- [ ] Optional: PTQ1_0
- [ ] Smoke `./scripts/start_llama_server.sh` на **GPU1 :8081** (FreeToken жив)
- [ ] agentbench / qualbench subset
- [ ] NOTES: tok/s, TTFT @ 32K/128K, pass-rate vs FreeToken baseline

---

## Статус

| Item | Status |
|---|---|
| Выбор модели | **Ternary-Bonsai-2-27B-gguf / PQ2_0 (+ mmproj)** |
| Download | **запланировано, не запущено** |
| Runtime | Prism Bonsai-demo only |
| Serve target | GPU1 `:8081` preferred (без stop FreeToken) |

Дата плана: 2026-10-04.
