#!/usr/bin/env python3
"""Model-in-the-loop checker for the qualbench `multimodal` category.

Unlike the other categories, one qualbench "task" here is a **visual
domain bucket** (charts / photos / screen-captures / diagrams / ocr /
counting / spatial / video), not a single prompt. Each bucket aggregates
the manifest items tagged with that domain and passes when the bucket's
accuracy clears the domain's threshold. That keeps the top-level
qualbench report readable (one line per domain) while still evaluating
dozens of images per run.

Usage (matching every other qualbench harness):

    python3 check.py --all --url http://192.168.0.88:8000 \
        --model qwen3.6-35b-a3b --timeout 300 --emit-artifacts
    python3 check.py charts --url http://192.168.0.88:8000

Media lives outside git (MMMU images are gigabytes). Point the checker at
it with --media-root or $QUALBENCH_MM_MEDIA_ROOT. Per-item JSONL results
are written to results/ for the variance and dashboard tools.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mm_common as mm  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE / "results"
DEFAULT_SUITE = "smoke"

# Per-domain pass thresholds (fraction of items that must be correct).
# These are *regression guards* calibrated on observed local behaviour,
# not claims about the model's absolute ability: chart/diagram reasoning
# is genuinely harder than OCR, so holding them to one flat bar would
# make the suite either trivially green or permanently red.
DEFAULT_THRESHOLDS = {
    "ocr": 0.75,
    "counting": 0.60,
    "spatial": 0.60,
    "charts": 0.50,
    "photos": 0.60,
    "screen-captures": 0.50,
    "diagrams": 0.40,
    "video": 0.40,
}
FALLBACK_THRESHOLD = 0.50
THRESHOLDS_FILE = HERE / "thresholds.json"


def load_thresholds() -> dict[str, float]:
    thresholds = dict(DEFAULT_THRESHOLDS)
    if THRESHOLDS_FILE.is_file():
        try:
            override = json.loads(THRESHOLDS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{THRESHOLDS_FILE}: invalid JSON: {exc}") from exc
        for key, value in override.items():
            if key.startswith("_"):
                continue  # documentation keys (e.g. _README)
            if key not in mm.KNOWN_DOMAINS:
                raise ValueError(
                    f"{THRESHOLDS_FILE}: {key!r} is not a known visual domain "
                    f"(known: {list(mm.KNOWN_DOMAINS)})"
                )
            try:
                threshold = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"{THRESHOLDS_FILE}: threshold for {key!r} must be a number, got {value!r}"
                ) from exc
            if not 0.0 <= threshold <= 1.0:
                raise ValueError(
                    f"{THRESHOLDS_FILE}: threshold for {key!r} must be in [0, 1], got {threshold}"
                )
            thresholds[key] = threshold
    return thresholds


def evaluate_item(
    item: dict,
    media_root: Path,
    base_url: str,
    model: str,
    timeout: int,
    max_tokens: int,
    video_frames: int,
) -> dict:
    """Run + grade one manifest item. Never raises for model-side problems."""
    t0 = time.time()
    record: dict = {
        "id": item["id"],
        "domain": item["domain"],
        "answer_type": item["answer_type"],
        "expected": str(item["answer"]),
        "extracted": "",
        "correct": False,
        "match_mode": "none",
        "reasons": [],
    }
    for optional in ("source", "subject", "question"):
        if item.get(optional):
            record[optional] = item[optional]

    try:
        media_paths = mm.resolve_media(item, media_root)
        messages = mm.build_messages(item, media_paths, video_frames=video_frames)
    except (mm.MediaMissingError, mm.VideoSupportUnavailableError) as exc:
        # A staging problem is a suite/environment error, not a model
        # failure -- flag it as such so it is never silently scored as a
        # wrong answer.
        record["reasons"] = [f"setup error: {exc}"]
        record["error"] = str(exc)
        record["error_kind"] = "setup"
        record["elapsed_s"] = round(time.time() - t0, 2)
        return record

    payload_bytes = sum(
        mm.data_url_bytes(part["image_url"]["url"])
        for part in messages[-1]["content"]
        if part.get("type") == "image_url"
    )
    record["n_images_sent"] = sum(
        1 for part in messages[-1]["content"] if part.get("type") == "image_url"
    )
    record["payload_bytes"] = payload_bytes

    try:
        response_text, meta = mm.call_model(
            base_url, model, messages, timeout, max_tokens=max_tokens
        )
    except mm.TruncatedResponseError as exc:
        record["reasons"] = [str(exc)]
        record["error"] = str(exc)
        record["error_kind"] = "truncated"
        record["elapsed_s"] = round(time.time() - t0, 2)
        return record
    except Exception as exc:  # noqa: BLE001
        record["reasons"] = [f"request failed: {exc}"]
        record["error"] = f"request failed: {exc}"
        record["error_kind"] = "request"
        record["elapsed_s"] = round(time.time() - t0, 2)
        return record

    graded = mm.grade_item(item, response_text)
    record.update(graded)
    record.update(
        {
            "finish_reason": meta.get("finish_reason"),
            "prompt_tokens": meta.get("prompt_tokens"),
            "completion_tokens": meta.get("completion_tokens"),
            "used_reasoning_content": meta.get("used_reasoning_content"),
            "response_excerpt": mm.artifact_snippet(response_text, 600),
            "elapsed_s": round(time.time() - t0, 2),
        }
    )
    return record


def make_records_writer(
    suite: str,
    model: str,
    base_url: str,
    out_path: Path | None,
    config: dict | None = None,
):
    """Open a JSONL writer that flushes each record as it is produced.

    Records are streamed rather than written at the end because a full
    MMMU run takes 1-2 hours. Buffering everything until the last item
    means a crash, a timeout or a killed process loses the entire run,
    which is a lot of GPU time to lose for want of an early flush.

    Returns `(path, write_record, close)`.
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if out_path is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = RESULTS_DIR / f"mm-{suite}-{stamp}.jsonl"
    else:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)

    header = {
        "_meta": True,
        "suite": suite,
        "model": model,
        "url": base_url,
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    # Record the run configuration so a later cross-run comparison can tell a
    # *config* change from model noise. Without this, aggregating runs taken
    # at different token budgets reports the config difference as if it were
    # nondeterminism -- which is exactly the kind of conflation this suite
    # exists to prevent.
    if config:
        header["config"] = dict(config)

    handle = path.open("w", encoding="utf-8")

    def write_record(record: dict) -> None:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")
        handle.flush()

    def close() -> None:
        handle.close()

    handle.write(json.dumps(header, ensure_ascii=True) + "\n")
    handle.flush()
    return path, write_record, close


def main() -> int:
    parser = argparse.ArgumentParser(
        description="qualbench multimodal checker (one task = one visual domain)"
    )
    parser.add_argument(
        "domain",
        nargs="?",
        help=f"Evaluate a single visual domain (one of {list(mm.KNOWN_DOMAINS)})",
    )
    parser.add_argument("--all", action="store_true", help="Evaluate every domain in the suite")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default="qwen3.6-35b-a3b")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--emit-artifacts", action="store_true")
    parser.add_argument(
        "--suite",
        default=os.environ.get("QUALBENCH_MM_SUITE", DEFAULT_SUITE),
        help=f"Manifest name under manifests/ (default: {DEFAULT_SUITE}; "
             f"override with $QUALBENCH_MM_SUITE)",
    )
    parser.add_argument(
        "--media-root",
        default=None,
        help=f"Directory manifest media paths resolve against "
             f"(default: ${mm.MEDIA_ROOT_ENV} or ./media)",
    )
    # Measured on this FP8 build, not guessed: 1024 truncated 21/60 MMMU
    # items, 2048 truncated chart reasoning mid-analysis, and 4096 still
    # truncated 12/60. Re-running those stragglers at 16384 resolved them,
    # consuming 9390, 9427 and 10421 completion tokens -- so they were never
    # reasoning loops, just genuinely long analyses. Real MMMU diagrams and
    # charts need ~10k tokens for this model to reach a conclusion.
    #
    # Cost of this default: a few items take minutes instead of seconds. The
    # alternative is scoring the model wrong for failing to finish inside a
    # budget we chose arbitrarily, which corrupts exactly the number this
    # suite exists to produce.
    parser.add_argument("--max-tokens", type=int, default=16384)
    parser.add_argument("--video-frames", type=int, default=8,
                        help="Frames sampled per video item (video suites only)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Evaluate at most N items per domain (smoke-testing aid)")
    parser.add_argument("--records-out", default=None,
                        help="Where to write the per-item JSONL (default: results/mm-<suite>-<ts>.jsonl)")
    parser.add_argument("--show-response", action="store_true")
    args = parser.parse_args()

    if not args.all and not args.domain:
        parser.error("provide a domain or --all")

    try:
        items = mm.load_manifest(args.suite)
        thresholds = load_thresholds()
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    root = mm.media_root(args.media_root)

    if args.domain:
        if args.domain not in mm.KNOWN_DOMAINS:
            parser.error(f"unknown domain {args.domain!r}; known: {list(mm.KNOWN_DOMAINS)}")
        items = [i for i in items if i["domain"] == args.domain]
        if not items:
            print(f"ERROR: suite {args.suite!r} has no items for domain {args.domain!r}",
                  file=sys.stderr)
            return 2

    domains = sorted({i["domain"] for i in items}, key=lambda d: mm.KNOWN_DOMAINS.index(d))

    try:
        records_path, write_record, close_records = make_records_writer(
            args.suite, args.model, args.url, args.records_out,
            config={
                "max_tokens": args.max_tokens,
                "video_frames": args.video_frames,
                "per_task_timeout_s": args.timeout,
                "limit": args.limit,
            },
        )
    except OSError as exc:
        print(f"ERROR: cannot open records file: {exc}", file=sys.stderr)
        return 2

    all_records: list[dict] = []
    all_passed = True

    for domain in domains:
        bucket = [i for i in items if i["domain"] == domain]
        if args.limit is not None:
            bucket = bucket[: args.limit]

        t0 = time.time()
        records = []
        for idx, item in enumerate(bucket, start=1):
            record = evaluate_item(
                item, root, args.url, args.model, args.timeout,
                args.max_tokens, args.video_frames,
            )
            records.append(record)
            write_record(record)
            # Progress goes to stderr: stdout is parsed by run_all.py and must
            # carry only PASS/FAIL, reason and ARTIFACT lines. A bucket can run
            # for many minutes, and silence that long is indistinguishable
            # from a hang -- especially with the output piped to a file.
            outcome = (
                "correct" if record["correct"]
                else (record.get("error_kind") or "wrong")
            )
            print(
                f"  [{domain} {idx}/{len(bucket)}] {item['id']}: {outcome} "
                f"({record.get('elapsed_s', 0):.1f}s)",
                file=sys.stderr,
                flush=True,
            )
        elapsed = time.time() - t0
        all_records.extend(records)

        n_total = len(records)
        n_correct = sum(1 for r in records if r["correct"])
        accuracy = (n_correct / n_total) if n_total else 0.0
        threshold = thresholds.get(domain, FALLBACK_THRESHOLD)
        setup_errors = [r for r in records if r.get("error_kind") == "setup"]

        # An un-staged dataset must not masquerade as a model regression.
        passed = bool(n_total) and not setup_errors and accuracy >= threshold

        print(f"[{'PASS' if passed else 'FAIL'}] {domain} ({elapsed:.1f}s)")

        reasons: list[str] = []
        if setup_errors:
            reasons.append(
                f"{len(setup_errors)}/{n_total} item(s) could not be evaluated "
                f"(setup/media error): {setup_errors[0]['error']}"
            )
        if not passed and n_total and not setup_errors:
            reasons.append(
                f"accuracy {n_correct}/{n_total} = {accuracy:.0%} "
                f"below threshold {threshold:.0%}"
            )
            for r in records:
                if not r["correct"]:
                    detail = r["reasons"][0] if r["reasons"] else "incorrect"
                    reasons.append(f"{r['id']}: {detail}")
        for reason in reasons:
            print(f"    - {reason}")

        if args.show_response:
            for r in records:
                print(f"    --- {r['id']} ---")
                for line in (r.get("response_excerpt") or "").splitlines():
                    print(f"    {line}")

        if args.emit_artifacts:
            summary = mm.summarize(records)
            artifact = {
                "task_id": domain,
                "category": "multimodal",
                "suite": args.suite,
                "n_items": n_total,
                "n_correct": n_correct,
                "accuracy": round(accuracy, 4),
                "threshold": threshold,
                "strict_accuracy": round(summary["strict_accuracy"], 4),
                "format_slack": round(summary["format_slack"], 4),
                "match_modes": summary["match_modes"],
                "truncated": sum(1 for r in records if r.get("error_kind") == "truncated"),
                "request_errors": sum(1 for r in records if r.get("error_kind") == "request"),
                "setup_errors": len(setup_errors),
                "total_payload_bytes": sum(r.get("payload_bytes") or 0 for r in records),
                "items": [
                    {
                        "id": r["id"],
                        "correct": r["correct"],
                        "match_mode": r["match_mode"],
                        "expected": r["expected"],
                        "extracted": r["extracted"],
                    }
                    for r in records
                ],
            }
            print(f"[ARTIFACT] {domain} {json.dumps(artifact, ensure_ascii=True)}")

        all_passed = all_passed and passed

    close_records()
    overall = mm.summarize(all_records)
    variance = mm.domain_variance(overall)
    print(
        f"  suite={args.suite} items={overall['n_total']} "
        f"accuracy={overall['accuracy']:.1%} "
        f"strict={overall['strict_accuracy']:.1%} "
        f"domain-range={variance.get('range', 0):.1%}"
    )
    print(f"  per-item records: {records_path}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
