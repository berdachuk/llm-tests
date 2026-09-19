#!/usr/bin/env python3
"""Render a multimodal-accuracy dashboard (Markdown, optionally HTML).

Combines three sources:

1. per-item JSONL results from `check.py` (one or more runs),
2. the per-domain pass thresholds this suite enforces,
3. `public_benchmarks.json` -- externally published reference numbers.

The comparison against published numbers is deliberately hedged. Our
suite is a 60-item stratified subset scored with our own prompt and
parser; a published MMMU score is the full 900-item validation set scored
with the official harness. Those are different measurements, so the
dashboard labels the comparison as indicative and refuses to present
unsourced placeholders as fact.

Usage:

    python3 dashboard.py results/mm-mmmu-subset-*.jsonl -o results/dashboard.md
    python3 dashboard.py results/*.jsonl --html results/dashboard.html
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mm_common as mm  # noqa: E402
import variance_report as vr  # noqa: E402
from check import FALLBACK_THRESHOLD, load_thresholds  # noqa: E402

HERE = Path(__file__).resolve().parent
PUBLIC_BENCHMARKS = HERE / "public_benchmarks.json"


def load_public_benchmarks(path: Path = PUBLIC_BENCHMARKS) -> dict:
    if not path.is_file():
        return {"benchmarks": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from exc


def pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def bar(value: float, width: int = 20) -> str:
    """Fixed-width text bar, so the Markdown table scans at a glance."""
    filled = int(round(max(0.0, min(1.0, value)) * width))
    return "#" * filled + "." * (width - filled)


def suite_reference_entries(public: dict, suite: str | None) -> tuple[str | None, list[dict]]:
    """Find published entries whose benchmark maps to this suite."""
    for key, bench in (public.get("benchmarks") or {}).items():
        if suite and bench.get("maps_to_suite") == suite:
            return bench.get("display_name", key), list(bench.get("entries") or [])
    return None, []


def render_markdown(report: dict, thresholds: dict[str, float], public: dict) -> str:
    s = report["summary"]
    e = report["errors"]
    v = report["domain_variance"]
    st = report["stability"]
    suite = report.get("suite")

    runs = report["runs"]
    model = runs[0].get("model") if runs else None
    url = runs[0].get("url") if runs else None

    lines: list[str] = [
        "# Multimodal accuracy dashboard",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Suite: `{suite}`",
        f"- Model: `{model}`",
        f"- Server: `{url}`",
        f"- Runs supplied: {len(runs)}",
    ]
    for idx, run in enumerate(runs):
        marker = " (headline/tables below)" if idx == len(runs) - 1 else ""
        lines.append(f"  - `{Path(run['path']).name}` ({run.get('n_items')} items){marker}")
    if len(runs) > 1:
        lines.append(
            "  - per-item tables use the **last run only**; earlier runs are "
            "used for the stability section, not averaged in"
        )
    sc = report.get("suite_consistency") or {}
    if not sc.get("consistent", True):
        # Blending suites produces a weighted average of two different
        # measurements; the headline would be a number that describes
        # neither. Report the problem instead of the number.
        lines += [
            "",
            "> **WARNING: mixed suites.** These runs come from different suites "
            f"({', '.join(sc.get('mixed') or [])}). The combined figures below "
            "mix item sets and are not a single measurement. Regenerate the "
            "dashboard per suite.",
        ]

    lines += [
        "",
        "## Headline",
        "",
        f"- **Accuracy: {s['n_correct']}/{s['n_total']} = {pct(s['accuracy'])}**",
        f"- Accuracy over items the model actually answered: "
        f"{pct(e['accuracy_over_answered'])} ({e['n_answered']} answered)",
        f"- Strict (exact-match) accuracy: {pct(s['strict_accuracy'])}",
        f"- Formatting slack (credit needing normalization/tolerance): {pct(s['format_slack'])}",
    ]
    if "chance_baseline" in report:
        lines.append(
            f"- Random-chance floor for this item mix: {pct(report['chance_baseline'])} "
            f"-> lift **{pct(report['lift_over_chance'])}**"
        )
    lines += [
        "",
        "Error decomposition -- wrong answers are separated from plumbing "
        "failures, because a truncated generation or a missing image is not a "
        "reasoning error:",
        "",
        "| Outcome | Count |",
        "|---|---|",
        f"| correct | {s['n_correct']} |",
        f"| wrong answer | {e['wrong_answers']} |",
        f"| no extractable answer | {e['unextractable']} |",
    ]
    for kind, count in sorted(e["by_kind"].items()):
        lines.append(f"| {vr.ERROR_KIND_LABELS.get(kind, kind)} | {count} |")

    lines += [
        "",
        "## Accuracy by visual domain",
        "",
        "`threshold` is the regression bar this suite enforces per domain "
        "(see `thresholds.json`); it is a guard against drift, not a claim "
        "about the model's ceiling.",
        "",
        "| Domain | Correct | Accuracy | | Threshold | Verdict |",
        "|---|---|---|---|---|---|",
    ]
    for name, d in sorted(report["by_domain"].items(), key=lambda kv: -kv[1]["accuracy"]):
        threshold = thresholds.get(name, FALLBACK_THRESHOLD)
        verdict = "PASS" if d["accuracy"] >= threshold else "**FAIL**"
        lines.append(
            f"| {name} | {d['n_correct']}/{d['n_total']} | {pct(d['accuracy'])} "
            f"| `{bar(d['accuracy'])}` | {pct(threshold)} | {verdict} |"
        )

    if v.get("n_domains", 0) > 1:
        lines += [
            "",
            f"Domain spread: range **{pct(v['range'])}**, stdev {pct(v['stdev'])} "
            f"(best `{v['best_domain']}`, worst `{v['worst_domain']}`). "
            "A wide spread means the headline number hides a modality the model "
            "is materially worse at.",
        ]

    for label, key in (
        ("MMMU subject", "by_subject"),
        ("stated difficulty", "by_difficulty"),
        ("answer type", "by_answer_type"),
    ):
        groups = report.get(key) or {}
        if len(groups) <= 1:
            continue
        lines += ["", f"## Accuracy by {label}", "", "| Group | Correct | Accuracy |", "|---|---|---|"]
        for name, d in sorted(groups.items(), key=lambda kv: -kv[1]["accuracy"]):
            lines.append(f"| {name} | {d['n_correct']}/{d['n_total']} | {pct(d['accuracy'])} |")

    lines += ["", "## Run-to-run stability", ""]
    if st["n_items_repeated"]:
        lines += [
            f"- Runs compared: {st['n_runs']}",
            f"- Repeated items: {st['n_items_repeated']} "
            f"({st['stable_correct']} always correct, {st['stable_incorrect']} always wrong, "
            f"{len(st['flaky_items'])} flipped)",
        ]
        if "accuracy_spread" in st:
            lines.append(
                f"- Per-run accuracy: {', '.join(pct(a) for a in st['per_run_accuracy'])} "
                f"-> spread **{pct(st['accuracy_spread'])}**. Differences smaller than "
                f"this are noise, not signal."
            )
        if st["flaky_items"]:
            lines += ["", "| Flaky item | Domain | Correct/attempts | Answers seen |", "|---|---|---|---|"]
            for f in st["flaky_items"]:
                answers = ", ".join(repr(a) for a in f["answers"])
                lines.append(
                    f"| {f['id']} | {f['domain']} | {f['n_correct']}/{f['n_attempts']} | {answers} |"
                )
    else:
        lines.append(
            "- Only one run supplied, so run-to-run variance is **unmeasured**. "
            "Re-run the suite and pass several JSONL files to quantify it."
        )

    bench_name, entries = suite_reference_entries(public, suite)
    lines += ["", "## Comparison against published benchmark numbers", ""]
    if not entries:
        lines.append(
            f"No published reference entries are mapped to suite `{suite}` in "
            f"`public_benchmarks.json`."
        )
    else:
        lines += [
            f"Reference benchmark: **{bench_name}**.",
            "",
            "> Caveat, and it is a big one: this suite scores a stratified "
            "**subset** with its own prompt and answer parser, while published "
            "numbers use the full official split and harness. The two are not "
            "the same measurement. Read this table as a sanity check on "
            "whether local vision is working at roughly the expected level, "
            "not as a leaderboard comparison.",
            "",
            "| Model | Accuracy | Comparability | Source | As of |",
            "|---|---|---|---|---|",
            f"| **this run** (`{model}`) | **{pct(s['accuracy'])}** | "
            f"local subset, n={s['n_total']} | this suite | "
            f"{datetime.now(timezone.utc).date().isoformat()} |",
        ]
        for entry in entries:
            acc = entry.get("accuracy")
            source = entry.get("source")
            if source is None or acc is None:
                source_cell = "**UNVERIFIED placeholder**"
            else:
                source_cell = f"[link]({source})"
            lines.append(
                f"| {entry.get('model')} | {pct(acc)} | "
                f"{entry.get('comparability', 'unknown')} | {source_cell} | "
                f"{entry.get('as_of') or 'n/a'} |"
            )
        unverified = [e for e in entries if not e.get("source") or e.get("accuracy") is None]
        if unverified:
            lines += [
                "",
                f"{len(unverified)} reference row(s) are unsourced placeholders and "
                f"must not be cited. Fill in `public_benchmarks.json` with sourced "
                f"figures (each needs `source` and `as_of`).",
            ]

    if report["failures"]:
        lines += [
            "",
            f"## Failing items ({len(report['failures'])})",
            "",
            "| Item | Domain | Expected | Got | Reason |",
            "|---|---|---|---|---|",
        ]
        for f in report["failures"]:
            reason = (f.get("reason") or "").replace("|", "\\|")[:120]
            kind = f" ({f['error_kind']})" if f.get("error_kind") else ""
            lines.append(
                f"| {f['id']} | {f.get('domain')}{kind} | `{f.get('expected')}` | "
                f"`{f.get('extracted')}` | {reason} |"
            )

    return "\n".join(lines) + "\n"


def render_html(markdown_text: str, report: dict) -> str:
    """Minimal self-contained HTML wrapper.

    Deliberately not a Markdown renderer: shipping a <pre> block keeps this
    dependency-free and guarantees the numbers render identically to the
    Markdown, rather than subtly differently through a third-party parser.
    """
    s = report["summary"]
    title = f"Multimodal dashboard -- {report.get('suite')} -- {pct(s['accuracy'])}"
    rows = "".join(
        f"<tr><td>{html.escape(name)}</td><td>{d['n_correct']}/{d['n_total']}</td>"
        f"<td>{pct(d['accuracy'])}</td>"
        f"<td><div style='background:#2d7;height:12px;width:{d['accuracy'] * 200:.0f}px'></div></td></tr>"
        for name, d in sorted(report["by_domain"].items(), key=lambda kv: -kv[1]["accuracy"])
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
 body {{ font-family: system-ui, sans-serif; margin: 2rem; max-width: 60rem; }}
 table {{ border-collapse: collapse; margin: 1rem 0; }}
 th, td {{ border: 1px solid #ccc; padding: 4px 10px; text-align: left; }}
 pre {{ background: #f6f6f6; padding: 1rem; overflow-x: auto; white-space: pre-wrap; }}
 .headline {{ font-size: 1.6rem; font-weight: 600; }}
</style></head><body>
<h1>Multimodal accuracy dashboard</h1>
<p class="headline">{s['n_correct']}/{s['n_total']} = {pct(s['accuracy'])}</p>
<p>Suite <code>{html.escape(str(report.get('suite')))}</code>.
Strict {pct(s['strict_accuracy'])}, formatting slack {pct(s['format_slack'])}.</p>
<h2>By visual domain</h2>
<table><tr><th>Domain</th><th>Correct</th><th>Accuracy</th><th></th></tr>{rows}</table>
<h2>Full report</h2>
<pre>{html.escape(markdown_text)}</pre>
</body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", nargs="+", help="Per-item JSONL file(s) from check.py")
    parser.add_argument("--suite", default=None)
    parser.add_argument("-o", "--out", default=None, help="Write Markdown here (default: stdout)")
    parser.add_argument("--html", default=None, help="Also write a standalone HTML dashboard here")
    parser.add_argument("--json", dest="json_out", default=None, help="Also write the raw report JSON")
    parser.add_argument("--benchmarks", default=str(PUBLIC_BENCHMARKS),
                        help="Path to public_benchmarks.json")
    args = parser.parse_args()

    records, runs = vr.load_records([Path(p) for p in args.records])
    suite = args.suite or runs[0].get("suite")
    report = vr.build_report(records, runs, suite)

    thresholds = load_thresholds()
    public = load_public_benchmarks(Path(args.benchmarks))
    markdown = render_markdown(report, thresholds, public)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")
        print(f"Markdown dashboard -> {out}")
    else:
        print(markdown)

    if args.html:
        html_path = Path(args.html)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(render_html(markdown, report), encoding="utf-8")
        print(f"HTML dashboard -> {html_path}")

    if args.json_out:
        json_path = Path(args.json_out)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"JSON report -> {json_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
