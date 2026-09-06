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

import requests

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
ARTIFACT_LINE_RE = re.compile(r"^\[ARTIFACT\]\s+(\S+)\s+(.+)$")


def parse_reason_line(line: str) -> str | None:
    if not line.startswith("    "):
        return None
    stripped = line.strip()
    if not stripped:
        return None
    if stripped.startswith("- "):
        return stripped[2:].strip()
    return stripped


def preflight_server(url: str, model: str, timeout_s: float) -> dict:
    endpoint = f"{url.rstrip('/')}/v1/models"
    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        resp = requests.get(endpoint, timeout=timeout_s)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"failed to query {endpoint}: {exc}") from exc

    try:
        payload = resp.json()
    except ValueError as exc:
        raise RuntimeError(f"{endpoint} returned non-JSON data") from exc

    data = payload.get("data")
    if not isinstance(data, list):
        raise RuntimeError(f"{endpoint} response missing 'data' list")

    available_model_ids: list[str] = []
    selected_model_entry: dict | None = None
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if not isinstance(model_id, str):
            continue
        available_model_ids.append(model_id)
        if model_id == model and selected_model_entry is None:
            selected_model_entry = item

    if selected_model_entry is None:
        preview = ", ".join(available_model_ids[:8])
        if len(available_model_ids) > 8:
            preview += ", ..."
        raise RuntimeError(
            f"requested model '{model}' not advertised by server at {endpoint}. "
            f"Available model ids: {preview or '(none)'}"
        )

    return {
        "checked_at": checked_at,
        "models_url": endpoint,
        "requested_model": model,
        "requested_model_found": True,
        "available_model_ids": available_model_ids,
        "selected_model_entry": selected_model_entry,
    }


def read_git_metadata(repo_dir: Path) -> dict:
    commit = None
    dirty = None
    try:
        cp = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        commit = cp.stdout.strip() or None

        dp = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        dirty = bool(dp.stdout.strip())
    except Exception:  # noqa: BLE001
        pass

    return {
        "repo": str(repo_dir),
        "commit": commit,
        "dirty": dirty,
    }


def run_category(cat_id: str, cfg: dict, url: str, model: str, extra_timeout: int | None) -> dict:
    cat_dir = FIXTURES / cfg["dir"]
    check_py = cat_dir / "check.py"
    timeout_s = extra_timeout or cfg["timeout"]

    cmd = [
        sys.executable, str(check_py), "--all",
        "--url", url, "--model", model,
        "--timeout", str(timeout_s),
        "--emit-artifacts",
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
    artifact_by_task: dict[str, dict] = {}
    category_logs: list[str] = []
    current_task: dict | None = None
    for line in stdout.splitlines():
        m = TASK_LINE_RE.match(line)
        if m:
            status, task_id, task_elapsed = m.groups()
            current_task = {
                "id": task_id,
                "passed": status == "PASS",
                "elapsed_s": float(task_elapsed) if task_elapsed else None,
                "reasons": [],
            }
            tasks.append(current_task)
            continue

        art = ARTIFACT_LINE_RE.match(line)
        if art:
            task_id, payload = art.groups()
            try:
                artifact_by_task[task_id] = json.loads(payload)
            except json.JSONDecodeError as exc:
                category_logs.append(f"artifact parse failed for {task_id}: {exc}")
                print(f"    artifact parse failed for {task_id}: {exc}")
            continue

        reason = parse_reason_line(line)
        if reason is not None and current_task is not None:
            current_task["reasons"].append(reason)
            continue

        if line.strip():
            category_logs.append(line)
            print(f"    {line}")

    n_pass = sum(1 for t in tasks if t["passed"])
    n_total = len(tasks)

    for task in tasks:
        artifact = artifact_by_task.get(task["id"])
        if artifact is not None:
            task["artifact"] = artifact

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
        "artifact_count": len(artifact_by_task),
        "logs": category_logs,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default="qwen3.6-35b-a3b")
    parser.add_argument("--notes", default="", help="Optional free-form notes to store in the run report.")
    parser.add_argument("--tag", required=True,
                         help="Short label for this run, e.g. 'fp8' or 'nvfp4' -- used in the output filename.")
    parser.add_argument("--categories", default=None,
                         help="Comma-separated subset of category ids to run (default: all).")
    parser.add_argument("--timeout", type=int, default=None,
                         help="Override every category's per-task --timeout.")
    parser.add_argument("--preflight-timeout", type=float, default=30.0,
                         help="Timeout (seconds) for the /v1/models preflight check.")
    args = parser.parse_args()

    if args.categories:
        selected = [c.strip() for c in args.categories.split(",")]
        unknown = [c for c in selected if c not in CATEGORIES]
        if unknown:
            parser.error(f"unknown category id(s): {unknown}. Known: {list(CATEGORIES)}")
    else:
        selected = list(CATEGORIES)

    print("=== Preflight: checking server model list ===", flush=True)
    try:
        preflight = preflight_server(args.url, args.model, args.preflight_timeout)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(
        f"Preflight OK: model '{args.model}' is advertised "
        f"({len(preflight['available_model_ids'])} model(s) total)."
    )

    RESULTS.mkdir(parents=True, exist_ok=True)

    run_started_at = datetime.now(timezone.utc).isoformat()
    t0 = time.time()
    git_meta = read_git_metadata(QUALBENCH_ROOT.parent)

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
        "notes": args.notes,
        "selected_categories": selected,
        "timeout_override_s": args.timeout,
        "runner_python": sys.version.split()[0],
        "suite_git_commit": git_meta["commit"],
        "suite_git_dirty": git_meta["dirty"],
        "preflight": preflight,
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
    preflight = report.get("preflight") or {}
    selected_entry = preflight.get("selected_model_entry") or {}
    advertised_ctx = selected_entry.get("max_model_len")
    if advertised_ctx is None:
        advertised_ctx = selected_entry.get("context_length")

    lines = [
        f"# qualbench run: {report['tag']}",
        "",
        f"- Server: `{report['url']}`",
        f"- Model: `{report['model']}`",
        f"- Selected categories: `{', '.join(report.get('selected_categories') or [])}`",
        f"- Started: {report['started_at']}",
        f"- Finished: {report['finished_at']}",
        f"- Total wall time: {report['total_wall_s']:.1f}s",
        f"- **Total: {report['total_pass']}/{report['total_tasks']} passed**",
        "",
        "| Category | Pass | Total | Wall (s) |",
        "|---|---|---|---|",
    ]

    if report.get("notes"):
        lines.insert(5, f"- Notes: {report['notes']}")
    if report.get("suite_git_commit"):
        lines.insert(5, f"- Suite commit: `{report['suite_git_commit']}`")
    if report.get("suite_git_dirty") is not None:
        lines.insert(6, f"- Suite git dirty: `{report['suite_git_dirty']}`")
    if preflight.get("requested_model_found"):
        lines.insert(7, "- Preflight: requested model present in `/v1/models`")
    if advertised_ctx is not None:
        lines.insert(8, f"- Advertised context length: `{advertised_ctx}`")

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
            for reason in t.get("reasons") or []:
                lines.append(f"  - {reason}")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
