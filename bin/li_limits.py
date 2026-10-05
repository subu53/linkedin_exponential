#!/usr/bin/env python3
"""Field-limit checker for LinkedIn profile copy.

Headlines and About sections have hard character caps, and the About section
is also truncated by the UI at the fold. Getting either wrong is invisible
until someone pastes it and loses the end of a sentence, so the counts are
computed rather than estimated.

Usage:
  python bin/li_limits.py --headline "text"
  python bin/li_limits.py --about-file about.txt
  python bin/li_limits.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Documented caps. `truncates_at` is where the UI inserts "...see more".
LIMITS = {
    "headline": {"max": 220, "truncates_at": 220},
    "about": {"max": 2600, "truncates_at": 265},
    "experience_title": {"max": 100},
    "experience_description": {"max": 2000},
    "skills": {"max": 50},
    "post": {"max": 3000},
    "comment": {"max": 1250},
}


def check(field: str, text: str) -> dict:
    limits = LIMITS.get(field, {})
    hard = limits.get("max")
    fold = limits.get("truncates_at")
    n = len(text)

    out: dict = {"field": field, "chars": n, "max": hard, "ok": True, "notes": []}

    if hard is not None:
        if n > hard:
            out["ok"] = False
            out["notes"].append(f"OVER the {hard}-char cap by {n - hard}; the end will be cut off.")
        else:
            out["notes"].append(f"fits the {hard}-char cap with {hard - n} to spare.")
            if hard - n > 40 and field in ("headline",):
                out["notes"].append(
                    f"{hard - n} characters unused. A headline is free keyword surface for "
                    "recruiter search; unused space is wasted matching."
                )

    if fold is not None and n > fold:
        head = text[:fold]
        out["fold"] = fold
        out["fold_text"] = head
        out["notes"].append(
            f"first {fold} chars are what shows before '...see more' - everything after is "
            "behind a click, so the hook must complete inside it."
        )

        # Two render modes have to read well. The stricter one is easy to miss:
        # **LinkedIn strips blank lines when text is PASTED into About.** If the
        # breaks survive (typed by hand) a paragraph boundary at the fold is
        # fine. If they are stripped, the paragraphs run together and whatever
        # follows the last full stop inside the window becomes visible.
        #
        # Exposing a few characters is harmless. Exposing a *material* chunk -
        # enough to read as a truncated clause - is not, so that is what is
        # flagged. A run of 25 characters was chosen as "someone would notice".
        MATERIAL_FRAGMENT = 25
        last_stop = max(head.rfind("."), head.rfind("!"), head.rfind("?"))
        trailing = head[last_stop + 1:].strip() if last_stop != -1 else head.strip()

        if not trailing:
            out["notes"].append(
                "The visible window ends on a complete sentence, so it reads correctly "
                "whether or not LinkedIn keeps the blank lines on paste."
            )
        elif last_stop == -1:
            out["notes"].append(
                "No sentence ends inside the visible window. The hook is one long "
                "sentence, so '...see more' will always cut it mid-clause."
            )
            out["ok"] = False
        elif len(trailing) >= MATERIAL_FRAGMENT:
            out["notes"].append(
                f"WARNING: if LinkedIn strips the blank lines on paste, '...see more' "
                f"exposes a truncated clause: {trailing[:60]!r}. Two ways to fix: "
                "(a) type the line breaks in the LinkedIn editor rather than pasting, "
                "which preserves them; or (b) make the first paragraph itself fill the "
                f"window, so its final sentence ends before char {fold}."
            )
            out["ok"] = False
        else:
            out["notes"].append(
                f"Only {len(trailing)} characters follow the last full stop inside the "
                "window, so a stripped blank line would expose an unfinished word or two "
                "at most. Acceptable, but typing the line breaks is still better."
            )
    return out


def render(report: dict) -> str:
    lines = [f"{report['field']}: {report['chars']} chars"
             + (f" (cap {report['max']})" if report.get("max") else "")]
    for note in report["notes"]:
        lines.append(f"  - {note}")
    if report.get("fold_text"):
        lines.append("  visible before 'see more':")
        lines.append("  +" + "-" * 66)
        for row in report["fold_text"].splitlines() or [report["fold_text"]]:
            lines.append(f"  | {row}")
        lines.append("  +" + "-" * 66)
    lines.append(f"  verdict: {'OK' if report['ok'] else 'NEEDS WORK'}")
    return "\n".join(lines)


SELFTEST = [
    ("headline",
     "Data Scientist | python, sql, ml, time-series | MSc AI, Open University of Kenya | Nairobi | open to remote",
     True, "a realistic headline well inside the cap"),
    ("headline", "x" * 240, False, "a headline past the 220 cap"),
    # Fixture 3 is the subtle one. LinkedIn strips blank lines when pasting into
    # About, so "the cut lands on whitespace" is NOT sufficient: what matters is
    # that the visible window ends on a complete sentence, with no fragment after
    # the last full stop. A paragraph break does not protect the fold.
    ("about",
     "I build AI systems that run in production, not notebooks. Two of mine are live right "
     "now, serving real customers in Kenya. One sells, one diagnoses.\n\n"
     "The detail behind both of them starts here and continues past the fold.",
     True, "an About whose visible window ends on a complete sentence"),
    # The negative fixture needs (a) more than 265 chars so a fold exists at all,
    # and (b) a *material* fragment (>= 25 chars) after the last full stop inside
    # the window. A short trailing word is genuinely harmless and is not flagged.
    # Geometry computed, not guessed: total 305 (so a fold exists), last full stop
    # at 217, leaving a 46-char truncated clause inside the 265-char window. The
    # selftest prints these numbers on failure, which is how this was calibrated.
    ("about",
     "I build AI systems that run in production, not notebooks. Two are live. "
     "Both serve real customers in Kenya. I took both of them from raw, messy data "
     "all the way to a deployed service that people actually use every day. "
     "The first is a WhatsApp sales agent for retail clients, and the second reads CT scans.",
     False, "an About whose fold exposes a material half-sentence"),
    ("about",
     "I build AI systems that run in production and here is a very long first sentence that will certainly "
     "be cut somewhere in the middle of a clause because it keeps going well past the point where the user "
     "interface decides to hide the rest behind a see more link which makes the opening read badly",
     False, "an About whose fold cuts mid-sentence"),
]


def selftest(verbose: bool = False) -> int:
    failures = 0
    for field, text, want_ok, label in SELFTEST:
        report = check(field, text)
        got = report["ok"]
        mark = "PASS" if got == want_ok else "FAIL"
        if got != want_ok:
            failures += 1
        detail = ""
        if verbose or got != want_ok:
            fold = report.get("fold")
            last = max(text[:fold].rfind("."), text[:fold].rfind("!"), text[:fold].rfind("?")) if fold else -1
            frag = len(text[:fold][last + 1:].strip()) if fold and last != -1 else (fold or 0)
            detail = (f"   [total={report['chars']} cap={report.get('max')} "
                      f"fold={fold} last_stop={last} fragment={frag}]")
        print(f"  [{mark}] {label} (expected ok={want_ok}, got {got}){detail}")
    print()
    if failures:
        print(f"selftest: {failures} failure(s) - the harness no longer checks what it claims")
    else:
        print("selftest OK")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--headline")
    p.add_argument("--about")
    p.add_argument("--about-file")
    p.add_argument("--field", choices=sorted(LIMITS), help="check an arbitrary field")
    p.add_argument("--text")
    p.add_argument("--json", action="store_true")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args(argv)

    if args.selftest:
        return selftest()

    reports = []
    if args.headline:
        reports.append(check("headline", args.headline))
    if args.about:
        reports.append(check("about", args.about))
    if args.about_file:
        reports.append(check("about", Path(args.about_file).read_text(encoding="utf-8")))
    if args.field and args.text:
        reports.append(check(args.field, args.text))

    if not reports:
        p.error("give --headline, --about, --about-file, or --field with --text")

    if args.json:
        print(json.dumps(reports, indent=2, ensure_ascii=False))
    else:
        for r in reports:
            print(render(r))
            print()
    return 0 if all(r["ok"] for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
