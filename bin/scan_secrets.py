"""Scan tracked files for credential-shaped strings, across all provider formats.

Written after a real miss: an earlier check only looked for `ghp_`/`github_pat_`,
found nothing, and reported "no secrets committed" while a live Publora key, a live
Apify token and a live Pixfaro token were sitting in `.env.example`. GitHub's own
push protection caught it. A scan that only knows one provider's format is worse
than no scan, because it returns a confident all-clear.

Usage:
  python bin/scan_secrets.py                 # scan the working tree
  python bin/scan_secrets.py --staged        # scan what git would commit
  python bin/scan_secrets.py --history       # scan every blob in every commit
  python bin/scan_secrets.py --selftest      # prove the patterns still match
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
ROOT = BIN.parent

# Anything that identifies a real credential rather than a placeholder. Ordered
# most-specific first so the reported name is the useful one.
PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("publora",   re.compile(r"sk_[A-Za-z0-9]{8,}_[A-Za-z0-9]{8,}\.[A-Za-z0-9]{20,}")),
    ("apify",     re.compile(r"apify_api_[A-Za-z0-9]{15,}")),
    ("pixfaro",   re.compile(r"pf_live_[A-Za-z0-9]{15,}")),
    ("github",    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("github-pat", re.compile(r"github_pat_[A-Za-z0-9_]{30,}")),
    ("openai",    re.compile(r"sk-[A-Za-z0-9]{40,}")),
    ("anthropic", re.compile(r"sk-ant-[A-Za-z0-9_-]{40,}")),
    ("slack",     re.compile(r"xox[baprs]-[A-Za-z0-9-]{15,}")),
    ("aws-akid",  re.compile(r"AKIA[0-9A-Z]{16}")),
    ("google-api", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("stripe",    re.compile(r"sk_live_[A-Za-z0-9]{20,}")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)

# Words that mark a value as an example rather than a credential.
PLACEHOLDER = re.compile(
    r"(your|paste|xxx|example|placeholder|redacted|here|\.\.\.|<|>|abc123|changeme|dummy)",
    re.IGNORECASE,
)

SKIP_DIRS = {".git", "__pycache__", ".pylibs", "node_modules", ".venv", "venv"}
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf", ".whl", ".pyc", ".zip"}


def scan_text(text: str, label: str) -> list[dict]:
    hits = []
    for name, pat in PATTERNS:
        for m in pat.finditer(text):
            value = m.group(0)
            if PLACEHOLDER.search(value):
                continue
            line = text.count("\n", 0, m.start()) + 1
            hits.append({
                "file": label,
                "line": line,
                "kind": name,
                "preview": value[:12] + f"... ({len(value)} chars)",
            })
    return hits


def scan_tree() -> list[dict]:
    hits = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in SKIP_SUFFIX:
            continue
        try:
            hits.extend(scan_text(p.read_text(encoding="utf-8", errors="ignore"),
                                  str(p.relative_to(ROOT))))
        except OSError:
            continue
    return hits


def scan_git(args: list[str], label: str) -> list[dict]:
    """Scan whatever `git <args>` lists: staged files, or every blob in history."""
    p = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True)
    if p.returncode != 0:
        return [{"file": label, "line": 0, "kind": "scan-error",
                 "preview": p.stderr.decode("utf-8", "replace")[:120]}]
    hits = []
    for entry in p.stdout.decode("utf-8", "replace").split("\x00"):
        if not entry.strip():
            continue
        # Formats: "sha path" (ls-tree) or ":mode sha stage\tpath" (diff --cached)
        parts = entry.split(None, 3)
        if len(parts) < 2:
            continue
        sha = parts[0] if re.fullmatch(r"[0-9a-f]{40}", parts[0]) else (parts[1] if len(parts) > 1 else "")
        path = parts[-1].strip()
        if not re.fullmatch(r"[0-9a-f]{40}", sha or ""):
            continue
        blob = subprocess.run(["git", "cat-file", "-p", sha], cwd=str(ROOT), capture_output=True).stdout
        try:
            text = blob.decode("utf-8", "ignore")
        except Exception:
            continue
        hits.extend(scan_text(text, f"{path}@{sha[:7]}"))
    return hits


# Synthetic fixtures only. An earlier version of this file pasted the operator's
# real keys in as test data, which made the scanner itself a leak. These are
# generated so they match each shape without being anyone's credential.
SELFTEST_MUST_HIT = {
    "publora": "sk_" + "testonly" + "_" + "0" * 8 + "." + "f" * 32,
    "apify": "apify_api_" + "T" * 30,
    "pixfaro": "pf_live_" + "0" * 30,
    "github": "ghp_" + "a1B2c3D4" * 5,
    "openai": "sk-" + "A1b2C3d4" * 6,
}
SELFTEST_MUST_PASS = {
    "empty": "",
    "publora placeholder": "PUBLORA_API_KEY=sk_...",
    "apify placeholder": "apify_api_your_token_here",
    "pixfaro placeholder": "pf_live_...",
    # 24 chars, below the github pattern's 30-char floor. Real classic tokens are
    # 40, so this keeps doc examples from tripping the scanner without weakening
    # detection of actual tokens.
    "github fixture": "ghp_" + "a1B2c3D4" * 3,
    "short sentinel": "sk_live",
    "prose": "The sk_ prefix is used by several providers.",
}


def selftest() -> int:
    failures = 0
    for label, value in SELFTEST_MUST_HIT.items():
        found = scan_text(value, "<fixture>")
        ok = any(h["kind"] == label for h in found)
        if not ok:
            failures += 1
        print(f"  [{'PASS' if ok else 'FAIL'}] detects {label}")
    for label, value in SELFTEST_MUST_PASS.items():
        found = scan_text(value, "<fixture>")
        ok = not found
        if not ok:
            failures += 1
        print(f"  [{'PASS' if ok else 'FAIL'}] ignores {label}"
              + (f"  (flagged {[h['kind'] for h in found]})" if not ok else ""))
    print()
    print("selftest OK" if not failures else f"selftest: {failures} failure(s)")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--staged", action="store_true", help="scan what git would commit")
    g.add_argument("--history", action="store_true", help="scan every blob in every commit")
    g.add_argument("--tracked", action="store_true", help="scan files git tracks now")
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    if args.selftest:
        return selftest()

    if args.staged:
        hits = scan_git(["diff", "--cached", "--name-only", "-z"], "staged")
        changed = subprocess.run(["git", "diff", "--cached", "--name-only", "-z"],
                                 cwd=str(ROOT), capture_output=True).stdout
        hits = []
        for name in changed.decode("utf-8", "replace").split("\x00"):
            if not name.strip():
                continue
            f = ROOT / name
            if f.is_file():
                hits.extend(scan_text(f.read_text(encoding="utf-8", errors="ignore"), name))
    elif args.history:
        hits = scan_git(["rev-list", "--objects", "--all"], "history")
    elif args.tracked:
        names = subprocess.run(["git", "ls-files", "-z"], cwd=str(ROOT),
                               capture_output=True).stdout.decode("utf-8", "replace").split("\x00")
        hits = []
        for name in names:
            if not name.strip():
                continue
            f = ROOT / name
            if f.is_file() and f.suffix.lower() not in SKIP_SUFFIX:
                hits.extend(scan_text(f.read_text(encoding="utf-8", errors="ignore"), name))
    else:
        hits = scan_tree()

    if args.json:
        print(json.dumps({"hits": hits, "count": len(hits)}, indent=2))
    else:
        if hits:
            print(f"{len(hits)} credential-shaped string(s) found:")
            for h in hits:
                print(f"  {h['file']}:{h['line']}  [{h['kind']}]  {h['preview']}")
        else:
            print("clean: no credential-shaped strings found")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
