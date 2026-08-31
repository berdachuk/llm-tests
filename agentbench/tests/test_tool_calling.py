"""Tool-calling tests -- the single highest-risk area for coding agents.

Qwen3.6-35B-A3B was trained on the native XML tool-call format
(`<tool_call><function=name><parameter=k>v</parameter></function></tool_call>`),
parsed server-side by FreeToken's `Qwen3CoderDetector`. The froggeric v22.4
chat_template fixes several bugs in the *official* Qwen template in this
exact area:

  * Crashes on serialized-JSON-string tool arguments (what every OpenAI-
    compatible client, including OpenCode/Cursor/Codex-via-proxy, sends when
    replaying assistant history).
  * Token misalignment between consecutive <tool_call> blocks in a single
    turn (parallel tool calls), which desyncs the KV-cache prefix.
  * "Stuck repeating the same failing tool call" -- the two-tier error
    escalation is specifically meant to break this loop.
  * False-positive "error" detection on tool results that legitimately
    contain the word "error" (e.g. grep output, `throw new Error(...)`,
    `console.error`) which otherwise triggers bogus retry storms.

These tests exercise the model with real tool schemas an agent would send
and validate the *parsed* tool_calls coming back out on all three protocols.
"""

from __future__ import annotations

import json

import pytest

from agentbench.client import AgentBenchClient

pytestmark = pytest.mark.tool_calling

READ_FILE_TOOL_OPENAI = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read the contents of a file at the given path.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "File path to read"}},
            "required": ["path"],
        },
    },
}

LIST_FILES_TOOL_OPENAI = {
    "type": "function",
    "function": {
        "name": "list_files",
        "description": "List files in a directory.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
}

RUN_COMMAND_TOOL_OPENAI = {
    "type": "function",
    "function": {
        "name": "run_command",
        "description": "Run a shell command and return its output.",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
}


def _as_anthropic_tool(openai_tool: dict) -> dict:
    fn = openai_tool["function"]
    return {"name": fn["name"], "description": fn.get("description", ""), "input_schema": fn["parameters"]}


class TestSingleToolCallOpenAI:
    def test_model_calls_the_only_available_tool(self, client: AgentBenchClient):
        result = client.chat_completions(
            messages=[{"role": "user", "content": "Please read the file located at /etc/hostname"}],
            tools=[READ_FILE_TOOL_OPENAI],
            max_tokens=200,
        )
        assert result.tool_calls, f"model did not call any tool; content={result.content!r}"
        call = result.tool_calls[0]
        assert call.name == "read_file"
        args = call.parsed_arguments()
        assert "path" in args
        assert "hostname" in args["path"]

    def test_tool_call_id_is_present_and_stable_for_response_matching(self, client: AgentBenchClient):
        result = client.chat_completions(
            messages=[{"role": "user", "content": "List files in /tmp"}],
            tools=[LIST_FILES_TOOL_OPENAI],
            max_tokens=200,
        )
        assert result.tool_calls
        assert result.tool_calls[0].id, "tool_call.id must be non-empty for the agent to match a tool result to it"


class TestSingleToolCallStreaming:
    def test_streamed_tool_call_arguments_reassemble_to_valid_json(self, client: AgentBenchClient):
        result = client.chat_completions(
            messages=[{"role": "user", "content": "Read the file at /var/log/syslog"}],
            tools=[READ_FILE_TOOL_OPENAI],
            max_tokens=200,
            stream=True,
        )
        assert result.tool_calls, "no tool call reconstructed from stream"
        call = result.tool_calls[0]
        args = call.parsed_arguments()  # raises if fragments didn't reassemble to valid JSON
        assert "path" in args


class TestToolChoiceForcing:
    @pytest.mark.xfail(
        reason=(
            "CONFIRMED SERVER BUG (2026-08-31, freetoken openai_api.py): "
            "`tool_choice='required'` is accepted by the request schema "
            "(api_models.py ChatCompletionRequest.tool_choice: Literal['none','auto','required']) "
            "but there is no server-side code path that actually enforces it -- "
            "`_should_parse_tools()` only special-cases 'none' (disables tool parsing "
            "entirely) and `ToolChoiceObject` (filters `_tools_for_template` down to the "
            "named function), never 'required'. FreeToken has no constrained/guided "
            "decoding (openai_api.py:_response_format_unsupported comment confirms this "
            "explicitly for response_format, and the same limitation applies here), so "
            "there is no mechanism to force the model to emit a tool call at all -- "
            "'required' silently behaves identically to 'auto'. Reproduced here with a "
            "greeting message that gives the model no reason to call a tool: it replies "
            "with plain text instead of being forced into a call. Any agent harness that "
            "relies on tool_choice='required' to guarantee a structured action (rather "
            "than free text) will get a plain-text response instead in this scenario."
        ),
        strict=True,
    )
    def test_tool_choice_required_forces_a_call(self, client: AgentBenchClient):
        result = client.chat_completions(
            messages=[{"role": "user", "content": "hello"}],
            tools=[LIST_FILES_TOOL_OPENAI],
            tool_choice="required",
            max_tokens=200,
        )
        assert result.tool_calls, (
            f"tool_choice='required' did not force a tool call; content={result.content!r}"
        )


class TestMultiTurnToolRoundTrip:
    """The core agentic loop: user asks -> model calls tool -> harness
    executes -> harness sends tool result back -> model answers using it.
    This is exactly what OpenCode/Cursor/Claude Code/Codex do on every step."""

    def test_full_round_trip_openai(self, client: AgentBenchClient):
        first = client.chat_completions(
            messages=[{"role": "user", "content": "What is the hostname of this machine? Use the read_file tool on /etc/hostname."}],
            tools=[READ_FILE_TOOL_OPENAI],
            max_tokens=200,
        )
        assert first.tool_calls
        call = first.tool_calls[0]
        messages = [
            {"role": "user", "content": "What is the hostname of this machine? Use the read_file tool on /etc/hostname."},
            {
                "role": "assistant",
                "content": first.content or None,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.name, "arguments": call.arguments},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": call.id, "content": "gpu-server-01"},
        ]
        second = client.chat_completions(messages=messages, max_tokens=200)
        assert "gpu-server-01" in second.content, (
            f"model did not use the tool result in its final answer: {second.content!r}"
        )

    def test_full_round_trip_anthropic(self, client: AgentBenchClient):
        tool = _as_anthropic_tool(READ_FILE_TOOL_OPENAI)
        first = client.messages(
            messages=[{"role": "user", "content": "Use the read_file tool to read /etc/hostname, then tell me the hostname."}],
            tools=[tool],
            max_tokens=200,
        )
        assert first.tool_calls, f"no tool_use block; content={first.content!r}"
        call = first.tool_calls[0]
        messages = [
            {"role": "user", "content": "Use the read_file tool to read /etc/hostname, then tell me the hostname."},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": call.id, "name": call.name, "input": call.parsed_arguments()}
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": call.id, "content": "gpu-server-01"}
                ],
            },
        ]
        second = client.messages(messages=messages, tools=[tool], max_tokens=200)
        assert "gpu-server-01" in second.content

    def test_full_round_trip_responses(self, client: AgentBenchClient):
        tool = {
            "type": "function",
            "name": "read_file",
            "description": "Read a file",
            "parameters": READ_FILE_TOOL_OPENAI["function"]["parameters"],
        }
        first = client.responses(
            input_items="Use the read_file tool to read /etc/hostname, then tell me the hostname.",
            tools=[tool],
            max_output_tokens=200,
        )
        assert first.tool_calls, f"no function_call item; content={first.content!r}"
        call = first.tool_calls[0]
        input_items = [
            {"role": "user", "content": "Use the read_file tool to read /etc/hostname, then tell me the hostname."},
            {"type": "function_call", "call_id": call.id, "name": call.name, "arguments": call.arguments},
            {"type": "function_call_output", "call_id": call.id, "output": "gpu-server-01"},
        ]
        second = client.responses(input_items=input_items, tools=[tool], max_output_tokens=200)
        assert "gpu-server-01" in second.content


class TestParallelToolCalls:
    """froggeric v22.4's changelog item #1 specifically targets token
    alignment between *consecutive* <tool_call> blocks in one turn. If this
    regresses, a model asked to use two independent tools in one turn either
    merges/corrupts the calls or drops the second one."""

    def test_model_can_request_two_independent_tools(self, client: AgentBenchClient):
        result = client.chat_completions(
            messages=[{
                "role": "user",
                "content": (
                    "I need two things done in this turn: (1) read the file /etc/hostname, "
                    "and (2) separately list files in /tmp. Call both tools."
                ),
            }],
            tools=[READ_FILE_TOOL_OPENAI, LIST_FILES_TOOL_OPENAI],
            max_tokens=400,
        )
        names = {c.name for c in result.tool_calls}
        # Not all models will always call both in one turn -- but if it calls
        # any, each call must be independently well-formed JSON with the
        # right tool name, i.e. no cross-contamination between the two calls.
        assert names, f"no tool calls at all: {result.content!r}"
        for call in result.tool_calls:
            args = call.parsed_arguments()
            assert isinstance(args, dict)
            if call.name == "read_file":
                assert "path" in args
            elif call.name == "list_files":
                assert "path" in args


class TestMalformedHistoryReplay:
    """An OpenAI-compatible harness (OpenCode, Cursor, generic proxies) may
    replay tool arguments as a JSON *string* (the literal wire format) rather
    than a dict when reconstructing history. The official Qwen template
    crashes here; froggeric v22.4 explicitly fixes it ('Universal Tool
    Argument Handling')."""

    def test_history_with_stringified_tool_arguments_does_not_error(self, client: AgentBenchClient):
        messages = [
            {"role": "user", "content": "Read /etc/hostname for me."},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_abc123",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": json.dumps({"path": "/etc/hostname"})},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_abc123", "content": "gpu-server-01"},
            {"role": "user", "content": "Thanks -- now what was that hostname again?"},
        ]
        result = client.chat_completions(messages=messages, tools=[READ_FILE_TOOL_OPENAI], max_tokens=100)
        assert "gpu-server-01" in result.content


class TestErrorLikeToolResultsDoNotConfuseModel:
    """Regression test for froggeric's 'Smart False-Positive Detection':
    tool output containing the substring 'error' in a clearly successful,
    structural, non-error context (grep/code search results) must not make
    the model treat the turn as failed and retry the same call forever."""

    def test_grep_style_result_with_word_error_is_treated_as_success(self, client: AgentBenchClient):
        # NOTE: the user question must already be fully answerable from the
        # single tool result, and must NOT itself invite further searching
        # ("search for X, then summarize" legitimately encourages a thorough
        # agent to broaden its search -- that's correct behavior, not a false-
        # positive-error retry, and an earlier version of this test conflated
        # the two). Here the question is narrow and closed so any further
        # tool call would only be explained by mistaking "error" text for
        # failure.
        messages = [
            {"role": "user", "content": "Run `grep -rn 'catch' src/` with run_command and tell me how many matching lines it found."},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_grep1",
                        "type": "function",
                        "function": {"name": "run_command", "arguments": json.dumps({"command": "grep -rn 'catch' src/"})},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_grep1",
                "content": (
                    "src/handlers.js:42:  } catch (err) {\n"
                    "src/handlers.js:43:    console.error('failed to process request', err);\n"
                    "src/utils.js:10:  } catch (e) {\n"
                    "src/utils.js:55:  } catch (error) {\n"
                ),
            },
        ]
        result = client.chat_completions(messages=messages, tools=[RUN_COMMAND_TOOL_OPENAI], max_tokens=500)
        # The model should synthesize an answer, not re-issue the identical
        # tool call because it thinks the previous one "failed".
        assert not result.tool_calls, (
            f"model re-issued a tool call instead of answering from a successful "
            f"grep result that merely contained the word 'error'; "
            f"tool_calls={result.tool_calls!r}"
        )
        assert result.content.strip(), (
            f"finish_reason={result.finish_reason!r} reasoning_content={result.reasoning_content!r}"
        )
        assert "4" in result.content


class TestRepeatedFailingToolCallDoesNotStall:
    """froggeric's 'Two-Tier Agentic Error Escalation': after a tool call
    genuinely fails validation/execution twice in a row, the model must
    change approach rather than looping forever on the identical call. We
    can't force the model to invent a *correct* second call, but we can
    assert it doesn't just silently stop responding (empty content, no tool
    call, no acknowledgment) -- the "fatal agentic stalling" failure mode."""

    def test_second_consecutive_failure_produces_a_response(self, client: AgentBenchClient):
        messages = [
            {"role": "user", "content": "Read the config file to check the timeout setting."},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": json.dumps({"path": "/etc/nonexistent_config.yaml"})},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "Error: No such file or directory: /etc/nonexistent_config.yaml"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": json.dumps({"path": "/etc/nonexistent_config.yaml"})},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_2", "content": "Error: No such file or directory: /etc/nonexistent_config.yaml"},
        ]
        result = client.chat_completions(messages=messages, tools=[READ_FILE_TOOL_OPENAI], max_tokens=250)
        stalled = not result.content.strip() and not result.tool_calls
        assert not stalled, "model produced neither text nor a (new) tool call after two consecutive failures -- agentic stall"
