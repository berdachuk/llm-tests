"""Input formats + batches for TEI Qwen3-Embedding-0.6B (:8004)."""

from __future__ import annotations

import pytest

from embeddings import settings
from embeddings.client import EmbeddingsClient, cosine, l2_norm
from embeddings.conftest import SAMPLE_TEXTS

pytestmark = pytest.mark.tei


def test_tei_health(tei: EmbeddingsClient):
    r = tei.health()
    assert r.status_code == 200


def test_tei_info_dtype(tei: EmbeddingsClient):
    info = tei.info()
    assert "Qwen3-Embedding" in info.get("model_id", "")
    assert info.get("model_dtype") in ("float16", "bfloat16", "float32")


def test_tei_string_input(tei: EmbeddingsClient):
    data, _ = tei.embed("single string query")
    assert len(data["data"]) == 1
    assert len(data["data"][0]["embedding"]) == settings.TEI_NATIVE_DIM
    assert abs(l2_norm(data["data"][0]["embedding"]) - 1.0) < 0.05


def test_tei_string_list_batch(tei: EmbeddingsClient):
    batch = SAMPLE_TEXTS[: settings.BATCH_SIZE]
    data, elapsed = tei.embed(batch)
    assert len(data["data"]) == len(batch)
    idxs = sorted(item["index"] for item in data["data"])
    assert idxs == list(range(len(batch)))
    for item in data["data"]:
        assert len(item["embedding"]) == settings.TEI_NATIVE_DIM
    assert elapsed < settings.TIMEOUT


@pytest.mark.batch
def test_tei_large_batch_vs_singles_similarity(tei: EmbeddingsClient):
    texts = SAMPLE_TEXTS[:6]
    batch, _ = tei.embed(texts)
    singles = [tei.embed(t)[0]["data"][0]["embedding"] for t in texts]
    for i, item in enumerate(sorted(batch["data"], key=lambda x: x["index"])):
        sim = cosine(item["embedding"], singles[i])
        assert sim > 0.999, f"index {i} batch vs single cosine={sim}"


@pytest.mark.parametrize("dim", [256, 512])
def test_tei_dimensions_truncate(tei: EmbeddingsClient, dim: int):
    data, _ = tei.embed("truncate me", dimensions=dim)
    assert len(data["data"][0]["embedding"]) == dim


def test_tei_semantic_relatedness(tei: EmbeddingsClient):
    a, _ = tei.embed("cat sleeping on a windowsill")
    b, _ = tei.embed("kitten resting near the window")
    c, _ = tei.embed("stock market volatility this quarter")
    va, vb, vc = (x["data"][0]["embedding"] for x in (a, b, c))
    assert cosine(va, vb) > cosine(va, vc)
