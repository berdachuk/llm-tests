#!/usr/bin/env python3
"""Bugfix-eval harness for qualbench TypeScript/Angular fixtures.

For each task: read the buggy source file (with `// BUG:` hint comments
stripped), send it to the model along with its spec file as context, ask
for a corrected version, extract the returned TS code, write it into a
scratch copy of the project, and run only that spec file via
`ng test --include=<spec>`. A task PASSes if all tests in that spec pass.

Each task gets its own temporary copy of the whole `base/` project
(hardlinked via `cp -al` where possible to avoid re-copying node_modules)
so tasks can't interfere with each other and the original fixture
directory is never mutated.
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
    return BUG_COMMENT_RE.sub("", source)


def extract_ts_code(response_text: str) -> str | None:
    blocks = re.findall(r"```(?:ts|typescript)?\n(.*?)```", response_text, re.DOTALL)
    if blocks:
        return max(blocks, key=len).strip() + "\n"
    stripped = response_text.strip()
    if stripped.startswith("import "):
        return stripped + "\n"
    return None


def call_model(base_url: str, model: str, buggy_source: str, spec_source: str,
                file_name: str, spec_name: str, timeout: int) -> str:
    prompt = f"""The following TypeScript/Angular file has a bug. Its spec (test) file, which you must make pass without modifying it, is also provided.

File under test (`{file_name}`):
```ts
{buggy_source}
```

Spec file (`{spec_name}`) -- do not modify this, it defines the expected behavior:
```ts
{spec_source}
```

Fix the bug in `{file_name}` so that all tests in `{spec_name}` pass. Respond with ONLY the complete, corrected contents of `{file_name}` inside a single ```ts code block, and nothing else."""

    resp = requests.post(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 6000,
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


def make_scratch(base_dir: Path, prefix: str) -> Path:
    scratch = Path(tempfile.mkdtemp(prefix=prefix))
    scratch.rmdir()
    # cp -al hardlinks files instead of copying (huge speedup + no extra
    # disk for node_modules); falls back to a normal recursive copy
    # (excluding node_modules/.angular caches, which get hardlinked
    # separately) if hardlinking across filesystems isn't possible.
    try:
        subprocess.run(["cp", "-al", str(base_dir), str(scratch)], check=True)
    except subprocess.CalledProcessError:
        shutil.copytree(base_dir, scratch, ignore=shutil.ignore_patterns(".angular"))
    return scratch


def run_task(task: dict, manifest: dict, base_url: str, model: str, timeout: int,
             keep_scratch: bool = False) -> tuple[bool, list[str], float]:
    base_dir = HERE / manifest["base_dir"]
    src_root = manifest["src_root"]
    file_name = task["file"]
    spec_name = task["spec"]
    src_file = base_dir / src_root / file_name
    spec_file = base_dir / src_root / spec_name

    buggy_source = strip_bug_comments(src_file.read_text())
    spec_source = spec_file.read_text()

    t0 = time.time()
    try:
        response_text = call_model(base_url, model, buggy_source, spec_source, file_name, spec_name, timeout)
    except Exception as e:  # noqa: BLE001
        return False, [f"request failed: {e}"], time.time() - t0

    fixed_code = extract_ts_code(response_text)
    if fixed_code is None:
        return False, ["could not extract TypeScript code from model response"], time.time() - t0

    scratch = make_scratch(base_dir, f"qualbench-ts-{task['id']}-")
    try:
        rel_src = Path(src_root) / file_name
        # Break the hardlink before writing so we don't mutate the
        # original fixture file that cp -al shares an inode with.
        target = scratch / rel_src
        target.unlink()
        target.write_text(fixed_code)

        include_path = str(Path(src_root) / spec_name)
        result = subprocess.run(
            ["npx", "ng", "test", f"--include={include_path}", "--watch=false"],
            cwd=scratch, capture_output=True, text=True, timeout=180,
        )
        elapsed = time.time() - t0
        output = result.stdout + result.stderr
        failed = bool(re.search(r"\bTests\s+\d+\s+failed", output)) or result.returncode != 0
        if not failed:
            return True, [], elapsed
        tail = "\n".join(output.splitlines()[-25:])
        return False, [f"ng test failed (exit {result.returncode}):", tail], elapsed
    except subprocess.TimeoutExpired:
        return False, ["ng test timed out"], time.time() - t0
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
    parser.add_argument("--timeout", type=int, default=300)
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
