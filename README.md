# llm-tests

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
