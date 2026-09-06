# qualbench run: ollama-deepseek-v4-flash

- Server: `http://192.168.0.73:11434`
- Model: `deepseek-v4-flash:0731-cloud`
- Started: 2026-09-03T12:25:46.447564+00:00
- Finished: 2026-09-03T12:33:33.434974+00:00
- Total wall time: 467.0s
- **Total: 47/50 passed**

| Category | Pass | Total | Wall (s) |
|---|---|---|---|
| java-spring | 10 | 10 | 111.2 |
| ts-angular | 8 | 8 | 58.5 |
| sql-migrations | 3 | 6 | 75.7 |
| mcp-tools | 8 | 8 | 15.7 |
| security-review | 8 | 8 | 120.0 |
| long-context | 10 | 10 | 86.0 |

## Task-level detail

### java-spring (10/10)
- [PASS] 01-pagination-calculator (7.5s)
- [PASS] 02-discount-calculator (12.0s)
- [PASS] 03-inventory-counter (8.1s)
- [PASS] 04-date-range-overlap (5.0s)
- [PASS] 05-csv-field-parser (16.9s)
- [PASS] 06-moving-average (6.0s)
- [PASS] 07-money (20.2s)
- [PASS] 08-retrying-operation (9.6s)
- [PASS] 09-request-id-generator (17.9s)
- [PASS] 10-lru-cache (8.0s)

### ts-angular (8/8)
- [PASS] 01-price-formatter (6.0s)
- [PASS] 02-search-service (7.2s)
- [PASS] 03-shopping-cart (8.8s)
- [PASS] 04-password-match-validator (6.0s)
- [PASS] 05-ticker-component (5.9s)
- [PASS] 06-todo-list-component (8.4s)
- [PASS] 07-counter-display-component (7.3s)
- [PASS] 08-batch-processor (8.0s)

### sql-migrations (3/6)
- [PASS] 01-add-column-not-null (3.6s)
- [FAIL] 02-unique-constraint-dupes (4.7s)
- [FAIL] 03-rename-column-view (15.3s)
- [PASS] 04-non-idempotent-migration (8.0s)
- [FAIL] 05-fk-missing-unique-target (18.0s)
- [PASS] 06-bad-backfill-update (26.0s)

### mcp-tools (8/8)
- [PASS] 01-single-tool-required-args
- [PASS] 02-enum-selection
- [PASS] 03-numeric-coercion
- [PASS] 04-nested-object-args
- [PASS] 05-tool-disambiguation
- [PASS] 06-missing-info-no-premature-call
- [PASS] 07-multi-step-context-carry
- [PASS] 08-array-argument

### security-review (8/8)
- [PASS] 01-sql-injection
- [PASS] 02-hardcoded-secret
- [PASS] 03-path-traversal
- [PASS] 04-insecure-deserialization
- [PASS] 05-weak-crypto-hash
- [PASS] 06-ssrf
- [PASS] 07-broken-access-control
- [PASS] 08-command-injection

### long-context (10/10)
- [PASS] 01-8k-pos10 (3.7s)
- [PASS] 02-8k-pos50 (4.1s)
- [PASS] 03-8k-pos90 (4.0s)
- [PASS] 04-64k-pos10 (18.1s)
- [PASS] 05-64k-pos50 (5.8s)
- [PASS] 06-64k-pos90 (5.9s)
- [PASS] 07-150k-pos10 (9.9s)
- [PASS] 08-150k-pos50 (17.9s)
- [PASS] 09-distractor-64k (4.8s)
- [PASS] 10-distractor-150k (11.1s)
