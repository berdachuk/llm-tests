#!/usr/bin/env python3
"""Model-in-the-loop eval harness for qualbench SQL/migration fixtures.

For each task: read the buggy `up.sql` (with `-- BUG: ...` hint comments
stripped) plus `seed.sql` for schema/data context, ask the model to
produce a corrected migration, extract the returned SQL, write it to a
scratch file, and run the existing `verify.sh` against it (which applies
seed.sql + the candidate migration to a fresh scratch database in the
qualbench-pg container, re-applies it a second time if RUN_TWICE is
present, then runs check.sql). A task PASSes iff verify.sh exits 0.

Requires the qualbench-pg Docker container to be running on
127.0.0.1:15432 (see fixtures/sql-migrations/README.md).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

HERE = Path(__file__).parent
BUG_COMMENT_RE = re.compile(r"[ \t]*--\s*BUG:.*(?:\n[ \t]*--.*)*\n?")


class TruncatedResponseError(RuntimeError):
    pass


def artifact_snippet(text: str, limit: int = 2000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "... [truncated]"


def load_manifest() -> dict:
    return json.loads((HERE / "tasks.json").read_text())


def strip_bug_comments(source: str) -> str:
    """Remove `-- BUG: ...` comments (and any directly-following `--`
    continuation lines) so the model isn't handed the answer."""
    return BUG_COMMENT_RE.sub("", source)


def extract_sql(response_text: str) -> str | None:
    """Pull SQL out of a markdown-fenced code block. Falls back to the
    largest fenced block, or the raw response if it looks like bare SQL."""
    blocks = re.findall(r"```(?:sql)?\n(.*?)```", response_text, re.DOTALL)
    if blocks:
        return max(blocks, key=len).strip() + "\n"
    stripped = response_text.strip()
    upper = stripped.upper()
    if any(upper.startswith(kw) for kw in ("ALTER", "CREATE", "UPDATE", "INSERT", "DROP", "--")):
        return stripped + "\n"
    return None


def call_model(base_url: str, model: str, seed_sql: str, buggy_up_sql: str,
                task_id: str, timeout: int) -> str:
    prompt = f"""The following PostgreSQL migration script has a bug. The schema and data it will be applied against (created by a prior migration) is also provided for context -- do not modify or resubmit this, it's just context.

Existing schema/data (already applied, for context only):
```sql
{seed_sql}
```

Pending migration under test (has a bug):
```sql
{buggy_up_sql}
```

Fix the bug in the pending migration so that it applies successfully to the existing schema/data shown above, and satisfies the migration's evident intent (e.g. backfilling existing rows sensibly, adding appropriate defaults/constraints for future rows, avoiding data loss, and being safe to re-run if it looks like it should be idempotent). Respond with ONLY the complete, corrected migration SQL inside a single ```sql code block, and nothing else."""

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


def run_task(task: dict, manifest: dict, base_url: str, model: str, timeout: int,
             keep_scratch: bool = False) -> tuple[bool, list[str], float, dict]:
    task_dir = HERE / manifest["base_dir"] / task["dir"]
    seed_sql = (task_dir / "seed.sql").read_text()
    buggy_up_sql = strip_bug_comments((task_dir / "up.sql").read_text())

    artifact: dict = {
        "task_id": task["id"],
        "category": "sql-migrations",
        "task_dir": str(task_dir),
    }

    t0 = time.time()
    try:
        response_text = call_model(base_url, model, seed_sql, buggy_up_sql, task["id"], timeout)
    except TruncatedResponseError as e:
        artifact["error"] = str(e)
        return False, [str(e)], time.time() - t0, artifact
    except Exception as e:  # noqa: BLE001
        msg = f"request failed: {e}"
        artifact["error"] = msg
        return False, [msg], time.time() - t0, artifact

    artifact["response_length"] = len(response_text)
    artifact["response_excerpt"] = artifact_snippet(response_text)

    fixed_sql = extract_sql(response_text)
    if fixed_sql is None:
        msg = "could not extract SQL from model response"
        artifact["error"] = msg
        return False, [msg], time.time() - t0, artifact

    artifact["candidate_sql"] = fixed_sql
    artifact["candidate_length"] = len(fixed_sql)

    candidate_path = None
    try:
        fd_dir = tempfile.mkdtemp(prefix=f"qualbench-sql-{task['id']}-")
        candidate_path = Path(fd_dir) / "up.candidate.sql"
        candidate_path.write_text(fixed_sql)
        # verify.sh resolves its second arg relative to TASK_DIR, so drop
        # the candidate file inside the task dir itself (cleaned up after).
        in_task_candidate = task_dir / "up.candidate.sql"
        in_task_candidate.write_text(fixed_sql)

        result = subprocess.run(
            ["bash", str(HERE / manifest["verify_script"]), str(task_dir), "up.candidate.sql"],
            capture_output=True, text=True, timeout=60,
        )
        elapsed = time.time() - t0
        artifact["verifier"] = {
            "command": ["bash", str(HERE / manifest["verify_script"]), str(task_dir), "up.candidate.sql"],
            "returncode": result.returncode,
        }
        if result.returncode == 0:
            return True, [], elapsed, artifact
        tail = "\n".join((result.stdout + result.stderr).splitlines()[-25:])
        artifact["verifier"]["output_tail"] = tail
        return False, [f"verify.sh failed (exit {result.returncode}):", tail], elapsed, artifact
    except subprocess.TimeoutExpired:
        msg = "verify.sh timed out"
        artifact["error"] = msg
        return False, [msg], time.time() - t0, artifact
    finally:
        if keep_scratch and candidate_path:
            print(f"    (candidate SQL kept at {candidate_path})")
        in_task_candidate = task_dir / "up.candidate.sql"
        if in_task_candidate.exists():
            if keep_scratch:
                print(f"    (candidate SQL kept at {in_task_candidate})")
            else:
                in_task_candidate.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id", nargs="?")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default="qwen3.6-35b-a3b")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--keep-scratch", action="store_true")
    parser.add_argument("--emit-artifacts", action="store_true")
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
        passed, reasons, elapsed, artifact = run_task(
            task, manifest, args.url, args.model, args.timeout, args.keep_scratch
        )
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {task['id']} ({elapsed:.1f}s)")
        for r in reasons:
            print(f"    {r}")
        if args.emit_artifacts:
            print(f"[ARTIFACT] {task['id']} {json.dumps(artifact, ensure_ascii=True)}")
        all_passed = all_passed and passed

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
