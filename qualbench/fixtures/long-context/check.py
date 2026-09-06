#!/usr/bin/env python3
"""Deterministic checker for qualbench long-context "needle in a haystack"
fixtures. See README.md.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

import gen_prompt

HERE = Path(__file__).parent


class TruncatedResponseError(RuntimeError):
    pass


def artifact_snippet(text: str, limit: int = 2000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "... [truncated]"


def load_task(task_dir: Path) -> dict:
    return json.loads((task_dir / "task.json").read_text())


def build_prompt(task: dict) -> str:
    text, actual_tokens, n_modules = gen_prompt.build(
        target_tokens=task["target_tokens"],
        position_pct=task["position_pct"],
        marker_value=task["marker_value"],
        decoys=task.get("decoys"),
    )
    return text


def call_model(base_url: str, model: str, prompt: str, timeout: int) -> str:
    resp = requests.post(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 3000,
            "reasoning_effort": "low",
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    choice = data["choices"][0]
    message = choice["message"]
    if choice.get("finish_reason") == "length":
        content = message.get("content") or ""
        if not content.strip():
            content = message.get("reasoning_content") or ""
        snippet = content.strip()[:200]
        raise TruncatedResponseError(f"truncated: finish_reason=length (content: {snippet!r})")
    content = message.get("content") or ""
    if not content.strip():
        content = message.get("reasoning_content") or ""
    return content


def normalize(line: str) -> str:
    return line.strip().strip('"\'`.,;: ')


def run_check(task_dir: Path, base_url: str, model: str, timeout: int) -> tuple[bool, list[str], float, dict]:
    task = load_task(task_dir)
    prompt = build_prompt(task)
    artifact: dict = {
        "task_id": task_dir.name,
        "category": "long-context",
        "expected_marker": task["marker_value"],
        "target_tokens": task["target_tokens"],
        "position_pct": task["position_pct"],
    }

    t0 = time.time()
    try:
        response_text = call_model(base_url, model, prompt, timeout)
    except TruncatedResponseError as e:
        artifact["error"] = str(e)
        return False, [str(e)], time.time() - t0, artifact
    except Exception as e:  # noqa: BLE001
        msg = f"request failed: {e}"
        artifact["error"] = msg
        return False, [msg], time.time() - t0, artifact
    elapsed = time.time() - t0
    artifact["response_length"] = len(response_text)
    artifact["response_excerpt"] = artifact_snippet(response_text)

    lines = [l for l in response_text.splitlines() if l.strip()]
    first_line = normalize(lines[0]) if lines else ""
    expected = task["marker_value"]
    artifact["first_line"] = first_line

    if first_line == expected:
        return True, [], elapsed, artifact

    # also accept if the exact expected value appears anywhere in the
    # response (slightly more lenient, but still exact-match on the value
    # itself, not a substring/fuzzy match) -- report as a soft-pass note
    # while still counting it as a fail against the strict "first line"
    # requirement, so callers can distinguish "found it, wrong place" from
    # "never found it" when debugging.
    found_anywhere = expected in response_text
    reasons = [f"first line was {first_line!r}, expected {expected!r}"]
    if found_anywhere:
        reasons.append("(note: expected value does appear somewhere in the response, just not as the first line)")
    decoy_hit = None
    for d in task.get("decoys", []):
        if d["marker_value"] in response_text:
            decoy_hit = d["marker_value"]
    if decoy_hit:
        reasons.append(f"(note: response contains decoy value {decoy_hit!r} instead)")
        artifact["decoy_hit"] = decoy_hit

    return False, reasons, elapsed, artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_dir", nargs="?")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default="qwen3.6-35b-a3b")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--show-response", action="store_true")
    parser.add_argument("--emit-artifacts", action="store_true")
    args = parser.parse_args()

    if args.all:
        task_dirs = sorted(p for p in HERE.iterdir() if p.is_dir() and (p / "task.json").exists())
    elif args.task_dir:
        task_dirs = [Path(args.task_dir)]
    else:
        parser.error("provide a task_dir or --all")
        return 2

    all_passed = True
    for task_dir in task_dirs:
        passed, reasons, elapsed, artifact = run_check(task_dir, args.url, args.model, args.timeout)
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
