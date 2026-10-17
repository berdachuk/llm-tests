# Plan: Strata Unsloth **UD-Q4_K_XL** on `llm-server` (`.175`)

> Источник: [docs/UNSLOTH_Q4.md](https://github.com/Niko1221/Strata/blob/main/docs/UNSLOTH_Q4.md)  
> Дата плана: **2026-10-15**  
> Статус: **прод cutover на UD-Q4_K_XL** (2026-10-17). IQ3_S снимок: STRATA_IQ3S_RESTORE_SNAPSHOT.md.

## 1. Что это

| | |
|---|---|
| Quant | Unsloth **UD-Q4_K_XL** (смесь Q4_K / Q5_1 / Q8_0 + PLE IQ4_NL), не «чистый Q4» |
| Repo / rev | `unsloth/Qwen3.8-Flash-Next-GGUF`, revision **`38bb39e`** |
| Размер | **4 шарда, 111.3 GB** (+ pack ~1.4 GB, MTP уже есть) |
| Served id (когда поднимем) | `qwen3.8-flash-next-ud-q4_k_xl` |
| Качество vs llama.cpp | argmax ~97–99% на коротких ответах; ближе к full, чем IQ3_S |
| Скорость при нехватке RAM | на 64 GB с `--resident-budget-gib 40` decode **~7–8.5 t/s** (SSD streaming); IQ3_S на той же карте ~53 t/s |
| Наш хост | **125 GiB RAM** → эксперты (~72 GiB) + запас **влезают в RAM** (~88 GB порог «все эксперты»). Ожидаем decode заметно выше budget-режима |

## 2. Файлы (SHA из UNSLOTH_Q4.md)

| File | Bytes |
|---|---:|
| `…-00001-of-00004.gguf` | 10,946,624 |
| `…-00002-of-00004.gguf` | 49,859,583,136 |
| `…-00003-of-00004.gguf` | 49,376,141,504 |
| `…-00004-of-00004.gguf` | 12,087,983,520 |

Каталог загрузки: `/mnt/data/strata-data/models/UD-Q4_K_XL/`  
Логи: `/mnt/data/strata/runs/20261015-ud-q4_k_xl-download/`

## 3. Почему download отделён от cutover

1. Прод Bifrost/OpenCode сидит на **UD-Q4_K_XL** (`qwen3.8-flash-next-ud-q4_k_xl`, `:8080`).
2. `./setup.sh --setup --family unsloth …` может переписать default config — **не запускать** пока идёт только download.
3. Тест Q4 лучше на **отдельном порту** (например `:8081`) или в окне downtime.

## 4. Этапы

| # | Шаг | Статус |
|---|---|---|
| 1 | Фоновая загрузка 4 шардов (HF, resumable) | **done** |
| 2 | `sha256sum` по таблице UNSLOTH_Q4 | **done** |
| 3 | Pack: `iq_pack.py --compat-bf16` → `packs/ud-q4_k_xl` | **done** |
| 4 | Config `strata-ud-q4_k_xl.json`, port **8080**, GPU0 cutover | **done** |
| 5 | Smoke + matrix A–F + qualbench-50 vs IQ3_S | **done** (48/50; matrix F calib PASS) |
| 6 | Решение: оставить IQ3_S / dual / cutover | **done** — прод **UD-Q4_K_XL**; IQ3_S snapshot for rollback |

Рекомендуемый pack (когда веса готовы):

```bash
cd /mnt/data/strata/Strata
.venv/bin/python tools/iq_pack.py \
  --gguf /mnt/data/strata-data/models/UD-Q4_K_XL/Qwen3.8-Flash-Next-UD-Q4_K_XL-00001-of-00004.gguf \
  --out /mnt/data/strata-data/packs/ud-q4_k_xl \
  --compat-bf16
```

На 125 GB RAM: без `--resident-budget-gib` (все эксперты в RAM), если setup/engine согласятся; иначе budget ≈ `RAM−24` ≈ **100** (cap по размеру экспертов).

## 5. Риски

- Disk ~111 GB — на `.175` свободно **~900 GB**, ок.
- Не трогать `strata-ud-q4_k_xl.service` / nginx / Bifrost до явного окна теста.
- Prefill/decode Q4 при полном RAM — измерить; не предполагать win над IQ3_S по wall time.

## 6. Мониторинг загрузки

```bash
ssh berda@192.168.0.175
tail -f /mnt/data/strata/runs/20261015-ud-q4_k_xl-download/download.log
du -sh /mnt/data/strata-data/models/UD-Q4_K_XL
ls -lh /mnt/data/strata-data/models/UD-Q4_K_XL
```
