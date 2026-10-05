#!/usr/bin/env python3
"""Deterministic draft checks for the LinkedIn voice rules.

The interesting design decision here: these checks are **arithmetic, not
judgement**. Em-dash density, character counts, AI-vocabulary density and the
structural openers all have exact answers, and an LLM asked "is this too many em
dashes?" gives a different answer each run. So the numbers are computed here and
the model is left to do the part that actually needs taste.

That split has a second payoff: this runs with no API key, no network, and no
credentials, so the checks work even in the fully unconfigured draft-only setup.

Rules are taken from the vendored `references/voice-rules.md` and the upstream
humanizer checklists. Where a rule is a *density* rather than a ban, the
threshold is named in the output so a reviewer can disagree with it explicitly
rather than silently.

Usage:
  python bin/lint_draft.py --text "..."            # or pipe on stdin
  python bin/lint_draft.py --file draft.txt --json
  python bin/lint_draft.py --explain               # what each rule is and why
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ── thresholds ────────────────────────────────────────────────────────────────
# Each is a density or count from the vendored rules, not invented here.
EM_DASH_PER_100_WORDS = 1.0     # voice-rules.md: capped, not banned
MAX_POST_CHARS = 3000           # LinkedIn hard limit
MIN_POST_CHARS = 900            # 2026 sweet spot lower bound
MAX_POST_CHARS_SWEET = 1300     # 2026 sweet spot upper bound
MIN_COMMENT_CHARS = 200
MAX_COMMENT_CHARS = 350
MAX_COMMENT_HARD = 1250         # LinkedIn hard limit on a comment
MAX_HASHTAGS = 2
FOLD_CHARS = 210                # "see more" cutoff: the hook must land inside it

# voice-rules.md rule 3: "No AI vocabulary". These are the named offenders.
AI_VOCAB = (
    "leverage", "leveraging", "leveraged",
    "fundamentally", "fundamental",
    "streamline", "streamlined", "streamlining",
    "harness", "harnessing",
    "delve", "delving",
    "unlock", "unlocking", "unlocked",
    "foster", "fostering",
    "game-changer", "game changer", "gamechanger",
    "deep dive", "deep-dive",
    "in today's fast-paced world",
    "tapestry", "testament to", "navigate the landscape",
    "synergy", "synergies", "robust solution", "seamless", "seamlessly",
    "cutting-edge", "state-of-the-art", "paradigm shift",
    "it's worth noting", "at the end of the day",
)

# Reveal bridges: 2026 AI-tell consensus lists name these explicitly.
REVEAL_BRIDGES = (
    "here's what", "here is what", "here's how", "here is how",
    "the result?", "plot twist:", "but here's the thing",
    "let me be honest", "let's be honest", "confession:",
    "what nobody tells you", "what most people miss", "the real question is",
    "and that's when it hit me", "little did i know",
)

# Generic-frame openers that carry a measured 2026 penalty (see hook-formulas.md).
PENALISED_OPENERS = (
    "stop ", "start ", "it's not ", "its not ",
)

EM_DASH = re.compile(r"[—–]")
HASHTAG = re.compile(r"(?<!\w)#\w+")
URL = re.compile(r"https?://\S+|(?<![\w.])www\.\S+", re.IGNORECASE)
WORD = re.compile(r"[A-Za-z0-9'’$%.-]+")


def words(text: str) -> list[str]:
    return WORD.findall(text)


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


def lint(text: str, *, kind: str = "post") -> dict:
    """Return a structured report. `ok` is False when a HARD rule is broken.

    Distinguishes `errors` (would hurt: breaks a platform limit or a named
    anti-pattern) from `warnings` (density or style, where a human may
    reasonably disagree).
    """
    text = text.strip()
    w = words(text)
    paras = paragraphs(text)
    sents = sentences(text)
    word_count = len(w)
    char_count = len(text)
    lines = text.splitlines()
    first_line = lines[0].strip() if lines else ""

    errors: list[dict] = []
    warnings: list[dict] = []
    notes: list[dict] = []

    def err(rule: str, detail: str, fix: str) -> None:
        errors.append({"rule": rule, "detail": detail, "fix": fix})

    def warn(rule: str, detail: str, fix: str) -> None:
        warnings.append({"rule": rule, "detail": detail, "fix": fix})

    # ── 1. length ────────────────────────────────────────────────────────────
    if kind == "comment":
        if char_count > MAX_COMMENT_HARD:
            err(
                "comment-hard-limit",
                f"{char_count} chars; LinkedIn rejects a comment over {MAX_COMMENT_HARD}",
                "Trim to under 1,250 or split the point across two comments.",
            )
        elif char_count > MAX_COMMENT_CHARS:
            warn(
                "comment-length",
                f"{char_count} chars; the {MIN_COMMENT_CHARS}-{MAX_COMMENT_CHARS} range gets noticed",
                "One sharp insight beats three vague ones. Cut to one idea.",
            )
        elif char_count < MIN_COMMENT_CHARS:
            warn(
                "comment-length",
                f"{char_count} chars; under {MIN_COMMENT_CHARS} reads as a drive-by",
                "Add the specific detail only you could add.",
            )
    else:
        if char_count > MAX_POST_CHARS:
            err(
                "post-hard-limit",
                f"{char_count} chars; LinkedIn caps a post at {MAX_POST_CHARS}",
                "Cut. This cannot be published as-is.",
            )
        elif char_count < MIN_POST_CHARS:
            warn(
                "post-length",
                f"{char_count} chars; below the {MIN_POST_CHARS}-{MAX_POST_CHARS_SWEET} sweet spot",
                "1,000+ chars carries a reach lift. Expand the middle, don't pad the end.",
            )
        elif char_count > MAX_POST_CHARS_SWEET:
            notes.append({
                "rule": "post-length",
                "detail": f"{char_count} chars; above the {MAX_POST_CHARS_SWEET} sweet spot but a long post is allowed",
                "fix": "Only trim if the operator asked for medium, not long.",
            })

    # ── 2. the fold (first ~210 chars) ───────────────────────────────────────
    if first_line:
        if first_line.endswith("?"):
            err(
                "question-opener",
                "line 1 is a question: -34% median likes across all follower bands",
                "Invert it into the number that answers it, and move the question to the close.",
            )
        if first_line.isupper() and len(first_line) > 12:
            err(
                "all-caps-opener",
                "line 1 is all caps",
                "Carry the intensity with word choice. Caps read as shouting and undercut the claim.",
            )
        lowered = first_line.lower()
        for opener in PENALISED_OPENERS:
            if lowered.startswith(opener):
                warn(
                    "generic-frame-opener",
                    f"line 1 opens with {opener.strip()!r}, a generic frame (measured penalty in 2026)",
                    "Replace with a specific, dated fact or a number. Keep at most one contrast per post.",
                )
                break
        for bridge in REVEAL_BRIDGES:
            if lowered.startswith(bridge):
                warn(
                    "reveal-bridge",
                    f"line 1 opens with the reveal bridge {bridge!r}",
                    "Delete the bridge and start on the substance. The gap must pay off in 2 lines.",
                )
                break
        if len(first_line) < 15:
            warn(
                "thin-hook",
                f"line 1 is only {len(first_line)} chars",
                "The hook has ~210 chars before 'see more'. Use them.",
            )

    # ── 3. em dashes (density, not a ban) ────────────────────────────────────
    dash_count = len(EM_DASH.findall(text))
    if word_count:
        per100 = dash_count * 100.0 / word_count
        if per_100 := round(per100, 2):
            if per100 > EM_DASH_PER_100_WORDS * 2:
                warn(
                    "em-dash-density",
                    f"{dash_count} dashes in {word_count} words ({per_100} per 100)",
                    f"Cap is about {EM_DASH_PER_100_WORDS}/100 words. Replace most with a full stop or a comma.",
                )
            elif per100 > EM_DASH_PER_100_WORDS:
                notes.append({
                    "rule": "em-dash-density",
                    "detail": f"{dash_count} dashes in {word_count} words ({per_100} per 100), just over the cap",
                    "fix": "Probably fine. The character is not the tell; the density is.",
                })

    # ── 4. AI vocabulary ─────────────────────────────────────────────────────
    lowered_text = text.lower()
    hits = []
    for term in AI_VOCAB:
        for m in re.finditer(re.escape(term), lowered_text):
            line_no = lowered_text.count("\n", 0, m.start()) + 1
            hits.append({"term": term, "line": line_no})
    if hits:
        unique = sorted({h["term"] for h in hits})
        err(
            "ai-vocabulary",
            f"AI vocabulary present: {', '.join(unique)}",
            "Replace with the plain word, or cut. These are named in voice-rules.md rule 3.",
        )

    for bridge in REVEAL_BRIDGES:
        if bridge in lowered_text and not lowered_text.startswith(bridge):
            warn(
                "reveal-bridge",
                f"reveal bridge {bridge!r} mid-text",
                "Reveal bridges are one of the strongest 2026 tells. Delete and start on the substance.",
            )
            break

    # ── 5. structure ─────────────────────────────────────────────────────────
    if URL.search(text):
        err(
            "link-in-body",
            "an external link appears in the body",
            "Move it to the first comment. Links in the body suppress reach.",
        )
    tags = HASHTAG.findall(text)
    if len(tags) > MAX_HASHTAGS:
        warn(
            "hashtags",
            f"{len(tags)} hashtags ({', '.join(tags)})",
            f"Use 0-{MAX_HASHTAGS}, at the end.",
        )
    fragments = [s for s in sents if len(words(s)) <= 3]
    if len(fragments) > 2:
        warn(
            "staccato-fragments",
            f"{len(fragments)} standalone fragments (<=3 words): {fragments[:4]}",
            "At most 2. A stack of fragments is the staccato tell.",
        )
    long_paras = [i + 1 for i, p in enumerate(paras) if len(sentences(p)) > 4]
    if long_paras:
        warn(
            "paragraph-length",
            f"paragraph(s) {long_paras} run over 4 sentences",
            "1-2 sentence paragraphs with blank lines between them is the recommended layout.",
        )
    if len(paras) == 1 and char_count > 600:
        warn(
            "single-block",
            "one wall of text with no blank lines",
            "Double line-breaks between ideas. Single breaks do not render as spacing.",
        )
    triads = re.findall(r"\b(\w+),\s+(\w+),?\s+and\s+(\w+)\b", text)
    if len(triads) > 1:
        warn(
            "stacked-triads",
            f"{len(triads)} rule-of-three lists",
            "One triple per post maximum. More reads as a template.",
        )

    # ── 6. concrete substance ────────────────────────────────────────────────
    digits = re.findall(r"\d", text)
    if not digits:
        warn(
            "no-specifics",
            "no number anywhere in the draft",
            "Specific numbers beat adjectives. Add at least one real figure per 100 words.",
        )
    if text.count("$") == 0 and any(k in lowered_text for k in ("revenue", "cost", "price", "savings")):
        notes.append({
            "rule": "money-unquantified",
            "detail": "money is discussed but no figure appears",
            "fix": "Give the real amount. '$14,200' beats 'significant savings'.",
        })

    return {
        "kind": kind,
        "ok": not errors,
        "char_count": char_count,
        "word_count": word_count,
        "paragraph_count": len(paras),
        "sentence_count": len(sents),
        "em_dashes": dash_count,
        "em_dashes_per_100_words": round(dash_count * 100.0 / word_count, 2) if word_count else 0.0,
        "hashtags": tags,
        "errors": errors,
        "warnings": warnings,
        "notes": notes,
    }


def render(report: dict) -> str:
    out: list[str] = []
    verdict = "PASS" if report["ok"] else "BLOCK"
    out.append(f"[{verdict}] {report['kind']}  "
               f"{report['char_count']} chars, {report['word_count']} words, "
               f"{report['paragraph_count']} paragraphs, "
               f"{report['em_dashes']} em dashes "
               f"({report['em_dashes_per_100_words']}/100 words)")
    if report["errors"]:
        out.append("")
        out.append("Must fix:")
        for e in report["errors"]:
            out.append(f"  x {e['rule']}: {e['detail']}")
            out.append(f"    -> {e['fix']}")
    if report["warnings"]:
        out.append("")
        out.append("Worth a look:")
        for w in report["warnings"]:
            out.append(f"  ! {w['rule']}: {w['detail']}")
            out.append(f"    -> {w['fix']}")
    if report["notes"]:
        out.append("")
        out.append("Fine as-is, for the record:")
        for n in report["notes"]:
            out.append(f"  . {n['rule']}: {n['detail']}")
    if not (report["errors"] or report["warnings"]):
        out.append("")
        out.append("No rule violations found.")
    out.append("")
    out.append(
        "These are the arithmetic rules only. The judgement calls - does it sound "
        "like the operator, is the claim true, does the hook earn the second line - "
        "are not checkable here and are not checked."
    )
    return "\n".join(out)


EXPLAIN = """\
Rule thresholds, and where each comes from
==========================================

post length        900-1,300 chars is the default target; 3,000 is the hard
                   LinkedIn cap. A long post (1,500-1,900) is allowed if the
                   operator asked for it - 1,000+ chars carries a reach lift,
                   so this is a warning, not an error.
comment length     200-350 chars; 1,250 is the hard cap.
fold               210 chars is roughly where "see more" cuts. The hook has to
                   land inside it.
question opener    An opening question is -34% median likes. A closing question
                   is +3%. The rule is about position, not about questions.
all-caps opener    No measurement, it just reads as shouting and undercuts the
                   claim. Holds even for the emotional cold-open formula.
em dashes          Capped at about 1 per 100 words - NOT banned. The character
                   stopped being a tell; the density is the tell.
AI vocabulary      Named list from voice-rules.md rule 3, plus the 2026
                   additions. An error, not a warning: these are on the
                   published tell lists.
reveal bridges     "The result?", "Plot twist:", "Here's what", "Let me be
                   honest". 2026 consensus tells. Delete; start on substance.
generic frames     "Stop X, start Y" and "It's not X, it's Y" carry a measured
                   penalty unless they are the post's ONLY contrast.
links in body      Move to the first comment. An error here because it is
                   mechanical, not a judgement call.
hashtags           0-2, at the end.
fragments          At most 2 standalone fragments (<=3 words each).
triples            One rule-of-three per post maximum.
specifics          At least one real number. This one is a warning, not an
                   error, because a genuinely numberless post can still work -
                   but it usually means the draft is vague.

What this does NOT do
=====================
It does not detect AI authorship and does not predict any detector's score. No
edit reliably does, and the upstream humanizer says so explicitly. It checks the
rules that have exact answers and leaves the rest to a reader.
"""


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--text")
    p.add_argument("--file")
    p.add_argument("--kind", choices=("post", "comment"), default="post")
    p.add_argument("--json", action="store_true")
    p.add_argument("--explain", action="store_true")
    p.add_argument("--strict", action="store_true", help="exit non-zero on warnings too")
    args = p.parse_args(argv)

    if args.explain:
        print(EXPLAIN)
        return 0

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8", errors="replace")
    elif args.text:
        text = args.text
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        p.error("provide --text, --file, or pipe the draft on stdin")

    if not text.strip():
        p.error("the draft is empty")

    report = lint(text, kind=args.kind)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(render(report))

    if not report["ok"]:
        return 1
    if args.strict and report["warnings"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
