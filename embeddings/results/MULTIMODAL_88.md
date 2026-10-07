# EmbeddingGemma-2 multimodal results (`.88:8005`)

> Generated: 2026-10-07 — live probe + `pytest embeddings/tests/test_gemma_multimodal.py`  
> Model: `google/embeddinggemma-2` · dim **768** · bf16 · modalities: text, image, audio, video*, message

## Pytest

| Result | Count |
|---|---:|
| passed | **18** |
| skipped | **1** (video — no torchcodec/NVRTC) |
| failed | **0** |
| wall time | ~12 s |

## Live latency / shape

| Case | OK | n | dim | latency s | mean L2 |
|---|---|---:|---:|---:|---:|
| image PNG | yes | 1 | 768 | 0.085 | 1.00 |
| image JPEG | yes | 1 | 768 | 0.071 | 1.00 |
| image list (2 in one item) | yes | 1 | 768 | 0.122 | 1.00 |
| image batch ×3 | yes | 3 | 768 | 0.191 | 1.00 |
| image MRL `dimensions=256` | yes | 1 | 256 | 0.071 | 1.00 |
| interleaved text+image | yes | 1 | 768 | 0.071 | 1.00 |
| interleaved text+2 images | yes | 1 | 768 | 0.121 | 1.00 |
| audio WAV | yes | 1 | 768 | 0.034 | 1.00 |
| batch text+2 audio | yes | 3 | 768 | 0.038 | 1.00 |
| interleaved text+audio | yes | 1 | 768 | 0.032 | 1.00 |
| interleaved text+image+audio | yes | 1 | 768 | 0.084 | 1.00 |
| full MM batch (4 items) | yes | 4 | 768 | 0.213 | 1.00 |
| video (mp4 / misuse) | **no** | — | — | — | needs torchcodec |

Extra: cosine between two different WAV tones ≈ **0.969** (различимы, но близки на коротких синтетических тонах).

## Что работает / нет

- **OK:** PNG/JPEG data-URL, multi-image, batches, HTTP URL download, `file://` reject, WAV audio, interleaved mixes, MRL truncate.
- **Не OK на текущем образе:** **video** (`torchcodec` + `libnvrtc` не подключены).

Raw JSON: `embeddings/results/multimodal-latest.json`
