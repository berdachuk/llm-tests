# Strata IQ3_S vs UD-Q4_K_XL on 1× RTX 4090

> Один хост (`192.168.0.175`), один engine (Strata v0.1.44.1), один suite.  
> IQ3_S: 2026-10-15 — [`STRATA_IQ3S_4090_TEST_REPORT.md`](STRATA_IQ3S_4090_TEST_REPORT.md)  
> UD-Q4_K_XL: 2026-10-17 — [`STRATA_UD_Q4_K_XL_4090_TEST_REPORT.md`](STRATA_UD_Q4_K_XL_4090_TEST_REPORT.md)

---

## Headline

| | IQ3_S (prod was) | UD-Q4_K_XL (prod now) |
|---|---|---|
| Served id | `qwen3.8-flash-next-iq3_s` | `qwen3.8-flash-next-ud-q4_k_xl` |
| Quant source | GSQ-RCO IQ3_S | Unsloth UD-Q4_K_XL |
| Pack | native IQ3_S | `iq_pack --compat-bf16` |
| VRAM GPU0 | ~23.97 GiB | ~23.97 GiB |
| Host RAM under load | ~**62 GiB** | ~**88 GiB** |
| Qualbench-50 | **50/50** @ **685–711 s** | **48/50** (sql 4/6; non-sql 44/44) @ ~**19 min** wall w/ long-ctx |
| agentbench fast | 50p / 5f / 3s | 50p / 5f / 3s |
| agentbench slow | (prior) | **5/5** |
| Vision smoke | Black | Black |
| Matrix E needle (~170K) | 3/3 | 3/3 |
| Matrix F (~248K) | 3/3 after calib | 3/3 after calib |
| Prefill @ ~248K | ~**1.98–2.00k** t/s | ~**1.25k** t/s |
| Decode short (A cold) | ~52 t/s | ~41 t/s |

**Cutover decision (2026-10-17):** прод на **UD-Q4_K_XL** (полный resident, без `--resident-budget`). IQ3_S остановлен; снимок отката сохранён. Качество agentic/text близко; Q4 ближе к full-weight по заявлениям Unsloth, но на этом железе платит **больше RAM** и **медленнее long prefill**. Qualbench −2 (оба SQL) — не блокеры для coding-agent daily.

---

## Matrix (cold first rep where available)

| Tier | IQ3_S prefill / decode | UD-Q4 prefill / decode |
|---|---|---|
| A (~1.2K) | 376 / 52 | 217 / 41 |
| B (~5K) | 1437 / 55 | 859 / 44 |
| C (~42K) | (see CSV) | 1162 / 30 |
| D (~85K) | (see CSV) | 1199 / 31 |
| E (~170K) | ~1.9–2.1k / 55–100+ | ~1285–1293 / 55–100 |
| F (~248K) | ~1985–2004 / 93–154 | ~1249 / 78–90 |

CSV: `strata-results/20261015-iq3s-full/matrix.csv` vs `strata-results/20261017-ud-q4_k_xl/matrix.csv`.

---

## Qualbench categories

| Category | IQ3_S prod | UD-Q4 |
|---|---|---|
| java-spring | 10/10 | 10/10 |
| ts-angular | 8/8 | 8/8 |
| sql-migrations | 6/6 | **4/6** (PG up) |
| mcp-tools | 8/8 | 8/8 |
| security-review | 8/8 | 8/8 |
| long-context | 10/10 | 10/10 |
| **Total** | **50/50** | **48/50** |

---

## Ops notes

- RAM: Q4 держит ~+26 GiB vs IQ3_S на той же карте — следить за headroom (host 125 GiB).
- Prefill: Q4 ~**0.6×** IQ3_S на E/F — длинные agent turns дороже по wall time.
- Clients: OpenCode + public llm-88 уже на Q4 id; Bifrost CM в k8s может всё ещё хранить старый id в git — live `/v1/models` отдаёт upstream Strata id.
- Rollback: [`STRATA_IQ3S_RESTORE_SNAPSHOT.md`](STRATA_IQ3S_RESTORE_SNAPSHOT.md).
