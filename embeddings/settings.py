"""Environment-driven targets for the two embedding backends on .88."""

from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


_REPO_ROOT = Path(__file__).resolve().parents[1]
_load_dotenv(_REPO_ROOT / ".env")


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


# Qwen3-Embedding-0.6B via HuggingFace TEI
TEI_URL = _env("EMBED_TEI_URL", "http://192.168.0.88:8004").rstrip("/")
TEI_MODEL = _env("EMBED_TEI_MODEL", "Qwen/Qwen3-Embedding-0.6B")
TEI_NATIVE_DIM = _env_int("EMBED_TEI_NATIVE_DIM", 1024)

# google/embeddinggemma-2 via SentenceTransformers FastAPI
GEMMA_URL = _env("EMBED_GEMMA_URL", "http://192.168.0.88:8005").rstrip("/")
GEMMA_MODEL = _env("EMBED_GEMMA_MODEL", "google/embeddinggemma-2")
GEMMA_NATIVE_DIM = _env_int("EMBED_GEMMA_NATIVE_DIM", 768)

TIMEOUT = _env_float("EMBED_TIMEOUT", 120.0)
BATCH_SIZE = _env_int("EMBED_BATCH_SIZE", 8)
MRL_DIMS = (128, 256, 512)
