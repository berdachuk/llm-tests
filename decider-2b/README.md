# decider-2b capability A/B

Прогон тех же SD-кейсов, что у FRIDA (`../frida-decisions/cases_sd.json`),
против `POST http://192.168.0.175:8008/v1/systemone`.

`ranking` → `choice` (у decider нет ranking).

```bash
export DECIDER_BASE=http://192.168.0.175:8008
python3 run_capability_suite.py
python3 run_capability_suite.py --gate   # soft floors RU>=50% EN>=30%
```

IaC / smoke: `avroflex-infra/llm-88/decider-2b/`.

Исследование «локальный Jev на EmbeddingGemma-2» (подход Agurov):  
[`RESEARCH_EMBEDDINGGEMMA2_LOCAL_JEV.md`](RESEARCH_EMBEDDINGGEMMA2_LOCAL_JEV.md).

Отчёт A/B: [`RESULTS_COMPARE_20261024.md`](RESULTS_COMPARE_20261024.md).
