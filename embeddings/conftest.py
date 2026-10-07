"""Fixtures for live embedding backend tests."""

from __future__ import annotations

import pytest

from embeddings import settings
from embeddings.client import EmbeddingsClient


def pytest_configure(config):
    config.addinivalue_line("markers", "tei: Qwen3 TEI embedding backend (:8004)")
    config.addinivalue_line(
        "markers", "gemma: EmbeddingGemma-2 multimodal backend (:8005)"
    )
    config.addinivalue_line("markers", "multimodal: image/audio/video input forms")
    config.addinivalue_line("markers", "batch: multi-input embedding requests")


@pytest.fixture(scope="session")
def tei() -> EmbeddingsClient:
    return EmbeddingsClient(
        settings.TEI_URL, settings.TEI_MODEL, timeout=settings.TIMEOUT
    )


@pytest.fixture(scope="session")
def gemma() -> EmbeddingsClient:
    return EmbeddingsClient(
        settings.GEMMA_URL, settings.GEMMA_MODEL, timeout=settings.TIMEOUT
    )


SAMPLE_TEXTS = [
    "ocean waves at sunset",
    "financial quarterly earnings report",
    "python fastapi embedding server",
    "кот спит на подоконнике",
    "machine learning retrieval augmented generation",
    "red sports car on a mountain road",
    "kubernetes ingress traefik bifrost",
    "тихий дождь по крыше вечером",
]
