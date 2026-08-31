"""Thin HTTP client for the three wire protocols coding agents actually speak
against a FreeToken server:

  * OpenAI Chat Completions  (``/v1/chat/completions``)  -- OpenCode, Cursor, generic
    OpenAI-compatible clients.
  * OpenAI Responses API     (``/v1/responses``)          -- Codex CLI.
  * Anthropic Messages API   (``/v1/messages``)            -- Claude Code.

The goal of this module is NOT to be a full SDK. It is a deliberately small,
dependency-light (``requests`` only) client that exercises the exact request/
response shapes an agent harness would send, including streaming (SSE), so
the test suite in ``agentbench/tests`` can assert on real wire behavior
(tool-call parsing, reasoning extraction, KV-cache-sensitive multi-turn
history, error handling) rather than a mocked abstraction.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

import requests


class AgentBenchError(RuntimeError):
    """Raised for transport-level failures (non-2xx, timeout, malformed SSE)."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string, as sent over the wire (may be malformed)

    def parsed_arguments(self) -> Any:
        return json.loads(self.arguments)


@dataclass
class ChatResult:
    """Normalized result across all three protocols so tests can assert on
    the same shape regardless of which endpoint produced it."""

    content: str = ""
    reasoning_content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: Optional[str] = None
    raw: Any = None
    usage: dict[str, Any] = field(default_factory=dict)
    elapsed_s: float = 0.0
    # Ordered list of SSE event "kinds" as observed on the wire, for streaming
    # calls only. Useful for asserting event ordering / no duplicate finals.
    stream_events: list[str] = field(default_factory=list)


class AgentBenchClient:
    def __init__(self, base_url: str, model: str, timeout: float = 300.0, api_key: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.session = requests.Session()
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self.session.headers.update(headers)

    # ------------------------------------------------------------------
    # Discovery / health
    # ------------------------------------------------------------------
    def list_models(self) -> dict[str, Any]:
        r = self.session.get(f"{self.base_url}/v1/models", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # OpenAI Chat Completions (/v1/chat/completions)
    # ------------------------------------------------------------------
    def chat_completions(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any = None,
        stream: bool = False,
        max_tokens: int = 200,
        temperature: float | None = None,
        reasoning_effort: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ChatResult:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "max_tokens": max_tokens,
        }
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if temperature is not None:
            payload["temperature"] = temperature
        if reasoning_effort is not None:
            payload["reasoning_effort"] = reasoning_effort
        if extra:
            payload.update(extra)

        start = time.time()
        if stream:
            return self._chat_completions_stream(payload, start)
        r = self.session.post(
            f"{self.base_url}/v1/chat/completions", json=payload, timeout=self.timeout
        )
        elapsed = time.time() - start
        self._raise_for_status(r)
        data = r.json()
        return self._normalize_chat_completion(data, elapsed)

    def _chat_completions_stream(self, payload: dict[str, Any], start: float) -> ChatResult:
        result = ChatResult()
        tool_call_buf: dict[int, dict[str, Any]] = {}
        with self.session.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            timeout=self.timeout,
            stream=True,
        ) as r:
            self._raise_for_status(r)
            for event in _iter_sse(r):
                if event == "[DONE]":
                    result.stream_events.append("done")
                    break
                try:
                    chunk = json.loads(event)
                except json.JSONDecodeError as exc:
                    raise AgentBenchError(f"malformed SSE JSON chunk: {event!r}") from exc
                result.stream_events.append("chunk")
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                choice = choices[0]
                delta = choice.get("delta") or {}
                if delta.get("content"):
                    result.content += delta["content"]
                if delta.get("reasoning_content"):
                    result.reasoning_content += delta["reasoning_content"]
                for tc in delta.get("tool_calls") or []:
                    idx = tc.get("index", 0)
                    buf = tool_call_buf.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                    if tc.get("id"):
                        buf["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        buf["name"] += fn["name"]
                    if fn.get("arguments"):
                        buf["arguments"] += fn["arguments"]
                if choice.get("finish_reason"):
                    result.finish_reason = choice["finish_reason"]
                if chunk.get("usage"):
                    result.usage = chunk["usage"]
        result.elapsed_s = time.time() - start
        result.tool_calls = [
            ToolCall(id=v["id"], name=v["name"], arguments=v["arguments"])
            for _, v in sorted(tool_call_buf.items())
        ]
        return result

    def _normalize_chat_completion(self, data: dict[str, Any], elapsed: float) -> ChatResult:
        result = ChatResult(raw=data, elapsed_s=elapsed, usage=data.get("usage") or {})
        choices = data.get("choices") or []
        if not choices:
            return result
        message = choices[0].get("message") or {}
        result.content = message.get("content") or ""
        result.reasoning_content = message.get("reasoning_content") or ""
        result.finish_reason = choices[0].get("finish_reason")
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function") or {}
            result.tool_calls.append(
                ToolCall(id=tc.get("id", ""), name=fn.get("name", ""), arguments=fn.get("arguments", ""))
            )
        return result

    # ------------------------------------------------------------------
    # OpenAI Responses API (/v1/responses) -- what Codex CLI speaks
    # ------------------------------------------------------------------
    def responses(
        self,
        input_items: str | list[dict[str, Any]],
        *,
        instructions: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        max_output_tokens: int = 200,
        temperature: float | None = None,
        reasoning: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ChatResult:
        payload: dict[str, Any] = {
            "model": self.model,
            "input": input_items,
            "stream": stream,
            "max_output_tokens": max_output_tokens,
        }
        if instructions is not None:
            payload["instructions"] = instructions
        if tools is not None:
            payload["tools"] = tools
        if temperature is not None:
            payload["temperature"] = temperature
        if reasoning is not None:
            payload["reasoning"] = reasoning
        if extra:
            payload.update(extra)

        start = time.time()
        if stream:
            return self._responses_stream(payload, start)
        r = self.session.post(f"{self.base_url}/v1/responses", json=payload, timeout=self.timeout)
        elapsed = time.time() - start
        self._raise_for_status(r)
        data = r.json()
        return self._normalize_responses(data, elapsed)

    def _normalize_responses(self, data: dict[str, Any], elapsed: float) -> ChatResult:
        result = ChatResult(raw=data, elapsed_s=elapsed, usage=data.get("usage") or {})
        for item in data.get("output") or []:
            itype = item.get("type")
            if itype == "message":
                for part in item.get("content") or []:
                    if part.get("type") in ("output_text", "text"):
                        result.content += part.get("text", "")
            elif itype == "reasoning":
                for part in item.get("content") or []:
                    result.reasoning_content += part.get("text", "")
            elif itype == "function_call":
                result.tool_calls.append(
                    ToolCall(
                        id=item.get("call_id", item.get("id", "")),
                        name=item.get("name", ""),
                        arguments=item.get("arguments", ""),
                    )
                )
        result.finish_reason = data.get("status")
        return result

    def _responses_stream(self, payload: dict[str, Any], start: float) -> ChatResult:
        result = ChatResult()
        tool_call_buf: dict[str, dict[str, Any]] = {}
        with self.session.post(
            f"{self.base_url}/v1/responses", json=payload, timeout=self.timeout, stream=True
        ) as r:
            self._raise_for_status(r)
            for event in _iter_sse(r):
                if not event:
                    continue
                try:
                    evt = json.loads(event)
                except json.JSONDecodeError as exc:
                    raise AgentBenchError(f"malformed SSE JSON event: {event!r}") from exc
                etype = evt.get("type", "")
                result.stream_events.append(etype)
                if etype == "response.output_text.delta":
                    result.content += evt.get("delta", "")
                elif etype == "response.reasoning_text.delta":
                    result.reasoning_content += evt.get("delta", "")
                elif etype == "response.function_call_arguments.delta":
                    item_id = evt.get("item_id", "")
                    buf = tool_call_buf.setdefault(item_id, {"id": item_id, "name": "", "arguments": ""})
                    buf["arguments"] += evt.get("delta", "")
                elif etype == "response.output_item.added":
                    item = evt.get("item") or {}
                    if item.get("type") == "function_call":
                        item_id = item.get("id", "")
                        buf = tool_call_buf.setdefault(item_id, {"id": item_id, "name": "", "arguments": ""})
                        buf["name"] = item.get("name", "")
                        buf["id"] = item.get("call_id", item_id)
                elif etype == "response.completed":
                    resp = evt.get("response") or {}
                    result.usage = resp.get("usage") or {}
                    result.finish_reason = resp.get("status")
                elif etype == "response.failed":
                    raise AgentBenchError(f"responses stream failed: {evt}")
        result.elapsed_s = time.time() - start
        result.tool_calls = [
            ToolCall(id=v["id"], name=v["name"], arguments=v["arguments"])
            for v in tool_call_buf.values()
        ]
        return result

    # ------------------------------------------------------------------
    # Anthropic Messages API (/v1/messages) -- what Claude Code speaks
    # ------------------------------------------------------------------
    def messages(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | list[dict[str, Any]] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | None = None,
        stream: bool = False,
        max_tokens: int = 200,
        temperature: float | None = None,
        thinking: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> ChatResult:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "max_tokens": max_tokens,
        }
        if system is not None:
            payload["system"] = system
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if temperature is not None:
            payload["temperature"] = temperature
        if thinking is not None:
            payload["thinking"] = thinking
        if extra:
            payload.update(extra)

        start = time.time()
        if stream:
            return self._messages_stream(payload, start)
        r = self.session.post(f"{self.base_url}/v1/messages", json=payload, timeout=self.timeout)
        elapsed = time.time() - start
        self._raise_for_status(r)
        data = r.json()
        return self._normalize_messages(data, elapsed)

    def _normalize_messages(self, data: dict[str, Any], elapsed: float) -> ChatResult:
        result = ChatResult(raw=data, elapsed_s=elapsed)
        if data.get("type") == "error":
            raise AgentBenchError(f"anthropic error response: {data}")
        usage = data.get("usage") or {}
        result.usage = {
            "prompt_tokens": usage.get("input_tokens"),
            "completion_tokens": usage.get("output_tokens"),
        }
        for block in data.get("content") or []:
            btype = block.get("type")
            if btype == "text":
                result.content += block.get("text", "")
            elif btype == "thinking":
                result.reasoning_content += block.get("thinking", "")
            elif btype == "tool_use":
                result.tool_calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        arguments=json.dumps(block.get("input", {})),
                    )
                )
        result.finish_reason = data.get("stop_reason")
        return result

    def _messages_stream(self, payload: dict[str, Any], start: float) -> ChatResult:
        result = ChatResult()
        tool_call_buf: dict[int, dict[str, Any]] = {}
        block_types: dict[int, str] = {}
        with self.session.post(
            f"{self.base_url}/v1/messages", json=payload, timeout=self.timeout, stream=True
        ) as r:
            self._raise_for_status(r)
            for event in _iter_sse(r):
                if not event:
                    continue
                try:
                    evt = json.loads(event)
                except json.JSONDecodeError as exc:
                    raise AgentBenchError(f"malformed SSE JSON event: {event!r}") from exc
                etype = evt.get("type", "")
                result.stream_events.append(etype)
                if etype == "content_block_start":
                    idx = evt.get("index", 0)
                    cb = evt.get("content_block") or {}
                    block_types[idx] = cb.get("type", "")
                    if cb.get("type") == "tool_use":
                        tool_call_buf[idx] = {
                            "id": cb.get("id", ""),
                            "name": cb.get("name", ""),
                            "arguments": "",
                        }
                elif etype == "content_block_delta":
                    idx = evt.get("index", 0)
                    delta = evt.get("delta") or {}
                    dtype = delta.get("type")
                    if dtype == "text_delta":
                        result.content += delta.get("text", "")
                    elif dtype == "thinking_delta":
                        result.reasoning_content += delta.get("thinking", "")
                    elif dtype == "input_json_delta":
                        buf = tool_call_buf.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                        buf["arguments"] += delta.get("partial_json", "")
                elif etype == "message_delta":
                    delta = evt.get("delta") or {}
                    if delta.get("stop_reason"):
                        result.finish_reason = delta["stop_reason"]
                    if evt.get("usage"):
                        result.usage = evt["usage"]
                elif etype == "error":
                    raise AgentBenchError(f"anthropic stream error event: {evt}")
        result.elapsed_s = time.time() - start
        result.tool_calls = [
            ToolCall(id=v["id"], name=v["name"], arguments=v["arguments"])
            for _, v in sorted(tool_call_buf.items())
        ]
        return result

    # ------------------------------------------------------------------
    # Cancellation helper: open a streaming request and close the
    # connection early to simulate an agent-side abort / Ctrl-C.
    # ------------------------------------------------------------------
    def stream_and_cancel(self, path: str, payload: dict[str, Any], after_events: int = 2) -> int:
        """POST a streaming request and close the connection after
        ``after_events`` SSE events. Returns the number of events actually
        observed before closing. Used to assert the server does not hang or
        crash when a client disconnects mid-generation (the exact behavior
        of a user hitting Ctrl-C in an agent CLI)."""
        seen = 0
        with self.session.post(
            f"{self.base_url}{path}", json=payload, timeout=self.timeout, stream=True
        ) as r:
            self._raise_for_status(r)
            for _ in _iter_sse(r):
                seen += 1
                if seen >= after_events:
                    break
        return seen

    @staticmethod
    def _raise_for_status(r: requests.Response) -> None:
        if r.status_code >= 400:
            try:
                body = r.json()
            except Exception:
                body = r.text
            raise AgentBenchError(f"HTTP {r.status_code}: {body}")


def _iter_sse(response: requests.Response) -> Iterator[str]:
    """Yield the ``data:`` payload of each SSE frame (already the stripped
    JSON-or-[DONE] string), skipping comments/keepalives/blank lines."""
    for raw_line in response.iter_lines(decode_unicode=True):
        if raw_line is None:
            continue
        line = str(raw_line).strip()
        if not line or not line.startswith("data:"):
            continue
        data = line[len("data:"):].strip()
        if not data:
            continue
        yield data
