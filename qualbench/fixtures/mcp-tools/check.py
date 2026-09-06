#!/usr/bin/env python3
"""Deterministic checker for qualbench MCP/tool-call fixtures.

Usage:
    python3 check.py <task-dir> --url http://127.0.0.1:8000 --model qwen3.6-35b-a3b
    python3 check.py --all --url http://127.0.0.1:8000 --model qwen3.6-35b-a3b

Each task directory must contain tools.json, messages.json, expected.json.
See README.md for the full schema of expected.json.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests
from jsonschema import Draft7Validator, ValidationError

HERE = Path(__file__).parent


def artifact_snippet(text: str, limit: int = 2000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "... [truncated]"


def load_task(task_dir: Path) -> tuple[list, list, dict]:
    tools = json.loads((task_dir / "tools.json").read_text())
    messages = json.loads((task_dir / "messages.json").read_text())
    expected = json.loads((task_dir / "expected.json").read_text())
    return tools, messages, expected


def call_model(base_url: str, model: str, tools: list, messages: list, timeout: int) -> dict:
    resp = requests.post(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        json={
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0,
            "max_tokens": 1024,
            "reasoning_effort": "low",
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def extract_tool_calls(response: dict) -> list[dict]:
    choice = response["choices"][0]
    message = choice["message"]
    return message.get("tool_calls") or []


_MISSING = object()


def get_by_path(obj: dict, dotted_path: str):
    """Resolve a possibly-nested field path like 'address.city' against a
    parsed JSON arguments dict. Returns _MISSING if any segment is absent.
    """
    current = obj
    for segment in dotted_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return _MISSING
        current = current[segment]
    return current


def tool_schema_by_name(tools: list, name: str) -> dict | None:
    for t in tools:
        fn = t.get("function", t)
        if fn.get("name") == name:
            return fn.get("parameters", {})
    return None


def run_check(task_dir: Path, base_url: str, model: str, timeout: int) -> tuple[bool, list[str], dict]:
    tools, messages, expected = load_task(task_dir)
    reasons: list[str] = []
    artifact: dict = {
        "task_id": task_dir.name,
        "category": "mcp-tools",
    }

    try:
        response = call_model(base_url, model, tools, messages, timeout)
    except Exception as e:  # noqa: BLE001
        msg = f"request failed: {e}"
        artifact["error"] = msg
        return False, [msg], artifact

    choice = response["choices"][0]
    message = choice["message"]
    finish_reason = choice.get("finish_reason")
    artifact["finish_reason"] = finish_reason
    if finish_reason == "length":
        content = (message.get("content") or "").strip()
        if not content:
            content = (message.get("reasoning_content") or "").strip()
        snippet = content[:200]
        msg = f"truncated: finish_reason=length (content: {snippet!r})"
        artifact["error"] = msg
        artifact["response_excerpt"] = artifact_snippet(content)
        return False, [msg], artifact

    tool_calls = extract_tool_calls(response)
    artifact["tool_call_count"] = len(tool_calls)
    artifact["tool_call_names"] = [tc["function"]["name"] for tc in tool_calls]
    if message.get("content"):
        artifact["response_excerpt"] = artifact_snippet(str(message.get("content")))
    elif message.get("reasoning_content"):
        artifact["response_excerpt"] = artifact_snippet(str(message.get("reasoning_content")))

    if expected.get("expected_no_call"):
        if tool_calls:
            names = [tc["function"]["name"] for tc in tool_calls]
            return False, [f"expected no tool call, but model called: {names}"], artifact
        return True, [], artifact

    if not tool_calls:
        content = message.get("content") or ""
        if not content.strip():
            content = message.get("reasoning_content") or ""
        return False, [f"expected a tool call but none was made (content: {content[:200]!r})"], artifact

    expected_name = expected.get("expected_tool_name")
    if expected_name is not None:
        called_names = [tc["function"]["name"] for tc in tool_calls]
        if expected_name not in called_names:
            reasons.append(f"expected a call to '{expected_name}', but got: {called_names}")

    max_calls = expected.get("max_tool_calls")
    if max_calls is not None and len(tool_calls) > max_calls:
        reasons.append(f"expected at most {max_calls} tool call(s), got {len(tool_calls)}")

    for tc in tool_calls:
        name = tc["function"]["name"]
        raw_args = tc["function"]["arguments"]
        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError as e:
            reasons.append(f"call to '{name}' has invalid JSON arguments: {e}")
            continue

        schema = tool_schema_by_name(tools, name)
        if schema is not None:
            try:
                Draft7Validator(schema).validate(args)
            except ValidationError as e:
                reasons.append(f"call to '{name}' arguments fail schema validation: {e.message}")

        if name == expected_name:
            for rule in expected.get("argument_checks", []):
                field = rule["field"]
                actual = get_by_path(args, field)
                is_present = actual is not _MISSING

                if "must_be_present" in rule and rule["must_be_present"] and not is_present:
                    reasons.append(f"expected argument '{field}' to be present, but it was missing")
                    continue
                if "must_be_absent" in rule and rule["must_be_absent"]:
                    if is_present:
                        reasons.append(
                            f"expected argument '{field}' to be absent/omitted, but it was present: {actual!r}"
                        )
                    continue

                if "equals" in rule and actual != rule["equals"]:
                    reasons.append(
                        f"expected argument '{field}' == {rule['equals']!r}, got {actual!r}"
                    )
                if "one_of" in rule and actual not in rule["one_of"]:
                    reasons.append(
                        f"expected argument '{field}' to be one of {rule['one_of']!r}, got {actual!r}"
                    )
                if "contains" in rule:
                    if not isinstance(actual, (str, list)) or rule["contains"] not in actual:
                        reasons.append(
                            f"expected argument '{field}' to contain {rule['contains']!r}, got {actual!r}"
                        )
                if "set_equals" in rule:
                    if not isinstance(actual, list) or set(actual) != set(rule["set_equals"]):
                        reasons.append(
                            f"expected argument '{field}' to equal the set {rule['set_equals']!r} "
                            f"(order-independent), got {actual!r}"
                        )

    return (len(reasons) == 0), reasons, artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_dir", nargs="?", help="Path to a single task directory")
    parser.add_argument("--all", action="store_true", help="Run every task under this directory")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default="qwen3.6-35b-a3b")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--emit-artifacts", action="store_true")
    args = parser.parse_args()

    if args.all:
        task_dirs = sorted(p for p in HERE.iterdir() if p.is_dir() and (p / "tools.json").exists())
    elif args.task_dir:
        task_dirs = [Path(args.task_dir)]
    else:
        parser.error("provide a task_dir or --all")
        return 2

    all_passed = True
    for task_dir in task_dirs:
        t0 = time.time()
        passed, reasons, artifact = run_check(task_dir, args.url, args.model, args.timeout)
        elapsed = time.time() - t0
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {task_dir.name} ({elapsed:.1f}s)")
        for r in reasons:
            print(f"    - {r}")
        if args.emit_artifacts:
            print(f"[ARTIFACT] {task_dir.name} {json.dumps(artifact, ensure_ascii=True)}")
        all_passed = all_passed and passed

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
