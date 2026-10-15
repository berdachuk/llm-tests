# qualbench run: strata-iq3s-mcp-longctx

- Server: `http://192.168.0.88:8080`
- Model: `qwen3.8-flash-next-iq3_s`
- Selected categories: `mcp-tools, long-context`
- Suite commit: `3d8d639504115ca31dfa6c5d1c015ab9a5931c46`
- Suite git dirty: `True`
- Preflight: requested model present in `/v1/models`
- Notes: After stop GPU1 ASR/embeddings; LAN :8080 via iptables ACCEPT; Strata restarted; QUALBENCH_API_KEY; plan §8
- Started: 2026-10-15T08:08:39.294016+00:00
- Finished: 2026-10-15T08:15:31.290434+00:00
- Total wall time: 412.0s
- **Total: 18/18 passed**

| Category | Pass | Total | Wall (s) |
|---|---|---|---|
| mcp-tools | 8 | 8 | 15.0 |
| long-context | 10 | 10 | 396.9 |

## Task-level detail

### mcp-tools (8/8)
- [PASS] 01-single-tool-required-args (2.1s)
- [PASS] 02-enum-selection (2.1s)
- [PASS] 03-numeric-coercion (1.7s)
- [PASS] 04-nested-object-args (2.4s)
- [PASS] 05-tool-disambiguation (1.8s)
- [PASS] 06-missing-info-no-premature-call (1.6s)
- [PASS] 07-multi-step-context-carry (1.5s)
- [PASS] 08-array-argument (1.8s)

### long-context (10/10)
- [PASS] 01-8k-pos10 (8.3s)
- [PASS] 02-8k-pos50 (8.1s)
- [PASS] 03-8k-pos90 (7.9s)
- [PASS] 04-64k-pos10 (36.4s)
- [PASS] 05-64k-pos50 (36.1s)
- [PASS] 06-64k-pos90 (21.5s)
- [PASS] 07-150k-pos10 (77.4s)
- [PASS] 08-150k-pos50 (77.1s)
- [PASS] 09-distractor-64k (37.4s)
- [PASS] 10-distractor-150k (86.0s)
