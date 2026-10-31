# Active stack snapshot — Strata IQ3_S **1×4090 production** (2026-10-28 engine; recheck 2026-10-30; gpu-unlock off 2026-10-31)

Bifrost `llm-88` → nginx `.51` → Strata on **ethernet** `192.168.0.175:8080`. FreeToken off.

Monitor / API: **http://192.168.0.175:8080/** (Bearer; paste key in Monitor Settings)  
Public: `https://llm-88.berdachuk.com/v1`  
SSH: `ssh llm-server` or `ssh berda@192.168.0.175` (legacy `192.168.0.88` → same host via `~/.ssh/config`)  
How-to (клиенты, без секретов): [`LLM_175_USAGE.md`](LLM_175_USAGE.md)  
Runbook: [`STRATA_88_PRODUCTION.md`](STRATA_88_PRODUCTION.md)  
IQ4 A/B (rolled back): [`STRATA_IQ3S_VS_UD_IQ4_XS_COMPARE.md`](STRATA_IQ3S_VS_UD_IQ4_XS_COMPARE.md)

> **LAN:** primary = ethernet **`.175`**. Wi‑Fi `.88` is not used by nginx/Docker.

## GPU0 — Strata (ACTIVE)

| Item | Value |
|---|---|
| Engine | Strata **v0.2.7.1** / engine **0.1.53** (`/mnt/data/strata/Strata`, tag `v0.2.7.1` / `46c152a1`) |
| Config | `/mnt/data/strata/Strata/strata-iq3_s.json` → `"gpu": 0`, **no** `layer_split` |
| Served model id | **`qwen3.8-flash-next-iq3_s`** |
| Bifrost | `llm-88/qwen3.8-flash-next-iq3_s` |
| systemd | `strata-iq3_s` + `strata-open-8080` (user, linger, enabled); `strata-ud-iq4_xs` disabled |
| Bind | `0.0.0.0:8080` |
| VRAM | GPU0 ~**23–24 GiB** |
| Context | advertised 262144; practical ~**248K** |
| Qualbench-50 | post-Maya recheck **50/50** @ **644 s** ([`STRATA_IQ3S_RECHECK_20261030.md`](STRATA_IQ3S_RECHECK_20261030.md)); upgrade **50/50** @ **639 s** ([`STRATA_UPGRADE_0271_REPORT.md`](STRATA_UPGRADE_0271_REPORT.md)); prior **50/50** @ **685–698 s** |
| gpu-unlock | Packages **installed** (`gpu-unlock-dkms` / `firmware` 2.0.0); GRUB **without** `gpu_unlock.targets` (inert). A/B 2026-10-31: unlock OK, Strata IQ3_S prefill/decode **≈ 0%** — leave off. Report [`GPU_UNLOCK_4090_STRATA_REPORT.md`](GPU_UNLOCK_4090_STRATA_REPORT.md); run `/mnt/data/strata/runs/20261031-gpu-unlock/` |
| Upgrade / rollback | `/mnt/data/strata/runs/20261028-upgrade-0271/` (`backup-pre-0271-v0.1.44.1`, `engine-0.1.44.1.tgz`); snapshot [`STRATA_IQ3S_RESTORE_SNAPSHOT.md`](STRATA_IQ3S_RESTORE_SNAPSHOT.md) |
| `:8004–8006` | TEI / EmbeddingGemma / FRIDA republished `192.168.0.175` (force-recreate 2026-10-28) |

## GPU1 — ASR / embeddings

| Port | Service | Publish |
|---|---|---|
| `:8002` | Speaches (`asr-speaches`) | `0.0.0.0` |
| `:8003` | GigaAM (`asr-gigaam`) | `0.0.0.0` |
| `:8004` | TEI Qwen3-Embedding | **`192.168.0.175`** |
| `:8005` | EmbeddingGemma-2 | **`192.168.0.175`** |
| `:8006` | FRIDA-Decisions | **`192.168.0.175`** (`HF_HUB_OFFLINE=1`) |

## FreeToken

| FreeToken `:8000` | **disabled** — restore via [`FREETOKEN_88_RESTORE.md`](FREETOKEN_88_RESTORE.md) + nginx site backup |

## Clients

| Client | Setting |
|---|---|
| OpenCode | default `llm-88-local/qwen3.8-flash-next-iq3_s`, limit **248000**; baseURL `http://192.168.0.175:8080/v1` |
| Direct LAN | `http://192.168.0.175:8080` + production Bearer |
