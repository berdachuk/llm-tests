#!/usr/bin/env python3
"""Deterministic checker for qualbench security-review fixtures.

Grades a model's free-text code review response by regex recall against
groups of acceptable phrasings for the planted defect(s). See README.md.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import requests

HERE = Path(__file__).parent


def load_task(task_dir: Path) -> tuple[str, str, dict]:
    code = (task_dir / "code.txt").read_text()
    prompt = (task_dir / "prompt.txt").read_text()
    expected = json.loads((task_dir / "expected.json").read_text())
    return code, prompt, expected


def call_model(base_url: str, model: str, code: str, prompt: str, timeout: int) -> str:
    user_content = f"{prompt}\n\n```\n{code}\n```"
    resp = requests.post(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "You are an experienced application security reviewer."},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0,
            "max_tokens": 4000,
            "reasoning_effort": "low",
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    message = data["choices"][0]["message"]
    # Some reasoning models return the whole answer via reasoning_content
    # and leave content empty if the token budget was exhausted mid-
    # thought. Fall back to reasoning_content so grading still sees the
    # model's actual analysis rather than failing on an artifact of
    # token-budget plumbing.
    content = message.get("content") or ""
    if not content.strip():
        content = message.get("reasoning_content") or ""
    return content


def run_check(task_dir: Path, base_url: str, model: str, timeout: int) -> tuple[bool, list[str], str]:
    code, prompt, expected = load_task(task_dir)

    try:
        response_text = call_model(base_url, model, code, prompt, timeout)
    except Exception as e:  # noqa: BLE001
        return False, [f"request failed: {e}"], ""

    groups = expected["required_pattern_groups"]
    min_groups = expected.get("min_groups_matched", len(groups))

    matched = 0
    reasons: list[str] = []
    for i, group in enumerate(groups):
        hit = any(re.search(pat, response_text, re.IGNORECASE) for pat in group)
        if hit:
            matched += 1
        else:
            reasons.append(f"group {i} not matched by any of: {group}")

    passed = matched >= min_groups
    if passed:
        reasons = []  # only report misses when failing
    else:
        reasons.insert(0, f"matched {matched}/{len(groups)} required groups (need >= {min_groups})")

    return passed, reasons, response_text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_dir", nargs="?")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default="qwen3.6-35b-a3b")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--show-response", action="store_true")
    args = parser.parse_args()

    if args.all:
        task_dirs = sorted(p for p in HERE.iterdir() if p.is_dir() and (p / "code.txt").exists())
    elif args.task_dir:
        task_dirs = [Path(args.task_dir)]
    else:
        parser.error("provide a task_dir or --all")
        return 2

    all_passed = True
    for task_dir in task_dirs:
        passed, reasons, response_text = run_check(task_dir, args.url, args.model, args.timeout)
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {task_dir.name}")
        for r in reasons:
            print(f"    - {r}")
        if args.show_response:
            print("    --- response ---")
            for line in response_text.splitlines():
                print(f"    {line}")
        all_passed = all_passed and passed

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
