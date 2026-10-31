# qualbench run: strata-iq3s-gpu-unlock-full50

- Server: `http://192.168.0.175:8080`
- Model: `qwen3.8-flash-next-iq3_s`
- Selected categories: `java-spring, ts-angular, sql-migrations, mcp-tools, security-review, long-context`
- Suite commit: `6baaecb3be0a635a283d4d3d33016fbde8cb0384`
- Suite git dirty: `True`
- Preflight: requested model present in `/v1/models`
- Started: 2026-10-31T11:11:11.904793+00:00
- Finished: 2026-10-31T11:21:56.979798+00:00
- Total wall time: 645.1s
- **Total: 48/50 passed**

| Category | Pass | Total | Wall (s) |
|---|---|---|---|
| java-spring | 10 | 10 | 77.8 |
| ts-angular | 8 | 8 | 57.6 |
| sql-migrations | 5 | 6 | 40.5 |
| mcp-tools | 8 | 8 | 14.0 |
| security-review | 7 | 8 | 86.4 |
| long-context | 10 | 10 | 368.8 |

## Task-level detail

### java-spring (10/10)
- [PASS] 01-pagination-calculator (7.6s)
- [PASS] 02-discount-calculator (9.3s)
- [PASS] 03-inventory-counter (7.9s)
- [PASS] 04-date-range-overlap (7.8s)
- [PASS] 05-csv-field-parser (8.3s)
- [PASS] 06-moving-average (6.3s)
- [PASS] 07-money (8.6s)
- [PASS] 08-retrying-operation (6.1s)
- [PASS] 09-request-id-generator (9.1s)
- [PASS] 10-lru-cache (6.6s)

### ts-angular (8/8)
- [PASS] 01-price-formatter (5.3s)
- [PASS] 02-search-service (8.4s)
- [PASS] 03-shopping-cart (9.7s)
- [PASS] 04-password-match-validator (5.9s)
- [PASS] 05-ticker-component (5.9s)
- [PASS] 06-todo-list-component (8.5s)
- [PASS] 07-counter-display-component (7.1s)
- [PASS] 08-batch-processor (5.5s)

### sql-migrations (5/6)
- [PASS] 01-add-column-not-null (2.5s)
- [FAIL] 02-unique-constraint-dupes (8.5s)
  - verify.sh failed (exit 1):
  - == Task: /home/berdachuk/projects-llm-test/llm-tests/qualbench/fixtures/sql-migrations/02-unique-constraint-dupes ==
- [PASS] 03-rename-column-view (6.6s)
- [PASS] 04-non-idempotent-migration (10.7s)
- [PASS] 05-fk-missing-unique-target (8.2s)
- [PASS] 06-bad-backfill-update (3.9s)

### mcp-tools (8/8)
- [PASS] 01-single-tool-required-args (1.7s)
- [PASS] 02-enum-selection (1.8s)
- [PASS] 03-numeric-coercion (1.8s)
- [PASS] 04-nested-object-args (2.1s)
- [PASS] 05-tool-disambiguation (1.8s)
- [PASS] 06-missing-info-no-premature-call (1.4s)
- [PASS] 07-multi-step-context-carry (1.4s)
- [PASS] 08-array-argument (1.8s)

### security-review (7/8)
- [PASS] 01-sql-injection (7.5s)
- [PASS] 02-hardcoded-secret (8.5s)
- [PASS] 03-path-traversal (11.0s)
- [PASS] 04-insecure-deserialization (10.2s)
- [PASS] 05-weak-crypto-hash (10.7s)
- [PASS] 06-ssrf (13.3s)
- [FAIL] 07-broken-access-control (9.9s)
  - matched 1/2 required groups (need >= 2)
  - group 1 not matched by any of: ['belongs to.*(user|customer)', 'owns? the invoice', 'ownership check', 'verify.*owner', 'check.*owner', 'current(ly)? authenticated user', 'invoice.*(and|with).*(user|owner).*id', '(user|owner).*id.*and.*invoice']
- [PASS] 08-command-injection (15.2s)

### long-context (10/10)
- [PASS] 01-8k-pos10 (8.3s)
- [PASS] 02-8k-pos50 (7.9s)
- [PASS] 03-8k-pos90 (7.5s)
- [PASS] 04-64k-pos10 (35.4s)
- [PASS] 05-64k-pos50 (36.3s)
- [PASS] 06-64k-pos90 (21.4s)
- [PASS] 07-150k-pos10 (75.2s)
- [PASS] 08-150k-pos50 (61.4s)
- [PASS] 09-distractor-64k (37.0s)
- [PASS] 10-distractor-150k (77.7s)
