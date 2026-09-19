#!/usr/bin/env python3
"""Shared helpers for the qualbench `multimodal` category.

This module is the single source of truth for:

* locating media (images / videos) referenced by a manifest,
* encoding media as **base64 `data:` URLs** for the OpenAI-compatible
  `/v1/chat/completions` `image_url` content part (we deliberately do NOT
  use `file://` URLs -- the eval client may run on a different host than
  the model server, e.g. inside Docker),
* building the chat request for one manifest item,
* extracting a final answer out of a reasoning model's free-text reply,
* grading that answer against ground truth at several strictness levels.

The multi-level grading is what makes the variance tooling possible: for
every item we record whether it matched `exact`ly, only after
`normalized` cleanup, or only within `numeric` tolerance. The spread
between those levels is *formatting* variance rather than *reasoning*
variance, and they are worth reporting separately.

Nothing in here talks to the network except `call_model`, and nothing
imports third-party packages beyond `requests` (plus `Pillow`, lazily,
and only for the optional synthetic-image generator).
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent

MEDIA_ROOT_ENV = "QUALBENCH_MM_MEDIA_ROOT"
DEFAULT_MEDIA_ROOT = HERE / "media"
MANIFEST_DIR = HERE / "manifests"

# Visual domains we bucket accuracy by. `run_all.py` sees one PASS/FAIL
# line per bucket, so these names double as qualbench task ids.
KNOWN_DOMAINS = (
    "charts",
    "photos",
    "screen-captures",
    "diagrams",
    "ocr",
    "counting",
    "spatial",
    "video",
)

MC_LETTERS = "ABCDEFGHIJ"

ANSWER_TYPES = ("multiple_choice", "exact", "numeric", "contains", "regex")


class MediaMissingError(RuntimeError):
    """Raised when a manifest references media that is not staged locally."""


class TruncatedResponseError(RuntimeError):
    """Raised when the server stopped generation because of the token budget."""


class VideoSupportUnavailableError(RuntimeError):
    """Raised when a video item is requested but frame extraction is not possible."""


# --------------------------------------------------------------------------
# manifests + media resolution
# --------------------------------------------------------------------------


def media_root(explicit: str | os.PathLike[str] | None = None) -> Path:
    """Resolve the directory that manifest-relative media paths hang off.

    Precedence: explicit argument > $QUALBENCH_MM_MEDIA_ROOT > ./media.
    Raw MMMU / Video-MME media is large and lives outside git (on the
    eval box under /mnt/data/qwen36-mm-eval), hence the env override.
    """
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get(MEDIA_ROOT_ENV)
    if env:
        return Path(env).expanduser().resolve()
    return DEFAULT_MEDIA_ROOT


def manifest_path(suite: str) -> Path:
    return MANIFEST_DIR / f"{suite}.jsonl"


def available_suites() -> list[str]:
    if not MANIFEST_DIR.is_dir():
        return []
    return sorted(p.stem for p in MANIFEST_DIR.glob("*.jsonl"))


def load_manifest(suite: str) -> list[dict]:
    """Read a JSONL manifest and validate every item up front.

    Failing loudly here (rather than mid-run, after minutes of inference)
    is intentional: a malformed manifest is a suite bug, not a model
    result, and must never be reported as a model failure.
    """
    path = manifest_path(suite)
    if not path.is_file():
        raise FileNotFoundError(
            f"no manifest for suite {suite!r} at {path} (available: {available_suites()})"
        )

    items: list[dict] = []
    seen_ids: set[str] = set()
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
        validate_item(item, f"{path}:{lineno}")
        if item["id"] in seen_ids:
            raise ValueError(f"{path}:{lineno}: duplicate item id {item['id']!r}")
        seen_ids.add(item["id"])
        items.append(item)

    if not items:
        raise ValueError(f"{path}: manifest is empty")
    return items


def validate_item(item: dict, where: str) -> None:
    for required in ("id", "domain", "question", "answer_type", "answer"):
        if required not in item:
            raise ValueError(f"{where}: item missing required field {required!r}")

    if item["domain"] not in KNOWN_DOMAINS:
        raise ValueError(
            f"{where}: unknown domain {item['domain']!r} (known: {list(KNOWN_DOMAINS)})"
        )
    if item["answer_type"] not in ANSWER_TYPES:
        raise ValueError(
            f"{where}: unknown answer_type {item['answer_type']!r} (known: {list(ANSWER_TYPES)})"
        )
    if not item.get("images") and not item.get("video"):
        raise ValueError(f"{where}: item has neither 'images' nor 'video'")
    if item["answer_type"] == "multiple_choice":
        options = item.get("options")
        if not isinstance(options, list) or len(options) < 2:
            raise ValueError(f"{where}: multiple_choice item needs an 'options' list of >= 2")
        if len(options) > len(MC_LETTERS):
            raise ValueError(f"{where}: at most {len(MC_LETTERS)} options supported")
        valid_letters = MC_LETTERS[: len(options)]
        for label, value in [("answer", item["answer"])] + [
            ("answer_any_of entry", a) for a in (item.get("answer_any_of") or [])
        ]:
            if str(value) not in valid_letters:
                raise ValueError(
                    f"{where}: multiple_choice {label} must be a letter in "
                    f"{valid_letters!r}, got {value!r}"
                )
    if item["answer_type"] == "regex":
        try:
            re.compile(item["answer"])
        except re.error as exc:
            raise ValueError(f"{where}: answer is not a valid regex: {exc}") from exc


def resolve_media(item: dict, root: Path) -> list[Path]:
    """Return absolute paths to every media file an item needs.

    Raises MediaMissingError listing *all* missing paths, so a single run
    tells you everything you still have to stage instead of one file at
    a time.
    """
    rel_paths = list(item.get("images") or [])
    if item.get("video"):
        rel_paths.append(item["video"])

    resolved: list[Path] = []
    missing: list[str] = []
    for rel in rel_paths:
        candidate = Path(rel)
        path = candidate if candidate.is_absolute() else (root / candidate)
        if not path.is_file():
            missing.append(str(path))
        resolved.append(path)

    if missing:
        raise MediaMissingError(
            f"missing media for item {item['id']!r}: {missing} "
            f"(media root: {root}; set ${MEDIA_ROOT_ENV} to relocate)"
        )
    return resolved


# --------------------------------------------------------------------------
# base64 data-URL encoding
# --------------------------------------------------------------------------

_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}


def guess_image_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in _MIME_BY_SUFFIX:
        return _MIME_BY_SUFFIX[suffix]
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed and guessed.startswith("image/"):
        return guessed
    raise ValueError(f"cannot determine an image MIME type for {path}")


def encode_data_url(path: Path, mime: str | None = None) -> str:
    """base64 `data:` URL for one media file.

    Used instead of `file://` on purpose: the served model resolves
    `file://` against *its own* filesystem, which breaks the moment the
    eval client runs elsewhere (another host, or a container).
    """
    mime = mime or guess_image_mime(path)
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def data_url_bytes(data_url: str) -> int:
    """Decoded payload size of a data URL, for cost/So bookkeeping."""
    _, _, b64 = data_url.partition(",")
    # every 4 base64 chars encode 3 bytes, minus padding
    padding = b64.count("=")
    return max(0, (len(b64) * 3) // 4 - padding)


# --------------------------------------------------------------------------
# video frames (pluggable; deliberately not required for the image suites)
# --------------------------------------------------------------------------


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def probe_duration_s(path: Path) -> float:
    """Clip duration in seconds via ffprobe."""
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise VideoSupportUnavailableError(
            f"ffprobe failed for {path} (code={proc.returncode}): {proc.stderr.strip()[:300]}"
        )
    try:
        return float(proc.stdout.strip())
    except ValueError as exc:
        raise VideoSupportUnavailableError(
            f"ffprobe returned an unparseable duration for {path}: {proc.stdout.strip()!r}"
        ) from exc


def frame_timestamps(duration_s: float, n_frames: int) -> list[float]:
    """Midpoints of `n_frames` equal slices of the clip.

    Sampling midpoints rather than 0..duration avoids the classic
    failure of grabbing a black first frame and an empty last frame.
    """
    if n_frames < 1:
        raise ValueError("n_frames must be >= 1")
    if duration_s <= 0:
        return [0.0] * n_frames
    step = duration_s / n_frames
    return [round(step * (i + 0.5), 3) for i in range(n_frames)]


def extract_video_frames(path: Path, n_frames: int, out_dir: Path | None = None) -> list[Path]:
    """Uniformly sample `n_frames` JPEG stills out of a video via ffmpeg.

    The served Qwen3.6 build accepts video, but Video-MME media is not
    staged yet (only its annotations are), so this path is exercised by
    unit tests and by whoever stages clips next -- it is not on the
    default suite's critical path. Kept as a narrow, documented seam so
    adding video later needs no changes to the checker.
    """
    if n_frames < 1:
        raise ValueError("n_frames must be >= 1")
    if not path.is_file():
        raise MediaMissingError(f"video not found: {path}")
    if not ffmpeg_available():
        raise VideoSupportUnavailableError(
            "ffmpeg/ffprobe not found on PATH; install ffmpeg to evaluate video items"
        )

    target = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="qualbench-frames-"))
    target.mkdir(parents=True, exist_ok=True)

    duration = probe_duration_s(path)
    frames: list[Path] = []
    for idx, ts in enumerate(frame_timestamps(duration, n_frames)):
        out_path = target / f"frame-{idx:03d}.jpg"
        proc = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-ss", str(ts), "-i", str(path),
                "-frames:v", "1", "-q:v", "2",
                str(out_path),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0 or not out_path.is_file():
            raise VideoSupportUnavailableError(
                f"ffmpeg frame extraction failed for {path} at t={ts}s "
                f"(code={proc.returncode}): {proc.stderr.strip()[:300]}"
            )
        frames.append(out_path)
    return frames


# --------------------------------------------------------------------------
# request construction
# --------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a careful visual reasoning assistant. Study the attached image(s) "
    "before answering. Reason concisely, then end your reply with a single "
    "final line of the exact form 'Answer: <answer>'."
)


def render_question(item: dict) -> str:
    """Question text plus, for multiple choice, the lettered option block."""
    parts = [item["question"].strip()]
    if item["answer_type"] == "multiple_choice":
        lines = [
            f"{MC_LETTERS[i]}. {opt}" for i, opt in enumerate(item["options"])
        ]
        parts.append("\n".join(lines))
        parts.append(
            "Respond with the letter of the correct option only, as "
            "'Answer: <letter>'."
        )
    elif item["answer_type"] == "numeric":
        parts.append("Respond with the number only, as 'Answer: <number>'.")
    else:
        parts.append("Respond as briefly as possible, as 'Answer: <answer>'.")
    return "\n\n".join(parts)


def build_messages(item: dict, media_paths: list[Path], video_frames: int = 8) -> list[dict]:
    """OpenAI-style chat messages with inline base64 image parts."""
    content: list[dict] = []

    if item.get("video"):
        video_path = media_paths[-1]
        image_paths = media_paths[:-1]
        frames = extract_video_frames(video_path, video_frames)
        image_paths = list(image_paths) + list(frames)
    else:
        image_paths = list(media_paths)

    for path in image_paths:
        content.append(
            {"type": "image_url", "image_url": {"url": encode_data_url(path)}}
        )
    content.append({"type": "text", "text": render_question(item)})

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]


def call_model(
    base_url: str,
    model: str,
    messages: list[dict],
    timeout: int,
    max_tokens: int = 1024,
    reasoning_effort: str | None = "low",
) -> tuple[str, dict]:
    """POST one chat completion; return (answer_text, metadata).

    Mirrors the truncation / `reasoning_content` handling the other
    qualbench categories already use, so a token-budget artifact is
    reported as a truncation rather than silently graded as a wrong
    answer.
    """
    payload: dict = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort

    resp = requests.post(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()

    choice = data["choices"][0]
    message = choice.get("message") or {}
    finish_reason = choice.get("finish_reason")
    usage = data.get("usage") or {}

    content = (message.get("content") or "").strip()
    reasoning = (message.get("reasoning_content") or "").strip()

    meta = {
        "finish_reason": finish_reason,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "used_reasoning_content": not content and bool(reasoning),
    }

    if finish_reason == "length":
        snippet = (content or reasoning)[:200]
        raise TruncatedResponseError(
            f"truncated: finish_reason=length (content: {snippet!r})"
        )

    return (content or reasoning), meta


# --------------------------------------------------------------------------
# answer extraction
# --------------------------------------------------------------------------

_BOXED_RE = re.compile(r"\\boxed\{([^{}]*)\}")
_ANSWER_RE = re.compile(
    r"(?:^|\n)\s*(?:\*\*)?(?:final\s+answer|answer)(?:\*\*)?\s*[:\-]\s*(.+)",
    re.IGNORECASE,
)
_MC_ONLY_RE = re.compile(r"^\(?([A-J])\)?[.:\)]?$")


def extract_answer(response_text: str, answer_type: str, n_options: int = 0) -> str:
    """Pull the model's final answer out of free-form reasoning text.

    Tries the explicit markers first (`\\boxed{}`, `Answer:`), then falls
    back to the last meaningful line. For multiple choice it additionally
    accepts a bare option letter.
    """
    text = (response_text or "").strip()
    if not text:
        return ""

    boxed = _BOXED_RE.findall(text)
    if boxed:
        return boxed[-1].strip()

    labelled = _ANSWER_RE.findall(text)
    if labelled:
        # last occurrence wins: reasoning models often restate the answer
        candidate = labelled[-1].strip()
        candidate = candidate.split("\n", 1)[0].strip()
        if candidate:
            return _strip_wrappers(candidate)

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ""

    if answer_type == "multiple_choice" and n_options:
        letters = MC_LETTERS[:n_options]
        for line in reversed(lines):
            m = _MC_ONLY_RE.match(line)
            if m and m.group(1) in letters:
                return m.group(1)
        # a trailing "... is B." style sentence
        for line in reversed(lines):
            m = re.search(rf"\b([{letters}])\b[.\)]?\s*$", line)
            if m:
                return m.group(1)

    return _strip_wrappers(lines[-1])


def resolve_choice_letter(extracted: str, n_options: int) -> tuple[str | None, bool]:
    """Resolve a multiple-choice reply to one option letter.

    Returns `(letter, ambiguous)`. `ambiguous` is True when the reply names
    several distinct in-range options ("both B and C", "B or C"): that is a
    refusal to choose, and must not be credited just because its first
    character happens to be the right letter.
    """
    text = (extracted or "").strip().upper()
    if not text:
        return None, False

    valid = set(MC_LETTERS[:n_options]) if n_options else set(MC_LETTERS)

    # A bare letter, optionally wrapped/punctuated: "B", "(B)", "B."
    bare = re.fullmatch(r"\(?([A-J])\)?[.:\)]?", text)
    if bare and bare.group(1) in valid:
        return bare.group(1), False

    # Otherwise collect standalone letter tokens mentioned in the reply.
    mentioned = [m for m in re.findall(r"\b([A-J])\b", text) if m in valid]
    distinct = list(dict.fromkeys(mentioned))
    if len(distinct) > 1:
        return None, True
    if len(distinct) == 1:
        return distinct[0], False
    return None, False


def _strip_wrappers(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^\*+|\*+$", "", value).strip()
    value = re.sub(r"^`+|`+$", "", value).strip()
    value = value.rstrip(".").strip()
    return value


# --------------------------------------------------------------------------
# normalization + grading
# --------------------------------------------------------------------------

_ARTICLES = {"a", "an", "the"}
_PUNCT_RE = re.compile(r"[^\w\s.\-/%]")
_NUMBER_RE = re.compile(r"-?\d+(?:[\d,]*\d)?(?:\.\d+)?")


def normalize_text(value: str) -> str:
    """Case/punctuation/article-insensitive form used for fuzzy matching."""
    text = (value or "").strip().lower()
    text = text.replace("\\%", "%").replace("\\$", "$")
    text = re.sub(r"\\(?:text|mathrm|mathbf)\{([^{}]*)\}", r"\1", text)
    text = text.replace("$", " ").replace("\\", " ")
    text = _PUNCT_RE.sub(" ", text)
    tokens = [t for t in text.split() if t and t not in _ARTICLES]
    return " ".join(tokens)


def parse_number(value: str) -> float | None:
    """First number in a string, tolerating thousands separators and units."""
    if value is None:
        return None
    match = _NUMBER_RE.search(str(value).replace(" ", ""))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def numbers_match(expected: float, actual: float, rel_tol: float, abs_tol: float) -> bool:
    if expected == actual:
        return True
    return abs(expected - actual) <= max(abs_tol, abs(expected) * rel_tol)


def grade_item(item: dict, response_text: str) -> dict:
    """Grade one response, recording *how* it matched.

    `match_mode` is the strictest level that accepted the answer:
      exact      -- byte-identical (after trivial wrapper stripping)
      normalized -- matched only after case/punctuation cleanup
      numeric    -- matched only as a number within tolerance
      contains / regex -- rule-based item types
      none       -- wrong
    """
    answer_type = item["answer_type"]
    n_options = len(item.get("options") or ())
    extracted = extract_answer(response_text, answer_type, n_options)
    expected = str(item["answer"])

    result = {
        "id": item["id"],
        "domain": item["domain"],
        "answer_type": answer_type,
        "expected": expected,
        "extracted": extracted,
        "correct": False,
        "match_mode": "none",
        "reasons": [],
    }
    if item.get("source"):
        result["source"] = item["source"]
    if item.get("subject"):
        result["subject"] = item["subject"]

    if not extracted:
        result["reasons"].append("could not extract any final answer from the response")
        return result

    if answer_type == "regex":
        if re.search(expected, response_text or "", re.IGNORECASE):
            result.update(correct=True, match_mode="regex")
        else:
            result["reasons"].append(f"response does not match required pattern {expected!r}")
        return result

    if answer_type == "contains":
        needles = item.get("answer_any_of") or [expected]
        hit = next(
            (n for n in needles if normalize_text(n) and normalize_text(n) in normalize_text(response_text)),
            None,
        )
        if hit is not None:
            result.update(correct=True, match_mode="contains", matched_variant=hit)
        else:
            result["reasons"].append(f"response contains none of {needles!r}")
        return result

    if answer_type == "multiple_choice":
        # `answer_any_of` lets a genuinely ambiguous item accept every
        # defensible option instead of arbitrarily crediting one. Grading a
        # model wrong for picking an equally-correct option measures the
        # fixture, not the model.
        acceptable = [expected.upper()] + [
            str(a).strip().upper() for a in (item.get("answer_any_of") or [])
        ]
        n_options = len(item.get("options") or ())
        chosen, ambiguous = resolve_choice_letter(extracted, n_options)
        if ambiguous:
            # A hedged reply ("both B and C", "B or C") is not an answer.
            # Taking its first letter would hand out full credit for
            # declining to choose, which silently inflates accuracy.
            result["reasons"].append(
                f"response does not commit to a single option: {extracted!r}"
            )
            return result
        if chosen is not None and chosen in acceptable:
            result.update(correct=True, match_mode="exact")
            return result
        # accept the option *text* as well: a model that writes out the
        # right option but omits the letter answered correctly.
        options = item.get("options") or []
        for letter in acceptable:
            idx = MC_LETTERS.index(letter) if letter in MC_LETTERS else -1
            if 0 <= idx < len(options):
                option_text = normalize_text(options[idx])
                if option_text and option_text == normalize_text(extracted):
                    result.update(correct=True, match_mode="normalized")
                    result["reasons"].append("matched option text rather than the letter")
                    return result
        wanted = expected if len(acceptable) == 1 else f"one of {acceptable}"
        result["reasons"].append(f"expected option {wanted}, got {extracted!r}")
        return result

    # exact / numeric
    variants = [expected] + list(item.get("answer_any_of") or [])

    for variant in variants:
        if extracted.strip() == str(variant).strip():
            result.update(correct=True, match_mode="exact", matched_variant=variant)
            return result

    for variant in variants:
        if normalize_text(variant) and normalize_text(variant) == normalize_text(extracted):
            result.update(correct=True, match_mode="normalized", matched_variant=variant)
            return result

    rel_tol = float(item.get("rel_tol", 0.01))
    abs_tol = float(item.get("abs_tol", 0.0))
    actual_num = parse_number(extracted)
    if actual_num is not None:
        for variant in variants:
            expected_num = parse_number(variant)
            if expected_num is not None and numbers_match(expected_num, actual_num, rel_tol, abs_tol):
                result.update(correct=True, match_mode="numeric", matched_variant=variant)
                result["reasons"].append(
                    f"matched numerically within rel_tol={rel_tol} abs_tol={abs_tol}"
                )
                return result

    if answer_type == "numeric" and actual_num is None:
        result["reasons"].append(f"no number found in extracted answer {extracted!r}")
    else:
        result["reasons"].append(f"expected {expected!r}, got {extracted!r}")
    return result


# --------------------------------------------------------------------------
# aggregation / variance
# --------------------------------------------------------------------------


def summarize(results: list[dict]) -> dict:
    """Overall + per-domain accuracy with match-mode breakdown."""
    total = len(results)
    correct = sum(1 for r in results if r.get("correct"))
    summary = {
        "n_total": total,
        "n_correct": correct,
        "accuracy": (correct / total) if total else 0.0,
        "match_modes": {},
        "domains": {},
    }

    for r in results:
        mode = r.get("match_mode", "none")
        summary["match_modes"][mode] = summary["match_modes"].get(mode, 0) + 1

    for domain in sorted({r["domain"] for r in results}):
        bucket = [r for r in results if r["domain"] == domain]
        n = len(bucket)
        n_ok = sum(1 for r in bucket if r.get("correct"))
        summary["domains"][domain] = {
            "n_total": n,
            "n_correct": n_ok,
            "accuracy": (n_ok / n) if n else 0.0,
        }

    summary["strict_accuracy"] = (
        sum(1 for r in results if r.get("match_mode") == "exact") / total if total else 0.0
    )
    summary["format_slack"] = summary["accuracy"] - summary["strict_accuracy"]
    return summary


def domain_variance(summary: dict) -> dict:
    """How unevenly accuracy is spread across visual domains.

    A model can post a respectable overall number while being useless on
    one modality (classically: fine on photos, blind on charts). The
    spread is the interesting signal, so report it explicitly instead of
    leaving it implicit in a table.
    """
    accs = [d["accuracy"] for d in summary["domains"].values()]
    if not accs:
        return {"n_domains": 0}
    out = {
        "n_domains": len(accs),
        "min": min(accs),
        "max": max(accs),
        "range": max(accs) - min(accs),
        "mean": statistics.fmean(accs),
    }
    out["stdev"] = statistics.pstdev(accs) if len(accs) > 1 else 0.0
    worst = min(summary["domains"].items(), key=lambda kv: kv[1]["accuracy"])
    best = max(summary["domains"].items(), key=lambda kv: kv[1]["accuracy"])
    out["worst_domain"] = worst[0]
    out["best_domain"] = best[0]
    return out


def artifact_snippet(text: str, limit: int = 2000) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit] + "... [truncated]"
