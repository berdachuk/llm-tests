# Strata production on `.88` (replaces FreeToken for Bifrost llm-88)

Host: `berda@192.168.0.88` (`llm-server`).  
Public path: Bifrost `llm-88` → `https://llm-88.berdachuk.com/v1` → nginx `.51` → **`http://192.168.0.88:8080`**.  
LAN monitor/API: `http://192.168.0.88:8080/` (Bearer required).

**Do not commit API keys.** Key files on host only:
`/mnt/data/strata/runs/production/api-key.txt`, config `api_key` in
`/mnt/data/strata/Strata/strata-iq3_s.json`. On `.51`:
`/etc/nginx/snippets/strata-upstream-auth.conf` (mode 600).

## What runs

| Item | Value |
|---|---|
| Engine | Strata v0.1.44.1 |
| Quant | Qwen3.8-Flash-Next **IQ3_S** (weights under `/mnt/data/strata-data/models/IQ3_S/`) |
| Served model id | **`qwen3.8-flash-next-iq3_s`** (Flash-Next IQ3_S) |
| GPU | **0 only** (RTX 4090). Do not enable `layer_split` in prod — GPU1 is ASR/TEI/Gemma |
| Port | `0.0.0.0:8080` |
| Units | `strata-iq3_s.service`, `strata-open-8080.service` (user, linger) |
| FreeToken | **disabled** (`freetoken-daemon` / `freetoken-engine`) |

## systemd

```bash
ssh berda@192.168.0.88
systemctl --user status strata-iq3_s.service strata-open-8080.service
systemctl --user restart strata-iq3_s.service
# logs
tail -f /mnt/data/strata/runs/production/server.out
```

Cold start loads experts (~1–3 min). `TimeoutStartSec=900` on the unit.

## Firewall (LAN :8080)

UFW default INPUT DROP blocks host listeners. Prod uses oneshot
`strata-open-8080.service` → `/mnt/data/strata/scripts/open-strata-8080.sh`
(privileged docker + iptables ACCEPT for tcp/8080). After reboot the unit
runs before Strata.

Prefer permanent (needs sudo once): `sudo ufw allow 8080/tcp && sudo ufw reload`.

## Smoke

```bash
KEY=$(ssh berda@192.168.0.88 'cat /mnt/data/strata/runs/production/api-key.txt')
curl -fsS -H "Authorization: Bearer $KEY" http://192.168.0.88:8080/v1/models

# via nginx (.51) — same LLM_88_API_KEY as Bifrost provider key
curl -fsS -H "Authorization: Bearer $LLM_88_API_KEY" \
  https://llm-88.berdachuk.com/v1/models

# via Bifrost (VK from k8s/secrets/vk9-code-llm88.txt — not in git)
curl -fsS https://llm.avroflex.ru/v1/chat/completions \
  -H "Authorization: Bearer $VK9" -H 'Content-Type: application/json' \
  -d '{"model":"llm-88/qwen3.8-flash-next-iq3_s","temperature":0,"max_tokens":32,"messages":[{"role":"user","content":"Reply with exactly: pong"}]}'
```

## Rollback to FreeToken

1. `systemctl --user disable --now strata-iq3_s.service strata-open-8080.service`
2. Follow [`FREETOKEN_88_RESTORE.md`](FREETOKEN_88_RESTORE.md)
3. On `.51`: restore site backup `llm-88.berdachuk.com.bak-strata-*` (proxy `:8000`, strip Authorization) and reload nginx
