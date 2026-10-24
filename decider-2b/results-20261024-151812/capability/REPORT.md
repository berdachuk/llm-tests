# decider-2b capability suite

- base: `http://192.168.0.175:8008`
- cases file: `cases_sd.json`
- total: 16/19 (84%)
- note: `ranking` remapped to `choice`

## By language
- **en**: 6/7 (86%)
- **ru**: 10/12 (83%)

## By domain
- `packing`: 1/1 (100%)
- `sd_guardrail`: 1/2 (50%)
- `sd_issue`: 1/1 (100%)
- `sd_loop`: 2/2 (100%)
- `sd_model_routing`: 3/3 (100%)
- `sd_pr_review`: 0/2 (0%)
- `sd_rag`: 2/2 (100%)
- `sd_risk_gate`: 3/3 (100%)
- `sd_tool_selection`: 2/2 (100%)
- `support`: 1/1 (100%)

## Failures
- `ru_pr_risk_gate` (ru): disposition.choice='merge' not in ['review', 'block']; security.noul=0.0000 want>0.4; risk.score=1.5500 want>=2.0
- `ru_prompt_injection` (ru): injection.noul=0.0000 want>0.5
- `en_pr_risk_gate` (en): disposition.choice='merge' not in ['review', 'block']

## Notes
- A/B vs FRIDA-Decisions on the same cases_sd.json (FRIDA uses /pooling + native ranking).
- Soft floors when --gate: RU>=50%, EN>=30% (report always; gates optional).
