"""Large-context tests.

Coding agents routinely stuff tens-to-hundreds of thousands of tokens of
repo context, tool output, and multi-file diffs into a single request. These
tests use the existing `gen_256k_prompt.py` generator (a synthetic
multi-module codebase with a needle-in-haystack marker,
`DEEP_CONTEXT_VERIFICATION_TOKEN`) to verify the server:

  1. Actually accepts and serves requests near the advertised 262144-token
     context window (not silently truncating far below it, e.g. due to a
     --kv-reserve-tokens misconfiguration).
  2. Performs basic long-context retrieval (finds the marker) rather than
     just not crashing.

These are marked `slow` (real GPU time on a 35B model) and are opt-in via
`--run-slow` / `AGENTBENCH_RUN_SLOW=1`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # moe_offload_repro/ for gen_256k_prompt
import gen_256k_prompt  # noqa: E402

from agentbench.client import AgentBenchClient  # noqa: E402

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def large_prompt_60k(agent_large_context_small_tokens):
    text, actual_tokens, _ = gen_256k_prompt.build(agent_large_context_small_tokens)
    return text, actual_tokens


@pytest.fixture(scope="module")
def large_prompt_200k(agent_large_context_large_tokens):
    text, actual_tokens, _ = gen_256k_prompt.build(agent_large_context_large_tokens)
    return text, actual_tokens


class TestLargeContextRetrieval:
    # NOTE: reasoning_effort="none" is required here. The generated prompt's
    # task ("exhaustive line-by-line review of a dozen services, ten
    # prioritized issues, changelog...") is elaborate enough that the
    # default (medium) reasoning effort spends the entire max_tokens budget
    # planning the review before emitting a single token of visible
    # content -- that's a reasoning-budget effect, not a needle-retrieval
    # failure. With reasoning off, content starts immediately and the
    # prompt's own instruction ("state the token as the very first line")
    # puts the needle within the first few tokens of output.
    def test_needle_retrieval_at_60k_tokens(self, client: AgentBenchClient, large_prompt_60k):
        text, actual_tokens = large_prompt_60k
        result = client.chat_completions(
            messages=[{"role": "user", "content": text}],
            max_tokens=600,
            reasoning_effort="none",
        )
        assert gen_256k_prompt.MARKER_VALUE in result.content, (
            f"marker not retrieved at ~{actual_tokens} prompt tokens; "
            f"content head: {result.content[:300]!r}; "
            f"reasoning_content head: {result.reasoning_content[:300]!r}"
        )

    def test_needle_retrieval_at_200k_tokens(
        self, client: AgentBenchClient, large_prompt_200k, agent_context_window: int
    ):
        text, actual_tokens = large_prompt_200k
        result = client.chat_completions(
            messages=[{"role": "user", "content": text}],
            max_tokens=600,
            reasoning_effort="none",
        )
        assert gen_256k_prompt.MARKER_VALUE in result.content, (
            f"marker not retrieved at ~{actual_tokens} prompt tokens (near advertised "
            f"{agent_context_window} context) -- check --kv-reserve-tokens / --max-seq-len-override; "
            f"content head: {result.content[:300]!r}; "
            f"reasoning_content head: {result.reasoning_content[:300]!r}"
        )

    def test_large_context_via_responses_api(self, client: AgentBenchClient, large_prompt_60k):
        text, actual_tokens = large_prompt_60k
        result = client.responses(
            input_items=text, max_output_tokens=600, reasoning={"effort": "none"}
        )
        assert gen_256k_prompt.MARKER_VALUE in result.content, (
            f"content head: {result.content[:300]!r}; "
            f"reasoning_content head: {result.reasoning_content[:300]!r}"
        )

    def test_large_context_via_anthropic_messages(self, client: AgentBenchClient, large_prompt_60k):
        text, actual_tokens = large_prompt_60k
        result = client.messages(
            messages=[{"role": "user", "content": text}],
            max_tokens=600,
            thinking={"type": "disabled"},
        )
        assert gen_256k_prompt.MARKER_VALUE in result.content, (
            f"content head: {result.content[:300]!r}; "
            f"reasoning_content head: {result.reasoning_content[:300]!r}"
        )


class TestLargeContextWithToolsPresent:
    """Realistic agent shape: a large amount of pasted/tool-fetched context
    PLUS a tool schema available, to catch template bugs that only surface
    when both a huge prompt and tool definitions are rendered together."""

    def test_large_context_plus_tool_schema_still_completes(self, client: AgentBenchClient, large_prompt_60k):
        text, _ = large_prompt_60k
        tool = {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
            },
        }
        result = client.chat_completions(
            messages=[{"role": "user", "content": text}],
            tools=[tool],
            max_tokens=600,
            reasoning_effort="none",
        )
        assert gen_256k_prompt.MARKER_VALUE in result.content, (
            f"content head: {result.content[:300]!r}; "
            f"reasoning_content head: {result.reasoning_content[:300]!r}"
        )
