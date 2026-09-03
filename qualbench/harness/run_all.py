#!/usr/bin/env python3
"""Unified qualbench runner.

Invokes each category's own `check.py --all` as a subprocess against a
given server/model, parses the `[PASS]`/`[FAIL]` lines every harness
already prints, and aggregates everything into one report (JSON +
Markdown) under `results/`.

This intentionally does NOT reimplement any category's grading logic --
each category's check.py remains the single source of truth for how its
own tasks are graded. This script is purely an aggregator/reporter.

Usage:
    python3 harness/run_all.py --url http://127.0.0.1:8000 --model qwen3.6-35b-a3b --tag fp8
    python3 harness/run_all.py --tag nvfp4 --categories java-spring,ts-angular
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
QUALBENCH_ROOT = HERE.parent
FIXTURES = QUALBENCH_ROOT / "fixtures"
RESULTS = QUALBENCH_ROOT / "results"

# category id -> (fixtures subdir, extra timeout override in seconds or None)
CATEGORIES = {
    "java-spring": {"dir": "java-spring", "timeout": 180},
    "ts-angular": {"dir": "ts-angular", "timeout": 300},
    "sql-migrations": {"dir": "sql-migrations", "timeout": 300},
    "mcp-tools": {"dir": "mcp-tools", "timeout": 120},
    "security-review": {"dir": "security-review", "timeout": 180},
    "long-context": {"dir": "long-context", "timeout": 600},
}

TASK_LINE_RE = re.compile(r"^\[(PASS|FAIL)\]\s+(\S+)(?:\s+\(([\d.]+)s\))?\s*$")


def run_category(cat_id: str, cfg: dict, url: str, model: str, extra_timeout: int | None) -> dict:
    cat_dir = FIXTURES / cfg["dir"]
    check_py = cat_dir / "check.py"
    timeout_s = extra_timeout or cfg["timeout"]

    cmd = [
        sys.executable, str(check_py), "--all",
        "--url", url, "--model", model,
        "--timeout", str(timeout_s),
    ]

    print(f"\n=== Running category: {cat_id} (per-task timeout {timeout_s}s) ===")
    t0 = time.time()
    try:
        # Give the whole category run generous wall-clock room: worst case
        # is every task individually timing out back-to-back.
        proc = subprocess.run(
            cmd, cwd=cat_dir, capture_output=True, text=True,
            timeout=timeout_s * 20 + 120,
        )
        stdout = proc.stdout
        stderr = proc.stderr
        returncode = proc.returncode
        category_timed_out = False
    except subprocess.TimeoutExpired as e:
        stdout = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = (e.stderr or b"").decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        returncode = -1
        category_timed_out = True
    elapsed = time.time() - t0

    tasks = []
    for line in stdout.splitlines():
        m = TASK_LINE_RE.match(line)
        if m:
            status, task_id, task_elapsed = m.groups()
            tasks.append({
                "id": task_id,
                "passed": status == "PASS",
                "elapsed_s": float(task_elapsed) if task_elapsed else None,
            })
        else:
            print(f"    {line}")

    n_pass = sum(1 for t in tasks if t["passed"])
    n_total = len(tasks)

    print(f"--- {cat_id}: {n_pass}/{n_total} passed ({elapsed:.1f}s wall) ---")
    if returncode not in (0, 1) or category_timed_out:
        print(f"    WARNING: harness exited abnormally (code={returncode}, timed_out={category_timed_out})")
        if stderr.strip():
            print("    stderr tail:")
            for line in stderr.strip().splitlines()[-15:]:
                print(f"    {line}")

    return {
        "category": cat_id,
        "n_pass": n_pass,
        "n_total": n_total,
        "wall_s": elapsed,
        "returncode": returncode,
        "timed_out": category_timed_out,
        "tasks": tasks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default="qwen3.6-35b-a3b")
    parser.add_argument("--tag", required=True,
                         help="Short label for this run, e.g. 'fp8' or 'nvfp4' -- used in the output filename.")
    parser.add_argument("--categories", default=None,
                         help="Comma-separated subset of category ids to run (default: all).")
    parser.add_argument("--timeout", type=int, default=None,
                         help="Override every category's per-task --timeout.")
    args = parser.parse_args()

    if args.categories:
        selected = [c.strip() for c in args.categories.split(",")]
        unknown = [c for c in selected if c not in CATEGORIES]
        if unknown:
            parser.error(f"unknown category id(s): {unknown}. Known: {list(CATEGORIES)}")
    else:
        selected = list(CATEGORIES)

    RESULTS.mkdir(parents=True, exist_ok=True)

    run_started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.time()

    category_results = []
    for cat_id in selected:
        result = run_category(cat_id, CATEGORIES[cat_id], args.url, args.model, args.timeout)
        category_results.append(result)

    total_wall = time.time() - t0
    total_pass = sum(r["n_pass"] for r in category_results)
    total_tasks = sum(r["n_total"] for r in category_results)

    report = {
        "tag": args.tag,
        "url": args.url,
        "model": args.model,
        "started_at": run_started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "total_wall_s": total_wall,
        "total_pass": total_pass,
        "total_tasks": total_tasks,
        "categories": category_results,
    }

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = RESULTS / f"run-{args.tag}-{timestamp}.json"
    json_path.write_text(json.dumps(report, indent=2))

    md_path = RESULTS / f"run-{args.tag}-{timestamp}.md"
    md_path.write_text(render_markdown(report))

    print(f"\n=== TOTAL: {total_pass}/{total_tasks} passed ({total_wall:.1f}s wall) ===")
    print(f"Report written to:\n  {json_path}\n  {md_path}")

    return 0 if total_pass == total_tasks else 1


def render_markdown(report: dict) -> str:
    lines = [
        f"# qualbench run: {report['tag']}",
        "",
        f"- Server: `{report['url']}`",
        f"- Model: `{report['model']}`",
        f"- Started: {report['started_at']}",
        f"- Finished: {report['finished_at']}",
        f"- Total wall time: {report['total_wall_s']:.1f}s",
        f"- **Total: {report['total_pass']}/{report['total_tasks']} passed**",
        "",
        "| Category | Pass | Total | Wall (s) |",
        "|---|---|---|---|",
    ]
    for r in report["categories"]:
        flag = "" if r["returncode"] in (0, 1) and not r["timed_out"] else " ⚠️"
        lines.append(f"| {r['category']} | {r['n_pass']} | {r['n_total']} | {r['wall_s']:.1f}{flag} |")

    lines.append("")
    lines.append("## Task-level detail")
    for r in report["categories"]:
        lines.append("")
        lines.append(f"### {r['category']} ({r['n_pass']}/{r['n_total']})")
        for t in r["tasks"]:
            status = "PASS" if t["passed"] else "FAIL"
            elapsed = f" ({t['elapsed_s']:.1f}s)" if t["elapsed_s"] is not None else ""
            lines.append(f"- [{status}] {t['id']}{elapsed}")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
