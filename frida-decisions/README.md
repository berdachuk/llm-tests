# FRIDA-Decisions tests (`.175:8006`)

Live decision model: `POST /pooling` (not chat).

## Suites

| Script | What |
|---|---|
| `run_lan_tests.sh` | Smoke: regression ports, 4 types, latency, catalog 50 |
| `run_capability_suite.py` + `cases_sd.json` | RU/EN capability cases, **software-dev** focused |

Capability cases cover (from FRIDA/Habr + [Jev coding agents](https://www.jevtypesafeai.com/jev/engineering-for-coding-agents)):

- model routing (`choice`)
- tool selection (`choice`)
- risk gate (`noul` + `choice` allow/confirm/block)
- PR risk / security (`choice` + `noul` + `score`)
- loop detection (`noul`)
- RAG code rerank (`ranking`)
- prompt injection (`noul`)
- issue triage (`choice` + `score`)
- multi-question packing

RU gate: ≥85% (all RU cases expected to pass).  
EN gate: ≥50% soft floor (model is RU-primary; EN ~57% on JevBench per authors).

```bash
export FRIDA_BASE=http://192.168.0.175:8006
./run_lan_tests.sh
python3 run_capability_suite.py --base "$FRIDA_BASE"
python3 run_capability_suite.py --lang ru
python3 run_capability_suite.py --lang en
```

Отчёт с выводами и сравнением с Jev / Qwen / decider-2b:  
[`RESULTS_COMPARE_20261024.md`](RESULTS_COMPARE_20261024.md).
