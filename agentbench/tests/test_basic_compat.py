"""Basic wire-protocol sanity: the server is up, advertises the right model,
and each of the three protocols coding agents speak returns a well-formed,
non-empty response to a trivial request.

These are the tests that should fail LOUDLY and FIRST if the chat_template,
the model, or the server config is broken -- before any of the more nuanced
tool-calling / reasoning / agentic-loop tests even get a chance to run.
"""

from __future__ import annotations

import pytest

from agentbench.client import AgentBenchClient


def test_models_endpoint_lists_target_model(client: AgentBenchClient, agent_model: str):
    data = client.list_models()
    ids = [m["id"] for m in data.get("data", [])]
    assert agent_model in ids, f"expected {agent_model!r} in {ids!r}"


def test_models_endpoint_reports_full_context(
    client: AgentBenchClient, agent_model: str, agent_min_context_tokens: int
):
    data = client.list_models()
    entry = next(m for m in data["data"] if m["id"] == agent_model)
    # Regression guard: catches a misconfigured --max-seq-len-override / kv
    # budget silently truncating the advertised context window.
    assert entry.get("max_model_len", 0) >= agent_min_context_tokens


# NOTE: Trivial "is the protocol alive" prompts still go through the model's
# default reasoning path on checkpoints where `enable_thinking` defaults on.
# A too-small max_tokens budget is entirely consumed by natural reasoning
# tokens before any visible content is emitted -- this is real, observed
# behavior (not a test bug to paper over), so basic sanity tests use a
# budget realistic for an actual agent request (nobody ships max_tokens=20)
# rather than artificially disabling reasoning just to make the assertion
# pass. Size via $AGENTBENCH_BASIC_MAX_TOKENS (see agent_basic_max_tokens
# fixture / settings.py) if a different model needs more/less room.


@pytest.mark.openai
def test_chat_completions_basic(client: AgentBenchClient, agent_basic_max_tokens: int):
    result = client.chat_completions(
        messages=[{"role": "user", "content": "Reply with exactly the word: pong"}],
        max_tokens=agent_basic_max_tokens,
    )
    assert result.content.strip(), (
        f"empty content on a trivial prompt with max_tokens={agent_basic_max_tokens} "
        f"(reasoning_content={result.reasoning_content!r}, finish_reason={result.finish_reason!r})"
    )
    assert result.finish_reason in ("stop", "length")


@pytest.mark.responses
def test_responses_api_basic(client: AgentBenchClient, agent_basic_max_tokens: int):
    result = client.responses(
        input_items="Reply with exactly the word: pong",
        max_output_tokens=agent_basic_max_tokens,
    )
    assert result.content.strip(), (
        f"empty content on a trivial prompt (reasoning_content={result.reasoning_content!r})"
    )


@pytest.mark.anthropic
def test_messages_api_basic(client: AgentBenchClient, agent_basic_max_tokens: int):
    result = client.messages(
        messages=[{"role": "user", "content": "Reply with exactly the word: pong"}],
        max_tokens=agent_basic_max_tokens,
    )
    assert result.content.strip(), (
        f"empty content on a trivial prompt (reasoning_content={result.reasoning_content!r})"
    )
    assert result.finish_reason in ("end_turn", "max_tokens")


@pytest.mark.anthropic
def test_messages_count_tokens(client: AgentBenchClient, agent_url, agent_model, agent_short_timeout):
    import requests

    r = requests.post(
        f"{agent_url}/v1/messages/count_tokens",
        json={
            "model": agent_model,
            "messages": [{"role": "user", "content": "Hello there, how are you?"}],
        },
        timeout=agent_short_timeout,
    )
    r.raise_for_status()
    data = r.json()
    assert data["input_tokens"] > 0


def test_all_three_protocols_agree_on_simple_arithmetic(client: AgentBenchClient):
    """Not a rigorous eval -- just a canary that all three protocols are
    hitting the *same* underlying model/template and not silently routing to
    something else or truncating badly. reasoning_effort='none' is used here
    specifically to keep this a fast, deterministic wire-format canary
    rather than a reasoning-budget test (that's covered separately in
    test_reasoning.py)."""
    prompt = "What is 12 + 7? Answer with only the number."
    oa = client.chat_completions(
        messages=[{"role": "user", "content": prompt}], max_tokens=30, reasoning_effort="none"
    )
    an = client.messages(
        messages=[{"role": "user", "content": prompt}], max_tokens=30, thinking={"type": "disabled"}
    )
    rp = client.responses(input_items=prompt, max_output_tokens=30, reasoning={"effort": "none"})
    for label, result in (("chat_completions", oa), ("messages", an), ("responses", rp)):
        assert "19" in result.content, f"{label} did not answer 19: {result.content!r}"
