#!/usr/bin/env python3
"""Run SD capability cases against Bespoke-Nimble-9B-v3 POST /v1/systemone.

Research-only (CC BY-NC). Reuses frida-decisions/cases_sd.json.
Remaps ranking → choice (Nimble has no ranking).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any


def remap_ranking_to_choice(request: dict[str, Any]) -> dict[str, Any]:
    """Copy request; convert type=ranking questions to choice over the same criteria."""
    out = json.loads(json.dumps(request, ensure_ascii=False))
    questions = out.get("questions") or {}
    for qid, q in list(questions.items()):
        if not isinstance(q, dict) or q.get("type") != "ranking":
            continue
        criteria = q.get("criteria")
        if isinstance(criteria, list):
            criteria_map = {str(i): str(c) for i, c in enumerate(criteria)}
        elif isinstance(criteria, dict):
            criteria_map = {str(k): str(v) for k, v in criteria.items()}
        else:
            continue
        questions[qid] = {
            "type": "choice",
            "instructions": q.get("instructions") or "Pick the best option.",
            "criteria": criteria_map,
        }
    return out


def remap_expect(expect: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, want in (expect or {}).items():
        if key.endswith(".ranking0"):
            qid = key[: -len(".ranking0")]
            out[f"{qid}.choice"] = want
        else:
            out[key] = want
    return out


def post_systemone(base: str, request: dict[str, Any], timeout: float = 180.0) -> dict[str, Any]:
    body = json.dumps(request, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{base.rstrip('/')}/v1/systemone",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    if isinstance(raw, dict) and "answers" in raw:
        return raw["answers"]
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict) and "answers" in raw["data"]:
        return raw["data"]["answers"]
    return raw


def _get(answers: dict[str, Any], qid: str) -> dict[str, Any]:
    a = answers.get(qid)
    if not isinstance(a, dict):
        raise AssertionError(f"missing answer {qid}")
    return a


def check_expect(answers: dict[str, Any], expect: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key, want in expect.items():
        if "." not in key:
            errors.append(f"bad expect key {key}")
            continue
        qid, kind = key.split(".", 1)
        a = _get(answers, qid)
        try:
            if kind == "choice":
                got = a.get("choice")
                if got != want and str(got) != str(want):
                    errors.append(f"{qid}.choice={got!r} want={want!r}")
            elif kind == "choice_in":
                got = a.get("choice")
                if got not in want and str(got) not in [str(x) for x in want]:
                    errors.append(f"{qid}.choice={got!r} not in {want!r}")
            elif kind == "noul_gt":
                got = float(a.get("noul"))
                if not (got > float(want)):
                    errors.append(f"{qid}.noul={got:.4f} want>{want}")
            elif kind == "noul_lt":
                got = float(a.get("noul"))
                if not (got < float(want)):
                    errors.append(f"{qid}.noul={got:.4f} want<{want}")
            elif kind == "score_gte":
                got = float(a.get("score"))
                if not (got >= float(want)):
                    errors.append(f"{qid}.score={got:.4f} want>={want}")
            else:
                errors.append(f"unknown expect kind {kind}")
        except (TypeError, ValueError, KeyError, IndexError) as e:
            errors.append(f"{qid}.{kind}: {e}")
    return errors


def main() -> int:
    default_cases = (
        Path(__file__).resolve().parent.parent / "frida-decisions" / "cases_sd.json"
    )
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--base",
        default=os.environ.get("NIMBLE_BASE", "http://192.168.0.175:8009"),
    )
    ap.add_argument("--cases", type=Path, default=default_cases)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--lang", choices=["all", "ru", "en"], default="all")
    ap.add_argument(
        "--gate",
        action="store_true",
        help="Exit non-zero on soft floors (RU>=50%% EN>=30%%). Default: report only.",
    )
    args = ap.parse_args()

    suite = json.loads(args.cases.read_text(encoding="utf-8"))
    cases = suite["cases"]
    if args.lang != "all":
        cases = [c for c in cases if c.get("lang") == args.lang]

    out_dir = args.out or Path(__file__).parent / f"results-cap-{time.strftime('%Y%m%d-%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    by_lang: dict[str, list[bool]] = defaultdict(list)
    by_domain: dict[str, list[bool]] = defaultdict(list)

    print(f"base={args.base} cases={len(cases)} out={out_dir} (CC BY-NC research-only)")
    for case in cases:
        cid = case["id"]
        lang = case.get("lang", "?")
        domain = case.get("domain", "?")
        t0 = time.perf_counter()
        err: str | None = None
        answers: dict[str, Any] | None = None
        try:
            req = remap_ranking_to_choice(case["request"])
            expect = remap_expect(case.get("expect") or {})
            answers = post_systemone(args.base, req)
            fails = check_expect(answers, expect)
            if fails:
                err = "; ".join(fails)
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            json.JSONDecodeError,
            AssertionError,
        ) as e:
            err = f"{type(e).__name__}: {e}"
        dt = time.perf_counter() - t0
        ok = err is None
        by_lang[lang].append(ok)
        by_domain[domain].append(ok)
        row = {
            "id": cid,
            "lang": lang,
            "domain": domain,
            "ok": ok,
            "ms": round(dt * 1000, 1),
            "error": err,
            "answers": answers,
        }
        results.append(row)
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {cid} ({lang}/{domain}) {row['ms']}ms" + (f" — {err}" if err else ""))

    (out_dir / "results.json").write_text(
        json.dumps(
            {
                "meta": {
                    **(suite.get("meta") or {}),
                    "backend": "bespoke-nimble-9b-v3",
                    "endpoint": "/v1/systemone",
                    "ranking_remap": "choice",
                    "license": "CC-BY-NC-4.0",
                    "research_only": True,
                },
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    def rate(xs: list[bool]) -> str:
        if not xs:
            return "n/a"
        return f"{sum(xs)}/{len(xs)} ({100 * sum(xs) / len(xs):.0f}%)"

    lines = [
        "# Bespoke-Nimble-9B-v3 capability suite",
        "",
        "> **License: CC BY-NC 4.0 — research-only.**",
        "",
        f"- base: `{args.base}`",
        f"- cases file: `{args.cases.name}`",
        f"- total: {rate([r['ok'] for r in results])}",
        "- note: `ranking` remapped to `choice`",
        "",
        "## By language",
    ]
    for lang in sorted(by_lang):
        lines.append(f"- **{lang}**: {rate(by_lang[lang])}")
    lines += ["", "## By domain"]
    for dom in sorted(by_domain):
        lines.append(f"- `{dom}`: {rate(by_domain[dom])}")
    lines += ["", "## Failures"]
    fails = [r for r in results if not r["ok"]]
    if not fails:
        lines.append("- none")
    else:
        for r in fails:
            lines.append(f"- `{r['id']}` ({r['lang']}): {r['error']}")
    lines += [
        "",
        "## Notes",
        "- A/B vs FRIDA-Decisions and decider-2b on the same cases_sd.json.",
        "- Soft floors when --gate: RU>=50%, EN>=30% (report always; gates optional).",
        "",
    ]
    report = "\n".join(lines)
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")
    print(report)

    if not args.gate:
        return 0
    ru = by_lang.get("ru") or []
    en = by_lang.get("en") or []
    ru_ok = (sum(ru) / len(ru) >= 0.50) if ru else True
    en_ok = (sum(en) / len(en) >= 0.30) if en else True
    if not ru_ok:
        print("GATE FAIL: RU pass rate < 50%", file=sys.stderr)
        return 1
    if not en_ok:
        print("GATE FAIL: EN pass rate < 30%", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
