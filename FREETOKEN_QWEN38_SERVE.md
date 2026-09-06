# FreeToken + Qwen3.8-27B-FP8 — serve runbook (RTX 4090, 192.168.0.88)

> Operational runbook for serving `Qwen/Qwen3.8-27B-FP8` with FreeToken.
> ⚠️ **Read §4 first: this is a dense model and does not fit the 24 GiB RTX 4090
> as-is.** Infrastructure facts verified 2026-09-06.

## 1. Machine and hardware

| Parameter | Value |
|---|---|
| Host | `berda@192.168.0.88` (SSH); FreeToken Desktop not required |
| GPU | RTX 4090, 24 GiB — the server's workhorse card |
| GPU 2 | RTX 5060 Ti, 16 GiB — idle (even less headroom than the 4090) |
| CPU / RAM | i9-14900KF, 32 threads, 125 GiB RAM (87 GiB available) |
| Disk | `/mnt/data` (NVMe 1.8T) — models and download log |

## 2. FreeToken repository

- Clone: `~/freetoken` on 192.168.0.88 — upstream `https://github.com/FlashML-org/FreeToken.git`.
- Version: `v0.1.2-28-gaf71ba4` (branch `main`, commit `af71ba4`, clean — **no local code patches at all**).
- Install: editable install in `~/freetoken/.venv` (Python 3.12); CUDA 13.0 via `activate.sh`
  (see the Qwen3.6 runbook `FREETOKEN_QWEN36_SERVE.md` §2 for the file contents).
- The only local file in the repo is `activate.sh` (untracked).

## 3. Model

- HF repo: `Qwen/Qwen3.8-27B-FP8`, downloaded via `hf download` (no HF_TOKEN) into:
  `/mnt/data/berda-models/models/Qwen3.8-27B-FP8` (28.7 GiB on disk, 81 files).
  Download log: `/mnt/data/berda-models/models/qwen38_download.log`.
- Checkpoint layout (`model.safetensors.index.json`, 66 shards):
  - `layers-0..63.safetensors` — 64 decoder layers (22.7 GiB total, 20 keys each)
  - `outside.safetensors` — 6.0 GiB, **~99% the vision tower** (`model.visual.*`, skipped text-only)
    plus the only text keys: `lm_head.weight`, `model.language_model.embed_tokens.weight`,
    `model.language_model.norm.weight` (all BF16)
  - `mtp.safetensors` — 0.48 GiB multi-token-prediction head (skipped by the loader)
- Architecture (arch `Qwen3_5ForConditionalGeneration`, text `qwen3_5_text`, dense):
  - **Dense** — `num_experts == 0`, no routed experts, no MoE offload possible
  - **Hybrid attention**: 64 layers, every 4th is `full_attention` (16 full + 48 GatedDeltaNet
    linear-attention layers), `full_attention_interval=4`
  - hidden 5120, 24 Q-heads / 4 KV-heads, head_dim 256, intermediate 17408, vocab 248320
  - `max_position_embeddings: 262144`; `tie_word_embeddings: false`
  - Vision-capable checkpoint served text-only (FreeToken drops `visual.*`)
- Quantization: per-tensor FP8 `e4m3` (W8A16) on attention/GDN/MLP linears + BF16 norms/scales;
  **`lm_head` and `embed_tokens` stay BF16** (in `modules_to_not_convert`).
- generation_config: temperature 1.0, top_k 20, top_p 0.95 (same sampling defaults as 3.6).

## 4. VRAM feasibility — CRITICAL

Resident GPU weights for a text-only serve:

| Component | Size |
|---|---|
| 64 layers (FP8 weights + BF16 scales/norms) | ≈ 22.7 GiB |
| `embed_tokens` [248320, 5120] BF16 | 2.37 GiB |
| `lm_head` [248320, 5120] BF16 | 2.37 GiB |
| **Total resident weights** | **≈ 27.4 GiB** |
| + KV cache + activations + CUDA-graph headroom | on top |

RTX 4090 has **24 GiB**. The model does **not fit** — `ft serve` will fail with a CUDA
OOM while materializing weights, before the API comes up.

Why the 35B-A3B runs on the same card: it is an **MoE** — `--moe-backend offload` keeps
31.4 GiB of experts in RAM, only attention/shared-expert/embed/KV sit in VRAM. The dense
27B has nothing to offload, and FreeToken has no dense-weight offload path (the `--moe-*`
knobs are inert for dense checkpoints). TP is `TP=1`-only in the loader
(`NotImplementedError` otherwise), so a 2-GPU split across 4090+5060 Ti is **not** an option.

Options if you really want to serve 3.8-27B on this box:
1. **NVFP4 quant release** (if/when Qwen publishes one): est. ≈ 11.4 GiB layers + 4.7 GiB
   embed/lm_head ≈ 16.1 GiB resident → fits the 4090, but KV must shrink
   (full-attn layers cost ≈ 64 KiB per token: 16 layers × 2 × 4 KV-heads × 256 dim × 2 B;
   300K tokens ≈ 19 GiB is impossible — plan ≈ 64–128K KV tokens).
2. Stay on `Qwen3.6-35B-A3B-FP8` (already serving, fits comfortably).
3. Bigger GPU (48 GiB+) for the FP8 dense model.

## 5. Chat template — patch to froggeric v22.4

The 3.8 model dir ships the **stock Qwen template** (`chat_template.jinja`, 169 lines,
md5 `519239a4908bb1f805bbce5fa8c8a242`) — the buggy class froggeric fixes:

- `reasoning_effort|default('xhigh')` — hardcoded xhigh default (burns max_tokens with zero visible content)
- `raise_exception` on any effort outside `xhigh/medium/low` (no graceful mapping of `none/high/max/...`)
- no inline `<|think_*|>` control tags
- XML `<tool_call><function>` only — no `tool_call_format: 'json'` option
- no `max_tool_arg_chars` / `max_tool_response_chars` truncation, no `auto_disable_thinking_with_tools`

The froggeric template is literally versioned for this model
(`template_version = "qwen3.8-froggeric-v22.4"`) and is already in use on the 3.6-35B —
copy it over and keep the stock one as `.orig`:

```bash
cd /mnt/data/berda-models/models/Qwen3.8-27B-FP8
cp chat_template.jinja chat_template.jinja.orig
cp /mnt/data/berda-models/models/Qwen3.6-35B-A3B-FP8/chat_template.jinja chat_template.jinja
# verify: head -1 chat_template.jinja → {%- set template_version = "qwen3.8-froggeric-v22.4" %}
```

Wiring-in is automatic: FreeToken's `load_tokenizer()` → `AutoTokenizer.from_pretrained()`
prefers a root-level `chat_template.jinja` (`CHAT_TEMPLATE_FILE`) over the inline template
string in `tokenizer_config.json` (verified empirically on the 3.6 dir). No server flag.
Full rationale + test-by-fix mapping: repo `README.md` → "Applied fix: froggeric's
Qwen-Fixed-Chat-Templates".

⚠️ Re-apply after any re-download; keep `.orig` (the agentbench
`test_chat_template.py::test_original_template_was_backed_up` check depends on it).

## 6. Launch command

Same shape as the 3.6 command (the `--moe-backend offload` flag is accepted but **inert**
for a dense checkpoint — it exists only for the MoE offload family):

```bash
ssh berda@192.168.0.88
source ~/freetoken/activate.sh
setsid nohup ft serve \
  --model /mnt/data/berda-models/models/Qwen3.8-27B-FP8 \
  --moe-backend offload \
  --served-model-name qwen3.8-27b-fp8 \
  --host 0.0.0.0 \
  --port 8000 \
  --cuda-graph-max-bs 4 \
  --max-running-requests 4 \
  --kv-reserve-tokens 300000 \
  --num-tokenizer 0 \
  --tool-call-parser qwen3_coder \
  --reasoning-parser qwen3 \
  >> ~/qwen38_fp8_4090_serve.log 2>&1 < /dev/null &
```

**Expected outcome on the 24 GiB card (see §4): CUDA OOM while loading weights.** Do not
run this casually — it also conflicts with the live 3.6 server (port 8000 + full VRAM).
A variant for a 48 GiB card, or for an NVFP4 release with a small KV budget
(`--kv-reserve-tokens 65536`), would use exactly this command.

If it ever starts, the expected log sequence matches the 3.6 runbook §5
(fp8 weights → KV cache → CUDA graphs → `API server is ready to serve on 0.0.0.0:8000`).

## 7. Health check and tests

```bash
ssh berda@192.168.0.88 "curl -s http://127.0.0.1:8000/v1/models"
# → id: qwen3.8-27b-fp8, max_model_len: 262144
```

Test suite (`.env.sample`), pointing at the 3.8 model id:

```bash
AGENTBENCH_URL=http://192.168.0.88:8000 AGENTBENCH_MODEL=qwen3.8-27b-fp8 \
  pytest agentbench/tests
AGENTBENCH_TEMPLATE_PATH=/mnt/data/berda-models/models/Qwen3.8-27B-FP8 \
  pytest agentbench/tests/test_chat_template.py
```

## 8. Management and diagnostics

- Server PID: `pgrep -af "ft serve"`; log: `tail -f ~/qwen38_fp8_4090_serve.log`.
- Restart: `kill <pid>`, re-run §6 command; watch for the ready line (or the OOM, see §4).
- GPU: `nvidia-smi` — the 4090 is 23.1/24 GiB used by the 3.6 server; the 3.8 cannot
  share it. Switching models means stopping the 3.6 engine first.
- Messages: `Aborting request for user N` — normal (client cancelled). `Unsupported
  upgrade request / No supported WebSocket library` — harmless. Same as the 3.6 runbook.

## 9. Autostart (systemd user units)

Same two user units as the 3.6 setup (see `FREETOKEN_QWEN36_SERVE.md` §8 for full file
contents): `freetoken-daemon.service` (supervisor, port 1900) + `freetoken-engine.service`
(oneshot that starts the engine). To point autostart at the 3.8 instead:

1. Edit `~/.config/systemd/user/freetoken-engine.service`:
   - `ExecStart=... ft daemon start /mnt/data/berda-models/models/Qwen3.8-27B-FP8 -- ... --served-model-name qwen3.8-27b-fp8 ...`
2. `systemctl --user daemon-reload`
3. Stop the 3.6 engine (else port 8000 bind error — the exact failure logged on 2026-09-05):
   `systemctl --user stop freetoken-engine.service`, `kill <3.6-pid>`.
4. `systemctl --user restart freetoken-engine.service`

Remember: even a successful autostart cannot overcome §4 — the dense FP8 weights don't
fit the card.

## 10. Checklist after a machine reboot (for the 3.8 switch)

1. `ssh berda@192.168.0.88` → confirm `~/freetoken/activate.sh` is present.
2. Verify model integrity: 66 safetensors shards; `chat_template.jinja` = froggeric v22.4
   (header `qwen3.8-froggeric-v22.4`), `.orig` alongside.
3. Recheck VRAM budget for the chosen quant before launching (§4).
4. Start the server (§6), wait for ready line or diagnose OOM.
5. `curl /v1/models` → id `qwen3.8-27b-fp8`, context 262144.
6. If qualbench is needed — bring up Postgres:
   `docker run --rm -d --name qualbench-pg -e POSTGRES_PASSWORD=qualbench -e POSTGRES_DB=qualbench -p 15432:5432 postgres:18-alpine`.
