# llm-tests

**See [`TEST_RESULTS.md`](TEST_RESULTS.md) for the latest qualbench
FP8-vs-NVFP4 comparative test results (50-task quality/regression eval).**

Live-server compatibility tests for local/self-hosted LLM deployments,
focused on the wire protocols coding agents actually speak: OpenAI Chat
Completions, OpenAI Responses, and Anthropic Messages.

There is no mocking. These tests talk to a real, running inference server
and assert on real protocol, tool-calling, reasoning-extraction, streaming,
concurrency, and chat-template behavior -- the kind of regressions that
silently break coding agents (OpenCode, Claude Code, Codex CLI, Cursor)
without ever showing up as an obvious server crash.

**Attribution:** the original idea and shape of this suite were inspired by
[alexziskind1/machine_tests](https://github.com/alexziskind1/machine_tests).

## What's here

```
agentbench/
  client.py          Thin HTTP client for the three protocols (OpenAI chat
                      completions, OpenAI responses, Anthropic messages),
                      including SSE streaming support.
  settings.py         Central, environment-variable-driven configuration.
                      Every hardcoded threshold, timeout, and token budget
                      lives here -- see .env.sample for the full list.
  conftest.py         Pytest fixtures/options built on top of settings.py.
  tests/
    test_basic_compat.py            Protocol-alive sanity checks.
    test_reasoning.py               Reasoning/thinking extraction.
    test_tool_calling.py            Tool-call wire-format correctness.
    test_agentic_sessions.py        Multi-turn, multi-tool session replay.
    test_code_edge_cases.py         Payload/content robustness.
    test_streaming_and_cancellation.py   SSE streaming + cancellation.
    test_concurrency.py             Parallel-request correctness (opt-in).
    test_large_context.py           Needle-in-haystack at scale (opt-in).
    test_chat_template.py           Offline chat_template.jinja checks.
gen_256k_prompt.py    Synthetic large-context prompt generator used by
                      test_large_context.py.
check_applied.py      Chat-template version-string parser used by
                      test_chat_template.py.
```

## Setup

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

All configuration is environment-variable driven -- no code edits are
needed to point the suite at a different server, model, or deployment
profile. See **`.env.sample`** for the full, documented list of every
variable (server URL/model/timeouts, context-window and concurrency-limit
thresholds, reasoning-aware `max_tokens` budgets, large-context test
sizing, chat-template checks).

To use a `.env` file (loaded automatically, and git-ignored so it's safe to
put local/private values in it):

```bash
cp .env.sample .env
# edit .env with your server's URL/model
```

Or set variables directly on the command line, which always takes priority
over `.env`:

```bash
AGENTBENCH_URL=http://192.168.0.88:8000 \
AGENTBENCH_MODEL=qwen3.6-35b-a3b \
pytest agentbench/tests
```

Every variable has a built-in default (see `agentbench/settings.py`), so the
suite also runs against `http://localhost:8000` with zero configuration if
that's where your server is.

## Running the tests

```bash
# Fast/default subset (skips slow and concurrency-heavy tests)
pytest agentbench/tests

# Include large-context tests (real GPU time on a big model)
pytest agentbench/tests --run-slow

# Include concurrency tests (deliberately saturates the shared GPU)
pytest agentbench/tests --run-concurrency

# Both
pytest agentbench/tests --run-slow --run-concurrency

# A single file/class/test
pytest agentbench/tests/test_tool_calling.py -v
pytest agentbench/tests/test_tool_calling.py::TestSingleToolCallOpenAI -v
```

`--agent-url` / `--agent-model` CLI flags are also available and take
priority over both `.env` and the shell environment:

```bash
pytest agentbench/tests --agent-url http://localhost:8000 --agent-model my-model
```

If the target server isn't reachable, the suite fails fast with a clear
message instead of letting every test time out independently.

### Chat-template checks

`test_chat_template.py` performs *offline* checks (no network call) against
a local copy of `chat_template.jinja`. They skip cleanly unless
`AGENTBENCH_TEMPLATE_PATH` is set:

```bash
AGENTBENCH_TEMPLATE_PATH=/path/to/model/dir pytest agentbench/tests/test_chat_template.py
```

## Applied fix: froggeric's Qwen-Fixed-Chat-Templates

The Qwen 3.5/3.6/3.8 checkpoints tested here are served with the community
chat template from
[froggeric/Qwen-Fixed-Chat-Templates](https://huggingface.co/froggeric/Qwen-Fixed-Chat-Templates)
(currently **v22.4**) installed in place of the vendor-shipped
`chat_template.jinja`, because the official Qwen template has several bugs
that specifically break coding-agent workloads (tool-calling harnesses that
replay history, streaming, and multi-turn agentic sessions) rather than
simple chat.

**Why this matters for this test suite:** a large fraction of the tests
here exist specifically to catch regressions in the exact bugs this
template fixes. If you swap back to the vendor template (or a different
community fork), expect the following tests to start failing:

| Fix in froggeric's template | Exercised by |
|---|---|
| "Empty think" poisoning cure -- no longer prepends a blank `<think></think>` ahead of replayed reasoning in history | `test_reasoning.py::TestNoDuplicateEmptyThinkPoisoning` |
| Safe `medium` default reasoning effort (vendor template hardcoded `xhigh`, which can burn the whole `max_tokens` budget with zero visible content) | `test_reasoning.py::TestReasoningEffortOpenAI`, and the "generous max_tokens" rationale throughout `test_code_edge_cases.py` / `test_basic_compat.py` |
| Inline `<|think_low|>` / `<|think_medium|>` / `<|think_xhigh|>` / `<|think_off|>` control tags | `test_reasoning.py::TestInlineThinkTags` |
| Universal tool-argument handling (mapping *and* serialized-JSON-string arguments in history, without crashing) | `test_tool_calling.py::TestMalformedHistoryReplay` |
| Parallel `<tool_call>` token-parity fix (single `\n` between consecutive calls, avoiding KV-cache-breaking drift) | `test_tool_calling.py::TestParallelToolCalls` |
| Two-tier agentic error escalation (breaks "stuck repeating the same failing tool call" loops) | `test_tool_calling.py::TestRepeatedFailingToolCallDoesNotStall`, `test_agentic_sessions.py::TestErrorRecoveryWorkflow` |
| Smart false-positive error detection (tool results containing the word "error", e.g. `console.error`/grep output, no longer trigger bogus retries) | `test_tool_calling.py::TestErrorLikeToolResultsDoNotConfuseModel` |
| Merging consecutive leading `system`/`developer` messages into one turn | `test_code_edge_cases.py::TestLongSystemPrompt::test_multiple_leading_system_messages_are_merged_not_rejected` |

Two gaps between the template's behavior and the *server's* (FreeToken)
handling of it are captured as confirmed, `xfail(strict=True)` bugs rather
than silently skipped -- see
[Known, documented server behavior](#known-documented-server-behavior)
below:

- `test_reasoning.py::TestInlineThinkTags::test_inline_think_off_tag_content_is_not_swallowed_into_reasoning`
  -- the template correctly disables `<think>` for an inline `<|think_off|>`
  tag, but the server's reasoning-content splitter doesn't know that and
  swallows the whole answer into `reasoning_content` anyway.
- `test_tool_calling.py::TestToolChoiceForcing::test_tool_choice_required_forces_a_call`
  -- unrelated to the template; the server has no constrained decoding, so
  `tool_choice="required"` silently behaves like `"auto"`.

**Installing the template on your own server:** download
`chat_template.jinja` from the model repo above and point your inference
engine at it, e.g. for `llama.cpp` / `llama-server`:

```bash
llama-server -m your_model.gguf --jinja --chat-template-file chat_template.jinja --reasoning-format deepseek
```

or for vLLM, replace the `"chat_template"` field in `tokenizer_config.json`
and serve with:

```bash
vllm serve <model> --reasoning-parser qwen3 --tool-call-parser qwen3_xml
```

See the model card for LM Studio / MLX instructions and the full kwarg
reference (`reasoning_effort`, `preserve_thinking`, `tool_call_format`,
`max_tool_arg_chars`, `max_tool_response_chars`). Keep a backup of the
original vendor `chat_template.jinja` as `chat_template.jinja.orig` next to
the patched one -- `test_chat_template.py::test_original_template_was_backed_up`
verifies this if you point `AGENTBENCH_TEMPLATE_PATH` at a model directory.

## Secrets

If you keep server SSH passwords, tokens, or similar credentials for your
own convenience (e.g. to script server-side template installs), put them in
`secrets/` -- that directory is git-ignored and will never be committed.
Nothing in the test suite itself reads from `secrets/`; it's purely a local
convenience location.

## Known, documented server behavior

Some tests are marked `xfail(strict=True)` with a detailed explanation in
the test file: these are confirmed, reproducible bugs in the server under
test at the time the test was written (not flaky tests or suite bugs). If a
strict xfail starts *passing*, that's pytest telling you the underlying bug
has been fixed -- remove the `xfail` marker at that point.
