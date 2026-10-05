#!/usr/bin/env python3
"""Push the local git history, optionally substituting file content per commit.

## Why this exists alongside gh_push.py

`gh_push.py` builds the remote from `git show <sha>:<path>` for every commit, which
faithfully reproduces whatever is in local history. That is wrong when local history
itself contains something that must not be published.

A concrete case: `.env.example` was committed with the operator's **real** Publora,
Apify and Pixfaro credentials in it. A fix-forward commit would leave the keys
readable in the earlier commit's tree, so the correct fix is to publish a history in
which that file only ever contained placeholders. `--replace PATH=FILE` does that
without rewriting the local repository.

Usage:
  # publish history, substituting .env.example in every commit
  python bin/gh_publish_clean.py --remote subu53/linkedin_exponential --branch main \
      --replace .env.example=.env.example --overwrite

  # verify first, upload nothing
  python bin/gh_publish_clean.py ... --dry-run
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
ROOT = BIN.parent

# Reuse the transport and git helpers rather than duplicating them.
sys.path.insert(0, str(BIN))
sys.path.insert(0, str(ROOT / "vendor" / ".pylibs"))
import gh_push  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--remote", required=True, help="owner/repo")
    p.add_argument("--branch", default="main")
    p.add_argument("--replace", action="append", default=[], metavar="PATH=FILE",
                   help="use FILE's content for PATH in every commit (repeatable)")
    p.add_argument("--overwrite", action="store_true",
                   help="force-update the branch if it already exists")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    replacements: dict[str, bytes] = {}
    for spec in args.replace:
        if "=" not in spec:
            print(f"FAIL  --replace needs PATH=FILE, got {spec!r}", file=sys.stderr)
            return 2
        rel, _, src = spec.partition("=")
        path = ROOT / src
        if not path.is_file():
            print(f"FAIL  replacement source not found: {path}", file=sys.stderr)
            return 2
        replacements[rel] = path.read_bytes()

    # Refuse to publish a replacement that itself contains a credential.
    scan = ROOT / "bin" / "scan_secrets.py"
    if scan.is_file() and replacements:
        import importlib.util

        spec_ = importlib.util.spec_from_file_location("scan_secrets", scan)
        mod = importlib.util.module_from_spec(spec_)
        spec_.loader.exec_module(mod)
        for rel, data in replacements.items():
            hits = mod.scan_text(data.decode("utf-8", "ignore"), rel)
            if hits:
                print(f"FAIL  the replacement for {rel} still contains a credential:", file=sys.stderr)
                for h in hits:
                    print(f"        line {h['line']}  [{h['kind']}]  {h['preview']}", file=sys.stderr)
                return 3

    gh = gh_push.GH()
    me = gh("GET", "/user")
    if me.status_code != 200:
        print(f"FAIL  token rejected: HTTP {me.status_code}", file=sys.stderr)
        return 3
    print(f"authenticated as {me.json()['login']}")

    commits = gh_push.local_commits()
    print(f"{len(commits)} commit(s); {len(replacements)} path(s) substituted per commit")
    for c in commits:
        print(f"  {c['sha'][:7]}  {len(c['files']):>4} files  {c['message'].splitlines()[0][:56]}")
    if args.dry_run:
        print("\ndry run: nothing uploaded")
        return 0

    ref = gh("GET", f"/repos/{args.remote}/git/ref/heads/{args.branch}")
    exists = ref.status_code == 200
    if exists and not args.overwrite:
        print(f"FAIL  {args.remote}@{args.branch} exists; pass --overwrite to replace it",
              file=sys.stderr)
        return 5
    parent_sha = ref.json()["object"]["sha"] if exists else None
    if parent_sha:
        print(f"\nforce-updating {args.branch} from {parent_sha[:7]}")

    blob_cache: dict[str, str] = {}
    uploaded = 0
    for c in commits:
        entries = []
        for rel in c["files"]:
            if rel in replacements:
                content = replacements[rel]
            else:
                content = gh_push.git_bytes("show", f"{c['sha']}:{rel}")
            key = hashlib.sha1(content).hexdigest()
            sha = blob_cache.get(key)
            if sha is None:
                r = gh("POST", f"/repos/{args.remote}/git/blobs", json={
                    "content": base64.b64encode(content).decode("ascii"), "encoding": "base64"})
                if r.status_code not in (200, 201):
                    print(f"FAIL  blob {rel}: HTTP {r.status_code} {gh_push.redact(r.text[:200])}",
                          file=sys.stderr)
                    return 4
                sha = r.json()["sha"]
                blob_cache[key] = sha
                uploaded += 1
            entries.append({"path": rel, "mode": "100644", "type": "blob", "sha": sha})

        tr = gh("POST", f"/repos/{args.remote}/git/trees", json={"tree": entries})
        if tr.status_code not in (200, 201):
            print(f"FAIL  tree: HTTP {tr.status_code} {gh_push.redact(tr.text[:200])}", file=sys.stderr)
            return 4

        payload = {
            "message": c["message"],
            "tree": tr.json()["sha"],
            "author": {"name": c["author_name"], "email": c["author_email"], "date": c["author_date"]},
            "committer": {"name": c["author_name"], "email": c["author_email"], "date": c["commit_date"]},
        }
        if parent_sha:
            payload["parents"] = [parent_sha]
        cr = gh("POST", f"/repos/{args.remote}/git/commits", json=payload)
        if cr.status_code not in (200, 201):
            print(f"FAIL  commit: HTTP {cr.status_code} {gh_push.redact(cr.text[:300])}", file=sys.stderr)
            return 4
        parent_sha = cr.json()["sha"]
        print(f"  {c['sha'][:7]} -> {parent_sha[:7]}  {c['message'].splitlines()[0][:48]}")

    body = {"sha": parent_sha, "force": True}
    rr = (gh("PATCH", f"/repos/{args.remote}/git/refs/heads/{args.branch}", json=body) if exists
          else gh("POST", f"/repos/{args.remote}/git/refs",
                  json={"ref": f"refs/heads/{args.branch}", "sha": parent_sha}))
    if rr.status_code not in (200, 201):
        print(f"FAIL  updating {args.branch}: HTTP {rr.status_code} {gh_push.redact(rr.text[:300])}",
              file=sys.stderr)
        return 4

    print(f"\n{args.branch} -> {parent_sha[:7]}  ({uploaded} blobs uploaded, "
          f"{len(blob_cache)} unique contents)")
    print(f"https://github.com/{args.remote}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
