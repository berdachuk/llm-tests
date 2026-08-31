"""Centralized, environment-variable-driven configuration for the agentbench
suite.

Every value that describes *which server/model to hit* or *how that server
is configured* (context window, concurrency limit, reasoning-budget-aware
token defaults, etc.) lives here instead of being hardcoded inside test
files. This lets the exact same test suite be pointed at a different
FreeToken-compatible server, a different model, or a differently-tuned
deployment (bigger/smaller --max-running-requests, different
--kv-reserve-tokens, a less verbose checkpoint, ...) purely via environment
variables or a local `.env` file -- no code edits required.

See `.env.sample` in the repo root for a documented list of every variable
below, and README.md for setup instructions.
"""

from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Minimal, dependency-free `.env` loader.

    Supports simple `KEY=VALUE` lines and `#` comments. Does not perform
    variable expansion or multi-line values. Never overrides a variable that
    is already set in the real environment (so `FOO=x pytest ...` on the
    command line always wins over `.env`).
    """
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


# Repo root is one level up from this file (agentbench/settings.py -> repo/).
_REPO_ROOT = Path(__file__).resolve().parents[1]
_load_dotenv(_REPO_ROOT / ".env")


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Server connection
# ---------------------------------------------------------------------------
#: Base URL of the FreeToken (or other OpenAI/Anthropic-compatible) server
#: under test. Defaults to a local server; override for a LAN/remote box.
DEFAULT_URL = _env_str("AGENTBENCH_URL", "http://localhost:8000")

#: Model id to request. Must match an id the target server actually serves
#: (verify with `curl $AGENTBENCH_URL/v1/models`).
DEFAULT_MODEL = _env_str("AGENTBENCH_MODEL", "qwen3.6-35b-a3b")

#: Per-request timeout (seconds) for normal test calls. Large-context /
#: slow tests can legitimately take minutes on a big model.
DEFAULT_TIMEOUT = _env_float("AGENTBENCH_TIMEOUT", 300.0)

#: Timeout (seconds) for quick, small raw-`requests` calls in tests that
#: don't go through AgentBenchClient (health checks, malformed-request
#: checks, token counting).
SHORT_TIMEOUT = _env_float("AGENTBENCH_SHORT_TIMEOUT", 30.0)

# ---------------------------------------------------------------------------
# Run-mode toggles (opt-in test categories)
# ---------------------------------------------------------------------------
#: Also honored as CLI flags (`--run-slow` / `--run-concurrency`); the CLI
#: flag always wins if passed. Env vars let CI configs enable these without
#: editing the pytest invocation.
RUN_SLOW_ENV = _env_flag("AGENTBENCH_RUN_SLOW")
RUN_CONCURRENCY_ENV = _env_flag("AGENTBENCH_RUN_CONCURRENCY")

# ---------------------------------------------------------------------------
# Server capability thresholds
# ---------------------------------------------------------------------------
#: Regression guard floor for `/v1/models`' advertised `max_model_len` --
#: catches a misconfigured context-window override silently truncating it.
MIN_CONTEXT_TOKENS = _env_int("AGENTBENCH_MIN_CONTEXT_TOKENS", 32_000)

#: The context window the server is *expected* to be configured for end to
#: end (used by the large-context needle-retrieval tests as their target).
ADVERTISED_CONTEXT_WINDOW = _env_int("AGENTBENCH_CONTEXT_WINDOW", 262_144)

#: Must match the server's actual `--max-running-requests` (or equivalent
#: admission-control limit) for the over-capacity concurrency test to be
#: testing the right boundary.
MAX_RUNNING_REQUESTS = _env_int("AGENTBENCH_MAX_RUNNING_REQUESTS", 4)

#: How many concurrent requests the over-capacity test fires -- deliberately
#: greater than MAX_RUNNING_REQUESTS so some must queue behind admission
#: control. Defaults to 2x the limit; override directly if needed.
OVER_CAPACITY_REQUEST_COUNT = _env_int(
    "AGENTBENCH_OVER_CAPACITY_REQUESTS", MAX_RUNNING_REQUESTS * 2
)

# ---------------------------------------------------------------------------
# Reasoning-budget-aware max_tokens defaults
# ---------------------------------------------------------------------------
# NOTE: these are not arbitrary magic numbers. Many checkpoints default to a
# non-trivial ("medium") reasoning effort whenever a request doesn't
# explicitly disable thinking, and can spend 100-200+ tokens deliberating
# before emitting any visible content. A too-small max_tokens budget gets
# entirely consumed by that natural reasoning -- which is real, observed
# model behavior, not a bug to paper over -- so tests that aren't
# specifically probing truncation use a budget realistic for an actual agent
# request instead of an artificially tiny one. If you point this suite at a
# less (or more) verbose model/checkpoint, raise or lower these via env var
# rather than editing test files.
BASIC_MAX_TOKENS = _env_int("AGENTBENCH_BASIC_MAX_TOKENS", 300)
GENEROUS_MAX_TOKENS = _env_int("AGENTBENCH_GENEROUS_MAX_TOKENS", 400)

# ---------------------------------------------------------------------------
# Large-context test sizing
# ---------------------------------------------------------------------------
LARGE_CONTEXT_SMALL_TOKENS = _env_int("AGENTBENCH_LARGE_CONTEXT_SMALL_TOKENS", 60_000)
LARGE_CONTEXT_LARGE_TOKENS = _env_int("AGENTBENCH_LARGE_CONTEXT_LARGE_TOKENS", 200_000)

# ---------------------------------------------------------------------------
# Chat-template installation checks (test_chat_template.py)
# ---------------------------------------------------------------------------
#: Optional path to a local `chat_template.jinja` (or a model directory
#: containing one) to run the offline template-version checks against. Left
#: unset by default; those tests skip cleanly when it's not provided, since
#: the canonical copy typically lives on the remote server's filesystem, not
#: this suite's.
TEMPLATE_PATH = os.environ.get("AGENTBENCH_TEMPLATE_PATH")

#: Minimum acceptable major version of the froggeric-patched chat template.
MIN_TEMPLATE_MAJOR_VERSION = _env_int("AGENTBENCH_MIN_TEMPLATE_VERSION", 22)
