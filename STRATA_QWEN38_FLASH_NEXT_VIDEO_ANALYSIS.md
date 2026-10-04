# Разбор: Strata + Qwen3.8-Flash-Next на 12GB GPU

Видео: [youtube.com/watch?v=i7nSjm5tTRw](https://www.youtube.com/watch?v=i7nSjm5tTRw) —
как 125B MoE крутится на игровой карте через offload GPU/RAM/SSD.

Ниже: тезисы, catches и применимость к локальному стенду
(berdachuk-pc: 5060 Ti 16GB / ~62GB RAM / FreeToken; сервер 88: 4090 24GB / 125GB RAM).

| | |
|---|---|
| Параметры | 125B (+51B n-gram) |
| Active / token | ~6B |
| Headline speed | ~95 t/s (2-bit, short chat) |
| Рекомендуемый RAM | 64GB |

Связанные документы: [`STRATA_QWEN38_FLASH_NEXT_4090_PLAN.md`](STRATA_QWEN38_FLASH_NEXT_4090_PLAN.md),
[`FREETOKEN_QWEN36_SERVE.md`](FREETOKEN_QWEN36_SERVE.md).

---

## Суть за 15 секунд

Заголовок «125B на 12GB» правдив технически, но перекладывает стоимость с
VRAM на системную RAM и SSD. Для больших MoE узкое место — **RAM**, не карта.
Скорость и качество зависят от quant (2-bit vs 3-bit), длины контекста и prefill.

---

## Что обещает видео

| Утверждение | Суть | Оговорка |
|---|---|---|
| 95 tok/s на RTX 5070 | Самый мелкий (2-bit) build, короткие чаты, 64GB DDR5 | Best case; на 128k → ~65 t/s |
| Strata ≫ llama.cpp | Тот же 3-bit: ~65 t/s vs ~15 t/s на том же ПК | Цифры разработчика, не независимый бенч |
| 3-bit ≈ lossless | ISTA-DASLab: >99% среднего score vs full | На LiveCodeBench 2-bit уже −~6 pts |
| SWE-bench Pro > Opus 4.6 Max | Официальные цифры Qwen по Flash-Next | Полная модель / другой runtime, не Strata 2-bit |

---

## Как это устроено

### GPU — hot path

Attention, routing, shared experts, KV-cache + hot expert cache
(~700 experts / GB свободной VRAM).

### RAM — experts

Тысячи MoE-экспертов (видео: 24 576 across 48 layers) живут в RAM
(35–55GB в зависимости от build). CPU считает miss параллельно с GPU.

### SSD — n-gram table

~29GB lookup short word sequences; читаются единицы строк на token →
можно mmap с диска.

### Три ускорителя скорости

| Трюк | Эффект |
|---|---|
| Adaptive expert cache в остатке VRAM | Частые эксперты не гоняются из RAM |
| CPU+GPU overlap на miss | RAM-latency не блокирует весь decode |
| MTP (до 3 token ahead, verify in one pass) | +1.6–1.8×, ответ идентичен |

---

## Три catches (главное в видео)

### 1. RAM, не VRAM

64GB — комфорт для всех build.  
48GB — только мелкие; 32GB — не влезает.  
DDR5 kit ~$1100 в момент съёмки (дефицит от AI DC).

### 2. Prefill убивает агентов

4k ≈ 7s · 32k ≈ 1 мин · 128k ≈ 4 мин до первого токена.

После первого сообщения — incremental. Один чат / один request;
смена сессии = полный re-prefill.

### 3. Quant trade-off

2-bit = headline speed; 3-bit ≈ качество full (~65 t/s).  
Lab scores на math/science/coding, не long agent sessions.

---

## Дополнительно из видео

| Тема | Вердикт видео |
|---|---|
| Swift 1.5 fine-tune | −63% thinking tokens, <1% accuracy loss (claim); мини-чек 8/8, 28s vs 46s |
| Experimental Speed Projection | Не ускорение — refusal-removal vector; на code ухудшает accuracy; off by default |
| Зрелость Strata | Старт 24 сен, 13 версий за 4 дня; баги temp/hang на large VRAM; license на момент съёмки неясен |
| Платформы (по видео) | NVIDIA RTX 30/40/50 + Win/Linux; Mac/AMD — нет (позже Strata добавил AMD — сверять README) |

---

## Применимость к стенду

**Железо в целом подходит.**  
berdachuk-pc: RTX 5060 Ti 16GB + ~62GB RAM + Ubuntu — попадает в «можно
пробовать» зону видео (RTX 50 + ~64GB). 16GB VRAM даёт больший expert
cache, чем 12GB headline-машина.

Сервер `192.168.0.88`: RTX 4090 24GB + 125GB RAM — комфортный профиль для
IQ3_S @ 262K (см. план запуска на 4090).

| Текущий контур | Что меняет это видео |
|---|---|
| FreeToken + Qwen3.6-35B-A3B FP8/NVFP4 | Другая модель (Qwen4-preview 125B/6B+n-gram) и другой engine (Strata) |
| moe_offload_repro уже меряет MoE offload tok/s | Тот же класс вопросов: RAM vs VRAM, CV, prefill vs decode |
| agentbench / qualbench на OpenAI-compatible API | Strata тоже отдаёт localhost API → можно прогнать те же suites |
| qualbench 47/50 + MMMU 80% на 35B-A3B | Flash-Next обещает выше agentic coding — надо мерить у вас, не верить headline |
| Coding agents с большим system+repo context | Prefill 32k–128k = минуты; single-session — слабое место vs серверный FreeToken |

### Практическая рекомендация

- Если цель — «попробовать frontier local coding»: 3-bit build на 5060 Ti
  + 64GB (или IQ3_S на 4090/125GB), затем agentbench smoke + узкий
  qualbench subset (mcp-tools + java-spring), не сразу 50-task.
- Если цель — стабильный agentic loop (Cursor/Codex, multi-turn, длинный
  context): текущий FreeToken 35B-A3B на 4090/5060 Ti остаётся более
  предсказуемым; Flash-Next/Strata — кандидат на A/B, не замена.
- Не включать Experimental Speed Projection для coding evals. Swift 1.5 —
  отдельная ветка с собственной лицензией.

---

## Что видео не доказывает

Независимых длинных agent-run нет; 95 t/s — short-chat best case; SWE-bench
цифры относятся к полной модели, не к 2-bit Strata на 12GB. Для контура
решающий тест — prefill latency на типичном agent prompt + qualbench
pass-rate, а не tok/s в пустом чате.

---

## Источники

- Транскрипт/описание ролика `i7nSjm5tTRw`
- Qwen3.8-Flash-Next model card / tech report
- Strata ([Niko1221/Strata](https://github.com/Niko1221/Strata)) README / FAQ

Дата разбора: 2026-10-03.  
Часть platform/license деталей в видео могла устареть — перед установкой
сверять текущий README.
