#!/usr/bin/env python3
"""Run FRIDA-Decisions capability cases (RU/EN, SD-focused) against POST /pooling."""

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


def post_pooling(base: str, request: dict[str, Any], timeout: float = 60.0) -> dict[str, Any]:
    body = json.dumps({"data": request}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{base.rstrip('/')}/pooling",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    return (raw.get("data") or raw).get("answers") or raw


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
                if got != want:
                    errors.append(f"{qid}.choice={got!r} want={want!r}")
            elif kind == "choice_in":
                got = a.get("choice")
                if got not in want:
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
            elif kind == "ranking0":
                ranking = a.get("ranking") or []
                # ranking may be list of keys or indices as strings
                top = ranking[0] if ranking else None
                if top != want and str(top) != str(want):
                    # also accept criteria key when ranking returns indices
                    probs = a.get("probabilities") or {}
                    if isinstance(probs, dict) and probs:
                        top_key = max(probs.items(), key=lambda kv: float(kv[1]))[0]
                        if top_key != want and str(top_key) != str(want):
                            errors.append(
                                f"{qid}.ranking0={top!r}/{top_key!r} want={want!r}"
                            )
                    else:
                        errors.append(f"{qid}.ranking0={top!r} want={want!r}")
            else:
                errors.append(f"unknown expect kind {kind}")
        except (TypeError, ValueError, KeyError, IndexError) as e:
            errors.append(f"{qid}.{kind}: {e}")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--base",
        default=os.environ.get("FRIDA_BASE", "http://192.168.0.175:8006"),
    )
    ap.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).with_name("cases_sd.json"),
    )
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--lang", choices=["all", "ru", "en"], default="all")
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

    print(f"base={args.base} cases={len(cases)} out={out_dir}")
    for case in cases:
        cid = case["id"]
        lang = case.get("lang", "?")
        domain = case.get("domain", "?")
        t0 = time.perf_counter()
        err: str | None = None
        answers: dict[str, Any] | None = None
        try:
            answers = post_pooling(args.base, case["request"])
            fails = check_expect(answers, case.get("expect") or {})
            if fails:
                err = "; ".join(fails)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, AssertionError) as e:
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
        json.dumps({"meta": suite.get("meta"), "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    def rate(xs: list[bool]) -> str:
        if not xs:
            return "n/a"
        return f"{sum(xs)}/{len(xs)} ({100 * sum(xs) / len(xs):.0f}%)"

    lines = [
        "# FRIDA-Decisions capability suite",
        "",
        f"- base: `{args.base}`",
        f"- cases file: `{args.cases.name}`",
        f"- total: {rate([r['ok'] for r in results])}",
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
        "- RU is the primary language of FRIDA-Decisions; EN is nominal (~57% JevBench per authors).",
        "- SD cases map to Jev coding-agent surfaces: model routing, tool choice, risk gate, PR gate, loop detect, RAG rank, injection.",
        "",
    ]
    report = "\n".join(lines)
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")
    print(report)

    # Gates: RU must be strong; EN soft floor (model is RU-first).
    ru = by_lang.get("ru") or []
    en = by_lang.get("en") or []
    ru_ok = (sum(ru) / len(ru) >= 0.85) if ru else True
    en_ok = (sum(en) / len(en) >= 0.50) if en else True
    if not ru_ok:
        print("GATE FAIL: RU pass rate < 85%", file=sys.stderr)
        return 1
    if not en_ok:
        print("GATE FAIL: EN pass rate < 50% (soft floor for nominal EN)", file=sys.stderr)
        return 1
    if not all(r["ok"] for r in results if r["lang"] == "ru"):
        # still exit 1 if any RU hard fail even if rate math somehow ok
        print("GATE FAIL: one or more RU cases failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
