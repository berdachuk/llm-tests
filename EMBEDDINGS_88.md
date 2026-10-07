# Embedding models on `.88` — how they are deployed and how to use them

Two live embedding backends share **GPU 1 (RTX 5060 Ti)** on `192.168.0.88` with Speaches (`:8002`) and GigaAM (`:8003`).

| | **Qwen3-Embedding-0.6B (TEI)** | **EmbeddingGemma-2** |
|---|---|---|
| Host bind | `192.168.0.88:8004` | `192.168.0.88:8005` |
| Runtime | HuggingFace Text Embeddings Inference | SentenceTransformers + FastAPI |
| Model id | `Qwen/Qwen3-Embedding-0.6B` | `google/embeddinggemma-2` |
| Native dim | **1024** | **768** (MRL 128/256/512) |
| Modalities | text | text, image, audio, video, interleaved |
| Compose / tree | `avroflex-infra/llm-88/qwen3-embedding` | `avroflex-infra/llm-88/embeddinggemma-2` → `~/voice-asr/embeddinggemma-2/` on host |
| Nginx prefix (`.51`) | `/embedding/` | `/embedding-gemma2/` |
| Bifrost (text) | `embedding-88/Qwen/Qwen3-Embedding-0.6B` | `embedding-gemma2-88/google/embeddinggemma-2` |
| Multimodal public | — | `https://llm.avroflex.ru/embedding-gemma2/v1/embeddings` |

IaC / topology details: `avroflex-infra/docs/embeddinggemma-2-deployment-plan.md`, `docs/bifrost-llm88-asr-stack.md`.

## Topology

```text
Text RAG (OpenAI /v1/embeddings via Bifrost + VK key):
  llm.avroflex.ru/v1/embeddings
    ├─ model embedding-88/...           → llm-88.berdachuk.com/embedding → :8004 TEI
    └─ model embedding-gemma2-88/...    → llm-88.berdachuk.com/embedding-gemma2 → :8005

Multimodal (image / audio / video / interleaved; llm-88 Bearer, NOT Bifrost):
  llm.avroflex.ru/embedding-gemma2/v1/embeddings
    → Traefik PathPrefix /embedding-gemma2
    → llm-88.berdachuk.com/embedding-gemma2
    → 192.168.0.88:8005
```

Bifrost only accepts OpenAI text `input: string | string[]`. Native ST modality objects must use the `/embedding-gemma2` path.

Auth:

- Bifrost / VK keys — for `llm.avroflex.ru/v1/*`.
- llm-88 nginx Bearer (`EMBEDDING_88_API_KEY` / same key as other `.88` fronts) — for `llm-88.berdachuk.com/*` and Traefik multimodal path.
- VPC: `http://192.168.0.88:8004|8005` — no auth.

## When to pick which

- **TEI Qwen (`:8004`)** — default text embeddings for RAG apps already on Bifrost `embedding-88`. Fast TEI batching, dim 1024.
- **Gemma-2 (`:8005`)** — multimodal retrieval, MRL shorter vectors, ST `prompt_name` (`SearchQuery` / `Document`). Text also available through Bifrost under `embedding-gemma2-88`.

## API shapes

### Common (both)

```bash
# string
curl -fsS http://192.168.0.88:8004/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen/Qwen3-Embedding-0.6B","input":"ocean waves"}'

# batch string[]
curl -fsS http://192.168.0.88:8005/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model":"google/embeddinggemma-2","input":["a","b","c"]}'

# optional MRL / truncate
curl -fsS http://192.168.0.88:8005/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model":"google/embeddinggemma-2","input":"q","dimensions":256}'
```

TEI also accepts `dimensions` (truncate). Gemma renormalizes after MRL truncate (`dimensions >= 128`).

### Gemma-only

```bash
# image modality object
curl -fsS http://192.168.0.88:8005/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model":"google/embeddinggemma-2","input":{"image":"data:image/png;base64,..."}}'

# interleaved text + image
curl -fsS http://192.168.0.88:8005/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model":"google/embeddinggemma-2","input":{"text":"caption <|image|>","image":"data:image/png;base64,..."}}'

# prompt_name (text-only inputs)
curl -fsS http://192.168.0.88:8005/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model":"google/embeddinggemma-2","input":["query"],"prompt_name":"SearchQuery"}'
```

Media: `data:` base64 URL or `https://` URL (server downloads; size/timeout capped). `file://` rejected.

### Public paths

```bash
# text via Bifrost (VK)
curl -fsS https://llm.avroflex.ru/v1/embeddings \
  -H "Authorization: Bearer $VK" -H 'Content-Type: application/json' \
  -d '{"model":"embedding-gemma2-88/google/embeddinggemma-2","input":["hi"]}'

# multimodal via Traefik (llm-88 key)
curl -fsS https://llm.avroflex.ru/embedding-gemma2/v1/embeddings \
  -H "Authorization: Bearer $LLM88KEY" -H 'Content-Type: application/json' \
  -d '{"model":"google/embeddinggemma-2","input":{"image":"data:image/png;base64,..."}}'
```

Body size on nginx for Gemma prefix: **50m**.

## Ops on `.88`

```bash
# TEI (existing)
ssh berda@192.168.0.88 'cd ~/voice-asr/qwen3-embedding && docker compose ps'

# Gemma
ssh berda@192.168.0.88 'cd ~/voice-asr/embeddinggemma-2 && docker compose ps'
curl -fsS http://192.168.0.88:8005/health
curl -fsS http://192.168.0.88:8005/info | jq
nvidia-smi --query-gpu=index,memory.used,memory.free --format=csv
```

Nginx on `.51` is already installed: only add/reload location snippets (`llm-88/nginx/install-embedding-gemma2.py`). Do not reinstall nginx packages.

## Tests in this repo

```bash
cd ~/projects-llm-test/llm-tests
source .venv/bin/activate   # or create venv + pip install -r requirements.txt
pytest embeddings/tests -v
pytest embeddings/tests -m multimodal -v   # Gemma image/audio/interleaved/batches
python -m embeddings.compare_report   # writes EMBEDDINGS_88_COMPARE.md
```

Multimodal coverage (`embeddings/tests/test_gemma_multimodal.py`): PNG/JPEG objects,
image lists, image batches, MRL on images, interleaved text+image(s), HTTP URL
download, `file://` reject, WAV audio (+ tones/batch/interleaved), text+image+audio
mix. **Video** is skipped until `torchcodec`+matching NVRTC is available in the
CUDA runtime image (audio uses `librosa`).

Env overrides: `EMBED_TEI_URL`, `EMBED_GEMMA_URL`, `EMBED_TEI_MODEL`, `EMBED_GEMMA_MODEL`, `EMBED_TIMEOUT`, `EMBED_BATCH_SIZE`.
