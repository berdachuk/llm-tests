#!/usr/bin/env python3
"""Bugfix-eval harness for qualbench Java/Spring fixtures.

For each task: read the buggy class (with `// BUG:` hint comments
stripped, so the model can't just read the answer off the page), send it
to the model along with its test file as context, ask for a corrected
version of the class, extract the returned Java code, write it into a
scratch copy of the project, and run only that class's test file with
Maven. A task PASSes if all tests in that one test class pass.

Each task gets its own temporary copy of the whole `base/` project
(via `cp -r`, excluding `target/`) so tasks can't interfere with each
other and the original fixture directory is never mutated.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

HERE = Path(__file__).parent
BUG_COMMENT_RE = re.compile(r"[ \t]*//\s*BUG:.*(?:\n[ \t]*//.*)*\n?")


def load_manifest() -> dict:
    return json.loads((HERE / "tasks.json").read_text())


def strip_bug_comments(source: str) -> str:
    """Remove `// BUG: ...` comments (and any directly-following `//`
    continuation lines) so the model isn't handed the answer."""
    return BUG_COMMENT_RE.sub("", source)


def extract_java_code(response_text: str, class_name: str) -> str | None:
    """Pull the Java source out of a markdown-fenced code block in the
    model's response. Falls back to the largest fenced block, or the
    raw response if it looks like bare Java (starts with 'package')."""
    blocks = re.findall(r"```(?:java)?\n(.*?)```", response_text, re.DOTALL)
    for block in blocks:
        if f"class {class_name}" in block:
            return block.strip() + "\n"
    if blocks:
        return max(blocks, key=len).strip() + "\n"
    stripped = response_text.strip()
    if stripped.startswith("package "):
        return stripped + "\n"
    return None


def call_model(base_url: str, model: str, buggy_source: str, test_source: str,
                class_name: str, timeout: int) -> str:
    prompt = f"""The following Java class has a bug. Its test file (which you must make pass, without modifying the test file) is also provided.

Class under test (`{class_name}.java`):
```java
{buggy_source}
```

Test file (`{class_name}Test.java`) -- do not modify this, it defines the expected behavior:
```java
{test_source}
```

Fix the bug in `{class_name}.java` so that all tests in `{class_name}Test.java` pass. Respond with ONLY the complete, corrected contents of `{class_name}.java` inside a single ```java code block, and nothing else."""

    resp = requests.post(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 4000,
            "reasoning_effort": "low",
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    message = data["choices"][0]["message"]
    content = message.get("content") or ""
    if not content.strip():
        content = message.get("reasoning_content") or ""
    return content


def run_task(task: dict, manifest: dict, base_url: str, model: str, timeout: int,
             keep_scratch: bool = False) -> tuple[bool, list[str], float]:
    class_name = task["class"]
    base_dir = HERE / manifest["base_dir"]
    src_file = base_dir / manifest["src_root"] / f"{class_name}.java"
    test_file = base_dir / manifest["test_root"] / f"{class_name}Test.java"

    buggy_source = strip_bug_comments(src_file.read_text())
    test_source = test_file.read_text()

    t0 = time.time()
    try:
        response_text = call_model(base_url, model, buggy_source, test_source, class_name, timeout)
    except Exception as e:  # noqa: BLE001
        return False, [f"request failed: {e}"], time.time() - t0

    fixed_code = extract_java_code(response_text, class_name)
    if fixed_code is None:
        return False, ["could not extract Java code from model response"], time.time() - t0

    scratch = Path(tempfile.mkdtemp(prefix=f"qualbench-java-{task['id']}-"))
    try:
        shutil.copytree(base_dir, scratch, dirs_exist_ok=True,
                         ignore=shutil.ignore_patterns("target"))
        rel_src = Path(manifest["src_root"]) / f"{class_name}.java"
        (scratch / rel_src).write_text(fixed_code)

        result = subprocess.run(
            ["mvn", "-q", "-o", "-Dtest=" + f"{class_name}Test", "test"],
            cwd=scratch, capture_output=True, text=True, timeout=180,
        )
        elapsed = time.time() - t0
        if result.returncode == 0:
            return True, [], elapsed
        tail = "\n".join((result.stdout + result.stderr).splitlines()[-25:])
        return False, [f"mvn test failed (exit {result.returncode}):", tail], elapsed
    except subprocess.TimeoutExpired:
        return False, ["mvn test timed out"], time.time() - t0
    finally:
        if keep_scratch:
            print(f"    (scratch kept at {scratch})")
        else:
            shutil.rmtree(scratch, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id", nargs="?")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default="qwen3.6-35b-a3b")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--keep-scratch", action="store_true")
    args = parser.parse_args()

    manifest = load_manifest()
    all_tasks = manifest["tasks"]

    if args.all:
        tasks = all_tasks
    elif args.task_id:
        tasks = [t for t in all_tasks if t["id"] == args.task_id]
        if not tasks:
            print(f"unknown task id: {args.task_id}", file=sys.stderr)
            return 2
    else:
        parser.error("provide a task_id or --all")
        return 2

    all_passed = True
    for task in tasks:
        passed, reasons, elapsed = run_task(task, manifest, args.url, args.model, args.timeout, args.keep_scratch)
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {task['id']} ({elapsed:.1f}s)")
        for r in reasons:
            print(f"    {r}")
        all_passed = all_passed and passed

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
