# Per-case results — Bespoke-Nimble-9B-v3

> CC BY-NC 4.0 · research-only · 2026-10-24

| Case | Lang | Domain | Result | Latency (ms) |
|---|---|---|---|---:|
| `ru_support_triage_4types` | ru | `support` | PASS | 4482.5 |
| `ru_model_routing` | ru | `sd_model_routing` | PASS | 1038.1 |
| `ru_model_routing_hard` | ru | `sd_model_routing` | PASS | 1056.6 |
| `ru_tool_selection` | ru | `sd_tool_selection` | PASS | 1060.9 |
| `ru_risk_gate_rm` | ru | `sd_risk_gate` | PASS | 2095.6 |
| `ru_risk_gate_safe_ls` | ru | `sd_risk_gate` | PASS | 2094.6 |
| `ru_pr_risk_gate` | ru | `sd_pr_review` | PASS | 3259.2 |
| `ru_loop_detection` | ru | `sd_loop` | PASS | 1016.4 |
| `ru_rag_rerank_code` | ru | `sd_rag` | PASS | 1059.2 |
| `ru_prompt_injection` | ru | `sd_guardrail` | PASS | 998.1 |
| `ru_issue_triage` | ru | `sd_issue` | PASS | 2177.6 |
| `en_model_routing` | en | `sd_model_routing` | PASS | 1001.3 |
| `en_tool_selection` | en | `sd_tool_selection` | PASS | 1016.8 |
| `en_risk_gate_rm` | en | `sd_risk_gate` | PASS | 2114.7 |
| `en_pr_risk_gate` | en | `sd_pr_review` | PASS | 3155.0 |
| `en_rag_rerank_code` | en | `sd_rag` | PASS | 1062.2 |
| `en_prompt_injection` | en | `sd_guardrail` | PASS | 1005.2 |
| `en_loop_detection` | en | `sd_loop` | PASS | 996.4 |
| `ru_multi_q_packing` | ru | `packing` | PASS | 3154.5 |

## Latency summary

- **short_choice**: n=20 p50=1008.5 ms p95=1015.4 ms mean=1009.9 ms
- **pr_3q**: n=15 p50=3161.6 ms p95=3197.2 ms mean=3167.9 ms
