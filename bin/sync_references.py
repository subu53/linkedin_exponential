#!/usr/bin/env python3
"""Regenerate the per-skill copies of the shared approval/voice reference.

## Why copies exist at all

A skill gets installed at a directory depth this project does not control - one
level under a project root, three levels under a home directory. A relative path
like `../../references/approval-and-voice.md` therefore resolves to a different
place depending on that depth, and a dangling reference is worse than a missing
skill: the agent reads half the instructions and improvises the rest.

So each skill carries its own copy at `skills/<skill>/references/approval-and-voice.md`,
and the bundle keeps the canonical file at `references/approval-and-voice.md`.
This script is what keeps them identical.

Usage:
  python bin/sync_references.py            # report drift and fix it
  python bin/sync_references.py --check    # report only; exit 1 if any differ
  python bin/sync_references.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
ROOT = BIN.parent
CANONICAL = ROOT / "references" / "approval-and-voice.md"
SKILLS = ROOT / "skills"
TARGET_NAME = "approval-and-voice.md"


def skill_dirs() -> list[Path]:
    if not SKILLS.is_dir():
        return []
    return sorted(p for p in SKILLS.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--check", action="store_true", help="report only; write nothing")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    if not CANONICAL.is_file():
        print(f"canonical reference not found: {CANONICAL}", file=sys.stderr)
        return 3

    canonical = CANONICAL.read_text(encoding="utf-8")
    results = []
    for skill in skill_dirs():
        target = skill / "references" / TARGET_NAME
        if not target.is_file():
            state = "missing"
        elif target.read_text(encoding="utf-8") == canonical:
            state = "identical"
        else:
            state = "differs"

        if state != "identical" and not args.check:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(canonical, encoding="utf-8")
            state = f"{state} -> synced"

        results.append({"skill": skill.name, "state": state})

    drifted = [r for r in results if not r["state"].startswith("identical")]

    if args.json:
        print(json.dumps({"canonical_chars": len(canonical), "results": results,
                          "drifted": len(drifted)}, indent=2))
    else:
        print(f"canonical: {CANONICAL.relative_to(ROOT)} ({len(canonical)} chars)")
        for r in results:
            mark = "ok  " if r["state"].startswith("identical") else "SYNC"
            print(f"  [{mark}] {r['skill']:<28} {r['state']}")
        print()
        if args.check and drifted:
            print(f"{len(drifted)} skill(s) out of date. Run without --check to fix.")
        elif drifted:
            print(f"{len(drifted)} skill copy(ies) updated.")
        else:
            print(f"All {len(results)} skill copies are identical to the canonical file.")

    return 1 if (args.check and drifted) else 0


if __name__ == "__main__":
    raise SystemExit(main())
