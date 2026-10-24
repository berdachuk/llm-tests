# Bespoke-Nimble-9B-v3 capability A/B (research-only)

**License: CC BY-NC 4.0 — не для коммерческого / клиентского billing Avroflex.**

Прогон тех же SD-кейсов, что у FRIDA (`../frida-decisions/cases_sd.json`),
против `POST http://192.168.0.175:8009/v1/systemone` (exclusive GPU1).

`ranking` → `choice` (у Nimble нет ranking).

## Отчёты (2026-10-24)

| Файл | Содержание |
|---|---|
| [`RESULTS_COMPARE_20261024.md`](RESULTS_COMPARE_20261024.md) | A/B vs FRIDA / decider: suite, latency, VRAM, выводы |
| [`results-cap-latest/REPORT.md`](results-cap-latest/REPORT.md) | Итог suite 19/19 + by domain |
| [`results-cap-latest/latency.json`](results-cap-latest/latency.json) | short / PR 3q p50/p95 |
| [`TEST_PLAN.md`](TEST_PLAN.md) | План и DoD (закрыт) |

**Итог:** suite **19/19**; short p50 ~**1009 ms**, PR 3q p50 ~**3162 ms**. Контейнер после теста **down**.

## Запуск

```bash
export NIMBLE_BASE=http://192.168.0.175:8009
# exclusive GPU1 — см. IaC README
python3 run_capability_suite.py
python3 run_capability_suite.py --gate   # soft floors RU>=50% EN>=30%
```

IaC / smoke: `avroflex-infra/llm-88/bespoke-nimble-9b-v3/`.
