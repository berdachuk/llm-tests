# qualbench run: freetoken013-longctx

- Server: `http://192.168.0.88:8000`
- Model: `qwen3.6-35b-a3b`
- Selected categories: `long-context`
- Suite commit: `a791f5f1a752eb4347c246dfd24e26c9243a065d`
- Suite git dirty: `True`
- Preflight: requested model present in `/v1/models`
- Advertised context length: `262144`
- Notes: FreeToken upgraded to 0.1.3 on 192.168.0.88; long-context first
- Started: 2026-09-19T07:15:11.165726+00:00
- Finished: 2026-09-19T07:25:44.269962+00:00
- Total wall time: 633.1s
- **Total: 10/10 passed**

| Category | Pass | Total | Wall (s) |
|---|---|---|---|
| long-context | 10 | 10 | 633.1 |

## Task-level detail

### long-context (10/10)
- [PASS] 01-8k-pos10 (37.4s)
- [PASS] 02-8k-pos50 (48.4s)
- [PASS] 03-8k-pos90 (32.4s)
- [PASS] 04-64k-pos10 (55.7s)
- [PASS] 05-64k-pos50 (53.6s)
- [PASS] 06-64k-pos90 (43.6s)
- [PASS] 07-150k-pos10 (102.2s)
- [PASS] 08-150k-pos50 (93.3s)
- [PASS] 09-distractor-64k (63.8s)
- [PASS] 10-distractor-150k (102.0s)
