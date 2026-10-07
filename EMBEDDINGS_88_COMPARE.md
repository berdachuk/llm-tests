# Embedding backends on `.88` — comparison

> Generated: **2026-10-07 13:41 UTC** by `embeddings/compare_report.py`.

## Deployment snapshot

| | TEI Qwen3-Embedding-0.6B | EmbeddingGemma-2 |
|---|---|---|
| Host | `http://192.168.0.88:8004` | `http://192.168.0.88:8005` |
| Model | `Qwen/Qwen3-Embedding-0.6B` | `google/embeddinggemma-2` |
| Native dim | 1024 | 768 |
| Health HTTP | 200 | 200 |
| Runtime | HuggingFace TEI | SentenceTransformers + FastAPI |
| Modalities | text | text, image, audio, video |
| Public text | Bifrost `embedding-88/...` | Bifrost `embedding-gemma2-88/...` |
| Public MM | — | `llm.avroflex.ru/embedding-gemma2/...` |

## Input format support

| Format | TEI :8004 | Gemma :8005 |
|---|---|---|
| `input: string` | yes | yes |
| `input: string[]` (batch) | yes | yes |
| `dimensions` (e.g. 256) | yes | yes |
| `prompt_name` (ST) | no | yes |
| `input: {image}` | no | yes |
| Mixed text+image batch | no | yes |

## Batch latency (n=8, mean of 3)

| Backend | dim | mean s | items/s | mean L2 |
|---|---:|---:|---:|---:|
| TEI | 1024 | 0.028 | 287.9 | 1.0000 |
| Gemma | 768 | 0.074 | 108.0 | 1.0020 |

## Semantic cosine (same text pairs)

| Pair | TEI | Gemma |
|---|---:|---:|
| related (cat/kitten) | 0.7455 | 0.9030 |
| unrelated (cat/markets) | 0.3635 | 0.5844 |
| cross-lang (ocean/море) | 0.7734 | 0.8791 |

## When to use which

- **TEI Qwen3-Embedding-0.6B (`:8004`)** — default for text RAG / Bifrost `embedding-88`. Higher native dim (1024), TEI batching, text-only.
- **EmbeddingGemma-2 (`:8005`)** — multimodal (image/audio/video/interleaved), MRL dims 128/256/512/768, ST `prompt_name`. Text also via Bifrost `embedding-gemma2-88`; multimodal only via `/embedding-gemma2` path (llm-88 Bearer).

## Pytest

```bash
cd ~/projects-llm-test/llm-tests
pytest embeddings/tests -v
```

Last pytest exit code in this run: **0**.
