"""Optional Bearer auth for OpenAI-compatible servers (e.g. Strata).

Set QUALBENCH_API_KEY (preferred) or OPENAI_API_KEY in the environment.
When unset, requests stay unauthenticated (FreeToken default).
"""
from __future__ import annotations

import os


def auth_headers() -> dict[str, str]:
    key = os.environ.get("QUALBENCH_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        return {}
    return {"Authorization": f"Bearer {key}"}
