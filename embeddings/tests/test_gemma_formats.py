"""Input formats + batches for EmbeddingGemma-2 (:8005)."""

from __future__ import annotations

import pytest

from embeddings import settings
from embeddings.client import EmbeddingsClient, cosine, l2_norm
from embeddings.conftest import SAMPLE_TEXTS

pytestmark = pytest.mark.gemma


def test_gemma_health(gemma: EmbeddingsClient):
    r = gemma.health()
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_gemma_info_modalities(gemma: EmbeddingsClient):
    info = gemma.info()
    assert info["model_id"] == settings.GEMMA_MODEL
    assert info["embedding_dimension"] == settings.GEMMA_NATIVE_DIM
    mods = set(info.get("modalities") or [])
    assert {"text", "image"}.issubset(mods)


def test_gemma_string_input(gemma: EmbeddingsClient):
    data, _ = gemma.embed("single string query")
    assert len(data["data"]) == 1
    assert len(data["data"][0]["embedding"]) == settings.GEMMA_NATIVE_DIM
    assert abs(l2_norm(data["data"][0]["embedding"]) - 1.0) < 0.05


def test_gemma_string_list_batch(gemma: EmbeddingsClient):
    batch = SAMPLE_TEXTS[: settings.BATCH_SIZE]
    data, elapsed = gemma.embed(batch)
    assert len(data["data"]) == len(batch)
    assert sorted(item["index"] for item in data["data"]) == list(range(len(batch)))
    for item in data["data"]:
        assert len(item["embedding"]) == settings.GEMMA_NATIVE_DIM
    assert elapsed < settings.TIMEOUT


@pytest.mark.batch
def test_gemma_large_batch_vs_singles_similarity(gemma: EmbeddingsClient):
    texts = SAMPLE_TEXTS[:6]
    batch, _ = gemma.embed(texts)
    singles = [gemma.embed(t)[0]["data"][0]["embedding"] for t in texts]
    for i, item in enumerate(sorted(batch["data"], key=lambda x: x["index"])):
        sim = cosine(item["embedding"], singles[i])
        assert sim > 0.999, f"index {i} batch vs single cosine={sim}"


@pytest.mark.parametrize("dim", list(settings.MRL_DIMS))
def test_gemma_mrl_dimensions(gemma: EmbeddingsClient, dim: int):
    data, _ = gemma.embed("mrl truncate", dimensions=dim)
    vec = data["data"][0]["embedding"]
    assert len(vec) == dim
    assert abs(l2_norm(vec) - 1.0) < 0.05


def test_gemma_prompt_name_text_only(gemma: EmbeddingsClient):
    data, _ = gemma.embed(
        ["search query about cats"],
        prompt_name="SearchQuery",
    )
    assert len(data["data"][0]["embedding"]) == settings.GEMMA_NATIVE_DIM


def test_gemma_semantic_relatedness(gemma: EmbeddingsClient):
    a, _ = gemma.embed("cat sleeping on a windowsill")
    b, _ = gemma.embed("kitten resting near the window")
    c, _ = gemma.embed("stock market volatility this quarter")
    va, vb, vc = (x["data"][0]["embedding"] for x in (a, b, c))
    assert cosine(va, vb) > cosine(va, vc)
