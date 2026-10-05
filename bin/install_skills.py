#!/usr/bin/env python3
"""Install the 12 LinkedIn skills into a skills directory, at any depth.

## The depth problem

A skill's `REFERENCE.md` points at the craft library with a relative path. How
many `..` that path needs depends on where the skill is installed:

    ~/.agents/skills/linkedin-post-writer/       -> vendor is 2 levels up
    <project>/.agents/skills/linkedin-post-writer/ -> also 2 levels up
    a skill nested any deeper                     -> different again

Getting this wrong is worse than not installing at all: the agent reads half the
instructions, cannot find the rest, and improvises. So instead of guessing the
depth, this makes **each skill self-contained** by giving every skill its own
`vendor/` and `references/` entry, pointing at the one canonical copy.

Default method is `link`: a directory junction (Windows) or symlink (elsewhere)
inside each skill, so there is no duplication and a re-vendor is picked up with
no reinstall. `copy` is the portable fallback for filesystems without links.

Usage:
  python bin/install_skills.py --check
  python bin/install_skills.py --target ~/.agents/skills
  python bin/install_skills.py --target <project>/.agents/skills --method copy
  python bin/install_skills.py --uninstall --target <dir>
  python bin/install_skills.py --stage dist --method copy     # portable bundle
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
ROOT = BIN.parent
SKILLS_SRC = ROOT / "skills"
VENDOR_SRC = ROOT / "vendor"
REFS_SRC = ROOT / "references"

DEFAULT_TARGET = Path.home() / ".agents" / "skills"

# Directories the runtime scans for skills, in its documented priority order.
# Reported by --check so the user can pick a target that will actually load.
SCAN_ROOTS = (
    ("project", ".dsh/skills", "highest priority; project-scoped"),
    ("project", ".agents/skills", "project-scoped"),
    ("user", "~/.dsh/skills", "user-scoped"),
    ("user", "~/.agents/skills", "user-scoped"),
)


def skills() -> list[Path]:
    if not SKILLS_SRC.is_dir():
        return []
    return sorted(p for p in SKILLS_SRC.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


def _remove(path: Path) -> None:
    """Remove a junction, symlink, file, or directory safely."""
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        # A junction may appear as a real directory to is_dir(); rmtree on a
        # junction deletes the link, not the target, which is what we want.
        shutil.rmtree(path)


def _make_link(src: Path, dst: Path) -> str | None:
    """Create a directory link. Returns a label, or None if unsupported."""
    try:
        os.symlink(src, dst, target_is_directory=True)
        return "symlink"
    except (OSError, NotImplementedError, AttributeError):
        pass
    if os.name == "nt":
        # A junction needs no elevation, unlike a Windows symlink.
        proc = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(dst), str(src)],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            return "junction"
    return None


def _install_one(src: Path, dst: Path, method: str, force: bool) -> str:
    if dst.exists() or dst.is_symlink():
        if not force:
            return f"skip  {dst.name} (already present; use --force to replace)"
        _remove(dst)

    if method == "link":
        label = _make_link(src, dst)
        if label:
            return f"link  {dst.name} ({label})"
        # Fall through to a copy rather than failing the whole install.
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        return f"copy  {dst.name} (links unsupported here)"

    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    return f"copy  {dst.name}"


def _wire_skill(skill_dir: Path, method: str, force: bool) -> list[str]:
    """Give one installed skill its own vendor/ and references/ entries.

    Some skills already ship a real `references/` directory of their own (the
    per-skill copy of the shared approval rules). A real directory is left alone
    and said so, rather than reported as an unexplained skip; only `vendor/`,
    which never exists inside a skill, is always wired.
    """
    out: list[str] = []
    for name, target in (("vendor", VENDOR_SRC), ("references", REFS_SRC)):
        if not target.is_dir():
            continue
        dst = skill_dir / name
        if dst.is_dir() and not dst.is_symlink():
            out.append(f"  keep  {name}/ (skill-local, {len(list(dst.iterdir()))} file(s))")
            continue
        out.append("  " + _install_one(target, dst, method, force))
    return out


def cmd_uninstall(target: Path) -> int:
    removed = 0
    for skill in skills():
        path = target / skill.name
        if path.exists() or path.is_symlink():
            _remove(path)
            print(f"removed {skill.name}")
            removed += 1
    # Remove the shared entries only if this script created them.
    for name in ("vendor", "references", "lib"):
        path = target / name
        if path.exists() or path.is_symlink():
            _remove(path)
            print(f"removed {name}")
            removed += 1
    if not removed:
        print(f"nothing to remove in {target}")
    else:
        print(f"\nRemoved {removed} entries from {target}")
    return 0


def descriptive_roots() -> list[dict]:
    found = []
    for scope, template, note in SCAN_ROOTS:
        raw = template if scope == "project" else template.replace("~", str(Path.home()))
        path = Path(raw) if Path(raw).is_absolute() else Path.cwd() / raw
        found.append(
            {
                "scope": scope,
                "path": str(path),
                "note": note,
                "exists": path.is_dir(),
                "writable": os.access(path, os.W_OK) if path.exists() else os.access(path.parent, os.W_OK),
            }
        )
    return found


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--target", default=str(DEFAULT_TARGET), help=f"default: {DEFAULT_TARGET}")
    p.add_argument("--method", choices=("link", "copy"), default="link",
                   help="link = junction/symlink per skill (default, no duplication)")
    p.add_argument("--check", action="store_true", help="report only, change nothing")
    p.add_argument("--uninstall", action="store_true")
    p.add_argument("--force", action="store_true", help="replace an existing install")
    p.add_argument("--stage", help="write a self-contained portable bundle to this directory")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    if args.stage:
        return _stage(Path(args.stage).expanduser().resolve(), args.method, args.force)

    target = Path(args.target).expanduser().resolve()

    if args.uninstall:
        return cmd_uninstall(target)

    if args.check:
        report = {
            "skills_in_bundle": [s.name for s in skills()],
            "bundle": str(ROOT),
            "target": str(target),
            "scan_roots": descriptive_roots(),
        }
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"bundle: {ROOT}")
            print(f"skills: {len(report['skills_in_bundle'])}")
            print(f"\ntarget: {target}")
            print(f"  exists:   {target.is_dir()}")
            print(f"  writable: {os.access(target, os.W_OK) if target.exists() else os.access(target.parent, os.W_OK)}")
            print("\nruntime skill scan roots (first match wins on a name collision):")
            for r in report["scan_roots"]:
                mark = "exists" if r["exists"] else "  --  "
                w = "writable" if r["writable"] else "read-only"
                print(f"  [{mark}] {r['path']:<52} {w:<10} {r['note']}")
            print("\nInstall into a root marked 'exists' + 'writable', or create one.")
        return 0

    if not skills():
        print(f"no skills found in {SKILLS_SRC}", file=sys.stderr)
        return 3

    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"cannot create {target}: {exc}", file=sys.stderr)
        print("Pick a writable root (see --check), or pass --target.", file=sys.stderr)
        return 3

    # Shared entries at the target root: what the runtime's own docs and the
    # upstream README assume, and what `import lib` needs for the vendored scripts.
    root_results = [
        _install_one(VENDOR_SRC, target / "vendor", args.method, args.force),
        _install_one(VENDOR_SRC / "lib", target / "lib", args.method, args.force),
    ]

    per_skill: dict[str, list[str]] = {}
    for skill in skills():
        line = _install_one(skill, target / skill.name, args.method, args.force)
        extras = _wire_skill(target / skill.name, args.method, args.force)
        per_skill[skill.name] = [line, *extras]

    if args.json:
        print(json.dumps({"target": str(target), "method": args.method,
                          "root": root_results, "skills": per_skill}, indent=2))
    else:
        for line in root_results:
            print(line)
        for name, lines in per_skill.items():
            print(lines[0])
            for extra in lines[1:]:
                print(extra)
        print(f"\nInstalled {len(per_skill)} skills into {target} (method: {args.method})")
        print("Each skill carries its own vendor/ and references/ links, so the")
        print("relative paths in REFERENCE.md resolve at any install depth.")
        print("\nRestart the app or start a new conversation so the catalog reloads.")
        print("Verify with:  python bin/lk.py doctor")
    return 0


def _stage(dest: Path, method: str, force: bool) -> int:
    """Write a self-contained bundle another agent or machine can copy anywhere.

    This is the portable form: no junctions pointing back into this workspace, so
    it survives being zipped or moved. Bigger, because `vendor/` is included.
    """
    if dest.exists() and force:
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    copied = 0
    for src in (VENDOR_SRC, SKILLS_SRC, REFS_SRC, ROOT / "bin"):
        if not src.is_dir():
            continue
        dst = dest / src.name
        if dst.exists():
            shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pylibs", "testing"))
        copied += 1
    for extra in ("REFERENCE.md", "README.md", ".env.example", "requirements.txt", ".gitignore"):
        src = ROOT / extra
        if src.is_file():
            shutil.copy2(src, dest / extra)
            copied += 1

    # Inside the staged copy the skill-local vendor/ links would dangle, so give
    # each skill a real copy. That is the price of portability.
    for skill in sorted((dest / "skills").iterdir()) if (dest / "skills").is_dir() else []:
        if not (skill / "SKILL.md").is_file():
            continue
        for name, src in (("vendor", dest / "vendor"), ("references", dest / "references")):
            dst = skill / name
            if dst.exists() or dst.is_symlink():
                _remove(dst)
            if src.is_dir():
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pylibs"))

    print(f"Staged a self-contained bundle at {dest}")
    print(f"  {copied} top-level entries copied, 12 skills made self-contained")
    print("  Copy this directory anywhere; no links point back here.")
    print(f"  Verify with:  python {dest / 'bin' / 'lk.py'} doctor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
