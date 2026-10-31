# Strata production on `llm-server` (replaces FreeToken for Bifrost llm-88)

Host: `berda@192.168.0.175` (`llm-server`, **ethernet**).  
SSH aliases: `ssh llm-server` / `ssh 192.168.0.88` → same host (legacy wifi IP redirected in `~/.ssh/config`).  

Снимок для отката IQ3_S (2026-10-16): [`STRATA_IQ3S_RESTORE_SNAPSHOT.md`](STRATA_IQ3S_RESTORE_SNAPSHOT.md).

Public path: Bifrost `llm-88` → `https://llm-88.berdachuk.com/v1` → nginx `.51` → **`http://192.168.0.175:8080`**.  
LAN monitor/API: **http://192.168.0.175:8080/** (Bearer; Monitor → About → Settings).

> **LAN policy (2026-10-15):** primary address is ethernet **`.175`**. Wi‑Fi may be up as backup — do not point nginx or Docker publishes at Wi‑Fi IPs.  
> Client how-to (no secrets): [`LLM_175_USAGE.md`](LLM_175_USAGE.md).

**Do not commit API keys.** Key files on host only:
`/mnt/data/strata/runs/production/api-key.txt`, config `api_key` in
`/mnt/data/strata/Strata/strata-iq3_s.json`. On `.51`:
`/etc/nginx/snippets/strata-upstream-auth.conf` (mode 600).

```bash
ssh berda@192.168.0.175 'cat /mnt/data/strata/runs/production/api-key.txt'
```

## What runs

| Item | Value |
|---|---|
| Engine | Strata **v0.2.7.1** / engine **0.1.53** |
| Quant | Qwen3.8-Flash-Next **IQ3_S** (`/mnt/data/strata-data/models/IQ3_S/`) |
| Pack | `/mnt/data/strata-data/packs/iq3_s` |
| Qualbench-50 (prod) | **50/50** @ **639–644 s** (upgrade + post-Maya recheck 2026-10-30); prior **685–698 s**; Unsloth A/B 48/50 then restore |
| Served / Bifrost model id | **`qwen3.8-flash-next-iq3_s`** / `llm-88/qwen3.8-flash-next-iq3_s` |
| GPU | **0 only** (RTX 4090). No `layer_split` in prod — GPU1 is ASR/TEI/Gemma |
| gpu-unlock | Packages may be present; prod cmdline **without** `gpu_unlock.targets` (A/B 2026-10-31: **≈0%** IQ3_S gain — leave off). See [`GPU_UNLOCK_4090_STRATA_REPORT.md`](GPU_UNLOCK_4090_STRATA_REPORT.md) |
| Port | `0.0.0.0:8080` |
| Context advertised | `n_ctx=262144`; **practical prompt ceiling ~248K** |
| Concurrency | default **1** |
| Units | `strata-iq3_s.service`, `strata-open-8080.service` (user, linger); `strata-ud-iq4_xs` disabled |
| FreeToken | **disabled** (`freetoken-daemon` / `freetoken-engine`) |
| OpenCode | default `llm-88-local/qwen3.8-flash-next-iq3_s`, context limit **248000**; direct provider baseURL `http://192.168.0.175:8080/v1` |

## systemd / autostart

```bash
ssh berda@192.168.0.175
systemctl --user status strata-iq3_s.service strata-open-8080.service
systemctl --user restart strata-iq3_s.service
tail -f /mnt/data/strata/runs/production/server.out
```

- Linger: `loginctl show-user berda -p Linger` → `yes`
- Both units `enabled` → `default.target`
- Firewall oneshot does **not** block Strata (no Docker; no `Before=strata`)
- After GPU recovery: system `nvidia-modules-ensure` → `restart-gpu-services.sh` starts
  `strata-open-8080` and restarts `strata-iq3_s`

Cold start loads experts (~1–3 min). `TimeoutStartSec=900`.

## Firewall (LAN :8080)

```text
strata-open-8080.service
  → sudo /usr/local/sbin/open-strata-8080.sh   # NOPASSWD
  → iptables -I INPUT -p tcp --dport 8080 -j ACCEPT
```

IaC: `avroflex-infra/llm-88/strata/` (+ nvidia-guard patch for Strata restart).

## Smoke

```bash
KEY=$(ssh berda@192.168.0.175 'cat /mnt/data/strata/runs/production/api-key.txt')
curl -fsS -H "Authorization: Bearer $KEY" http://192.168.0.175:8080/v1/models

curl -fsS -H "Authorization: Bearer $LLM_88_API_KEY" \
  https://llm-88.berdachuk.com/v1/models

curl -fsS https://llm.avroflex.ru/v1/chat/completions \
  -H "Authorization: Bearer $VK9" -H 'Content-Type: application/json' \
  -d '{"model":"llm-88/qwen3.8-flash-next-iq3_s","temperature":0,"max_tokens":64,"messages":[{"role":"user","content":"Reply with exactly: pong"}]}'
```

## Verification (qualbench-50 text)

| Run | Score | Wall | Notes |
|---|---|---|---|
| Morning 1× IQ3_S (GPU1 stopped) | **50/50** | **711 s** | [`run-strata-iq3s-full50-20261015-113238.md`](qualbench/results/run-strata-iq3s-full50-20261015-113238.md) |
| Prod re-check IQ3_S post-reboot | **50/50** | **685 s** | [`run-strata-iq3s-prod-full50-20261015-135743.md`](qualbench/results/run-strata-iq3s-prod-full50-20261015-135743.md) |
| UD-Q4_K_XL cutover (2026-10-17) | **48/50** | ~**19 min** | [`STRATA_UD_Q4_K_XL_4090_TEST_REPORT.md`](STRATA_UD_Q4_K_XL_4090_TEST_REPORT.md), sql retry [`run-strata-ud-q4-sql-retry-20261017-214920.md`](qualbench/results/run-strata-ud-q4-sql-retry-20261017-214920.md) |
| UD-IQ4_XS A/B → restore IQ3_S (2026-10-18) | **48/50** (A/B) | **857 s** | [`STRATA_UD_IQ4_XS_4090_TEST_REPORT.md`](STRATA_UD_IQ4_XS_4090_TEST_REPORT.md), compare [`STRATA_IQ3S_VS_UD_IQ4_XS_COMPARE.md`](STRATA_IQ3S_VS_UD_IQ4_XS_COMPARE.md) |
| IQ3_S recheck post-restore (2026-10-18) | **50/50** | **698 s** | [`STRATA_IQ3S_RECHECK_20261018.md`](STRATA_IQ3S_RECHECK_20261018.md) (security flake retry 8/8) |

Prefill on long prompts (matrix): ~**1.9–2.1k tok/s** cold @ 40K–248K. Short prompts on Monitor look much lower (~100–400 t/s) — that is expected.

## Rollback to FreeToken

1. `systemctl --user disable --now strata-iq3_s.service strata-open-8080.service`
2. Follow [`FREETOKEN_88_RESTORE.md`](FREETOKEN_88_RESTORE.md)
3. On `.51`: restore site backup `llm-88.berdachuk.com.bak-strata-*` (proxy `:8000`, strip Authorization) and reload nginx
4. Point Bifrost / clients back to served id `qwen3.6-35b-a3b` if restored
