"""Tiny synthetic media payloads for multimodal embedding tests."""

from __future__ import annotations

import base64
import io
import math
import struct
import wave


def _b64_data_url(mime: str, raw: bytes) -> str:
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


# Valid 1x1 PNG
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)
PNG_DATA_URL = _b64_data_url("image/png", PNG_BYTES)

# Minimal JPEG (1x1) — standard tiny JPEG
JPEG_BYTES = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707"
    "070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c"
    "1c2837292c30313434341f27393d38323c2e333432ffdb0043010909090c0b0c180d"
    "0d1832211c2132323232323232323232323232323232323232323232323232323232"
    "323232323232323232323232323232323232323232323232ffc00011080001000103"
    "011100021101031101ffc40014000100000000000000000000000000000000ffc400"
    "14100100000000000000000000000000000000ffda000c0301000210031000003f00"
    "7fbfc0ffd9"
)
JPEG_DATA_URL = _b64_data_url("image/jpeg", JPEG_BYTES)


def make_wav_data_url(
    *,
    seconds: float = 0.25,
    rate: int = 16000,
    freq: float = 440.0,
) -> str:
    n = max(1, int(seconds * rate))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"".join(
            struct.pack(
                "<h",
                int(12000 * math.sin(2 * math.pi * freq * i / rate)),
            )
            for i in range(n)
        )
        w.writeframes(frames)
    return _b64_data_url("audio/wav", buf.getvalue())


def make_tone_wav_pair() -> tuple[str, str]:
    """Two different tones for audio similarity sanity checks."""
    return make_wav_data_url(freq=220.0), make_wav_data_url(freq=880.0)