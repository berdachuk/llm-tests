# qualbench run: fp8-longctx-retry

- Server: `http://127.0.0.1:8000`
- Model: `qwen3.6-35b-a3b`
- Started: 2026-09-03T07:28:45.858436+00:00
- Finished: 2026-09-03T07:48:58.379258+00:00
- Total wall time: 1212.5s
- **Total: 10/10 passed**

| Category | Pass | Total | Wall (s) |
|---|---|---|---|
| long-context | 10 | 10 | 1212.5 |

## Task-level detail

### long-context (10/10)
- [PASS] 01-8k-pos10 (87.6s)
- [PASS] 02-8k-pos50 (73.4s)
- [PASS] 03-8k-pos90 (90.6s)
- [PASS] 04-64k-pos10 (75.4s)
- [PASS] 05-64k-pos50 (117.3s)
- [PASS] 06-64k-pos90 (104.9s)
- [PASS] 07-150k-pos10 (164.0s)
- [PASS] 08-150k-pos50 (178.6s)
- [PASS] 09-distractor-64k (115.1s)
- [PASS] 10-distractor-150k (204.9s)
