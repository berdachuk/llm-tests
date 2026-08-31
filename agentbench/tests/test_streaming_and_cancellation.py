"""Streaming and mid-generation cancellation tests.

Every agent CLI streams tokens as they arrive, and every agent CLI must
survive the user hitting Ctrl-C mid-generation without leaving the server in
a bad state (leaked generation slot, engine hang, next request stuck behind
a phantom in-flight request). This is exactly what
`freetoken.server: state.stream_with_cancellation` is meant to guarantee.
"""

from __future__ import annotations

import time

import pytest

from agentbench.client import AgentBenchClient

pytestmark = pytest.mark.streaming


class TestStreamingProducesIncrementalContent:
    # NOTE: reasoning_effort="none" is used here deliberately -- these tests
    # check SSE wire-format mechanics (multiple chunks, correct event types,
    # correct terminal frames), not reasoning quality. At the default
    # (medium) reasoning effort, this checkpoint can spend the entire
    # max_tokens budget deliberating over a trivial counting task before any
    # visible content streams out, which would make these tests flaky for a
    # reason unrelated to what they're actually testing.
    def test_chat_completions_stream_has_multiple_chunks(self, client: AgentBenchClient):
        result = client.chat_completions(
            messages=[{"role": "user", "content": "Count from one to twenty, one number per line."}],
            max_tokens=300,
            stream=True,
            reasoning_effort="none",
        )
        assert result.content.strip(), f"stream_events={result.stream_events!r}"
        assert len(result.stream_events) > 1, "expected multiple SSE chunks for a non-trivial generation"
        assert "done" in result.stream_events, "OpenAI stream must terminate with a [DONE] frame"

    def test_responses_stream_has_delta_events(self, client: AgentBenchClient):
        result = client.responses(
            input_items="Count from one to twenty, one number per line.",
            max_output_tokens=300,
            stream=True,
            reasoning={"effort": "none"},
        )
        assert result.content.strip(), f"stream_events={result.stream_events!r}"
        assert "response.output_text.delta" in result.stream_events
        assert "response.completed" in result.stream_events

    def test_anthropic_stream_has_content_block_events(self, client: AgentBenchClient):
        result = client.messages(
            messages=[{"role": "user", "content": "Count from one to twenty, one number per line."}],
            max_tokens=300,
            stream=True,
            thinking={"type": "disabled"},
        )
        assert result.content.strip(), f"stream_events={result.stream_events!r}"
        assert "content_block_start" in result.stream_events
        assert "content_block_delta" in result.stream_events
        assert "message_delta" in result.stream_events


class TestMidStreamToolCallStreaming:
    def test_anthropic_stream_reconstructs_tool_use_input_json(self, client: AgentBenchClient):
        tool = {
            "name": "read_file",
            "description": "Read a file",
            "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        }
        result = client.messages(
            messages=[{"role": "user", "content": "Read the file at /etc/hostname"}],
            tools=[tool],
            max_tokens=200,
            stream=True,
        )
        assert result.tool_calls, "no tool_use block reconstructed from anthropic stream"
        args = result.tool_calls[0].parsed_arguments()
        assert "path" in args


class TestCancellationDoesNotWedgeServer:
    """Open a streaming request, forcibly close the connection after a
    couple of events (simulating Ctrl-C in an agent CLI), then immediately
    verify the server is still healthy and can serve a fresh request. If
    cancellation leaks the generation slot, this second request will hang
    or time out."""

    def test_cancel_chat_completions_stream_then_new_request_succeeds(self, client: AgentBenchClient, agent_url, agent_model):
        payload = {
            "model": agent_model,
            "messages": [{"role": "user", "content": "Write a very long, detailed 2000-word essay about distributed systems."}],
            "stream": True,
            "max_tokens": 1000,
        }
        seen = client.stream_and_cancel("/v1/chat/completions", payload, after_events=2)
        assert seen >= 1

        # Give the server a brief moment to reap the cancelled generation
        # slot before asserting it's healthy again. reasoning_effort="none"
        # keeps this a fast, deterministic health check rather than a
        # reasoning-budget test.
        time.sleep(1.0)
        result = client.chat_completions(
            messages=[{"role": "user", "content": "Reply with exactly: pong"}],
            max_tokens=50,
            reasoning_effort="none",
        )
        assert result.content.strip(), (
            f"server did not recover after a cancelled streaming request "
            f"(reasoning_content={result.reasoning_content!r})"
        )

    def test_cancel_anthropic_stream_then_new_request_succeeds(self, client: AgentBenchClient, agent_url, agent_model):
        payload = {
            "model": agent_model,
            "messages": [{"role": "user", "content": "Write a very long, detailed 2000-word essay about distributed systems."}],
            "stream": True,
            "max_tokens": 1000,
        }
        seen = client.stream_and_cancel("/v1/messages", payload, after_events=2)
        assert seen >= 1

        time.sleep(1.0)
        result = client.messages(
            messages=[{"role": "user", "content": "Reply with exactly: pong"}],
            max_tokens=50,
            thinking={"type": "disabled"},
        )
        assert result.content.strip(), (
            f"server did not recover after a cancelled anthropic stream "
            f"(reasoning_content={result.reasoning_content!r})"
        )

    def test_cancel_responses_stream_then_new_request_succeeds(self, client: AgentBenchClient, agent_url, agent_model):
        payload = {
            "model": agent_model,
            "input": "Write a very long, detailed 2000-word essay about distributed systems.",
            "stream": True,
            "max_output_tokens": 1000,
        }
        seen = client.stream_and_cancel("/v1/responses", payload, after_events=2)
        assert seen >= 1

        time.sleep(1.0)
        result = client.responses(
            input_items="Reply with exactly: pong",
            max_output_tokens=50,
            reasoning={"effort": "none"},
        )
        assert result.content.strip(), (
            f"server did not recover after a cancelled responses stream "
            f"(reasoning_content={result.reasoning_content!r})"
        )
