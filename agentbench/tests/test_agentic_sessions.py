"""End-to-end multi-turn agentic session tests.

These simulate the shape of a real OpenCode/Claude Code/Codex/Cursor session:
several turns deep, mixing system instructions, tool calls, tool results
(including ones that legitimately contain error-looking text), and
reasoning -- all replayed as history on every subsequent request, exactly as
a stateless agent harness does. This is where chat_template KV-cache bugs,
reasoning/tool interaction bugs, and history-rendering bugs actually show up
in practice, as opposed to the more surgical single-behavior tests in
test_tool_calling.py / test_reasoning.py.
"""

from __future__ import annotations

import json

import pytest

from agentbench.client import AgentBenchClient

READ_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read the contents of a file.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
}

WRITE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Write content to a file.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    },
}

RUN_TESTS_TOOL = {
    "type": "function",
    "function": {
        "name": "run_tests",
        "description": "Run the project's test suite.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

SYSTEM_PROMPT = (
    "You are an autonomous coding agent operating in a CLI. You have tools to read files, "
    "write files, and run the test suite. Work step by step: gather information with tools "
    "before making changes, and verify changes by running tests. Be concise in your final "
    "answers to the user."
)


def _tool_call_message(call_id: str, name: str, arguments: dict) -> dict:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}
        ],
    }


def _tool_result_message(call_id: str, content: str) -> dict:
    return {"role": "tool", "tool_call_id": call_id, "content": content}


class TestBugfixWorkflow:
    """A realistic 4-step bugfix loop: read a file, discover a bug, write a
    fix, run tests, report success. Each step replays the full growing
    history, as a real stateless harness would.

    KNOWN RARE FLAKE (observed 2026-08-31, ~1-in-9 across manual repro runs,
    0-in-3 on immediate retry): at step 3 the model has occasionally emitted a
    malformed, non-Qwen3-coder tool-call attempt (e.g. an Anthropic-style
    `<invoke name="run_tests">...</invoke>` snippet) without ever emitting a
    closing `</think>`. Because the reasoning parser's force_reasoning=True
    for this session (thinking is on by default) and no `</think>` ever
    arrives, the *entire* malformed attempt -- which would otherwise still be
    visible in `content` as garbage the harness could react to -- is instead
    swallowed whole into `reasoning_content`, leaving both `content` and
    `tool_calls` empty: a genuine harness-visible stall. This looks like a
    probabilistic model-level tool-syntax hallucination (not a deterministic
    template/parser bug -- retrying the identical request succeeds), but the
    parser behavior it interacts with (attributing an entire unclosed turn to
    reasoning with zero fallback) means any such hallucination is silently
    invisible to the agent instead of surfacing as a recoverable parse error.
    If this test starts failing consistently rather than rarely, treat it as
    a regression."""

    def test_full_bugfix_loop_completes_with_final_summary(self, client: AgentBenchClient):
        tools = [READ_FILE_TOOL, WRITE_FILE_TOOL, RUN_TESTS_TOOL]
        history = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                "There's a bug in src/math_utils.py: the `divide` function doesn't handle "
                "division by zero. Please read the file, fix it, and run the tests to confirm."
            )},
        ]

        # Step 1: expect the model to read the file first.
        step1 = client.chat_completions(messages=history, tools=tools, max_tokens=200)
        assert step1.tool_calls, f"expected a tool call to gather info first; got {step1.content!r}"
        call1 = step1.tool_calls[0]
        history.append(_tool_call_message(call1.id, call1.name, call1.parsed_arguments()))
        history.append(_tool_result_message(call1.id, (
            "def divide(a, b):\n"
            "    return a / b\n"
        )))

        # Step 2: expect the model to now write a fix.
        step2 = client.chat_completions(messages=history, tools=tools, max_tokens=250)
        assert step2.tool_calls, f"expected a write_file/further tool call; got {step2.content!r}"
        call2 = step2.tool_calls[0]
        history.append(_tool_call_message(call2.id, call2.name, call2.parsed_arguments()))
        history.append(_tool_result_message(call2.id, "OK: file written"))

        # Step 3: give it a chance to run tests (may or may not call the tool
        # depending on how it phrased the fix step -- either is acceptable,
        # but it must not stall).
        step3 = client.chat_completions(messages=history, tools=tools, max_tokens=250)
        assert step3.content.strip() or step3.tool_calls, "agent stalled mid-workflow (no content, no tool call)"
        if step3.tool_calls:
            call3 = step3.tool_calls[0]
            history.append(_tool_call_message(call3.id, call3.name, call3.parsed_arguments()))
            history.append(_tool_result_message(call3.id, "All tests passed: 5 passed, 0 failed"))
            step4 = client.chat_completions(messages=history, tools=tools, max_tokens=150)
            assert step4.content.strip(), "agent produced no final summary after tests passed"


class TestErrorRecoveryWorkflow:
    """Tool genuinely fails once (file not found), agent should adapt (e.g.
    list the directory or ask), not repeat the identical call forever nor
    silently stall."""

    def test_recovers_from_a_genuine_tool_error(self, client: AgentBenchClient):
        tools = [READ_FILE_TOOL, WRITE_FILE_TOOL]
        history = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Read src/config.py and tell me the DEBUG flag value."},
        ]
        step1 = client.chat_completions(messages=history, tools=tools, max_tokens=200)
        assert step1.tool_calls
        call1 = step1.tool_calls[0]
        history.append(_tool_call_message(call1.id, call1.name, call1.parsed_arguments()))
        history.append(_tool_result_message(
            call1.id, "Error: [Errno 2] No such file or directory: 'src/config.py'"
        ))

        step2 = client.chat_completions(messages=history, tools=tools, max_tokens=200)
        assert step2.content.strip() or step2.tool_calls, (
            "agent stalled after a genuine file-not-found error"
        )
        if step2.tool_calls:
            # If it retries, the retry should not be byte-identical to the
            # failed call (same tool AND same arguments) -- that would be the
            # "stuck repeating the same failing call" failure mode.
            call2 = step2.tool_calls[0]
            assert not (call2.name == call1.name and call2.arguments == call1.arguments), (
                "agent repeated the identical failing tool call verbatim"
            )


class TestLongMultiToolSession:
    """A longer session (6 turns) mixing multiple tools and a mid-session
    error-looking-but-successful tool result, to stress KV-cache-sensitive
    history rendering over more turns than the other tests exercise."""

    def test_six_turn_session_stays_coherent(self, client: AgentBenchClient):
        tools = [READ_FILE_TOOL, WRITE_FILE_TOOL, RUN_TESTS_TOOL]
        history = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Read src/app.py."},
        ]
        step1 = client.chat_completions(messages=history, tools=tools, max_tokens=250)
        assert step1.tool_calls
        c1 = step1.tool_calls[0]
        history.append(_tool_call_message(c1.id, c1.name, c1.parsed_arguments()))
        history.append(_tool_result_message(c1.id, "import logging\nlogger = logging.getLogger(__name__)\n"))

        history.append({"role": "user", "content": "Now read src/handlers.py too."})
        step2 = client.chat_completions(messages=history, tools=tools, max_tokens=250)
        assert step2.tool_calls
        c2 = step2.tool_calls[0]
        history.append(_tool_call_message(c2.id, c2.name, c2.parsed_arguments()))
        history.append(_tool_result_message(c2.id, (
            "def handle(req):\n    try:\n        return process(req)\n    except Exception as e:\n"
            "        logger.error('handler failed: %s', e)\n        raise\n"
        )))

        history.append({"role": "user", "content": "Based on both files, in one sentence: is there a shared logger?"})
        # NOTE: this step requires the model to reason over both prior tool
        # results before answering -- at the default (medium) reasoning
        # effort that deliberation alone can run 100-150+ tokens, so a small
        # max_tokens here tests "did we truncate mid-thought", not turn
        # coherence. Budget generously.
        step3 = client.chat_completions(messages=history, tools=tools, max_tokens=400)
        assert step3.content.strip(), (
            f"agent lost coherence after 2 tool round-trips "
            f"(finish_reason={step3.finish_reason!r} reasoning_content={step3.reasoning_content!r})"
        )
        assert "logger" in step3.content.lower() or "logging" in step3.content.lower()

        history.append({"role": "assistant", "content": step3.content})
        history.append({"role": "user", "content": "Great, thanks. Now run the tests."})
        step4 = client.chat_completions(messages=history, tools=tools, max_tokens=300)
        assert step4.content.strip() or step4.tool_calls, "agent stalled at turn 4"


class TestReasoningPersistsAcrossToolCalls:
    """When reasoning_effort is elevated, reasoning_content produced before a
    tool call must not corrupt the subsequent tool_call rendering when that
    turn is replayed back as history (both fields on the same assistant
    message)."""

    def test_reasoning_plus_tool_call_replays_cleanly(self, client: AgentBenchClient):
        tools = [READ_FILE_TOOL]
        history = [
            {"role": "user", "content": "Think it through, then read /etc/hostname."},
        ]
        step1 = client.chat_completions(messages=history, tools=tools, max_tokens=300, reasoning_effort="high")
        assert step1.tool_calls, f"expected a tool call; content={step1.content!r}"
        call = step1.tool_calls[0]
        history.append({
            "role": "assistant",
            "content": step1.content or None,
            "reasoning_content": step1.reasoning_content or None,
            "tool_calls": [
                {"id": call.id, "type": "function", "function": {"name": call.name, "arguments": call.arguments}}
            ],
        })
        history.append(_tool_result_message(call.id, "gpu-server-01"))
        history.append({"role": "user", "content": "What was the hostname?"})
        step2 = client.chat_completions(messages=history, max_tokens=250)
        assert "gpu-server-01" in step2.content, (
            "reasoning_content + tool_calls on the same replayed assistant turn broke history rendering"
        )
