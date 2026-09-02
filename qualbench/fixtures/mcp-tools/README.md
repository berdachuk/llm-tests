# MCP / Tool-Call fixtures

8 tasks that test whether a model, given a set of OpenAI-format tool
definitions and a short conversation, produces well-formed, correctly-
targeted tool calls -- or correctly declines to call a tool when it
shouldn't.

Each task directory contains:

- `tools.json` -- the list of tool definitions offered to the model,
  each with a JSON Schema `parameters` object (this is what a real
  MCP/tool-calling client would send as the `tools` array).
- `messages.json` -- the conversation to send (system + user messages,
  and for multi-step tasks, prior assistant/tool turns already
  "completed" to set up context).
- `expected.json` -- deterministic pass/fail rules checked against the
  model's tool call(s) (see `check.py` for the rule vocabulary).
- `README.md` -- human-readable description of what's being tested.

## Running a single task

```bash
python3 check.py <task-dir> --url http://127.0.0.1:8000 --model qwen3.6-35b-a3b
```

Prints PASS/FAIL and the reasons; exits 0 on pass, 1 on fail.

## Running all 8

```bash
python3 check.py --all --url http://127.0.0.1:8000 --model qwen3.6-35b-a3b
```

## Grading approach

All 8 tasks are graded fully deterministically:
- The tool name(s) actually called are compared against
  `expected.json`'s `expected_tool_name` (or `forbidden_no_call` /
  `expected_no_call`).
- Every tool call's `arguments` JSON is first validated for well-formed
  JSON, then schema-validated against that tool's own declared
  `parameters` JSON Schema from `tools.json` (catches type errors,
  missing required fields, wrong enum values structurally).
- `expected.json` then applies specific value-level assertions (e.g.
  "argument X must equal/contain/be one of ...") on top of schema
  validity.

No LLM-judge fallback is needed for this category since tool-call
correctness is fully mechanically checkable.
