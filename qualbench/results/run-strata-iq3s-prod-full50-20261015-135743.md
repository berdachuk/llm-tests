# qualbench run: strata-iq3s-full50-20261015-134618

- Server: `http://192.168.0.88:8080`
- Model: `qwen3.8-flash-next-iq3_s`
- Selected categories: `java-spring, ts-angular, sql-migrations, mcp-tools, security-review, long-context`
- Suite commit: `9db223d2c3f2c4de11ff32518bbed1d256f7194f`
- Suite git dirty: `True`
- Preflight: requested model present in `/v1/models`
- Notes: Full text qualbench-50 on Strata IQ3_S post-reboot; LAN :8080; model qwen3.8-flash-next-iq3_s
- Started: 2026-10-15T10:46:18.640361+00:00
- Finished: 2026-10-15T10:57:43.836374+00:00
- Total wall time: 685.2s
- **Total: 50/50 passed**

| Category | Pass | Total | Wall (s) |
|---|---|---|---|
| java-spring | 10 | 10 | 78.7 |
| ts-angular | 8 | 8 | 54.1 |
| sql-migrations | 6 | 6 | 43.9 |
| mcp-tools | 8 | 8 | 15.0 |
| security-review | 8 | 8 | 95.2 |
| long-context | 10 | 10 | 398.3 |

## Task-level detail

### java-spring (10/10)
- [PASS] 01-pagination-calculator (6.8s)
- [PASS] 02-discount-calculator (8.8s)
- [PASS] 03-inventory-counter (7.8s)
- [PASS] 04-date-range-overlap (6.1s)
- [PASS] 05-csv-field-parser (9.6s)
- [PASS] 06-moving-average (6.7s)
- [PASS] 07-money (8.8s)
- [PASS] 08-retrying-operation (7.7s)
- [PASS] 09-request-id-generator (9.9s)
- [PASS] 10-lru-cache (6.4s)

### ts-angular (8/8)
- [PASS] 01-price-formatter (5.0s)
- [PASS] 02-search-service (8.9s)
- [PASS] 03-shopping-cart (9.7s)
- [PASS] 04-password-match-validator (6.0s)
- [PASS] 05-ticker-component (5.5s)
- [PASS] 06-todo-list-component (7.8s)
- [PASS] 07-counter-display-component (5.0s)
- [PASS] 08-batch-processor (5.3s)

### sql-migrations (6/6)
- [PASS] 01-add-column-not-null (3.3s)
- [PASS] 02-unique-constraint-dupes (9.8s)
- [PASS] 03-rename-column-view (9.7s)
- [PASS] 04-non-idempotent-migration (8.4s)
- [PASS] 05-fk-missing-unique-target (8.7s)
- [PASS] 06-bad-backfill-update (3.9s)

### mcp-tools (8/8)
- [PASS] 01-single-tool-required-args (1.7s)
- [PASS] 02-enum-selection (2.2s)
- [PASS] 03-numeric-coercion (1.8s)
- [PASS] 04-nested-object-args (2.4s)
- [PASS] 05-tool-disambiguation (2.1s)
- [PASS] 06-missing-info-no-premature-call (1.5s)
- [PASS] 07-multi-step-context-carry (1.5s)
- [PASS] 08-array-argument (1.7s)

### security-review (8/8)
- [PASS] 01-sql-injection (8.3s)
- [PASS] 02-hardcoded-secret (10.3s)
- [PASS] 03-path-traversal (11.8s)
- [PASS] 04-insecure-deserialization (10.4s)
- [PASS] 05-weak-crypto-hash (13.7s)
- [PASS] 06-ssrf (13.9s)
- [PASS] 07-broken-access-control (11.7s)
- [PASS] 08-command-injection (14.9s)

### long-context (10/10)
- [PASS] 01-8k-pos10 (8.7s)
- [PASS] 02-8k-pos50 (8.2s)
- [PASS] 03-8k-pos90 (7.8s)
- [PASS] 04-64k-pos10 (36.6s)
- [PASS] 05-64k-pos50 (36.1s)
- [PASS] 06-64k-pos90 (21.5s)
- [PASS] 07-150k-pos10 (77.4s)
- [PASS] 08-150k-pos50 (77.0s)
- [PASS] 09-distractor-64k (38.8s)
- [PASS] 10-distractor-150k (85.5s)
