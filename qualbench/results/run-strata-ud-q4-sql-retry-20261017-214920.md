# qualbench run: strata-ud-q4-sql-retry

- Server: `http://192.168.0.175:8080`
- Model: `qwen3.8-flash-next-ud-q4_k_xl`
- Selected categories: `sql-migrations`
- Suite commit: `809da0309d4f20da1a8667f7994268fe69b47f5f`
- Suite git dirty: `True`
- Preflight: requested model present in `/v1/models`
- Started: 2026-10-17T18:48:23.483587+00:00
- Finished: 2026-10-17T18:49:20.152675+00:00
- Total wall time: 56.7s
- **Total: 4/6 passed**

| Category | Pass | Total | Wall (s) |
|---|---|---|---|
| sql-migrations | 4 | 6 | 56.7 |

## Task-level detail

### sql-migrations (4/6)
- [PASS] 01-add-column-not-null (4.8s)
- [FAIL] 02-unique-constraint-dupes (7.3s)
  - verify.sh failed (exit 1):
  - == Task: /home/berdachuk/projects-llm-test/llm-tests/qualbench/fixtures/sql-migrations/02-unique-constraint-dupes ==
- [PASS] 03-rename-column-view (14.8s)
- [PASS] 04-non-idempotent-migration (14.3s)
- [FAIL] 05-fk-missing-unique-target (9.6s)
  - verify.sh failed (exit 1):
  - == Task: /home/berdachuk/projects-llm-test/llm-tests/qualbench/fixtures/sql-migrations/05-fk-missing-unique-target ==
  - ^
- [PASS] 06-bad-backfill-update (5.7s)
