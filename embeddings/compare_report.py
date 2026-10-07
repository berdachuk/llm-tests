#!/usr/bin/env python3
"""Run comparative probes against TEI :8004 and EmbeddingGemma-2 :8005.

Writes a markdown report under embeddings/results/.
"""

from __future__ import annotations

import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from embeddings import settings
from embeddings.client import (
    TINY_PNG_DATA_URL,
    EmbeddingsClient,
    cosine,
    l2_norm,
)
from embeddings.conftest import SAMPLE_TEXTS

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _bench_batch(client: EmbeddingsClient, texts: list[str], repeats: int = 3) -> dict[str, Any]:
    times: list[float] = []
    last: dict[str, Any] | None = None
    for _ in range(repeats):
        last, elapsed = client.embed(texts)
        times.append(elapsed)
    assert last is not None
    dim = len(last["data"][0]["embedding"])
    return {
        "n": len(texts),
        "dim": dim,
        "latency_s_mean": statistics.mean(times),
        "latency_s_stdev": statistics.pstdev(times) if len(times) > 1 else 0.0,
        "items_per_s": len(texts) / statistics.mean(times),
        "l2_norm_mean": statistics.mean(l2_norm(d["embedding"]) for d in last["data"]),
    }


def _semantic(client: EmbeddingsClient) -> dict[str, float]:
    pairs = [
        ("cat sleeping on a windowsill", "kitten resting near the window", "related"),
        ("cat sleeping on a windowsill", "stock market volatility", "unrelated"),
        ("ocean waves at sunset", "море на закате", "cross_lang"),
    ]
    out: dict[str, float] = {}
    for a, b, label in pairs:
        va = client.embed(a)[0]["data"][0]["embedding"]
        vb = client.embed(b)[0]["data"][0]["embedding"]
        out[label] = cosine(va, vb)
    return out


def _formats(client: EmbeddingsClient, *, multimodal: bool) -> dict[str, Any]:
    results: dict[str, Any] = {}
    try:
        data, _ = client.embed("hello")
        results["string"] = {"ok": True, "dim": len(data["data"][0]["embedding"])}
    except Exception as exc:  # noqa: BLE001
        results["string"] = {"ok": False, "error": str(exc)}

    try:
        data, _ = client.embed(["one", "two", "three"])
        results["string_list"] = {"ok": True, "n": len(data["data"])}
    except Exception as exc:  # noqa: BLE001
        results["string_list"] = {"ok": False, "error": str(exc)}

    try:
        data, _ = client.embed("mrl", dimensions=256)
        results["dimensions_256"] = {"ok": True, "dim": len(data["data"][0]["embedding"])}
    except Exception as exc:  # noqa: BLE001
        results["dimensions_256"] = {"ok": False, "error": str(exc)}

    if multimodal:
        try:
            data, _ = client.embed({"image": TINY_PNG_DATA_URL})
            results["image_object"] = {
                "ok": True,
                "dim": len(data["data"][0]["embedding"]),
            }
        except Exception as exc:  # noqa: BLE001
            results["image_object"] = {"ok": False, "error": str(exc)}
        try:
            data, _ = client.embed(
                [
                    "text item",
                    {"image": TINY_PNG_DATA_URL},
                ]
            )
            results["mixed_batch"] = {"ok": True, "n": len(data["data"])}
        except Exception as exc:  # noqa: BLE001
            results["mixed_batch"] = {"ok": False, "error": str(exc)}
        try:
            data, _ = client.embed(
                ["q"],
                prompt_name="SearchQuery",
            )
            results["prompt_name"] = {"ok": True, "dim": len(data["data"][0]["embedding"])}
        except Exception as exc:  # noqa: BLE001
            results["prompt_name"] = {"ok": False, "error": str(exc)}
    else:
        results["image_object"] = {"ok": False, "error": "not supported by TEI text-only"}
        results["mixed_batch"] = {"ok": False, "error": "not supported by TEI text-only"}
        results["prompt_name"] = {"ok": False, "error": "TEI ignores / no ST prompt_name"}

    return results


def _probe_backend(
    name: str,
    client: EmbeddingsClient,
    *,
    multimodal: bool,
    native_dim: int,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    health = client.health()
    info: dict[str, Any] | None = None
    try:
        info = client.info()
    except Exception:  # noqa: BLE001
        info = None
    formats = _formats(client, multimodal=multimodal)
    batch = _bench_batch(client, SAMPLE_TEXTS[: settings.BATCH_SIZE])
    semantic = _semantic(client)
    return {
        "name": name,
        "url": client.base_url,
        "model": client.model,
        "native_dim": native_dim,
        "health_status": health.status_code,
        "info": info,
        "formats": formats,
        "batch": batch,
        "semantic": semantic,
        "probe_s": time.perf_counter() - t0,
    }


def _ok(v: dict[str, Any]) -> str:
    return "yes" if v.get("ok") else "no"


def render_md(tei: dict[str, Any], gemma: dict[str, Any], pytest_rc: int | None) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Embedding backends on `.88` — comparison",
        "",
        f"> Generated: **{now}** by `embeddings/compare_report.py`.",
        "",
        "## Deployment snapshot",
        "",
        "| | TEI Qwen3-Embedding-0.6B | EmbeddingGemma-2 |",
        "|---|---|---|",
        f"| Host | `{tei['url']}` | `{gemma['url']}` |",
        f"| Model | `{tei['model']}` | `{gemma['model']}` |",
        f"| Native dim | {tei['native_dim']} | {gemma['native_dim']} |",
        f"| Health HTTP | {tei['health_status']} | {gemma['health_status']} |",
        f"| Runtime | HuggingFace TEI | SentenceTransformers + FastAPI |",
        f"| Modalities | text | text, image, audio, video |",
        f"| Public text | Bifrost `embedding-88/...` | Bifrost `embedding-gemma2-88/...` |",
        f"| Public MM | — | `llm.avroflex.ru/embedding-gemma2/...` |",
        "",
        "## Input format support",
        "",
        "| Format | TEI :8004 | Gemma :8005 |",
        "|---|---|---|",
        f"| `input: string` | {_ok(tei['formats']['string'])} | {_ok(gemma['formats']['string'])} |",
        f"| `input: string[]` (batch) | {_ok(tei['formats']['string_list'])} | {_ok(gemma['formats']['string_list'])} |",
        f"| `dimensions` (e.g. 256) | {_ok(tei['formats']['dimensions_256'])} | {_ok(gemma['formats']['dimensions_256'])} |",
        f"| `prompt_name` (ST) | {_ok(tei['formats']['prompt_name'])} | {_ok(gemma['formats']['prompt_name'])} |",
        f"| `input: {{image}}` | {_ok(tei['formats']['image_object'])} | {_ok(gemma['formats']['image_object'])} |",
        f"| Mixed text+image batch | {_ok(tei['formats']['mixed_batch'])} | {_ok(gemma['formats']['mixed_batch'])} |",
        "",
        "## Batch latency (n={n}, mean of 3)".format(n=tei["batch"]["n"]),
        "",
        "| Backend | dim | mean s | items/s | mean L2 |",
        "|---|---:|---:|---:|---:|",
        (
            f"| TEI | {tei['batch']['dim']} | {tei['batch']['latency_s_mean']:.3f} | "
            f"{tei['batch']['items_per_s']:.1f} | {tei['batch']['l2_norm_mean']:.4f} |"
        ),
        (
            f"| Gemma | {gemma['batch']['dim']} | {gemma['batch']['latency_s_mean']:.3f} | "
            f"{gemma['batch']['items_per_s']:.1f} | {gemma['batch']['l2_norm_mean']:.4f} |"
        ),
        "",
        "## Semantic cosine (same text pairs)",
        "",
        "| Pair | TEI | Gemma |",
        "|---|---:|---:|",
        f"| related (cat/kitten) | {tei['semantic']['related']:.4f} | {gemma['semantic']['related']:.4f} |",
        f"| unrelated (cat/markets) | {tei['semantic']['unrelated']:.4f} | {gemma['semantic']['unrelated']:.4f} |",
        f"| cross-lang (ocean/море) | {tei['semantic']['cross_lang']:.4f} | {gemma['semantic']['cross_lang']:.4f} |",
        "",
        "## When to use which",
        "",
        "- **TEI Qwen3-Embedding-0.6B (`:8004`)** — default for text RAG / Bifrost "
        "`embedding-88`. Higher native dim (1024), TEI batching, text-only.",
        "- **EmbeddingGemma-2 (`:8005`)** — multimodal (image/audio/video/interleaved), "
        "MRL dims 128/256/512/768, ST `prompt_name`. Text also via Bifrost "
        "`embedding-gemma2-88`; multimodal only via `/embedding-gemma2` path "
        "(llm-88 Bearer).",
        "",
        "## Pytest",
        "",
        "```bash",
        "cd ~/projects-llm-test/llm-tests",
        "pytest embeddings/tests -v",
        "```",
        "",
    ]
    if pytest_rc is not None:
        lines.append(f"Last pytest exit code in this run: **{pytest_rc}**.")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    tei_c = EmbeddingsClient(settings.TEI_URL, settings.TEI_MODEL, settings.TIMEOUT)
    gemma_c = EmbeddingsClient(settings.GEMMA_URL, settings.GEMMA_MODEL, settings.TIMEOUT)
    tei = _probe_backend("tei", tei_c, multimodal=False, native_dim=settings.TEI_NATIVE_DIM)
    gemma = _probe_backend(
        "gemma", gemma_c, multimodal=True, native_dim=settings.GEMMA_NATIVE_DIM
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    payload = {"tei": tei, "gemma": gemma, "generated_at": stamp}
    json_path = RESULTS_DIR / f"compare-{stamp}.json"
    md_path = RESULTS_DIR / f"compare-{stamp}.md"
    latest_md = RESULTS_DIR / "COMPARE_88.md"
    latest_json = RESULTS_DIR / "compare-latest.json"

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")

    # pytest run embedded for the report footer
    import subprocess
    import sys

    rc = subprocess.call(
        [sys.executable, "-m", "pytest", "embeddings/tests", "-q", "--tb=no"],
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    md = render_md(tei, gemma, rc)
    md_path.write_text(md, encoding="utf-8")
    latest_md.write_text(md, encoding="utf-8")
    # Also publish a stable top-level copy for the repo README pointer.
    top = Path(__file__).resolve().parents[1] / "EMBEDDINGS_88_COMPARE.md"
    top.write_text(md, encoding="utf-8")
    print(md_path)
    print(latest_md)
    print(top)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
