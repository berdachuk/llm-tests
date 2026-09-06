# FreeToken + Qwen3.6-35B-A3B-FP8 — serve runbook (RTX 4090, 192.168.0.88)

> Operational runbook for the LLM server that feeds agentbench/qualbench.
> Infrastructure fact (verified 2026-09-06). Related material: `README.md`
> (the froggeric template and why it is needed), `qualbench/README.md` and `qualbench/results/`.

## 1. Machine and hardware

| Parameter | Value |
|---|---|
| Host | `berda@192.168.0.88` (SSH); FreeToken Desktop not required |
| GPU | RTX 4090, 24 GiB — **the server's workhorse card** (23.1 GiB used, ~1 GiB free) |
| GPU 2 | RTX 5060 Ti, 16 GiB — idle, not used for the server |
| CPU / RAM | i9-14900KF, 32 threads, 125 GiB RAM (87 GiB available) |
| Disk | `/mnt/data` (NVMe 1.8T) — models and download log |

## 2. FreeToken repository

- Clone: `~/freetoken` on 192.168.0.88 — upstream `https://github.com/FlashML-org/FreeToken.git`.
- Version: `v0.1.2-28-gaf71ba4` (branch `main`, commit `af71ba4`, clean — **no local code patches at all**).
- Install: editable install in `~/freetoken/.venv` (Python 3.12), the `.pth` points to `~/freetoken/python`.
- CUDA 13.0: `/usr/local/cuda-13.0` plus paths in `activate.sh`.
- The only local file in the repo is `activate.sh` (untracked).

`activate.sh` (required before any `ft` command):
```bash
export PATH="$HOME/.local/bin:$PATH"
source "$HOME/freetoken/.venv/bin/activate"
export PATH="/usr/local/cuda-13.0/bin:$HOME/freetoken/.venv/lib/python3.12/site-packages/nvidia/cu13/bin:$PATH"
export CUDA_HOME=/usr/local/cuda-13.0
```

## 3. Model

- HF repo: `Qwen/Qwen3.6-35B-A3B-FP8`, downloaded via `hf download` (no HF_TOKEN) into:
  `/mnt/data/berda-models/models/Qwen3.6-35B-A3B-FP8` (35 GB, 42 shards `layers-*.safetensors`).
- Architecture: `qwen3_5_moe` — 256 experts / 8 per token, 40 layers, 2048 hidden, mamba-SSM.
- Download log: `/mnt/data/berda-models/models/qwen36_download.log`.

## 4. The "patch": froggeric chat template v22.4 (the important part)

Qwen's stock `chat_template.jinja` is broken for coding-agent scenarios (tool-call replay,
reasoning-effort, parallel tool calls). It is replaced by the community template
`froggeric/Qwen-Fixed-Chat-Templates` v22.4:

```
/mnt/data/berda-models/models/Qwen3.6-35B-A3B-FP8/chat_template.jinja      # patched (froggeric v22.4)
/mnt/data/berda-models/models/Qwen3.6-35B-A3B-FP8/chat_template.jinja.orig # stock template backup
```

### How the template is wired in

The engine loads the template **from `chat_template.jinja` in the model directory**, not
from the inline `"chat_template"` string inside `tokenizer_config.json`. FreeToken's
`load_tokenizer()` (`~/freetoken/python/freetoken/utils/hf.py`) calls
`AutoTokenizer.from_pretrained(model_path)`; modern `transformers` treats
`chat_template.jinja` at the repo root as a first-class template file
(`CHAT_TEMPLATE_FILE = "chat_template.jinja"`) and prefers it over the inline config
string. Verified empirically (2026-09-06): loading this model dir with FreeToken's
tokenizer yields the 27 KB froggeric v22.4 template, not the 7.7 KB stock one from
`tokenizer_config.json`. No server flag or code change is involved — the file is picked
up automatically.

### File facts (verified 2026-09-06)

| | `chat_template.jinja` | `chat_template.jinja.orig` |
|---|---|---|
| Lines | 430 | 153 |
| md5 | `e904fed1e909c364b0a4473f713d6932` | `52b6d51ae5b203cb67e64b648494dad2` |
| Content | froggeric v22.4 (line 1: `template_version = "qwen3.8-froggeric-v22.4"`) | stock Qwen |

The same v22.4 file is also patched over the NVFP4 copy of the model
(`Qwen3.6-35B-A3B-NVFP4`); the stock originals were byte-identical, so the patch is
like-for-like on both.

### Template variables (froggeric v22.4 API surface)

Passed through as chat-template kwargs from the API (FreeToken passes them from
OpenAI/Anthropic-compatible request fields):

| Variable | Default | Effect |
|---|---|---|
| `tool_call_format` | `'xml'` | `'json'` → `<tool_call>{"name","arguments"}</tool_call>` JSON blocks; `'xml'` → nested `<function>` XML. Only applied when `tools` are present in the request |
| `reasoning_effort` | `'medium'` | `none/off` disables thinking; `minimal/low` → low; `high/xhigh/max/ultracode/extreme` → xhigh; anything else → medium |
| `enable_thinking` | `true` | master switch for the ` thinking` block |
| `preserve_thinking` / `preserve_reasoning` | `true` | keep the original `thinking` content when replaying assistant turns in history |
| `auto_disable_thinking_with_tools` | `false` | if true and the request has tools, thinking is disabled for the turn |
| `max_tool_arg_chars` | `0` (unlimited) | truncate tool-call arguments in history |
| `max_tool_response_chars` | `0` (unlimited) | truncate tool-result content in history |

Inline control tags in user content are also honored: `<|think_off|>`, `<|think_on|>`,
`<|think_low|>`, `<|think_medium|>`, `<|think_high|>`, `<|think_xhigh|>`, `<|think_max|>`,
`<|think_ultracode|>`, `<|think_extreme|>`.

### What the patch fixes (vs. stock)

- "Empty think" poisoning — no blank ` thinking response` prepended when replaying
  reasoning in history
- Safe `medium` default reasoning effort (stock hardcoded `xhigh`, which can burn the whole
  `max_tokens` budget with zero visible content)
- Inline `<|think_*|>` control tags
- Universal tool-argument handling (mapping *and* serialized-JSON-string arguments in history)
- Parallel `<tool_call>` token parity (single `\n` between consecutive calls — avoids
  KV-cache-breaking drift)
- Two-tier agentic error escalation (breaks "stuck repeating the same failing tool call" loops)
- Smart false-positive error detection (tool results containing the word "error",
  e.g. `console.error`/grep output, no longer trigger bogus retries)
- Merging consecutive leading `system`/`developer` messages into one turn

Full rationale and the test-by-fix mapping — `README.md` → "Applied fix: froggeric's
Qwen-Fixed-Chat-Templates" (same section has a table of which tests fail without the patch).

⚠️ The patch must be re-applied whenever the model is re-downloaded/updated; keep `.orig` —
`agentbench/tests/test_chat_template.py::test_original_template_was_backed_up` depends on it.

## 5. Launch command (the working one, v2 for RTX 4090)

```bash
ssh berda@192.168.0.88
source ~/freetoken/activate.sh
setsid nohup ft serve \
  --model /mnt/data/berda-models/models/Qwen3.6-35B-A3B-FP8 \
  --port 1919 \
  --moe-backend offload \
  --served-model-name qwen3.6-35b-a3b \
  --host 0.0.0.0 \
  --port 8000 \
  --cuda-graph-max-bs 4 \
  --max-running-requests 4 \
  --kv-reserve-tokens 300000 \
  --num-tokenizer 0 \
  --tool-call-parser qwen3_coder \
  --reasoning-parser qwen3 \
  >> ~/qwen36_fp8_4090_serve_v2.log 2>&1 < /dev/null &
```

(In `ps` it shows as: `bash -c source ~/freetoken/activate.sh && setsid nohup ft serve ... &
echo "launched pid=$!"`; `--port 1919` is a historical leftover — the server listens on port 8000.)

Key flags and what they do:

| Flag | Meaning |
|---|---|
| `--moe-backend offload` | experts are offloaded from the GPU (31.4G of experts load at startup), active ones stay on GPU |
| `--kv-reserve-tokens 300000` | KV cache of 300006 tokens ≈ 5.7 GiB; `max_model_len=262144` |
| `--cuda-graph-max-bs 4` | CUDA graphs for batches 1/2/4 (capture takes ~48 s at startup) |
| `--max-running-requests 4` | admission control; agentbench probes the 4-request boundary |
| `--num-tokenizer 0` | tokenizer runs in the shared process (lower RAM) |
| `--tool-call-parser qwen3_coder` | tool-call parser for the OpenAI-compatible API |
| `--reasoning-parser qwen3` | extracts `reasoning_content` from `thinking` blocks |

Expected startup sequence (from the log): fp8 weights load ~1.5 s → experts in parallel
31.4G ~6 s → KV cache → CUDA graph capture ~48 s → the line
`API server is ready to serve on 0.0.0.0:8000`. Full startup ≈ 1 minute.

## 6. Health check

```bash
ssh berda@192.168.0.88 "curl -s http://127.0.0.1:8000/v1/models"
# → id: qwen3.6-35b-a3b, max_model_len: 262144, supported_reasoning_efforts: high/medium/low
# → default_reasoning_effort: medium
```

Locally (from the workstation): `curl http://192.168.0.88:8000/v1/models`.

Running the test suite (already configured in `.env.sample`):
```bash
AGENTBENCH_URL=http://192.168.0.88:8000 AGENTBENCH_MODEL=qwen3.6-35b-a3b \
  pytest agentbench/tests
```

## 7. Management and diagnostics

- Server PID: `pgrep -af "ft serve"` (currently PID 6203); log: `tail -f ~/qwen36_fp8_4090_serve_v2.log`.
- Restart: `kill <pid>`, then the command from section 5; watch for the ready line.
- Log metrics: `gen throughput (token/s)` — typically 40–80 on decode; prefill up to ~1500 tok/s.
- Messages: `Aborting request for user N` — normal (client cancelled the stream, not a failure).
  `WARNING: Unsupported upgrade request / No supported WebSocket library` — harmless.
- GPU: `nvidia-smi` — 23.1/24 GiB used, 925 MiB free. With this configuration
  (300K KV-reserve) there is almost no free VRAM — long sessions plus large context
  can hit OOM (reproduced on the 16 GB 5060 Ti; see the qualbench README).
- Historical same-purpose configs (reference only, not in use):
  `~/qwen36_fp8_4090_serve.log` (v1: 127.0.0.1, `--cuda-graph-max-bs 1`),
  `~/qwen36_35b_serve.log`, `~/qwen36_35b_serve_5060ti.log` (5060 Ti, `--max-running-requests 8`),
  `~/qwen36_nvfp4_4090_serve.log` (NVFP4 quant, crashed on flashinfer JIT).

## 8. Autostart (systemd user units)

Two user-level systemd units in `~/.config/systemd/user/` start everything at boot
(no login session needed — `loginctl show-user berda | grep Linger` → `Linger=yes`).
Both are `enabled` and use the same CUDA 13.0 + venv environment as `activate.sh`.

### freetoken-daemon.service — supervisor (port 1900)

```ini
[Unit]
Description=FreeToken Daemon (supervisor, no model auto-load)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
Environment=PATH=/usr/local/cuda-13.0/bin:%h/freetoken/.venv/bin:.../nvidia/cu13/bin:...
Environment=CUDA_HOME=/usr/local/cuda-13.0
ExecStart=%h/freetoken/.venv/bin/ft daemon --host 127.0.0.1 --port 1900 --state-dir %h/.local/state/freetoken
Restart=on-failure
RestartSec=10
KillSignal=SIGINT
```

- A lightweight supervisor API on `127.0.0.1:1900` (health: `/health`,
  engine control: `/engine/start`, `/engine/status`, `/engine/stop`).
- State/logs: `~/.local/state/freetoken/` (`daemon.pid`, `logs/serve-1919.log`,
  `logs/serve-8000.log`).

### freetoken-engine.service — oneshot that loads the model

```ini
[Unit]
Description=FreeToken Engine Autostart (loads the model after the daemon is up)
After=freetoken-daemon.service network-online.target
Requires=freetoken-daemon.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStartPre=/bin/sh -c 'for i in $(seq 1 30); do curl -sf http://127.0.0.1:1900/health >/dev/null 2>&1 && exit 0; sleep 1; done; exit 1'
ExecStart=%h/freetoken/.venv/bin/ft daemon start /mnt/data/berda-models/models/Qwen3.6-35B-A3B-FP8 -- --moe-backend offload --served-model-name qwen3.6-35b-a3b --host 0.0.0.0 --port 8000 --cuda-graph-max-bs 4 --max-running-requests 4 --kv-reserve-tokens 300000 --num-tokenizer 0 --tool-call-parser qwen3_coder --reasoning-parser qwen3
TimeoutStartSec=60
```

- Waits up to 30 s for the daemon's `/health`, then asks it to spawn the engine
  (`ft daemon start <model> -- <engine args>`). Flags are **identical** to the manual
  launch command in section 5.
- On a clean boot the engine serves port 8000 via the daemon (log
  `~/.local/state/freetoken/logs/serve-1919.log`), not via the manual `nohup` command.

### Caveat — current state (2026-09-06)

- The engine started by autostart at boot **failed to bind port 8000**
  (`ERROR: [Errno 98] address already in use` in `serve-1919.log`): the manually
  launched server (PID 6203, started 12:17) held the port.
- `/engine/status` reports `running:false, lastExitCode:3, lastExitReason:"exited"`.
- **The live server right now is the manual one (PID 6203, log `~/qwen36_fp8_4090_serve_v2.log`).**
- After a reboot this conflict disappears; the autostart engine takes over. To fall
  back to the manual launch later, stop the daemon-owned engine first or the manual
  server will hit the same bind error.

### Useful commands

```bash
systemctl --user status freetoken-daemon.service freetoken-engine.service
systemctl --user restart freetoken-daemon.service     # then engine restarts via Requires
systemctl --user stop freetoken-engine.service        # stop only the model server
curl -s http://127.0.0.1:1900/engine/status           # daemon's view of the engine
journalctl --user -u freetoken-engine.service --no-pager
```

## 9. Checklist after a machine reboot

1. `ssh berda@192.168.0.88` → confirm `~/freetoken/activate.sh` is present.
2. Verify model integrity: 42 shards, `chat_template.jinja` = froggeric v22.4, `.orig` alongside.
3. Start the server (section 5), wait for `API server is ready to serve on 0.0.0.0:8000`.
4. `curl /v1/models` → id `qwen3.6-35b-a3b`, context 262144.
5. If qualbench is needed — bring up Postgres: `docker run --rm -d --name qualbench-pg -e POSTGRES_PASSWORD=qualbench -e POSTGRES_DB=qualbench -p 15432:5432 postgres:18-alpine`.
