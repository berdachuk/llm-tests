"""Minimal OpenAI-compatible embeddings HTTP client."""

from __future__ import annotations

import time
from typing import Any

import requests

from embeddings.media_fixtures import PNG_DATA_URL as TINY_PNG_DATA_URL

__all__ = [
    "EmbeddingsClient",
    "TINY_PNG_DATA_URL",
    "cosine",
    "l2_norm",
]


class EmbeddingsClient:
    def __init__(self, base_url: str, model: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.session = requests.Session()

    def health(self) -> requests.Response:
        last = None
        for path in ("/health", "/info"):
            last = self.session.get(
                f"{self.base_url}{path}", timeout=min(30.0, self.timeout)
            )
            if last.status_code < 500:
                return last
        assert last is not None
        return last

    def info(self) -> dict[str, Any]:
        r = self.session.get(f"{self.base_url}/info", timeout=min(30.0, self.timeout))
        r.raise_for_status()
        return r.json()

    def models(self) -> dict[str, Any]:
        r = self.session.get(
            f"{self.base_url}/v1/models", timeout=min(30.0, self.timeout)
        )
        r.raise_for_status()
        return r.json()

    def embed(
        self,
        input_payload: Any,
        *,
        dimensions: int | None = None,
        prompt_name: str | None = None,
        model: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], float]:
        body: dict[str, Any] = {
            "model": model or self.model,
            "input": input_payload,
        }
        if dimensions is not None:
            body["dimensions"] = dimensions
        if prompt_name is not None:
            body["prompt_name"] = prompt_name
        if extra:
            body.update(extra)
        t0 = time.perf_counter()
        r = self.session.post(
            f"{self.base_url}/v1/embeddings",
            json=body,
            timeout=self.timeout,
        )
        elapsed = time.perf_counter() - t0
        r.raise_for_status()
        return r.json(), elapsed


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"dim mismatch {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def l2_norm(vec: list[float]) -> float:
    return sum(x * x for x in vec) ** 0.5
