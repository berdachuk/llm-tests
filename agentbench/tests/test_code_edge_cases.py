"""Edge cases around the actual *content* coding agents send: large fenced
code blocks, nested backticks/JSON-in-markdown, unicode identifiers, long
system prompts (agent "skills"/instructions files), empty/whitespace-only
messages, and null-ish fields the server must not choke on.

None of these are protocol tests -- they are chat_template / server
robustness tests using payload shapes that are completely ordinary for a
code agent but easy for a Jinja template or a naive JSON serializer to
mishandle (unbalanced backticks, `${...}` template-literal syntax, raw
control characters, etc.).
"""

from __future__ import annotations

import json

import pytest

from agentbench.client import AgentBenchClient, AgentBenchError

# NOTE: Many checkpoints default to a non-trivial ("medium") reasoning
# effort whenever a request doesn't explicitly disable thinking, and
# routinely spend 100-200+ tokens deliberating even on trivial questions
# before emitting any visible content. Every test in this module is about
# content/template robustness, not reasoning budgets, so max_tokens must be
# generous enough that "reasoning consumed the whole budget" never gets
# confused with "the template/server mishandled this payload" -- the actual
# failure mode these tests exist to catch. Size via
# $AGENTBENCH_GENEROUS_MAX_TOKENS (see agent_generous_max_tokens fixture /
# settings.py) for a different model.

LARGE_CODE_BLOCK = """\
```python
import asyncio
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Order:
    id: str
    items: list[str] = field(default_factory=list)
    total: float = 0.0


class OrderService:
    def __init__(self):
        self._orders: dict[str, Order] = {}
        self._lock = asyncio.Lock()

    async def create_order(self, order_id: str, items: list[str]) -> Order:
        async with self._lock:
            if order_id in self._orders:
                raise ValueError(f"duplicate order: {order_id}")
            order = Order(id=order_id, items=items, total=sum(len(i) for i in items))
            self._orders[order_id] = order
            return order

    async def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)
```
"""

NESTED_BACKTICKS_AND_TEMPLATE_LITERALS = """\
Here's a snippet with nested backticks and JS template literals:

```markdown
Run `npm install` then use this in code:
```js
const msg = `Hello ${name}, you have ${count} items (${count > 1 ? 'plural' : 'singular'})`;
console.log(`Result: ${JSON.stringify({a: 1, b: [1,2,3]})}`);
```
```

Also consider this raw JSON-looking string that is NOT actually a tool call:
{"name": "not_a_real_tool_call", "arguments": {"just": "text in the prompt"}}
"""

UNICODE_AND_SPECIAL_CHARS = (
    "Please review this identifier naming: `变量名`, `функция_имя`, `émoji_🚀_var`, "
    "and this control-char-adjacent string: 'tab\\there\\nand\\nnewlines'. "
    "Also: <script>alert('xss')</script> and SQL: SELECT * FROM users WHERE name = 'O''Brien';"
)


class TestLargeCodeBlocks:
    def test_large_fenced_code_block_in_user_message(self, client: AgentBenchClient, agent_generous_max_tokens: int):
        result = client.chat_completions(
            messages=[{
                "role": "user",
                "content": LARGE_CODE_BLOCK + "\n\nIs the create_order method thread-safe? Answer yes or no and why, in one sentence.",
            }],
            max_tokens=agent_generous_max_tokens,
            reasoning_effort="none",
        )
        assert result.content.strip(), (
            f"finish_reason={result.finish_reason!r} reasoning_content={result.reasoning_content!r}"
        )

    def test_nested_backticks_and_template_literals_do_not_break_template(self, client: AgentBenchClient, agent_generous_max_tokens: int):
        result = client.chat_completions(
            messages=[{"role": "user", "content": NESTED_BACKTICKS_AND_TEMPLATE_LITERALS + "\n\nSummarize in one sentence."}],
            max_tokens=agent_generous_max_tokens,
            reasoning_effort="none",
        )
        assert result.content.strip(), (
            f"finish_reason={result.finish_reason!r} reasoning_content={result.reasoning_content!r}"
        )
        # The JSON-looking text in the prompt is NOT a real tool call request
        # (no tools were even passed) -- the model must not hallucinate a
        # tool_calls response for it.
        assert not result.tool_calls

    def test_code_block_containing_literal_tool_call_xml_tags(self, client: AgentBenchClient, agent_generous_max_tokens: int):
        """A user pasting Qwen's own <tool_call> XML syntax as *documentation
        text* (e.g. explaining the format) must not be mistaken by the
        parser for a real model-generated tool call in the prompt itself."""
        content = (
            "Here is the tool call format our old system used, for reference:\n"
            "```xml\n<tool_call>\n<function=old_tool>\n<parameter=x>1</parameter>\n"
            "</function>\n</tool_call>\n```\n"
            "Just acknowledge you've seen this format in one sentence."
        )
        result = client.chat_completions(
            messages=[{"role": "user", "content": content}],
            max_tokens=agent_generous_max_tokens,
            reasoning_effort="none",
        )
        assert result.content.strip(), (
            f"finish_reason={result.finish_reason!r} reasoning_content={result.reasoning_content!r}"
        )


class TestUnicodeAndSpecialCharacters:
    def test_unicode_identifiers_and_special_chars_do_not_error(self, client: AgentBenchClient, agent_generous_max_tokens: int):
        result = client.chat_completions(
            messages=[{"role": "user", "content": UNICODE_AND_SPECIAL_CHARS}],
            max_tokens=agent_generous_max_tokens,
            reasoning_effort="none",
        )
        assert result.content.strip(), (
            f"finish_reason={result.finish_reason!r} reasoning_content={result.reasoning_content!r}"
        )

    def test_emoji_and_rtl_text(self, client: AgentBenchClient, agent_generous_max_tokens: int):
        result = client.chat_completions(
            messages=[{"role": "user", "content": "Translate 'hello 👋 world 🌍' and also handle this RTL text: مرحبا بالعالم. Reply briefly."}],
            max_tokens=agent_generous_max_tokens,
            reasoning_effort="none",
        )
        assert result.content.strip(), (
            f"finish_reason={result.finish_reason!r} reasoning_content={result.reasoning_content!r}"
        )


class TestLongSystemPrompt:
    """Coding agents (OpenCode, Claude Code, Cursor) send substantial system
    prompts (project rules / persona / tool descriptions) on every request.
    Multiple leading system-role turns is a case the froggeric template
    explicitly merges into one block; test both single and multi-part."""

    def test_long_single_system_prompt(self, client: AgentBenchClient, agent_generous_max_tokens: int):
        system_prompt = (
            "You are a senior software engineering assistant embedded in a CLI coding tool. "
            "Follow the user's instructions exactly. Always use the provided tools when file "
            "or shell access is needed. Never fabricate file contents. "
        ) * 30  # a few hundred tokens, representative of a real agent system prompt
        result = client.chat_completions(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Reply with exactly: acknowledged"},
            ],
            max_tokens=agent_generous_max_tokens,
        )
        assert "acknowledged" in result.content.lower(), (
            f"finish_reason={result.finish_reason!r} reasoning_content={result.reasoning_content!r}"
        )

    def test_multiple_leading_system_messages_are_merged_not_rejected(self, client: AgentBenchClient, agent_generous_max_tokens: int):
        result = client.chat_completions(
            messages=[
                {"role": "system", "content": "You are a helpful coding assistant."},
                {"role": "system", "content": "Always answer concisely."},
                {"role": "user", "content": "What is 3 + 4?"},
            ],
            max_tokens=agent_generous_max_tokens,
        )
        assert "7" in result.content, (
            f"finish_reason={result.finish_reason!r} reasoning_content={result.reasoning_content!r}"
        )


class TestEmptyAndNullishInputs:
    def test_empty_user_message_does_not_crash_server(self, client: AgentBenchClient):
        result = client.chat_completions(messages=[{"role": "user", "content": ""}], max_tokens=30)
        # Server must respond (even if with a clarifying question), not 500.
        assert result.finish_reason is not None

    def test_whitespace_only_message(self, client: AgentBenchClient):
        result = client.chat_completions(messages=[{"role": "user", "content": "   \n\t  "}], max_tokens=30)
        assert result.finish_reason is not None

    def test_assistant_message_with_null_content_and_tool_calls_only(self, client: AgentBenchClient, agent_generous_max_tokens: int):
        """This exact shape (content=None, only tool_calls set) is what every
        OpenAI-compatible agent sends for an assistant turn that only called
        a tool -- it must round-trip through history without the template
        crashing on `None`."""
        messages = [
            {"role": "user", "content": "List files in /tmp"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_x",
                        "type": "function",
                        "function": {"name": "list_files", "arguments": json.dumps({"path": "/tmp"})},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_x", "content": "file1.txt\nfile2.txt"},
            {"role": "user", "content": "How many files were there?"},
        ]
        result = client.chat_completions(
            messages=messages,
            tools=[{
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "list files",
                    "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
                },
            }],
            max_tokens=agent_generous_max_tokens,
        )
        assert "2" in result.content, (
            f"finish_reason={result.finish_reason!r} reasoning_content={result.reasoning_content!r}"
        )


class TestMalformedRequests:
    """The server should reject these cleanly (4xx) rather than 500ing or
    hanging -- an agent harness needs a fast, parseable error to retry or
    surface to the user."""

    def test_zero_max_tokens_is_rejected_or_handled(self, client: AgentBenchClient):
        try:
            result = client.chat_completions(
                messages=[{"role": "user", "content": "hi"}], max_tokens=0
            )
            # Some servers clamp to a minimum instead of erroring -- either
            # behavior is acceptable as long as it doesn't hang.
            assert result.finish_reason is not None
        except AgentBenchError:
            pass  # explicit rejection is also fine

    def test_missing_required_field_returns_client_error_not_hang(
        self, client: AgentBenchClient, agent_url, agent_model, agent_short_timeout
    ):
        import requests

        r = requests.post(
            f"{agent_url}/v1/chat/completions",
            json={"model": agent_model},  # missing 'messages'
            timeout=agent_short_timeout,
        )
        assert r.status_code >= 400
        assert r.status_code < 500

    def test_anthropic_missing_max_tokens_rejected_cleanly(self, agent_url, agent_model, agent_short_timeout):
        import requests

        r = requests.post(
            f"{agent_url}/v1/messages",
            json={"model": agent_model, "messages": [{"role": "user", "content": "hi"}]},
            timeout=agent_short_timeout,
        )
        assert r.status_code >= 400
        assert r.status_code < 500
        body = r.json()
        # froggeric-adjacent server behavior: Anthropic-shaped error, not a
        # raw FastAPI 422 {"detail": [...]}
        assert body.get("type") == "error" or "error" in body
