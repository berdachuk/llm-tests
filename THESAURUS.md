# llm-tests — Thesaurus (project glossary)

> **AI load:** Lookup table only. Find a term with search, read its row, then open the linked doc. Never normative — runbooks and reports hold the current numbers.

Shared vocabulary for hosts, engines, model ids, ports, and test suites used on the home LLM stack. Each row maps the **canonical term** to a **code / id** (served model, systemd unit, Docker name, or path) and a short **meaning**.

**Conventions**

- *Code / id* is what appears in configs, `/v1/models`, Bifrost provider prefixes, or shell.
- **Prefer** the name to use in new docs and tickets; **avoid** lists synonyms that cause confusion.
- When a served id, port, or host policy changes, update its row here in the same change.
- Secrets never live in this file — see [`LLM_175_USAGE.md`](LLM_175_USAGE.md) §3.

---

## Hosts and network

| Term | Code / id | Meaning |
| --- | --- | --- |
| **llm-server** | `llm-server`, `berda@192.168.0.175` | Physical host with RTX 4090 (GPU0) + RTX 5060 Ti (GPU1). SSH alias `llm-server`. |
| **`.175`** | `192.168.0.175` | Primary **ethernet** LAN IP. Nginx and Docker publishes bind here. **Prefer** this for all clients. |
| **`.88`** | `192.168.0.88` | Legacy Wi‑Fi IP / shorthand in older doc names (`STRATA_88_*`, `EMBEDDINGS_88`). Same machine as `.175`; **avoid** pointing services at it. |
| **`.51`** | nginx edge | Public reverse proxy host for `llm-88.berdachuk.com` / paths into Bifrost and LAN backends. |
| **llm-88 (public)** | `https://llm-88.berdachuk.com/v1` | Internet-facing OpenAI-shaped chat path → Strata on `.175:8080`. Auth: `LLM_88_API_KEY`. |
| **Bifrost** | `https://llm.avroflex.ru/v1` | Gateway that prefixes providers (`llm-88/…`, `embedding-88/…`, …). Auth: Virtual Key `sk-bf-…`. |
| **Virtual Key (VK)** | `sk-bf-…` | Bifrost client key. **Avoid** confusing with Strata Bearer or `LLM_88_API_KEY`. |
| **Strata Bearer** | production `api-key.txt` / `strata-api-key.txt` | Auth for direct LAN `:8080` and Monitor UI. |
| **LLM_88_API_KEY** | `llm-88-api-key.txt` | Bearer for `llm-88.berdachuk.com` and public `/frida` (bypasses Bifrost). |

## Engines and quants (GPU0 chat)

| Term | Code / id | Meaning |
| --- | --- | --- |
| **Strata** | `strata-iq3_s.service`, `:8080` | Production chat engine for Qwen3.8-Flash-Next. Runbook [`STRATA_88_PRODUCTION.md`](STRATA_88_PRODUCTION.md). |
| **IQ3_S** | pack / quant `iq3_s` | Current production quant of Flash-Next on this host. |
| **Served model (prod)** | `qwen3.8-flash-next-iq3_s` | Id returned by Strata `/v1/models` and used by OpenCode / Bifrost (`llm-88/…`). |
| **Flash-Next** | Qwen3.8-Flash-Next | Upstream MoE checkpoint family; not the same story as dense Qwen3.8-27B. |
| **n_ctx / practical ceiling** | `262144` / ~**248K** | Advertised context vs safe prompt budget clients should use (leave ~14K headroom). |
| **FreeToken** | `:8000` (disabled) | Prior MoE offload stack (Qwen3.6 FP8). Restore only via dedicated FreeToken runbook. |
| **Unsloth UD-Q4_K_XL / UD-IQ4_XS** | A/B packs (rolled back) | Higher-bit Unsloth quants tried on Strata; score **48/50**, more RAM / slower long prefill → restored IQ3_S. |
| **Maya** | Project Maya, `:8090` | Alternate engine for large MoE (GLM). Needs whole 4090 + host RAM; stop Strata for the window. |
| **Maya-S24** | quant ~95 GB | Maya pack used for GLM-5.3-Flash experiment. |
| **GLM-5.3-Flash** | `glm-5.3-flash` | Served id under Maya; hard **32K** context. Report [`MAYA_GLM53_FLASH_175_REPORT.md`](MAYA_GLM53_FLASH_175_REPORT.md). |
| **gpu-unlock** | `gpu_unlock.targets=PCI` | Kernel module raising GeForce tensor rate (Ada experimental). On this IQ3_S path: **≈0%** gain; leave cmdline **without** targets. Report [`GPU_UNLOCK_4090_STRATA_REPORT.md`](GPU_UNLOCK_4090_STRATA_REPORT.md). |
| **layer_split** | Strata multi-GPU | Split model layers across 4090+5060 Ti. Works but **slows** long prefill here; prod uses GPU0 only. |

## GPU1 services (ASR / embeddings / decisions)

| Term | Code / id | Meaning |
| --- | --- | --- |
| **Speaches** | Docker `asr-speaches`, `:8002` | Multilingual ASR (faster-whisper). Bifrost: `audio-88/…`. |
| **GigaAM** | Docker `asr-gigaam`, `:8003` | RU ASR. Model `gigaam-v3`. Bifrost: `gigaam-88/gigaam-v3`. |
| **TEI** | Docker `qwen3-embedding-0-6b`, `:8004` | Hugging Face Text Embeddings Inference. Model `Qwen/Qwen3-Embedding-0.6B` (1024-d). Bifrost: `embedding-88/…`. |
| **EmbeddingGemma-2** | Docker `embeddinggemma-2`, `:8005` | Google embedding model (768-d default). Bifrost: `embedding-gemma2-88/…`. Guide [`EMBEDDINGS_88.md`](EMBEDDINGS_88.md). |
| **FRIDA-Decisions** | Docker `frida-decisions`, `:8006` | Decision / scoring model via **`POST /pooling`**, not chat. Public: `…/frida`. |

## Test suites and metrics

| Term | Code / id | Meaning |
| --- | --- | --- |
| **llm-tests** | this repo | Live (no-mock) protocol and quality suites against real inference servers. |
| **agentbench** | `agentbench/` | Pytest suite for OpenAI Chat / Responses / Anthropic Messages, tools, streaming, concurrency. |
| **qualbench** | `qualbench/` | Text correctness suite (java/ts/sql/mcp/security/long-context); often **qualbench-50**. |
| **qualbench-50** | 50-task full run | Score `N/50` + wall seconds — primary quality/speed gate for chat stacks. |
| **Monitor** | Strata UI `#monitor` | Built-in prefill/decode probes (warm/reuse cells). Needs Bearer in Settings. |
| **matrix (A–F)** | context ladder | Long-context needle tiers; **F-calib** ~248K practical; raw F@262K often HTTP 400. |
| **prefill** | tok/s on prompt | Prompt-processing throughput (tensor-heavy). |
| **decode** | tok/s on generation | Token generation (usually memory-bound). |
| **wall tok/s** | session tokens / elapsed | End-to-end agent feel including prefill; often ≪ peak decode. |
| **embeddings suite** | `embeddings/tests` | Live TEI + Gemma format/batch/MRL probes. |

## Clients and tooling

| Term | Code / id | Meaning |
| --- | --- | --- |
| **OpenCode** | `llm-88-local/…` | Local coding agent; LAN baseURL `http://192.168.0.175:8080/v1`, context limit **248000**. |
| **Bifrost model prefix** | `llm-88/`, `embedding-88/`, … | Provider namespace on `llm.avroflex.ru/v1`; strip when talking to LAN Strata/TEI directly. |
| **active stack** | [`STRATA_88_ACTIVE_STACK.md`](STRATA_88_ACTIVE_STACK.md) | Snapshot of what should be running on GPU0/GPU1 right now. |
| **usage how-to** | [`LLM_175_USAGE.md`](LLM_175_USAGE.md) | Client-facing paths, auth matrix, curl examples (no secrets). |

---

## Prefer / avoid (quick)

| Prefer | Avoid |
| --- | --- |
| `.175` / `llm-server` | `.88` as service bind or nginx upstream |
| `qwen3.8-flash-next-iq3_s` | Retired compat alias `qwen3.6-35b-a3b` |
| Strata Bearer on LAN `:8080` | Using VK or LLM_88 key against raw `:8080` |
| VK (`sk-bf-…`) on Bifrost `/v1` | Strata production key on Bifrost |
| `POST /pooling` for FRIDA | Treating FRIDA as chat completions |
| Practical ~248K client limit | Advertising raw 262144 as safe prompt size |
| gpu-unlock **off** (no `targets=`) for IQ3_S prod | Leaving Ada unlock enabled “for free speed” |
