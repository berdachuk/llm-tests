# Bespoke-Nimble-9B-v3 capability suite

> **License: CC BY-NC 4.0 — research-only.**  
> **Дата:** 2026-10-24 · **base:** `http://192.168.0.175:8009`  
> **Сравнение:** [`../RESULTS_COMPARE_20261024.md`](../RESULTS_COMPARE_20261024.md)

## Capability

- cases: `cases_sd.json` (19 SD)
- total: **19/19 (100%)**
- note: `ranking` remapped to `choice`

### By language

- **en**: 7/7 (100%)
- **ru**: 12/12 (100%)

### By domain

| Domain | Pass |
|---|---|
| packing | 1/1 |
| sd_guardrail | 2/2 |
| sd_issue | 1/1 |
| sd_loop | 2/2 |
| sd_model_routing | 3/3 |
| sd_pr_review | 2/2 |
| sd_rag | 2/2 |
| sd_risk_gate | 3/3 |
| sd_tool_selection | 2/2 |
| support | 1/1 |

### Failures

- none

## Latency (LAN HTTP, exclusive GPU1)

Источник: [`latency.json`](latency.json).

| Сценарий | n | p50 | p95 | mean |
|---|---:|---:|---:|---:|
| short choice | 20 | **1008.5 ms** | 1015.4 ms | 1009.9 ms |
| PR 3 questions | 15 | **3161.6 ms** | 3197.2 ms | 3167.9 ms |

Ориентиры A/B: FRIDA 14 / 24 ms · decider 20 / 53 ms (те же сценарии, ранее).

## VRAM / режим

- Exclusive GPU1: ASR/TEI/Gemma/FRIDA/decider stopped на время прогона
- Load: `device_map=auto`, max GPU ~12 GiB → ~**10.4 GiB** used, free ≥2 GiB
- После теста: nimble `compose down`; ASR/TEI/Gemma восстановлены

## Notes

- A/B vs FRIDA-Decisions и decider-2b на том же `cases_sd.json`
- Soft floors при `--gate`: RU≥50%, EN≥30% (здесь 100% без gate)
