# Active stack snapshot — Strata UD-Q4_K_XL **1×4090 production** (2026-10-17)

Bifrost `llm-88` → nginx `.51` → Strata on **ethernet** `192.168.0.175:8080`. FreeToken off.

Monitor / API: **http://192.168.0.175:8080/** (Bearer; paste key in Monitor Settings)  
Public: `https://llm-88.berdachuk.com/v1`  
SSH: `ssh llm-server` or `ssh berda@192.168.0.175` (legacy `192.168.0.88` → same host via `~/.ssh/config`)  
How-to (клиенты, без секретов): [`LLM_175_USAGE.md`](LLM_175_USAGE.md)  
Runbook: [`STRATA_88_PRODUCTION.md`](STRATA_88_PRODUCTION.md)  
Compare: [`STRATA_VS_FREETOKEN_4090_COMPARE.md`](STRATA_VS_FREETOKEN_4090_COMPARE.md)

> **LAN:** primary = ethernet **`.175`**. Wi‑Fi `.88` is not used by nginx/Docker.

## GPU0 — Strata (ACTIVE)

| Item | Value |
|---|---|
| Engine | Strata **v0.1.44.1** (`/mnt/data/strata/Strata`) |
| Config | `/mnt/data/strata/Strata/strata-ud-q4_k_xl.json` → `"gpu": 0`, **no** `layer_split` |
| Served model id | **`qwen3.8-flash-next-ud-q4_k_xl`** |
| Bifrost | `llm-88/qwen3.8-flash-next-ud-q4_k_xl` |
| systemd | `strata-ud-q4_k_xl` + `strata-open-8080` (user, linger, enabled); IQ3_S disabled (restore snapshot available) |
| Bind | `0.0.0.0:8080` |
| VRAM | GPU0 ~**23 GiB** |
| Context | advertised 262144; practical ~**248K** |
| Qualbench-50 | **48/50** (sql 4/6) — [`STRATA_UD_Q4_K_XL_4090_TEST_REPORT.md`](STRATA_UD_Q4_K_XL_4090_TEST_REPORT.md) |
| IQ3_S restore | [`STRATA_IQ3S_RESTORE_SNAPSHOT.md`](STRATA_IQ3S_RESTORE_SNAPSHOT.md) |

## GPU1 — ASR / embeddings

| Port | Service | Publish |
|---|---|---|
| `:8002` | Speaches | `0.0.0.0` |
| `:8003` | GigaAM | `0.0.0.0` |
| `:8004` | TEI Qwen3-Embedding | **`192.168.0.175`** |
| `:8005` | EmbeddingGemma-2 | **`192.168.0.175`** |

## FreeToken

| FreeToken `:8000` | **disabled** — restore via [`FREETOKEN_88_RESTORE.md`](FREETOKEN_88_RESTORE.md) + nginx site backup |

## Clients

| Client | Setting |
|---|---|
| OpenCode | default `llm-88-local/qwen3.8-flash-next-ud-q4_k_xl`, limit **248000**; baseURL `http://192.168.0.175:8080/v1` |
| Direct LAN | `http://192.168.0.175:8080` + production Bearer |
