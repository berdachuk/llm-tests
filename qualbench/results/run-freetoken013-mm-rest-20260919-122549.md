# qualbench run: freetoken013-mm-rest

- Server: `http://192.168.0.88:8000`
- Model: `qwen3.6-35b-a3b`
- Selected categories: `java-spring, ts-angular, sql-migrations, mcp-tools, security-review`
- Suite commit: `a791f5f1a752eb4347c246dfd24e26c9243a065d`
- Suite git dirty: `True`
- Preflight: requested model present in `/v1/models`
- Advertised context length: `262144`
- Notes: post-multimodal-enable run: --text-model-only removed, vision tower active
- Started: 2026-09-19T08:56:40.616969+00:00
- Finished: 2026-09-19T09:25:49.469913+00:00
- Total wall time: 1748.9s
- **Total: 37/40 passed**

| Category | Pass | Total | Wall (s) |
|---|---|---|---|
| java-spring | 9 | 10 | 612.6 |
| ts-angular | 8 | 8 | 407.8 |
| sql-migrations | 4 | 6 | 361.5 |
| mcp-tools | 8 | 8 | 48.4 |
| security-review | 8 | 8 | 318.6 |

## Task-level detail

### java-spring (9/10)
- [PASS] 01-pagination-calculator (39.4s)
- [PASS] 02-discount-calculator (67.3s)
- [PASS] 03-inventory-counter (55.2s)
- [PASS] 04-date-range-overlap (62.5s)
- [PASS] 05-csv-field-parser (54.5s)
- [PASS] 06-moving-average (55.3s)
- [FAIL] 07-money (90.8s)
  - truncated: finish_reason=length (content: '```java\npackage com.qualbench.bugs;\n\nimport java.math')
- [PASS] 08-retrying-operation (59.4s)
- [PASS] 09-request-id-generator (86.3s)
- [PASS] 10-lru-cache (41.8s)

### ts-angular (8/8)
- [PASS] 01-price-formatter (36.7s)
- [PASS] 02-search-service (61.3s)
- [PASS] 03-shopping-cart (87.2s)
- [PASS] 04-password-match-validator (55.6s)
- [PASS] 05-ticker-component (37.3s)
- [PASS] 06-todo-list-component (50.6s)
- [PASS] 07-counter-display-component (33.8s)
- [PASS] 08-batch-processor (44.4s)

### sql-migrations (4/6)
- [PASS] 01-add-column-not-null (30.3s)
- [PASS] 02-unique-constraint-dupes (57.3s)
- [PASS] 03-rename-column-view (77.0s)
- [FAIL] 04-non-idempotent-migration (83.2s)
  - truncated: finish_reason=length (content: 'The user wants me to fix a PostgreSQL migration script.\nThe existing schema has an `accounts` table with `id` and `name`.\nThe pending migration adds a column `is_active` to `accounts`, creates an inde')
- [FAIL] 05-fk-missing-unique-target (72.0s)
  - truncated: finish_reason=length (content: 'The user wants me to fix a PostgreSQL migration script.\nThe existing schema has `warehouses` and `shipments` tables.\n`warehouses` has `id`, `code`, `city`. `code` is unique in business logic but not e')
- [PASS] 06-bad-backfill-update (41.5s)

### mcp-tools (8/8)
- [PASS] 01-single-tool-required-args (5.2s)
- [PASS] 02-enum-selection (5.6s)
- [PASS] 03-numeric-coercion (6.1s)
- [PASS] 04-nested-object-args (8.3s)
- [PASS] 05-tool-disambiguation (5.7s)
- [PASS] 06-missing-info-no-premature-call (5.1s)
- [PASS] 07-multi-step-context-carry (5.4s)
- [PASS] 08-array-argument (6.7s)

### security-review (8/8)
- [PASS] 01-sql-injection (24.2s)
- [PASS] 02-hardcoded-secret (52.0s)
- [PASS] 03-path-traversal (44.7s)
- [PASS] 04-insecure-deserialization (29.7s)
- [PASS] 05-weak-crypto-hash (39.7s)
- [PASS] 06-ssrf (45.9s)
- [PASS] 07-broken-access-control (34.4s)
- [PASS] 08-command-injection (47.8s)
