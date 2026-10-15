# FreeToken snapshot + restore (2026-10-15)

Stopped for Strata Flash-Next context matrix on GPU0.
**Do not lose this file** — restore FreeToken with the commands below.

## Live state when snapped

| Field | Value |
|---|---|
| Host | `berda@192.168.0.88` |
| FreeToken | `0.1.3` at `/home/berda/freetoken-0.1.3` |
| Model path | `/mnt/data/berda-models/models/Qwen3.6-35B-A3B-FP8` |
| Served id | `qwen3.6-35b-a3b` |
| API | `0.0.0.0:8000` (also binds worker `:8001`) |
| Daemon | `127.0.0.1:1900`, state `/home/berda/.local/state/freetoken` |
| GPU | device 0 = RTX 4090 (~22 GB used while serving) |
| Multimodal | ON (no `--text-model-only`); media root `/mnt/data/qualbench-mm` |
| Units | `freetoken-daemon.service` + `freetoken-engine.service` (user, linger, **enabled**) |

## Exact serve argv (from live process / engine unit)

```text
ft daemon start /mnt/data/berda-models/models/Qwen3.6-35B-A3B-FP8 -- \
  --moe-strategy offload \
  --allowed-local-media-path /mnt/data/qualbench-mm \
  --served-model-name qwen3.6-35b-a3b \
  --host 0.0.0.0 --port 8000 \
  --cuda-graph-max-bs 4 \
  --max-running-requests 4 \
  --kv-reserve-tokens 300000 \
  --num-tokenizer 0 \
  --tool-call-parser qwen3_coder \
  --reasoning-parser qwen3
```

Env in units: `CUDA_HOME=/usr/local/cuda-13.0`, PATH includes cuda-13.0 + venv + nvidia/cu13.

## Artifacts in this directory

- `systemd-units/freetoken-*.service` — exact unit copies
- `configs/serve.json`, `daemon.env`, `pyproject.toml`
- `health.json`, `models.json`, `preflight.txt`, `cmdline.txt`, `journal-tail.txt`

## Stop procedure used (this session)

```bash
# 1) prevent boot/autostart from reloading the model during Strata window
systemctl --user disable freetoken-engine.service

# 2) stop model via daemon API
/home/berda/freetoken-0.1.3/.venv/bin/ft daemon stop
# if orphans remain:
# /home/berda/freetoken-0.1.3/.venv/bin/ft daemon stop --force

# 3) stop supervisor
systemctl --user stop freetoken-engine.service
systemctl --user stop freetoken-daemon.service

# 4) verify
ss -lntp | grep -E ':8000|:1900' || echo 'ports free'
nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv
pgrep -af 'freetoken|ft serve|ft daemon' || echo 'no ft procs'
```

## Restore procedure

```bash
systemctl --user enable freetoken-daemon.service
systemctl --user enable freetoken-engine.service
systemctl --user start freetoken-daemon.service
# wait for daemon
for i in $(seq 1 30); do curl -sf http://127.0.0.1:1900/health && break; sleep 1; done
systemctl --user start freetoken-engine.service
# wait for model API
for i in $(seq 1 120); do
  curl -sf http://127.0.0.1:8000/health && break
  sleep 5
done
curl -sS http://127.0.0.1:8000/v1/models | python3 -m json.tool | head -40
nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv
```

Manual equivalent if units broken:

```bash
export PATH="/usr/local/cuda-13.0/bin:$HOME/freetoken-0.1.3/.venv/bin:$HOME/freetoken-0.1.3/.venv/lib/python3.12/site-packages/nvidia/cu13/bin:$HOME/.local/bin:$PATH"
export CUDA_HOME=/usr/local/cuda-13.0
$HOME/freetoken-0.1.3/.venv/bin/ft daemon --host 127.0.0.1 --port 1900 --state-dir $HOME/.local/state/freetoken &
sleep 2
$HOME/freetoken-0.1.3/.venv/bin/ft daemon start /mnt/data/berda-models/models/Qwen3.6-35B-A3B-FP8 -- \
  --moe-strategy offload \
  --allowed-local-media-path /mnt/data/qualbench-mm \
  --served-model-name qwen3.6-35b-a3b \
  --host 0.0.0.0 --port 8000 \
  --cuda-graph-max-bs 4 \
  --max-running-requests 4 \
  --kv-reserve-tokens 300000 \
  --num-tokenizer 0 \
  --tool-call-parser qwen3_coder \
  --reasoning-parser qwen3
```

## Notes

- Chat template: froggeric in model dir `chat_template.jinja` (see llm-tests `FREETOKEN_QWEN36_SERVE.md`).
- Bifrost id: `llm-88/qwen3.6-35b-a3b` — do not rename served-model-name without Bifrost update.
- GPU1 (5060 Ti) ASR/embeddings left running; only FreeToken on GPU0 is stopped.
stopped_at_planned: 2026-10-15T03:12:05-04:00
