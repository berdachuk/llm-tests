# qualbench run: freetoken013-mm-longctx

- Server: `http://192.168.0.88:8000`
- Model: `qwen3.6-35b-a3b`
- Selected categories: `long-context`
- Suite commit: `a791f5f1a752eb4347c246dfd24e26c9243a065d`
- Suite git dirty: `True`
- Preflight: requested model present in `/v1/models`
- Advertised context length: `262144`
- Notes: post-multimodal-enable run: --text-model-only removed, vision tower active
- Started: 2026-09-19T08:33:10.868411+00:00
- Finished: 2026-09-19T08:43:34.079374+00:00
- Total wall time: 623.2s
- **Total: 10/10 passed**

| Category | Pass | Total | Wall (s) |
|---|---|---|---|
| long-context | 10 | 10 | 623.2 |

## Task-level detail

### long-context (10/10)
- [PASS] 01-8k-pos10 (25.3s)
- [PASS] 02-8k-pos50 (40.7s)
- [PASS] 03-8k-pos90 (40.2s)
- [PASS] 04-64k-pos10 (51.8s)
- [PASS] 05-64k-pos50 (66.0s)
- [PASS] 06-64k-pos90 (50.2s)
- [PASS] 07-150k-pos10 (98.3s)
- [PASS] 08-150k-pos50 (87.5s)
- [PASS] 09-distractor-64k (57.5s)
- [PASS] 10-distractor-150k (104.9s)
