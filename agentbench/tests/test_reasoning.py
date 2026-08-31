"""Reasoning / thinking extraction tests.

The froggeric v22.4 chat_template fixes several reasoning-related bugs in the
official Qwen 3.5/3.6/3.8 template that directly affect coding agents:

  * Official template hardcodes/burns tokens on high reasoning effort with no
    content ever generated ("empty content timeout").
  * Official template can prepend duplicate blank <think></think> blocks to
    real thoughts in history (KV-cache-breaking "empty think poisoning").
  * reasoning_content must be split cleanly out of `content` on every
    protocol (OpenAI reasoning_content, Anthropic thinking blocks, Responses
    API reasoning items) -- an agent that sees raw <think> tags leaking into
    the visible answer text will render them to the user or, worse, try to
    parse them as part of a tool call.

These tests are model-behavior tests, not just wire-format tests: they send
real prompts and assert properties of the actual generated text.
"""

from __future__ import annotations

import pytest

from agentbench.client import AgentBenchClient

pytestmark = pytest.mark.reasoning


def _no_leaked_think_tags(text: str) -> bool:
    return "<think>" not in text and "</think>" not in text


class TestReasoningEffortOpenAI:
    def test_reasoning_effort_low_produces_some_content(self, client: AgentBenchClient):
        # NOTE: even "low" effort legitimately spends 100-200+ reasoning tokens
        # on this checkpoint before emitting visible content -- max_tokens must
        # give it room, or this degenerates into testing "did we truncate
        # mid-thought" rather than "did reasoning->content extraction work".
        result = client.chat_completions(
            messages=[{"role": "user", "content": "What is the capital of France?"}],
            max_tokens=300,
            reasoning_effort="low",
        )
        assert result.content.strip(), (
            f"finish_reason={result.finish_reason!r} "
            f"reasoning_content={result.reasoning_content!r}"
        )
        assert _no_leaked_think_tags(result.content)

    def test_reasoning_effort_none_disables_thinking(self, client: AgentBenchClient):
        result = client.chat_completions(
            messages=[{"role": "user", "content": "What is the capital of France?"}],
            max_tokens=100,
            reasoning_effort="none",
        )
        assert result.content.strip()
        # With thinking fully off, reasoning_content should be empty (or at
        # least not contain the model's actual deliberation) and no raw tags
        # should leak into content.
        assert _no_leaked_think_tags(result.content)

    @pytest.mark.parametrize("effort", ["low", "medium", "high", "xhigh"])
    def test_reasoning_effort_levels_do_not_error(self, client: AgentBenchClient, effort: str):
        result = client.chat_completions(
            messages=[{"role": "user", "content": "What is 2 + 2?"}],
            max_tokens=150,
            reasoning_effort=effort,
        )
        assert result.content.strip() or result.reasoning_content.strip(), (
            f"effort={effort} produced neither content nor reasoning_content "
            f"(likely the 'burns tokens with zero content' regression)"
        )


class TestReasoningContentField:
    def test_reasoning_content_separated_from_content_openai(self, client: AgentBenchClient):
        result = client.chat_completions(
            messages=[{"role": "user", "content": "Think step by step: what is 17 * 23?"}],
            max_tokens=500,
        )
        assert _no_leaked_think_tags(result.content)
        # visible answer should contain the final number even if reasoning_content
        # holds the scratch work.
        assert "391" in result.content or "391" in result.reasoning_content

    def test_thinking_block_separated_anthropic(self, client: AgentBenchClient):
        result = client.messages(
            messages=[{"role": "user", "content": "Think step by step: what is 17 * 23?"}],
            max_tokens=500,
        )
        assert _no_leaked_think_tags(result.content)

    def test_reasoning_item_separated_responses(self, client: AgentBenchClient):
        result = client.responses(
            input_items="Think step by step: what is 17 * 23?",
            max_output_tokens=500,
        )
        assert _no_leaked_think_tags(result.content)


class TestNoDuplicateEmptyThinkPoisoning:
    """Regression test for the 'empty think poisoning' bug the froggeric
    template specifically fixes: replaying an assistant turn that already
    contains reasoning back into history must not prepend a second, blank
    <think></think> block ahead of it (which the official template did and
    which caused an 80%+ premature turn-abort rate in agentic loops)."""

    def test_multi_turn_with_prior_reasoning_does_not_stall(self, client: AgentBenchClient):
        # max_tokens=200 was observed too tight even for a trivial arithmetic
        # question at the default (medium) reasoning effort -- the model
        # legitimately used ~150-200 reasoning tokens deliberating before any
        # visible content. Budget generously so this test isolates the
        # poisoning behavior, not the reasoning token budget.
        first = client.chat_completions(
            messages=[{"role": "user", "content": "Think carefully: what is 9 * 9?"}],
            max_tokens=400,
        )
        assert first.content.strip(), (
            f"finish_reason={first.finish_reason!r} "
            f"reasoning_content={first.reasoning_content!r}"
        )

        # Replay the assistant turn (with its reasoning_content, as an agent
        # harness would) and ask a follow-up. If the template double-injects
        # an empty <think></think> ahead of it, the model is prone to abort
        # the *next* turn with empty content.
        messages = [
            {"role": "user", "content": "Think carefully: what is 9 * 9?"},
            {
                "role": "assistant",
                "content": first.content,
                "reasoning_content": first.reasoning_content or None,
            },
            {"role": "user", "content": "Great. Now what is that number plus 1?"},
        ]
        second = client.chat_completions(messages=messages, max_tokens=400)
        assert second.content.strip(), (
            f"empty content on the turn following a replayed reasoning "
            f"message -- possible empty-think-poisoning regression "
            f"(finish_reason={second.finish_reason!r} "
            f"reasoning_content={second.reasoning_content!r})"
        )
        assert "82" in second.content


class TestInlineThinkTags:
    """The froggeric template supports inline <|think_off|> / <|think_low|> /
    <|think_xhigh|> control tags inside chat text itself (useful for agent
    harnesses that can't pass chat_template_kwargs, e.g. simple relay
    proxies). These must be stripped before inference and must not appear
    in the model's visible output."""

    @pytest.mark.parametrize("tag", ["<|think_low|>", "<|think_xhigh|>"])
    def test_inline_tag_is_stripped_and_does_not_error(self, client: AgentBenchClient, tag: str):
        result = client.chat_completions(
            messages=[{"role": "user", "content": f"What is the capital of Spain? {tag}"}],
            max_tokens=300,
        )
        assert result.content.strip(), (
            f"finish_reason={result.finish_reason!r} "
            f"reasoning_content={result.reasoning_content!r}"
        )
        assert tag not in result.content
        assert "think_off" not in result.content
        assert "think_low" not in result.content
        assert "think_xhigh" not in result.content

    @pytest.mark.xfail(
        reason=(
            "CONFIRMED SERVER BUG (2026-08-31, freetoken + froggeric v22.4 template, "
            "reasoning_parser=qwen3): when a request's message text contains the inline "
            "'<|think_off|>' control tag, the froggeric chat_template correctly disables "
            "the <think>...</think> wrapper (the model emits its answer with no think tags "
            "at all -- confirmed by direct template rendering and by raw model output). "
            "However, freetoken's server-side reasoning parser is instantiated with "
            "force_reasoning computed ONLY from chat_template_kwargs.get('enable_thinking') "
            "(see server/generation.py:_make_reasoning_parser, line ~349), which does not "
            "inspect inline '<|think_off|>' tags embedded in message *content*. The parser "
            "is therefore built with force_reasoning=True (thinking assumed on), starts "
            "'inside' a reasoning block, never sees a '</think>' close marker (because the "
            "model never emitted '<think>' to begin with), and so attributes 100% of the "
            "model's visible answer to `reasoning_content` while `content` stays empty. "
            "100% reproducible across multiple prompts/seeds. Root cause: generation.py's "
            "force_reasoning computation and chat_template.jinja's own inline-tag parsing "
            "(chat_template.jinja lines 38-49) are two independent, unsynchronized decisions "
            "about the same thing. Fix needs either (a) the server to also scan request "
            "message content for inline think-control tags before computing force_reasoning, "
            "or (b) the template to stop supporting inline tags and require "
            "chat_template_kwargs.enable_thinking=False instead. Affects any agent/proxy that "
            "relies on the documented inline-tag mechanism instead of chat_template_kwargs."
        ),
        strict=True,
    )
    def test_inline_think_off_tag_content_is_not_swallowed_into_reasoning(
        self, client: AgentBenchClient
    ):
        result = client.chat_completions(
            messages=[{"role": "user", "content": "What is the capital of Spain? <|think_off|>"}],
            max_tokens=300,
        )
        assert result.content.strip(), (
            f"reasoning_content={result.reasoning_content!r} "
            f"(the answer landed here instead of `content`)"
        )
