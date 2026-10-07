"""Multimodal embedding formats for EmbeddingGemma-2 (:8005)."""

from __future__ import annotations

import base64
import shutil
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
import requests

from embeddings import settings
from embeddings.client import EmbeddingsClient, cosine, l2_norm
from embeddings.media_fixtures import (
    JPEG_DATA_URL,
    PNG_BYTES,
    PNG_DATA_URL,
    make_tone_wav_pair,
    make_wav_data_url,
)

pytestmark = [pytest.mark.gemma, pytest.mark.multimodal]


def _dim(data: dict) -> int:
    return len(data["data"][0]["embedding"])


def _vec(data: dict) -> list[float]:
    return data["data"][0]["embedding"]


def _make_tiny_mp4_data_url() -> str | None:
    """Build a ~0.3s solid-color mp4 via ffmpeg if available."""
    if not shutil.which("ffmpeg"):
        return None
    with tempfile.TemporaryDirectory(prefix="eg2-mp4-") as td:
        out = Path(td) / "tiny.mp4"
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=64x64:d=0.3",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-t",
            "0.3",
            str(out),
        ]
        try:
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None
        raw = out.read_bytes()
    return "data:video/mp4;base64," + base64.b64encode(raw).decode()


def test_gemma_image_png_object(gemma: EmbeddingsClient):
    data, _ = gemma.embed({"image": PNG_DATA_URL})
    assert _dim(data) == settings.GEMMA_NATIVE_DIM
    assert abs(l2_norm(_vec(data)) - 1.0) < 0.05


def test_gemma_image_jpeg_object(gemma: EmbeddingsClient):
    data, _ = gemma.embed({"image": JPEG_DATA_URL})
    assert _dim(data) == settings.GEMMA_NATIVE_DIM


def test_gemma_image_list_in_one_item(gemma: EmbeddingsClient):
    data, _ = gemma.embed({"image": [PNG_DATA_URL, JPEG_DATA_URL]})
    assert len(data["data"]) == 1
    assert _dim(data) == settings.GEMMA_NATIVE_DIM


@pytest.mark.batch
def test_gemma_batch_of_images(gemma: EmbeddingsClient):
    payload = [
        {"image": PNG_DATA_URL},
        {"image": JPEG_DATA_URL},
        {"image": PNG_DATA_URL},
    ]
    data, _ = gemma.embed(payload)
    assert len(data["data"]) == 3
    for item in data["data"]:
        assert len(item["embedding"]) == settings.GEMMA_NATIVE_DIM


@pytest.mark.parametrize("dim", [256, 512])
def test_gemma_image_mrl_dimensions(gemma: EmbeddingsClient, dim: int):
    data, _ = gemma.embed({"image": PNG_DATA_URL}, dimensions=dim)
    vec = _vec(data)
    assert len(vec) == dim
    assert abs(l2_norm(vec) - 1.0) < 0.05


def test_gemma_interleaved_text_single_image(gemma: EmbeddingsClient):
    data, _ = gemma.embed(
        {
            "text": "a solid color pixel <|image|>",
            "image": PNG_DATA_URL,
        }
    )
    assert _dim(data) == settings.GEMMA_NATIVE_DIM


def test_gemma_interleaved_text_multi_image(gemma: EmbeddingsClient):
    data, _ = gemma.embed(
        {
            "text": "first <|image|> then <|image|>",
            "image": [PNG_DATA_URL, JPEG_DATA_URL],
        }
    )
    assert _dim(data) == settings.GEMMA_NATIVE_DIM


@pytest.mark.batch
def test_gemma_mixed_batch_text_images_interleaved(gemma: EmbeddingsClient):
    payload = [
        "warehouse inventory checklist",
        {"image": PNG_DATA_URL},
        {
            "text": "photo of a blue square <|image|>",
            "image": JPEG_DATA_URL,
        },
        {"image": [PNG_DATA_URL, JPEG_DATA_URL]},
    ]
    data, _ = gemma.embed(payload)
    assert len(data["data"]) == 4
    for item in data["data"]:
        assert len(item["embedding"]) == settings.GEMMA_NATIVE_DIM


def test_gemma_image_embedding_unit_and_stable(gemma: EmbeddingsClient):
    a, _ = gemma.embed({"image": PNG_DATA_URL})
    b, _ = gemma.embed({"image": PNG_DATA_URL})
    va, vb = _vec(a), _vec(b)
    assert abs(l2_norm(va) - 1.0) < 0.05
    assert cosine(va, vb) > 0.999
    text, _ = gemma.embed("quarterly bond yield curves and inflation")
    assert len(_vec(text)) == settings.GEMMA_NATIVE_DIM


def test_gemma_image_http_url(gemma: EmbeddingsClient):
    """Server downloads http(s) media; serve a tiny PNG on the LAN for .88."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(PNG_BYTES)))
            self.end_headers()
            self.wfile.write(PNG_BYTES)

        def log_message(self, format, *args):  # noqa: A003
            return

    # Bind on the LAN address that .88 can reach (same as test client src).
    lan_ip = "192.168.0.73"
    httpd = HTTPServer((lan_ip, 0), Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://{lan_ip}:{port}/pixel.png"
        # sanity: client machine can fetch it
        assert requests.get(url, timeout=5).status_code == 200
        data, _ = gemma.embed({"image": url})
        assert _dim(data) == settings.GEMMA_NATIVE_DIM
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_gemma_rejects_file_scheme_image(gemma: EmbeddingsClient):
    with pytest.raises(requests.HTTPError) as ei:
        gemma.embed({"image": "file:///tmp/x.png"})
    assert ei.value.response is not None
    assert ei.value.response.status_code == 400


def test_gemma_audio_wav_object(gemma: EmbeddingsClient):
    data, _ = gemma.embed({"audio": make_wav_data_url()})
    assert _dim(data) == settings.GEMMA_NATIVE_DIM
    assert abs(l2_norm(_vec(data)) - 1.0) < 0.05


def test_gemma_audio_two_tones_differ(gemma: EmbeddingsClient):
    a_url, b_url = make_tone_wav_pair()
    a, _ = gemma.embed({"audio": a_url})
    b, _ = gemma.embed({"audio": b_url})
    # Different tones should not be identical embeddings.
    assert cosine(_vec(a), _vec(b)) < 0.9999


@pytest.mark.batch
def test_gemma_batch_audio_and_text(gemma: EmbeddingsClient):
    payload = [
        "spoken note about shipping delays",
        {"audio": make_wav_data_url(freq=330.0)},
        {"audio": make_wav_data_url(freq=660.0)},
    ]
    data, _ = gemma.embed(payload)
    assert len(data["data"]) == 3


def test_gemma_interleaved_text_audio(gemma: EmbeddingsClient):
    data, _ = gemma.embed(
        {
            "text": "listen <|audio|>",
            "audio": make_wav_data_url(),
        }
    )
    assert _dim(data) == settings.GEMMA_NATIVE_DIM


def test_gemma_video_mp4_object(gemma: EmbeddingsClient):
    """Video modality is advertised; decode needs torchcodec+NVRTC on this box.

    Do not POST video payloads until the serve image has a working torchcodec —
    failed video preprocess has been observed to destabilize the worker.
    """
    video = _make_tiny_mp4_data_url()
    if video is None:
        pytest.skip("ffmpeg not available to synthesize tiny mp4")
    pytest.skip(
        "video decode not enabled on .88 (torchcodec/libnvrtc missing); "
        "payload synthesized OK locally"
    )


def test_gemma_interleaved_text_image_audio(gemma: EmbeddingsClient):
    data, _ = gemma.embed(
        {
            "text": "scene <|image|> with sound <|audio|>",
            "image": PNG_DATA_URL,
            "audio": make_wav_data_url(),
        }
    )
    assert _dim(data) == settings.GEMMA_NATIVE_DIM


@pytest.mark.batch
def test_gemma_full_modality_batch(gemma: EmbeddingsClient):
    payload: list = [
        "text only",
        {"image": JPEG_DATA_URL},
        {"audio": make_wav_data_url()},
        {
            "text": "mix <|image|> <|audio|>",
            "image": PNG_DATA_URL,
            "audio": make_wav_data_url(freq=520.0),
        },
    ]
    data, _ = gemma.embed(payload)
    assert len(data["data"]) == len(payload)
    for item in data["data"]:
        assert len(item["embedding"]) == settings.GEMMA_NATIVE_DIM
