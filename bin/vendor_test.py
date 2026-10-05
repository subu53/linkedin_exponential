#!/usr/bin/env python3
"""Run the vendored upstream test suite and quality gates.

This exists because upstream's suite needs two things that are easy to get
wrong on Windows, and because the failure modes are confusing when you hit them
blind:

  1. `PYTHONUTF8=1`. Several upstream tests call `read_text()` without
     `encoding=`, which raises `UnicodeDecodeError` on a cp1252 console. The
     files are UTF-8; the console assumption is the bug.
  2. PyYAML, a dev-only dependency, needed by the frontmatter tests. `pip` may be
     unable to reach PyPI here, so `--provision` fetches the wheel over Node's
     `fetch` (which does work) and extracts it into `vendor/.pylibs/`.

Usage:
  python bin/vendor_test.py                 # tests + gates, offline
  python bin/vendor_test.py --provision     # fetch PyYAML first, then run
  python bin/vendor_test.py --tests-only
  python bin/vendor_test.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
ROOT = BIN.parent
VENDOR = ROOT / "vendor"
PYLIBS = VENDOR / ".pylibs"

PYYAML_VERSION = "6.0.3"


def _has_yaml() -> bool:
    code, _ = _run([sys.executable, "-c", "import yaml"], cwd=VENDOR)
    return code == 0


def _has_dotenv() -> bool:
    code, _ = _run([sys.executable, "-c", "import dotenv"], cwd=VENDOR)
    return code == 0


def provision() -> bool:
    """Make PyYAML and python-dotenv importable from `vendor/.pylibs`.

    PyYAML is fetched from PyPI over Node's `fetch` (pip cannot reach PyPI here).
    python-dotenv is copied from a local interpreter when one has it, because it
    is pure Python and downloading is unnecessary; if no local copy exists we fall
    back to the same fetch route.
    """
    if _has_yaml() and _has_dotenv():
        print("PyYAML and python-dotenv already importable; nothing to provision")
        return True

    PYLIBS.mkdir(parents=True, exist_ok=True)

    if not _has_yaml():
        _fetch_pyyaml()
    else:
        print("PyYAML already present")

    if not _has_dotenv():
        if not _copy_local_dotenv():
            _fetch_wheel("python-dotenv", "python_dotenv", "py3-none-any")
    else:
        print("python-dotenv already present")

    return _has_yaml() and _has_dotenv()


def _copy_local_dotenv() -> bool:
    """Copy python-dotenv from any local interpreter that has it.

    Pure Python, so a copy is safe across interpreter versions - unlike PyYAML,
    which ships a compiled `_yaml` extension and must match the platform.
    """
    import shutil

    candidates = [
        Path(sys.prefix) / "Lib" / "site-packages",
        Path.home() / "miniconda3" / "Lib" / "site-packages",
        Path.home() / "anaconda3" / "Lib" / "site-packages",
    ]
    for base in candidates:
        pkg = base / "dotenv"
        if not pkg.is_dir():
            continue
        if any(pkg.rglob("*.pyd")) or any(pkg.rglob("*.so")):
            continue  # not pure; skip rather than risk an ABI mismatch
        shutil.copytree(pkg, PYLIBS / "dotenv", dirs_exist_ok=True)
        for dist in base.glob("python_dotenv*.dist-info"):
            shutil.copytree(dist, PYLIBS / dist.name, dirs_exist_ok=True)
        print(f"copied python-dotenv from {base}")
        return _has_dotenv()
    return False


def _fetch_pyyaml() -> bool:
    node = os.environ.get("DSH_NODE") or "node"
    # PyYAML publishes no pure-python wheel, so pick the one matching this
    # platform. PyPI is reachable from Node's fetch even where pip is not.
    js = f"""
const fs = require('fs'); const path = require('path');
const dest = {json.dumps(str(PYLIBS))};
const wanted = process.platform === 'win32' ? 'win_amd64' : 'x86_64';
(async () => {{
  const meta = await (await fetch('https://pypi.org/pypi/pyyaml/{PYYAML_VERSION}/json')).json();
  const pick = meta.urls.find(u => u.filename.includes(wanted) && u.filename.includes('cp'))
            || meta.urls.find(u => u.filename.includes('py3-none-any'));
  if (!pick) {{ console.error('no suitable wheel for ' + wanted); process.exit(1); }}
  const buf = Buffer.from(await (await fetch(pick.url)).arrayBuffer());
  fs.mkdirSync(dest, {{recursive: true}});
  fs.writeFileSync(path.join(dest, pick.filename), buf);
  console.log(pick.filename);
}})().catch(e => {{ console.error('ERR ' + e.message); process.exit(1); }});
"""
    return _install_fetched(js, "PyYAML")


def _fetch_wheel(package: str, dist_prefix: str, prefer: str) -> bool:
    node = os.environ.get("DSH_NODE") or "node"
    js = f"""
const fs = require('fs'); const path = require('path');
const dest = {json.dumps(str(PYLIBS))};
(async () => {{
  const meta = await (await fetch('https://pypi.org/pypi/{package}/json')).json();
  const pick = meta.urls.find(u => u.filename.includes({json.dumps(prefer)}))
            || meta.urls.find(u => u.filename.endsWith('.whl'));
  if (!pick) {{ console.error('no wheel for {package}'); process.exit(1); }}
  const buf = Buffer.from(await (await fetch(pick.url)).arrayBuffer());
  fs.mkdirSync(dest, {{recursive: true}});
  fs.writeFileSync(path.join(dest, pick.filename), buf);
  console.log(pick.filename);
}})().catch(e => {{ console.error('ERR ' + e.message); process.exit(1); }});
"""
    return _install_fetched(js, package)


def _install_fetched(js: str, label: str) -> bool:
    import zipfile

    node = os.environ.get("DSH_NODE") or "node"
    tmp = PYLIBS.parent / "_get_wheel.cjs"
    tmp.write_text(js, encoding="utf-8")
    try:
        code, out = _run([node, str(tmp)], cwd=VENDOR)
    finally:
        tmp.unlink(missing_ok=True)
    if code != 0:
        print(f"could not fetch {label}: {out.strip()}", file=sys.stderr)
        return False
    wheel = PYLIBS / out.strip().splitlines()[-1]
    if not wheel.is_file():
        print(f"wheel not found at {wheel}", file=sys.stderr)
        return False
    with zipfile.ZipFile(wheel) as z:
        z.extractall(PYLIBS)
    wheel.unlink(missing_ok=True)
    print(f"provisioned {label} into {PYLIBS}")
    return True


def _env() -> dict:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    # Make vendored support libraries (python-dotenv, PyYAML) importable without a
    # pip install. pip cannot reach PyPI here, and several vendored scripts hard-
    # depend on dotenv: without this, check_config.py reports a fully configured
    # account as "not set", and the frontmatter tests error out.
    parts = [str(PYLIBS)]
    if env.get("PYTHONPATH"):
        parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(parts)
    return env


def _run(cmd: list[str], *, cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), env=_env(), capture_output=True, text=True, errors="replace")
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _git_work_tree() -> bool:
    code, _ = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=VENDOR)
    return code == 0


# Patterns that look like a real credential rather than a placeholder. Mirrors
# the intent of upstream's check_no_secrets.py for the case where git is absent.
#
# Getting these character classes right is not guesswork for long: a real
# Publora key is ~73 chars and contains lowercase letters, digits, underscores
# AND a period. The obvious `sk_[A-Za-z0-9]{20,}` misses it on all three counts,
# which is why `_self_test_patterns()` below exists - a detector that silently
# stops detecting is worse than none, because it reads as a pass.
#
# The 40-char floor keeps short `sk_...` placeholders out. `.` is allowed
# anywhere but the final position so a trailing sentence period is not swallowed.
_SECRET_PATTERNS = (
    re.compile(r"apify_api_[A-Za-z0-9_.-]{10,}"),
    re.compile(r"pf_live_[A-Za-z0-9_.-]{10,}"),
    re.compile(r"sk_[A-Za-z0-9_.-]{40,}[A-Za-z0-9_-]"),
    re.compile(r"sk-[A-Za-z0-9-]{30,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),            # GitHub
    re.compile(r"AKIA[0-9A-Z]{16}"),                     # AWS access key id
)
_PLACEHOLDER = re.compile(r"(your|paste|xxx|\.\.\.|example|here|placeholder|redacted)", re.IGNORECASE)


def _self_test_patterns() -> tuple[bool, str]:
    """Prove the patterns still match the key shapes they exist to catch.

    Called by --check-patterns and by the no-secrets gate. Without this, widening
    or narrowing a class is invisible: the gate keeps printing "clean" for a file
    it can no longer read. Values here are synthetic and are not credentials.
    """
    must_match = {
        "publora key (lowercase, digits, underscores, a period)":
            "sk_" + ("a1b2c3d4e5f6g7h8i9j0" * 2) + "_x." + ("k9l8m7n6o5p4" * 2),
        "openai-style key": "sk-" + ("A" * 40),
        "apify token": "apify_api_" + ("Xy9" * 8),
        "pixfaro token": "pf_live_" + ("Zz1" * 8),
        "github token": "ghp_" + ("a1B2c3D4" * 4),
        "AWS access key id": "AKIA" + ("Q7W8E9R0T1Y2U3I4"),
    }
    must_not_match = {
        "empty": "",
        "placeholder (your key here)": "sk_your_key_here",
        "short sentinel": "sk_live",
        "word with sk_ prefix": "sk_test_thing",
        "prose": "The sk_ prefix is used by several providers.",
    }

    problems: list[str] = []
    for label, value in must_match.items():
        if not any(p.search(value) for p in _SECRET_PATTERNS):
            # Report the shape, never the (synthetic) value.
            problems.append(f"MISSED {label} (len {len(value)})")
    for label, value in must_not_match.items():
        if any(p.search(value) for p in _SECRET_PATTERNS) and not _PLACEHOLDER.search(value):
            problems.append(f"FALSE POSITIVE on {label}")

    if problems:
        return False, "; ".join(problems)
    return True, f"{len(must_match)} key shapes matched, {len(must_not_match)} non-keys ignored"


def _scan_for_secrets() -> tuple[bool, str]:
    """Scan the bundle for credential-shaped strings, skipping placeholders.

    Substitutes for upstream's `git ls-files`-based check when there is no work
    tree, so a leaked key is still caught in a plain copy.
    """
    skip_dirs = {".git", "__pycache__", ".pylibs", "testing", "node_modules"}
    findings: list[str] = []
    scanned = 0
    for path in VENDOR.rglob("*"):
        if not path.is_file() or any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".zip", ".whl", ".pyc"}:
            continue
        if path.name in {".env"}:
            findings.append(f"{path.relative_to(VENDOR)}: a real .env file is present")
            continue
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern in _SECRET_PATTERNS:
            for match in pattern.finditer(text):
                token = match.group(0)
                if _PLACEHOLDER.search(token):
                    continue
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{path.relative_to(VENDOR)}:{line}: {token[:14]}...")

    if findings:
        return False, f"{len(findings)} credential-shaped string(s): " + "; ".join(findings[:4])
    return True, f"clean ({scanned} files scanned; no git work tree, so scanned directly)"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--provision", action="store_true", help="fetch PyYAML into vendor/.pylibs first")
    p.add_argument("--tests-only", action="store_true", help="skip the quality gates")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if args.provision:
        provision()

    results: list[dict] = []

    code, out = _run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"], cwd=VENDOR)
    results.append({"check": "unit tests (116)", "ok": code == 0, "code": code, "tail": out.strip().splitlines()[-1:]})

    if not args.tests_only:
        for script, label in (
            ("scripts/check_frontmatter.py", "frontmatter"),
            ("scripts/check_markdown_references.py", "markdown references"),
        ):
            path = VENDOR / script
            if not path.is_file():
                continue
            code, out = _run([sys.executable, script], cwd=VENDOR)
            results.append({"check": label, "ok": code == 0, "code": code, "tail": out.strip().splitlines()[-1:]})

        # check_no_secrets.py uses `git ls-files`, so it cannot run outside a
        # work tree. The bundle is normally not a repo of its own (it is a copy
        # of one), so say "skipped, here is the substitute" rather than reporting
        # a failure that is really a missing prerequisite.
        secrets_script = VENDOR / "scripts" / "check_no_secrets.py"
        if secrets_script.is_file():
            if _git_work_tree():
                code, out = _run([sys.executable, "scripts/check_no_secrets.py"], cwd=VENDOR)
                results.append(
                    {"check": "no secrets (git)", "ok": code == 0, "code": code,
                     "tail": out.strip().splitlines()[-1:]}
                )
            else:
                # Prove the detector works before trusting a clean result from it.
                patterns_ok, patterns_detail = _self_test_patterns()
                results.append(
                    {"check": "secret patterns", "ok": patterns_ok,
                     "code": 0 if patterns_ok else 1, "tail": [patterns_detail]}
                )
                ok, detail = _scan_for_secrets()
                results.append(
                    {"check": "no secrets (scan)", "ok": ok, "code": 0 if ok else 1,
                     "tail": [detail]}
                )

        code, out = _run([sys.executable, "scripts/check_config.py", "--offline"], cwd=VENDOR)
        results.append({"check": "config (offline)", "ok": code == 0, "code": code, "tail": out.strip().splitlines()[-1:]})

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            mark = "PASS" if r["ok"] else "FAIL"
            detail = r["tail"][0] if r["tail"] else ""
            print(f"[{mark}] {r['check']:<22} {detail}")
        failed = [r["check"] for r in results if not r["ok"]]
        print()
        if failed:
            print(f"{len(failed)} failed: {', '.join(failed)}")
        else:
            print("Vendored engine is green.")

    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
