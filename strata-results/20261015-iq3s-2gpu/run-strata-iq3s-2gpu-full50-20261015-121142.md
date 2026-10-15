# qualbench run: strata-iq3s-2gpu-full50

- Server: `http://192.168.0.88:8080`
- Model: `qwen3.8-flash-next-iq3_s`
- Selected categories: `java-spring, ts-angular, sql-migrations, mcp-tools, security-review, long-context`
- Suite commit: `3d8d639504115ca31dfa6c5d1c015ab9a5931c46`
- Suite git dirty: `True`
- Preflight: requested model present in `/v1/models`
- Started: 2026-10-15T08:55:36.228358+00:00
- Finished: 2026-10-15T09:11:42.442815+00:00
- Total wall time: 966.2s
- **Total: 50/50 passed**

| Category | Pass | Total | Wall (s) |
|---|---|---|---|
| java-spring | 10 | 10 | 95.5 |
| ts-angular | 8 | 8 | 60.6 |
| sql-migrations | 6 | 6 | 48.2 |
| mcp-tools | 8 | 8 | 23.5 |
| security-review | 8 | 8 | 108.1 |
| long-context | 10 | 10 | 630.3 |

## Task-level detail

### java-spring (10/10)
- [PASS] 01-pagination-calculator (8.0s)
- [PASS] 02-discount-calculator (9.9s)
- [PASS] 03-inventory-counter (9.9s)
- [PASS] 04-date-range-overlap (10.2s)
- [PASS] 05-csv-field-parser (11.2s)
- [PASS] 06-moving-average (7.9s)
- [PASS] 07-money (10.2s)
- [PASS] 08-retrying-operation (8.3s)
- [PASS] 09-request-id-generator (12.1s)
- [PASS] 10-lru-cache (7.7s)

### ts-angular (8/8)
- [PASS] 01-price-formatter (5.7s)
- [PASS] 02-search-service (9.0s)
- [PASS] 03-shopping-cart (10.8s)
- [PASS] 04-password-match-validator (6.9s)
- [PASS] 05-ticker-component (6.7s)
- [PASS] 06-todo-list-component (8.0s)
- [PASS] 07-counter-display-component (6.1s)
- [PASS] 08-batch-processor (6.5s)

### sql-migrations (6/6)
- [PASS] 01-add-column-not-null (4.5s)
- [PASS] 02-unique-constraint-dupes (9.8s)
- [PASS] 03-rename-column-view (9.8s)
- [PASS] 04-non-idempotent-migration (9.5s)
- [PASS] 05-fk-missing-unique-target (9.9s)
- [PASS] 06-bad-backfill-update (4.6s)

### mcp-tools (8/8)
- [PASS] 01-single-tool-required-args (2.9s)
- [PASS] 02-enum-selection (3.1s)
- [PASS] 03-numeric-coercion (2.9s)
- [PASS] 04-nested-object-args (3.4s)
- [PASS] 05-tool-disambiguation (3.0s)
- [PASS] 06-missing-info-no-premature-call (2.6s)
- [PASS] 07-multi-step-context-carry (2.6s)
- [PASS] 08-array-argument (2.8s)

### security-review (8/8)
- [PASS] 01-sql-injection (8.5s)
- [PASS] 02-hardcoded-secret (10.7s)
- [PASS] 03-path-traversal (13.4s)
- [PASS] 04-insecure-deserialization (12.4s)
- [PASS] 05-weak-crypto-hash (14.8s)
- [PASS] 06-ssrf (17.8s)
- [PASS] 07-broken-access-control (12.1s)
- [PASS] 08-command-injection (18.2s)

### long-context (10/10)
- [PASS] 01-8k-pos10 (12.5s)
- [PASS] 02-8k-pos50 (11.2s)
- [PASS] 03-8k-pos90 (11.5s)
- [PASS] 04-64k-pos10 (57.8s)
- [PASS] 05-64k-pos50 (57.7s)
- [PASS] 06-64k-pos90 (34.8s)
- [PASS] 07-150k-pos10 (122.2s)
- [PASS] 08-150k-pos50 (121.9s)
- [PASS] 09-distractor-64k (65.0s)
- [PASS] 10-distractor-150k (135.1s)
