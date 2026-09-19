#!/usr/bin/env python3
"""Compare model outputs against ground truth for multimodal reasoning.

`check.py` answers "did the bucket clear its threshold". This tool answers
the follow-up questions you actually need when a bucket is red:

* **where** the errors are -- accuracy split by visual domain, by MMMU
  subject, by stated difficulty, and by answer type;
* **what kind** of error it is -- a genuinely wrong answer, a formatting
  mismatch the normalizer had to rescue, a truncated generation, or a
  transport failure. Conflating these is the fastest way to misdiagnose a
  model;
* **how stable** the model is across repeats -- given several runs of the
  same suite, which items flip between correct and incorrect. On a
  reasoning model at temperature 0 that flip set is the real
  nondeterminism budget, and it bounds how much any single run's number
  can be trusted;
* **guessing check** -- accuracy versus the random-chance baseline implied
  by each item's option count, so a bucket that merely looks weak is
  distinguished from one that carries no signal at all.

Usage:

    python3 variance_report.py results/mm-smoke-*.jsonl
    python3 variance_report.py --json out.json results/mm-mmmu-subset-*.jsonl
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mm_common as mm  # noqa: E402

ERROR_KIND_LABELS = {
    "truncated": "truncated generation (token budget)",
    "request": "transport/request failure",
    "setup": "media/staging error (not a model failure)",
}


def load_records(paths: list[Path]) -> tuple[list[dict], list[dict]]:
    """Read one or more per-item JSONL files written by check.py.

    Returns (records, run_metadata). Each record is tagged with `_run` so
    cross-run stability can be computed.
    """
    records: list[dict] = []
    runs: list[dict] = []

    for path in paths:
        if not path.is_file():
            raise SystemExit(f"no such records file: {path}")
        meta: dict = {"path": str(path)}
        run_records: list[dict] = []
        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            if obj.get("_meta"):
                meta.update({k: v for k, v in obj.items() if k != "_meta"})
                continue
            obj["_run"] = str(path)
            run_records.append(obj)
        if not run_records:
            raise SystemExit(f"{path}: contains no item records")
        meta["n_items"] = len(run_records)
        runs.append(meta)
        records.extend(run_records)

    return records, runs


def chance_baseline(records: list[dict], manifest_items: dict[str, dict] | None) -> float | None:
    """Expected accuracy from uniform guessing over the graded items.

    Only multiple-choice items have a well-defined chance rate; if the set
    is mostly free-form there is nothing meaningful to compare against, so
    return None rather than invent a number.
    """
    if not manifest_items:
        return None
    rates: list[float] = []
    for r in records:
        item = manifest_items.get(r["id"])
        if not item or item.get("answer_type") != "multiple_choice":
            continue
        n_opts = len(item.get("options") or ())
        if n_opts >= 2:
            rates.append(1.0 / n_opts)
    if not rates:
        return None
    return statistics.fmean(rates)


def group_accuracy(records: list[dict], key: str) -> dict[str, dict]:
    """Accuracy bucketed by an arbitrary record field."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        buckets[str(r.get(key) or "(unknown)")].append(r)

    out: dict[str, dict] = {}
    for name in sorted(buckets):
        bucket = buckets[name]
        n = len(bucket)
        n_ok = sum(1 for r in bucket if r.get("correct"))
        out[name] = {
            "n_total": n,
            "n_correct": n_ok,
            "accuracy": n_ok / n if n else 0.0,
            "n_exact": sum(1 for r in bucket if r.get("match_mode") == "exact"),
            "n_errors": sum(1 for r in bucket if r.get("error_kind")),
        }
    return out


def error_breakdown(records: list[dict]) -> dict:
    """Separate real wrong answers from plumbing failures."""
    out = {
        "n_total": len(records),
        "n_correct": sum(1 for r in records if r.get("correct")),
        "by_kind": defaultdict(int),
        "wrong_answers": 0,
        "unextractable": 0,
    }
    for r in records:
        kind = r.get("error_kind")
        if kind:
            out["by_kind"][kind] += 1
            continue
        if r.get("correct"):
            continue
        if not (r.get("extracted") or "").strip():
            out["unextractable"] += 1
        else:
            out["wrong_answers"] += 1
    out["by_kind"] = dict(out["by_kind"])
    # Accuracy over only the items the model actually got to answer. When
    # media is missing or generations truncate, the raw accuracy understates
    # the model; this is the honest denominator for a model claim.
    answered = [r for r in records if not r.get("error_kind")]
    out["n_answered"] = len(answered)
    out["accuracy_over_answered"] = (
        sum(1 for r in answered if r.get("correct")) / len(answered) if answered else 0.0
    )
    return out


def stability(records: list[dict]) -> dict:
    """Per-item agreement across repeated runs of the same suite."""
    by_item: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_item[r["id"]].append(r)

    repeated = {k: v for k, v in by_item.items() if len(v) > 1}
    n_runs = len({r["_run"] for r in records})

    out = {
        "n_runs": n_runs,
        "n_items_repeated": len(repeated),
        "flaky_items": [],
        "stable_correct": 0,
        "stable_incorrect": 0,
        "unmeasurable_items": [],
    }
    if not repeated:
        return out

    for item_id, attempts in sorted(repeated.items()):
        # An item that failed for a plumbing reason in *any* run tells us
        # nothing about model stability: a truncated generation produces an
        # empty answer, which looks exactly like a wrong-answer flip if you
        # only compare booleans. Counting those as flakiness would blame the
        # model for the harness's token budget.
        if any(a.get("error_kind") for a in attempts):
            out["unmeasurable_items"].append(
                {
                    "id": item_id,
                    "domain": attempts[0].get("domain"),
                    "kinds": [
                        a.get("error_kind") or "ok" for a in attempts
                    ],
                }
            )
            continue

        outcomes = [bool(a.get("correct")) for a in attempts]
        if all(outcomes):
            out["stable_correct"] += 1
        elif not any(outcomes):
            out["stable_incorrect"] += 1
        else:
            out["flaky_items"].append(
                {
                    "id": item_id,
                    "domain": attempts[0].get("domain"),
                    "n_correct": sum(outcomes),
                    "n_attempts": len(outcomes),
                    "answers": [a.get("extracted") for a in attempts],
                }
            )

    # Flakiness is a fraction of the items we could actually observe across
    # every run, not of all repeated items.
    measurable = len(repeated) - len(out["unmeasurable_items"])
    out["n_measurable"] = measurable
    out["flake_rate"] = len(out["flaky_items"]) / measurable if measurable else 0.0
    # Run-level accuracy spread: the width of this band is how much of a
    # single run's headline number is noise.
    per_run = []
    for run in sorted({r["_run"] for r in records}):
        bucket = [r for r in records if r["_run"] == run]
        per_run.append(sum(1 for r in bucket if r.get("correct")) / len(bucket))
    out["per_run_accuracy"] = per_run
    if len(per_run) > 1:
        out["accuracy_spread"] = max(per_run) - min(per_run)
        out["accuracy_stdev"] = statistics.pstdev(per_run)
    return out


def compare_run_configs(runs: list[dict]) -> dict:
    """Detect whether the supplied runs were taken with the same settings.

    Mixing runs from different token budgets and reporting the resulting
    gap as "run-to-run variance" would be a straightforward lie: the
    difference is caused by the configuration, not by the model. Returns
    the per-run config plus a `differing` list of settings that changed.
    """
    configs: dict[str, dict] = {
        str(run.get("path") or "(unknown)"): dict(run.get("config") or {})
        for run in runs
    }
    settings = sorted({key for cfg in configs.values() for key in cfg})

    differing = []
    for key in settings:
        values = {cfg.get(key) for cfg in configs.values()}
        if len(values) > 1:
            differing.append(
                {
                    "setting": key,
                    "values": [
                        {"run": Path(path).name, "value": configs[path].get(key)}
                        for path in sorted(configs)
                    ],
                }
            )

    missing = [Path(p).name for p, cfg in configs.items() if not cfg]
    return {
        "compared": len(configs),
        "settings": settings,
        "differing": differing,
        "runs_without_config": missing,
        "comparable": not differing and not missing,
    }


def check_suite_consistency(runs: list[dict]) -> dict:
    """Verify every supplied run is from the same suite.

    Aggregating different suites into one headline number is meaningless:
    the combined denominator mixes item sets and the accuracy is a
    weighted average of two different measurements. Reported explicitly so
    the caller can refuse or warn rather than quietly producing a number.
    """
    suites = sorted({str(run.get("suite") or "(unknown)") for run in runs})
    return {
        "suites": suites,
        "consistent": len(suites) == 1,
        "mixed": suites if len(suites) > 1 else [],
    }


def latest_run_only(records: list[dict]) -> list[dict]:
    """Deduplicate to one attempt per item (the last run seen)."""
    by_item: dict[str, dict] = {}
    for r in records:
        by_item[r["id"]] = r
    return list(by_item.values())


def build_report(records: list[dict], runs: list[dict], suite: str | None) -> dict:
    manifest_items: dict[str, dict] | None = None
    if suite:
        try:
            manifest_items = {i["id"]: i for i in mm.load_manifest(suite)}
        except (FileNotFoundError, ValueError) as exc:
            print(f"  note: could not load manifest {suite!r} ({exc}); "
                  f"skipping chance baseline", file=sys.stderr)

    unique = latest_run_only(records)
    summary = mm.summarize(unique)

    report = {
        "runs": runs,
        "suite": suite,
        "suite_consistency": check_suite_consistency(runs),
        "run_config_comparison": compare_run_configs(runs),
        "summary": summary,
        "domain_variance": mm.domain_variance(summary),
        "errors": error_breakdown(unique),
        "by_domain": group_accuracy(unique, "domain"),
        "by_subject": group_accuracy(unique, "subject"),
        "by_difficulty": group_accuracy(unique, "difficulty"),
        "by_answer_type": group_accuracy(unique, "answer_type"),
        "stability": stability(records),
        "failures": [
            {
                "id": r["id"],
                "domain": r.get("domain"),
                "subject": r.get("subject"),
                "expected": r.get("expected"),
                "extracted": r.get("extracted"),
                "error_kind": r.get("error_kind"),
                "reason": (r.get("reasons") or [""])[0],
            }
            for r in unique
            if not r.get("correct")
        ],
    }

    baseline = chance_baseline(unique, manifest_items)
    if baseline is not None:
        report["chance_baseline"] = baseline
        report["lift_over_chance"] = summary["accuracy"] - baseline

    return report


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_text(report: dict) -> str:
    lines: list[str] = []
    s = report["summary"]
    e = report["errors"]

    lines.append("=" * 72)
    lines.append("multimodal variance report")
    lines.append("=" * 72)
    for run in report["runs"]:
        lines.append(
            f"  run: {Path(run['path']).name}  suite={run.get('suite')}  "
            f"model={run.get('model')}  items={run.get('n_items')}"
        )
    sc = report.get("suite_consistency") or {}
    if not sc.get("consistent", True):
        lines.append("")
        lines.append(
            f"  WARNING: these runs are from DIFFERENT suites "
            f"({', '.join(sc.get('mixed') or [])}). The aggregate below mixes "
            f"item sets and is not a single measurement; compare per-suite."
        )

    lines.append("")
    lines.append(f"Overall accuracy       : {s['n_correct']}/{s['n_total']} = {pct(s['accuracy'])}")
    lines.append(f"  over answered items  : {e['n_answered']} answered -> {pct(e['accuracy_over_answered'])}")
    lines.append(f"  strict (exact match) : {pct(s['strict_accuracy'])}")
    lines.append(f"  formatting slack     : {pct(s['format_slack'])}  "
                 f"(credit that required normalization/tolerance)")
    if "chance_baseline" in report:
        lines.append(f"  random-chance floor  : {pct(report['chance_baseline'])}  "
                     f"-> lift {pct(report['lift_over_chance'])}")
    lines.append("")

    lines.append("Match modes:")
    for mode, count in sorted(s["match_modes"].items(), key=lambda kv: -kv[1]):
        lines.append(f"  {mode:12s} {count}")
    lines.append("")

    lines.append("Error decomposition (wrong answer vs plumbing):")
    lines.append(f"  wrong answers            : {e['wrong_answers']}")
    lines.append(f"  no extractable answer    : {e['unextractable']}")
    for kind, count in sorted(e["by_kind"].items()):
        lines.append(f"  {ERROR_KIND_LABELS.get(kind, kind):25s}: {count}")
    lines.append("")

    v = report["domain_variance"]
    if v.get("n_domains"):
        lines.append("Accuracy by visual domain:")
        lines.append(f"  {'domain':18s} {'correct':>9s} {'acc':>8s} {'exact':>7s}")
        for name, d in sorted(report["by_domain"].items(), key=lambda kv: kv[1]["accuracy"]):
            lines.append(
                f"  {name:18s} {d['n_correct']:>4d}/{d['n_total']:<4d} "
                f"{pct(d['accuracy']):>8s} {d['n_exact']:>7d}"
            )
        lines.append(
            f"  spread: range {pct(v['range'])}, stdev {pct(v['stdev'])}  "
            f"(best {v['best_domain']}, worst {v['worst_domain']})"
        )
        lines.append("")

    for label, key in (
        ("MMMU subject", "by_subject"),
        ("stated difficulty", "by_difficulty"),
        ("answer type", "by_answer_type"),
    ):
        groups = report.get(key) or {}
        if len(groups) <= 1:
            continue
        lines.append(f"Accuracy by {label}:")
        for name, d in sorted(groups.items(), key=lambda kv: kv[1]["accuracy"]):
            lines.append(
                f"  {name:28s} {d['n_correct']:>3d}/{d['n_total']:<3d} {pct(d['accuracy']):>8s}"
            )
        lines.append("")

    cfg = report.get("run_config_comparison") or {}
    if len(report["runs"]) > 1:
        lines.append("Run configuration:")
        if cfg.get("differing"):
            lines.append(
                "  WARNING: these runs were NOT taken with the same settings, "
                "so the accuracy spread below is NOT model variance:"
            )
            for diff in cfg["differing"]:
                rendered = ", ".join(
                    f"{v['run']}={v['value']!r}" for v in diff["values"]
                )
                lines.append(f"    {diff['setting']}: {rendered}")
        elif cfg.get("runs_without_config"):
            lines.append(
                f"  unknown: {', '.join(cfg['runs_without_config'])} carry no "
                f"config metadata, so comparability cannot be verified"
            )
        else:
            lines.append(
                f"  all {cfg.get('compared', 0)} runs used identical settings "
                f"({', '.join(f'{k}' for k in cfg.get('settings') or [])})"
            )
        lines.append("")

    st = report["stability"]
    lines.append(f"Cross-run stability ({st['n_runs']} run(s)):")
    if st["n_items_repeated"]:
        lines.append(
            f"  repeated items {st['n_items_repeated']}: "
            f"{st['stable_correct']} always correct, "
            f"{st['stable_incorrect']} always wrong, "
            f"{len(st['flaky_items'])} flipped ({pct(st.get('flake_rate', 0.0))})"
        )
        if st.get("unmeasurable_items"):
            # These are NOT flaky answers -- they are items where at least one
            # run failed for a plumbing reason, so the comparison is void.
            lines.append(
                f"  {len(st['unmeasurable_items'])} item(s) EXCLUDED from the "
                f"flakiness count (a run was truncated/errored, so the "
                f"comparison is void):"
            )
            for item in st["unmeasurable_items"][:10]:
                lines.append(
                    f"    excluded {item['id']} ({item['domain']}): runs={item['kinds']}"
                )
        if "accuracy_spread" in st:
            lines.append(
                f"  per-run accuracy: "
                f"{', '.join(pct(a) for a in st['per_run_accuracy'])} "
                f"(spread {pct(st['accuracy_spread'])})"
            )
        for f in st["flaky_items"]:
            lines.append(
                f"    FLAKY {f['id']} ({f['domain']}): "
                f"{f['n_correct']}/{f['n_attempts']} correct, answers={f['answers']}"
            )
    else:
        lines.append("  only one run supplied -- pass several JSONL files to measure flakiness")
    lines.append("")

    if report["failures"]:
        lines.append(f"Failing items ({len(report['failures'])}):")
        for f in report["failures"]:
            tag = f" [{f['error_kind']}]" if f.get("error_kind") else ""
            where = f"{f['domain']}" + (f"/{f['subject']}" if f.get("subject") else "")
            lines.append(f"  {f['id']} ({where}){tag}")
            lines.append(f"      expected={f['expected']!r} got={f['extracted']!r}")
            if f.get("reason"):
                lines.append(f"      {f['reason']}")
    else:
        lines.append("No failing items.")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", nargs="+", help="Per-item JSONL file(s) written by check.py")
    parser.add_argument("--suite", default=None,
                        help="Manifest name to load for the random-chance baseline "
                             "(default: taken from the first records file's metadata)")
    parser.add_argument("--json", dest="json_out", default=None,
                        help="Also write the full report as JSON here")
    args = parser.parse_args()

    records, runs = load_records([Path(p) for p in args.records])
    suite = args.suite or runs[0].get("suite")

    report = build_report(records, runs, suite)
    print(render_text(report))

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"JSON report written to {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
