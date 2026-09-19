# FreeToken + Qwen3.8-27B-NVFP4 — serve runbook (RTX 4090, 192.168.0.88)

> Operational runbook for serving `nvidia/Qwen3.8-27B-NVFP4` (Model Optimizer
> mixed-precision release) with FreeToken on the 24 GiB RTX 4090.
> Infrastructure facts verified 2026-09-06. The original FP8 runbook concluded
> the dense FP8 checkpoint (≈27.4 GiB resident) cannot fit this card; the NVFP4
> release **fits, but only with a tiny KV budget (≈5.6K tokens)** — verified
> empirically: the dense weights leave ~2 GiB of the 24.5 GiB card, and the KV
> allocator caps at 5,577 tokens regardless of `--kv-reserve-tokens`.

## 1. Machine and hardware

| Parameter | Value |
|---|---|
| Host | `berda@192.168.0.88` (SSH); FreeToken Desktop not required |
| GPU | RTX 4090, 24 GiB — the server's workhorse card |
| GPU 2 | RTX 5060 Ti, 16 GiB — idle (reserve for a second engine, not used here) |
| CPU / RAM | i9-14900KF, 32 threads, 125 GiB RAM (87 GiB available) |
| Disk | `/mnt/data` (NVMe 1.8T) — models and download log |

## 2. FreeToken repository

- Clone: `~/freetoken` on 192.168.0.88 — upstream `https://github.com/FlashML-org/FreeToken.git`.
- Version: `v0.1.2-28-gaf71ba4` (branch `main`, commit `af71ba4`, clean — **no local code patches at all**).
- Install: editable install in `~/freetoken/.venv` (Python 3.12); CUDA 13.0 via `activate.sh`
  (prepends `/usr/local/cuda-13.0/bin` and sets `CUDA_HOME` — required for flashinfer JIT).
- The only local file in the repo is `activate.sh` (untracked).

## 3. Model

- HF repo: `nvidia/Qwen3.8-27B-NVFP4` (Model Optimizer `0.47.0.dev0`), downloaded into:
  `/mnt/data/berda-models/models/Qwen3.8-27B-NVFP4` (21 GiB on disk, 3 safetensors shards,
  `model-00001/2/3-of-00003` = 9.3 / 9.3 / 1.9 GiB, 2194 tensors incl. 333 vision tensors
  that FreeToken drops for text-only serving).
- Quantization (`hf_quant_config.json`): `MIXED_PRECISION` —
  - MLP `gate/up/down_proj`: **NVFP4, group_size 16**
  - attention / linear-attn projections: **FP8**
  - `lm_head.weight`, `model.language_model.embed_tokens.weight`, norms: unquantized (BF16)
  - `kv_cache_quant_algo: FP8` (model-opt metadata; FreeToken uses its own KV settings)
- Architecture (arch `Qwen3_5ForConditionalGeneration`, text `qwen3_5_text`, **dense**):
  - **Dense** — `num_experts == 0`, no routed experts, no MoE offload possible
  - **Hybrid attention**: 64 layers, every 4th is `full_attention` (16 full + 48 GatedDeltaNet
    linear-attention layers), `full_attention_interval=4`
  - hidden 5120, 24 Q-heads / 4 KV-heads, head_dim 256, intermediate 17408, vocab 248320
  - `max_position_embeddings: 262144`; `tie_word_embeddings: false`
- `generation_config` sampling defaults: temperature 1.0, top_k 20, top_p 0.95 (same as 3.6).

## 4. VRAM feasibility — FITS but KV is tiny (measured, 2026-09-06)

Resident GPU weights for a text-only serve of the NVFP4 release:

| Component | Size (approx.) |
|---|---|
| 64 layers, quantized (NVFP4 MLP + FP8 attention + BF16 norms/scales) | ≈ 20.4 GiB total per `model.safetensors.index.json` metadata (incl. 333 vision tensors that FreeToken skips) |
| `embed_tokens` [248320, 5120] BF16 | 2.37 GiB |
| `lm_head` [248320, 5120] BF16 | 2.37 GiB |
| **Total resident weights (measured)** | **≈ 22.2 GiB** (VRAM 22.0–22.3 of 24.6 GiB after load) |

Measured on the live server:
- Free VRAM before model load: **23.07 GiB**
- VRAM after weights + CUDA graphs: **2.04 GiB free** (nvidia-smi 22.0/24.6 GiB used)
- KV allocator result: **5,577 tokens, K+V = 0.34 GiB** — IDENTICAL for
  `--kv-reserve-tokens 8192` and `--kv-reserve-tokens 32768` (the allocator
  takes what fits, not what was requested; an oversized request just clamps).
- `--kv-reserve-tokens 65536` with `--max-running-requests 4` → hard
  `AssertionError: Not enough memory for KV cache` at startup.

So "maximum context" for this model on this card is **~5.6K tokens** (about
what the default floor gives), **not** the advertised 262,144. The dense NVFP4
checkpoint has no MoE experts to offload, so the RAM/PCIe trick that makes the
35B-A3B work does not apply. The KV ceiling only rises with a smaller weight
footprint (FP8→NF4, or a larger card).

The 35B-A3B runs on the same card only because it is an MoE
(`--moe-backend offload` keeps 31.4 GiB of experts in RAM). The dense 27B has
nothing to offload; the `--moe-*` knobs are inert for dense checkpoints.

## 5. Chat template — patched to froggeric v22.4 (already applied)

The NVFP4 dir ships the **stock Qwen template** — the buggy class froggeric fixes
(`reasoning_effort` xhigh default, no inline `<|think_*|>` tags, XML-only tool calls,
no `tool_call_format: 'json'`, no truncation knobs). Patched 2026-09-06:

```bash
cd /mnt/data/berda-models/models/Qwen3.8-27B-NVFP4
cp chat_template.jinja chat_template.jinja.orig
cp /mnt/data/berda-models/models/Qwen3.6-35B-A3B-FP8/chat_template.jinja chat_template.jinja
# verify: head -1 chat_template.jinja → {%- set template_version = "qwen3.8-froggeric-v22.4" %}
```

Wiring-in is automatic: FreeToken's tokenizer load prefers a root-level
`chat_template.jinja` over the inline template string. Re-apply after any
re-download; keep `.orig` (agentbench `test_chat_template.py` depends on it).

## 6. Launch command (verified working)

```bash
ssh berda@192.168.0.88
source ~/freetoken/activate.sh
setsid nohup ft serve \
  --model /mnt/data/berda-models/models/Qwen3.8-27B-NVFP4 \
  --moe-backend offload \
  --served-model-name qwen3.8-27b-nvfp4 \
  --host 0.0.0.0 \
  --port 8000 \
  --cuda-graph-max-bs 1 \
  --max-running-requests 1 \
  --kv-reserve-tokens 32768 \
  --num-tokenizer 0 \
  --tool-call-parser qwen3_coder \
  --reasoning-parser qwen3 \
  >> ~/qwen38_nvfp4_4090_serve.log 2>&1 < /dev/null &
```

Notes (all verified 2026-09-06):
- `--moe-backend offload` is accepted but **inert** for a dense checkpoint.
- **KV is clamped by the allocator, not the flag:** `--kv-reserve-tokens 32768`
  yields 5,577 tokens (0.34 GiB). `--max-running-requests 4` + 65536 → hard
  startup assertion; `1` is the working profile.
- Expected log sequence: mixed-fp8 weights (3/3 shards) → `Allocating 5577
  tokens for KV cache` → CUDA graphs → `API server is ready to serve on 0.0.0.0:8000`.
- This conflicts with the live 3.6 server (port 8000 + full VRAM) — stop it first.
- `--max-running-requests 1` also shrinks the GDN linear-state pool (25→21 slots),
  which is part of why this profile fits where the 4-request profile asserts.

## 7. Health check and tests

```bash
ssh berda@192.168.0.88 "curl -s http://127.0.0.1:8000/v1/models"
# → id: qwen3.8-27b-nvfp4, max_model_len: 262144 (advertised ceiling; served KV
#   budget is what §6 actually reserved — check the startup log line)
```

Test suite (`.env.sample`), pointing at the 3.8 model id:

```bash
AGENTBENCH_URL=http://192.168.0.88:8000 AGENTBENCH_MODEL=qwen3.8-27b-nvfp4 \
  pytest agentbench/tests
AGENTBENCH_TEMPLATE_PATH=/mnt/data/berda-models/models/Qwen3.8-27B-NVFP4 \
  pytest agentbench/tests/test_chat_template.py
```

⚠️ Most agentbench tests assume a large context (basic tests send modest
prompts, but `test_large_context.py` needs 60K–200K tokens and will **fail**
against this 5.6K-token ceiling). Run only the short-prompt tests, or restore
the 3.6 engine for the full suite.

## 8. Management and diagnostics

- Server PID: `pgrep -af "ft serve"`; log: `tail -f ~/qwen38_nvfp4_4090_serve.log`.
- Restart: `kill <pid>`, re-run §6 command; watch for the ready line (or the OOM).
- GPU: `nvidia-smi` — the 4090 is fully used by this server; switching models means
  stopping the current engine first.
- Messages: `Aborting request for user N` — normal (client cancelled). `Unsupported
  upgrade request / No supported WebSocket library` — harmless. Same as the 3.6 runbook.

## 9. Autostart (systemd user units)

Same two user units as the 3.6 setup (see `FREETOKEN_QWEN36_SERVE.md` §8 for full file
contents): `freetoken-daemon.service` (supervisor, port 1900) + `freetoken-engine.service`
(oneshot that starts the engine). To point autostart at the 3.8 instead:

1. Edit `~/.config/systemd/user/freetoken-engine.service`:
   - `ExecStart=... ft daemon start /mnt/data/berda-models/models/Qwen3.8-27B-NVFP4 -- ... --served-model-name qwen3.8-27b-nvfp4 ... --kv-reserve-tokens 32768 --max-running-requests 1 --cuda-graph-max-bs 1 ...`
   - Keep the CUDA 13 `PATH`/`CUDA_HOME` lines from the 2026-09-05 fix.
2. `systemctl --user daemon-reload`
3. Stop the 3.6 engine (else port 8000 bind error):
   `systemctl --user stop freetoken-engine.service`, `kill <3.6-pid>`.
4. `systemctl --user restart freetoken-engine.service`

## 10. Checklist after a machine reboot (for the 3.8 switch)

1. `ssh berda@192.168.0.88` → confirm `~/freetoken/activate.sh` is present.
2. Verify model integrity: 3 safetensors shards; `chat_template.jinja` = froggeric v22.4
   (header `qwen3.8-froggeric-v22.4`), `.orig` alongside.
3. Remember the KV ceiling: **5,577 tokens** on this card (see §4) — do not expect
   the advertised 262,144 context.
4. Start the server (§6), wait for ready line (`Allocating 5577 tokens for KV cache`).
5. `curl /v1/models` → id `qwen3.8-27b-nvfp4`; `max_model_len` reports 262144
   (model ceiling, not served budget — trust the startup log, not the metadata).
6. If qualbench is needed — bring up Postgres:
   `docker run --rm -d --name qualbench-pg -e POSTGRES_PASSWORD=qualbench -e POSTGRES_DB=qualbench -p 15432:5432 postgres:18-alpine`.

## 11. Verdict

Qwen3.8-27B-NVFP4 **starts and serves** on the 4090, but the dense weights
(~22.2 GiB resident) leave room for only **~5.6K KV tokens** — a short-context
interactive profile, not a long-context coding server. If the goal was 262K
context, restore the Qwen3.6-35B-A3B-FP8 MoE server (see `FREETOKEN_QWEN36_SERVE.md`)
or use a larger card for the dense 27B.
