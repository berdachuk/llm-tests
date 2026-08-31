"""Pytest configuration for the agent-compatibility test suite.

The suite talks to a *live* FreeToken-compatible server (default:
http://localhost:8000). There is no mocking: these tests exist to catch real
protocol, tool-calling, and chat-template regressions that would break coding
agents (OpenCode, Claude Code, Codex CLI, Cursor) talking to this server.

All configuration lives in `agentbench/settings.py` and is environment-
variable driven (optionally via a local `.env` file -- see `.env.sample` in
the repo root) so the same suite can be pointed at any compatible server
without editing code:

    AGENTBENCH_URL=http://192.168.0.88:8000   pytest agentbench/tests
    AGENTBENCH_MODEL=qwen3.6-35b-a3b
    AGENTBENCH_TIMEOUT=300

See README.md for full setup instructions.
"""

from __future__ import annotations

import pytest

from agentbench import settings
from agentbench.client import AgentBenchClient


def pytest_addoption(parser):
    parser.addoption(
        "--agent-url", action="store", default=None,
        help="Base URL of the server under test (default: $AGENTBENCH_URL or "
             f"{settings.DEFAULT_URL})",
    )
    parser.addoption(
        "--agent-model", action="store", default=None,
        help="Model id to request (default: $AGENTBENCH_MODEL or "
             f"{settings.DEFAULT_MODEL})",
    )
    parser.addoption(
        "--run-slow", action="store_true", default=settings.RUN_SLOW_ENV,
        help="Also run tests marked 'slow' (large context, long generations). "
             "Defaults on if $AGENTBENCH_RUN_SLOW is set.",
    )
    parser.addoption(
        "--run-concurrency", action="store_true", default=settings.RUN_CONCURRENCY_ENV,
        help="Also run tests marked 'concurrency' (multiple parallel requests "
             "against the live server; can be heavy on shared hardware). "
             "Defaults on if $AGENTBENCH_RUN_CONCURRENCY is set.",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: large-context / long-generation tests")
    config.addinivalue_line("markers", "concurrency: multi-request parallelism tests")
    config.addinivalue_line("markers", "streaming: SSE streaming tests")
    config.addinivalue_line("markers", "tool_calling: tool-call wire-format tests")
    config.addinivalue_line("markers", "reasoning: reasoning/thinking extraction tests")
    config.addinivalue_line("markers", "anthropic: Anthropic /v1/messages protocol tests")
    config.addinivalue_line("markers", "responses: OpenAI /v1/responses protocol tests")
    config.addinivalue_line("markers", "openai: OpenAI /v1/chat/completions protocol tests")


def pytest_collection_modifyitems(config, items):
    skip_slow = pytest.mark.skip(reason="need --run-slow to run large-context tests")
    skip_conc = pytest.mark.skip(reason="need --run-concurrency to run parallel-request tests")
    run_slow = config.getoption("--run-slow")
    run_conc = config.getoption("--run-concurrency")
    for item in items:
        if "slow" in item.keywords and not run_slow:
            item.add_marker(skip_slow)
        if "concurrency" in item.keywords and not run_conc:
            item.add_marker(skip_conc)


@pytest.fixture(scope="session")
def agent_url(pytestconfig) -> str:
    return pytestconfig.getoption("--agent-url") or settings.DEFAULT_URL


@pytest.fixture(scope="session")
def agent_model(pytestconfig) -> str:
    return pytestconfig.getoption("--agent-model") or settings.DEFAULT_MODEL


@pytest.fixture(scope="session")
def agent_timeout() -> float:
    return settings.DEFAULT_TIMEOUT


@pytest.fixture(scope="session")
def agent_short_timeout() -> float:
    """Timeout (seconds) for quick raw-`requests` calls that bypass
    AgentBenchClient (health checks, malformed-request checks, etc.)."""
    return settings.SHORT_TIMEOUT


@pytest.fixture(scope="session")
def agent_basic_max_tokens() -> int:
    """max_tokens budget for trivial "is the protocol alive" prompts, sized
    generously enough to survive a checkpoint's default reasoning effort
    without truncating (see settings.py for rationale)."""
    return settings.BASIC_MAX_TOKENS


@pytest.fixture(scope="session")
def agent_generous_max_tokens() -> int:
    """max_tokens budget for content/template-robustness tests that are not
    themselves testing reasoning-token budgets."""
    return settings.GENEROUS_MAX_TOKENS


@pytest.fixture(scope="session")
def agent_min_context_tokens() -> int:
    return settings.MIN_CONTEXT_TOKENS


@pytest.fixture(scope="session")
def agent_context_window() -> int:
    return settings.ADVERTISED_CONTEXT_WINDOW


@pytest.fixture(scope="session")
def agent_max_running_requests() -> int:
    return settings.MAX_RUNNING_REQUESTS


@pytest.fixture(scope="session")
def agent_over_capacity_request_count() -> int:
    return settings.OVER_CAPACITY_REQUEST_COUNT


@pytest.fixture(scope="session")
def agent_large_context_small_tokens() -> int:
    return settings.LARGE_CONTEXT_SMALL_TOKENS


@pytest.fixture(scope="session")
def agent_large_context_large_tokens() -> int:
    return settings.LARGE_CONTEXT_LARGE_TOKENS


@pytest.fixture(scope="session")
def client(agent_url, agent_model, agent_timeout) -> AgentBenchClient:
    return AgentBenchClient(agent_url, agent_model, timeout=agent_timeout)


@pytest.fixture(scope="session", autouse=True)
def _server_reachable(agent_url, client):
    """Fail fast with a clear message if the server is not reachable, instead
    of every single test timing out independently."""
    try:
        client.list_models()
    except Exception as exc:  # noqa: BLE001
        pytest.exit(
            f"FreeToken server at {agent_url} is not reachable ({exc}). "
            f"Start it or pass --agent-url / set AGENTBENCH_URL.",
            returncode=1,
        )
