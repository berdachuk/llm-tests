#!/usr/bin/env python3
"""Build a qualbench multimodal manifest from the MMMU HF parquet snapshot.

Run this **on the box that holds the dataset** (the images are gigabytes
and stay outside git):

    python3 prep_mmmu.py \
        --mmmu-root /mnt/data/qwen36-mm-eval/raw/MMMU-hf \
        --media-root /mnt/data/qwen36-mm-eval/media \
        --out manifests/mmmu-subset.jsonl

It writes two things:

* extracted PNG/JPEG files under `<media-root>/mmmu/<subject>/` -- heavy,
  stays out of git;
* a JSONL manifest (one line per item) -- small, **committed** to git so
  the exact evaluated subset is reproducible and reviewable.

Sampling is stratified by **visual domain** (charts / photos /
screen-captures / diagrams), because that is the axis accuracy is
reported on and each bucket needs enough items to mean anything. Within a
domain, items are drawn round-robin across MMMU subjects so no single
subject dominates a bucket. Selection is seeded and therefore
reproducible.

Only the `validation` split is used: it is the split with public
ground-truth answers (MMMU's `test` split answers are withheld), so it is
the only one we can grade locally.
"""
from __future__ import annotations

import argparse
import ast
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

# MMMU `img_type` label -> our visual-domain bucket. Anything unmapped is
# skipped rather than guessed at, so the buckets stay meaningful.
IMG_TYPE_TO_DOMAIN = {
    # data visualisations and tabular reads
    "Plots and Charts": "charts",
    "Tables": "charts",
    "Historical Timelines": "charts",
    # real-world / captured imagery
    "Photographs": "photos",
    "Paintings": "photos",
    "Portraits": "photos",
    "Landscapes": "photos",
    "Sculpture": "photos",
    "Medical Images": "photos",
    "Microscopic Images": "photos",
    "Pathological Images": "photos",
    "Body Scans: MRI, CT scans, and X-rays": "photos",
    # screen-rendered / synthetic graphics
    "Screenshots": "screen-captures",
    "Poster": "screen-captures",
    "Advertisements": "screen-captures",
    "Logos and Branding": "screen-captures",
    "Icons and Symbols": "screen-captures",
    "Comics and Cartoons": "screen-captures",
    # schematic / structural figures
    "Diagrams": "diagrams",
    "Technical Blueprints": "diagrams",
    "Trees and Graphs": "diagrams",
    "Geometric Shapes": "diagrams",
    "Chemical Structures": "diagrams",
    "Mathematical Notations": "diagrams",
    "Sheet Music": "diagrams",
    "Maps": "diagrams",
}

DEFAULT_TARGETS = {
    "charts": 16,
    "photos": 16,
    "diagrams": 16,
    "screen-captures": 12,
}

IMAGE_COLUMNS = [f"image_{i}" for i in range(1, 8)]
SPLIT = "validation"


def parse_list_field(raw: str | None) -> list[str]:
    """MMMU stores lists as Python-literal strings (e.g. "['Tables']")."""
    if not raw:
        return []
    try:
        value = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return [raw.strip()]
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value]
    return [str(value).strip()]


def classify(img_types: list[str]) -> str | None:
    """Map an item's img_type labels to exactly one bucket.

    First mapped label wins; MMMU lists them in figure order, so the
    leading label describes the primary figure.
    """
    for label in img_types:
        domain = IMG_TYPE_TO_DOMAIN.get(label)
        if domain:
            return domain
    return None


def image_suffix(data: bytes, declared_path: str | None) -> str:
    """Pick a file extension from magic bytes, falling back to the name."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data.startswith(b"GIF8"):
        return ".gif"
    if data.startswith(b"BM"):
        return ".bmp"
    if declared_path:
        suffix = Path(declared_path).suffix.lower()
        if suffix:
            return suffix
    return ".png"


def collect_candidates(mmmu_root: Path) -> list[dict]:
    """Read every subject's validation parquet into candidate records."""
    import pyarrow.parquet as pq  # local import: only prep needs pyarrow

    subject_dirs = sorted(p for p in mmmu_root.iterdir() if p.is_dir())
    if not subject_dirs:
        raise SystemExit(f"no subject directories under {mmmu_root}")

    candidates: list[dict] = []
    for subject_dir in subject_dirs:
        parquet = subject_dir / f"{SPLIT}-00000-of-00001.parquet"
        if not parquet.is_file():
            matches = sorted(subject_dir.glob(f"{SPLIT}-*.parquet"))
            if not matches:
                print(f"  skip {subject_dir.name}: no {SPLIT} parquet", file=sys.stderr)
                continue
            parquet = matches[0]

        columns = [
            "id", "question", "options", "answer",
            "img_type", "question_type", "subfield", "topic_difficulty",
        ] + IMAGE_COLUMNS
        table = pq.read_table(parquet, columns=columns)
        rows = table.to_pylist()

        for row in rows:
            # Only multiple-choice items are gradeable without an LLM
            # judge; MMMU's open items expect free-form prose that a
            # deterministic checker cannot score fairly.
            if row.get("question_type") != "multiple-choice":
                continue
            options = parse_list_field(row.get("options"))
            if len(options) < 2:
                continue
            answer = (row.get("answer") or "").strip()
            if len(answer) != 1 or not answer.isalpha():
                continue
            if ord(answer.upper()) - ord("A") >= len(options):
                continue

            domain = classify(parse_list_field(row.get("img_type")))
            if domain is None:
                continue

            images = [
                (col, row[col]) for col in IMAGE_COLUMNS
                if isinstance(row.get(col), dict) and row[col].get("bytes")
            ]
            if not images:
                continue

            candidates.append(
                {
                    "mmmu_id": row["id"],
                    "subject": subject_dir.name,
                    "subfield": row.get("subfield"),
                    "difficulty": row.get("topic_difficulty"),
                    "domain": domain,
                    "question": row["question"],
                    "options": options,
                    "answer": answer.upper(),
                    "images": images,
                }
            )

    return candidates


def stratified_sample(candidates: list[dict], targets: dict[str, int], seed: int) -> list[dict]:
    """Take `targets[domain]` items per domain, round-robin across subjects."""
    rng = random.Random(seed)

    by_domain: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for cand in candidates:
        by_domain[cand["domain"]][cand["subject"]].append(cand)

    selected: list[dict] = []
    for domain, want in sorted(targets.items()):
        subjects = by_domain.get(domain, {})
        if not subjects:
            print(f"  WARNING: no candidates for domain {domain!r}", file=sys.stderr)
            continue

        pools = {}
        for subject, items in subjects.items():
            shuffled = list(items)
            rng.shuffle(shuffled)
            pools[subject] = shuffled

        order = sorted(pools)
        rng.shuffle(order)

        picked: list[dict] = []
        while len(picked) < want and any(pools[s] for s in order):
            for subject in order:
                if len(picked) >= want:
                    break
                if pools[subject]:
                    picked.append(pools[subject].pop())

        if len(picked) < want:
            print(
                f"  WARNING: domain {domain!r} wanted {want} items, only {len(picked)} available",
                file=sys.stderr,
            )
        selected.extend(picked)

    selected.sort(key=lambda c: (c["domain"], c["subject"], c["mmmu_id"]))
    return selected


def write_media_and_manifest(
    selected: list[dict],
    media_root: Path,
    out_path: Path,
    dry_run: bool,
) -> dict:
    counters: dict[str, int] = defaultdict(int)
    lines: list[str] = []
    total_bytes = 0

    for cand in selected:
        counters[cand["domain"]] += 1
        idx = counters[cand["domain"]]
        item_id = f"{cand['domain']}-{idx:02d}-{cand['subject'].lower()}"

        rel_paths: list[str] = []
        for n, (_col, blob) in enumerate(cand["images"], start=1):
            data = blob["bytes"]
            suffix = image_suffix(data, blob.get("path"))
            rel = Path("mmmu") / cand["subject"] / f"{cand['mmmu_id']}-{n}{suffix}"
            dest = media_root / rel
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
            total_bytes += len(data)
            rel_paths.append(rel.as_posix())

        item = {
            "id": item_id,
            "domain": cand["domain"],
            "source": f"MMMU/{SPLIT}/{cand['mmmu_id']}",
            "subject": cand["subject"],
            "subfield": cand["subfield"],
            "difficulty": cand["difficulty"],
            "images": rel_paths,
            "question": cand["question"],
            "answer_type": "multiple_choice",
            "options": cand["options"],
            "answer": cand["answer"],
        }
        lines.append(json.dumps(item, ensure_ascii=False))

    if not dry_run:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        header = (
            f"# qualbench multimodal manifest -- MMMU {SPLIT} subset\n"
            f"# {len(lines)} items; media paths are relative to $QUALBENCH_MM_MEDIA_ROOT\n"
            f"# regenerate with: python3 prep_mmmu.py --mmmu-root <dir> --media-root <dir>\n"
        )
        out_path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")

    return {
        "n_items": len(lines),
        "per_domain": dict(counters),
        "media_bytes": total_bytes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mmmu-root", required=True,
                        help="MMMU HF snapshot dir (one subdirectory per subject)")
    parser.add_argument("--media-root", required=True,
                        help="Where to write extracted images (keep outside git)")
    parser.add_argument("--out", default=str(HERE / "manifests" / "mmmu-subset.jsonl"),
                        help="Manifest output path (commit this)")
    parser.add_argument("--seed", type=int, default=20260919,
                        help="Sampling seed; changing it changes the subset")
    parser.add_argument("--targets", default=None,
                        help='JSON overriding per-domain counts, e.g. \'{"charts": 20}\'')
    parser.add_argument("--dry-run", action="store_true",
                        help="Report the selection without writing anything")
    args = parser.parse_args()

    targets = dict(DEFAULT_TARGETS)
    if args.targets:
        targets.update({k: int(v) for k, v in json.loads(args.targets).items()})

    mmmu_root = Path(args.mmmu_root).expanduser().resolve()
    if not mmmu_root.is_dir():
        raise SystemExit(f"--mmmu-root is not a directory: {mmmu_root}")

    print(f"Reading MMMU {SPLIT} split from {mmmu_root} ...")
    candidates = collect_candidates(mmmu_root)
    print(f"  {len(candidates)} gradeable multiple-choice candidates")
    by_domain: dict[str, int] = defaultdict(int)
    for c in candidates:
        by_domain[c["domain"]] += 1
    for domain in sorted(by_domain):
        print(f"    {domain:16s} {by_domain[domain]:4d} available")

    selected = stratified_sample(candidates, targets, args.seed)
    print(f"Selected {len(selected)} items (seed={args.seed})")

    stats = write_media_and_manifest(
        selected,
        Path(args.media_root).expanduser().resolve(),
        Path(args.out).expanduser().resolve(),
        args.dry_run,
    )
    print(
        f"  per-domain: {stats['per_domain']}\n"
        f"  media: {stats['media_bytes'] / 1e6:.1f} MB"
        f"{' (dry run, nothing written)' if args.dry_run else ''}"
    )
    if not args.dry_run:
        print(f"  manifest: {args.out}")
        print(f"  media root: {args.media_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
