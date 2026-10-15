# Active stack snapshot — Strata IQ3_S **1×4090 production** (2026-10-15)

Supersedes the temporary 2×GPU test window. Bifrost `llm-88` now points at Strata.

Monitor / API: **http://192.168.0.88:8080/**  
Public: `https://llm-88.berdachuk.com/v1` → nginx `.51` → `:8080`  
Full runbook: [`STRATA_88_PRODUCTION.md`](STRATA_88_PRODUCTION.md)

## GPU0 — Strata (ACTIVE)

| Item | Value |
|---|---|
| Engine | Strata **v0.1.44.1** (`/mnt/data/strata/Strata`) |
| Config | `/mnt/data/strata/Strata/strata-iq3_s.json` → `"gpu": 0`, **no** `layer_split` |
| Served model id | **`qwen3.8-flash-next-iq3_s`** |
| systemd | `strata-iq3_s.service` + `strata-open-8080.service` (user, linger) |
| Bind | `0.0.0.0:8080` |
| VRAM | GPU0 ~**23 GiB** |

## GPU1 — ASR / embeddings (ACTIVE)

Speaches `:8002`, GigaAM `:8003`, TEI `:8004`, EmbeddingGemma-2 `:8005` — restored after the 2×GPU test window.

## FreeToken

| FreeToken `:8000` | **disabled** — units `freetoken-daemon` / `freetoken-engine` off; restore via `FREETOKEN_88_RESTORE.md` + nginx site backup |
