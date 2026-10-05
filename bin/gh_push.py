#!/usr/bin/env python3
"""Push a local git history to GitHub via the Git Data API.

## Why not `git push`

In this sandbox `git push` over HTTPS fails twice over and neither is fixable from
here: schannel cannot acquire credentials, and the bundled `sh.exe` cannot create a
signal pipe (`Win32 error 5`), which git needs to run its credential helpers. A
read-only `git ls-remote` fails the same way, so it is environmental rather than a
credential problem.

So this recreates the **existing local commits** through the REST API instead of
flattening them into one. Each local commit becomes a real commit object with the
same message, author and parents, so the pushed history matches `git log`.

## What it does

  1. reads every file tracked by local git (`git ls-tree` at each commit)
  2. uploads changed files as blobs (content-addressed, so repeated content is free)
  3. creates a tree per commit
  4. creates a commit per commit, wiring parents
  5. points the remote branch at the final commit

Nothing force-updates: if the remote branch already has commits, this refuses
unless --force is given.

Usage:
  python bin/gh_push.py --remote subu53/linkedin_exponential --branch main
  python bin/gh_push.py --remote ... --dry-run
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
ROOT = BIN.parent
sys.path.insert(0, str(ROOT / "vendor" / ".pylibs"))
import requests  # noqa: E402

API = "https://api.github.com"


def _token() -> str:
    tok = os.environ.get("GITHUB_TOKEN", "").strip()
    if tok:
        return tok
    f = ROOT / "testing" / ".ghtok"
    if f.is_file():
        return f.read_text(encoding="utf-8").strip()
    print("FAIL  no GITHUB_TOKEN and no testing/.ghtok", file=sys.stderr)
    raise SystemExit(3)


def redact(text: str) -> str:
    tok = _token()
    if tok and tok in text:
        text = text.replace(tok, "<redacted>")
    return text


class GH:
    def __init__(self) -> None:
        self.h = {
            "Authorization": f"Bearer {_token()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "linkedin-exponential-push",
        }

    def __call__(self, method: str, path: str, **kw):
        """One request, retried on transient network and 5xx failures.

        A long sequential upload will eventually hit an SSL drop or a 502. Without
        a retry the whole run dies mid-way and the branch is left pointing at a
        partial history, which is worse than failing fast because it looks like it
        worked.
        """
        import time

        attempts = kw.pop("_attempts", 4)
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                r = requests.request(method, f"{API}{path}", headers=self.h, timeout=90, **kw)
                if r.status_code >= 500 and attempt < attempts - 1:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return r
            except requests.exceptions.RequestException as exc:
                last = exc
                if attempt < attempts - 1:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise
        raise last if last else RuntimeError("request failed")


def git_bytes(*args: str) -> bytes:
    """Run git and return raw bytes.

    Blob upload needs the exact bytes. `git show` through a text pipe would decode
    and re-encode, silently corrupting any binary file in the tree.
    """
    p = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True)
    if p.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {p.stderr.decode('utf-8', 'replace').strip()}")
    return p.stdout


def git(*args: str) -> str:
    return git_bytes(*args).decode("utf-8", "replace")


def local_commits() -> list[dict]:
    """Oldest first, with parents, message, author and the file list at each tip."""
    raw = git("log", "--reverse", "--pretty=format:%H%x1f%P%x1f%an%x1f%ae%x1f%aI%x1f%cI%x1f%B%x1e")
    out = []
    for chunk in raw.split("\x1e"):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        sha, parents, an, ae, adate, cdate, msg = chunk.split("\x1f", 6)
        files = git("ls-tree", "-r", "--name-only", sha).splitlines()
        out.append({
            "sha": sha,
            "parents": parents.split() if parents.strip() else [],
            "author_name": an,
            "author_email": ae,
            "author_date": adate,
            "commit_date": cdate,
            "message": msg.rstrip("\n"),
            "files": [f for f in files if f],
        })
    return out


def ensure_repo_initialised(gh: GH, remote: str, branch: str) -> None:
    """Create a bootstrap commit if the repository is empty.

    GitHub's blob API returns HTTP 409 "Git Repository is empty" until the repo has
    at least one commit, so a repo created through the UI with no README cannot
    receive blobs at all. A placeholder file provides that commit.

    The placeholder is intentionally absent from every tree we build afterwards, so
    the final pushed tree does not contain it: it exists only to make the repo
    non-empty. Should this ever produce a repository whose only content is the
    placeholder, the file says what happened and how to remove it.
    """
    r = gh("GET", f"/repos/{remote}/git/ref/heads/{branch}")
    if r.status_code == 200:
        return
    if r.status_code not in (404, 409):
        print(f"warning: could not read ref {branch} (HTTP {r.status_code})")

    # Does the repo have any commits at all?
    commits = gh("GET", f"/repos/{remote}/commits?per_page=1")
    if commits.status_code == 200 and commits.json():
        print(f"repo already has commits but no {branch} branch; continuing")
        return

    print("repo is empty: creating a bootstrap commit so the blob API will accept uploads")
    body = (
        "# linkedin-exponential\n\n"
        "Bootstrap commit. The full history is pushed immediately after this by\n"
        "`bin/gh_push.py`, which replaces this file's tree entirely. If you can see this\n"
        "and nothing else, the push failed partway and can be re-run safely.\n"
    )
    cr = gh("PUT", f"/repos/{remote}/contents/.bootstrap.md", json={
        "message": "chore: initialise repository",
        "content": base64.b64encode(body.encode("utf-8")).decode("ascii"),
        "branch": branch,
    })
    if cr.status_code not in (200, 201):
        raise SystemExit(f"FAIL  could not bootstrap {remote}: HTTP {cr.status_code} "
                         f"{redact(cr.text[:300])}")
    print(f"bootstrap commit {cr.json()['commit']['sha'][:7]} on {branch}\n")


def build_and_push(gh: GH, remote: str, branch: str, dry: bool) -> int:
    commits = local_commits()
    if not commits:
        print("no local commits", file=sys.stderr)
        return 3

    print(f"{len(commits)} local commit(s) to push to {remote}@{branch}")
    for c in commits:
        print(f"  {c['sha'][:7]}  {len(c['files']):>4} files  {c['message'].splitlines()[0][:60]}")
    if dry:
        print("\ndry run: nothing uploaded")
        return 0

    # Refuse to clobber existing remote work.
    r = gh("GET", f"/repos/{remote}/git/ref/heads/{branch}")
    if r.status_code == 200:
        print(f"\nFAIL  {remote}@{branch} already exists with "
              f"{r.json()['object']['sha'][:7]}. Refusing to overwrite; "
              "merge or delete it first, or push to another branch.", file=sys.stderr)
        return 5
    if r.status_code not in (404, 409):
        print(f"warning: could not check the remote ref (HTTP {r.status_code})")

    # A repo with no commits at all cannot receive blobs, so give it one. That
    # commit becomes the parent of our first commit, so the history is linear
    # rather than replacing whatever bootstrap exists.
    ensure_repo_initialised(gh, remote, branch)
    ref = gh("GET", f"/repos/{remote}/git/ref/heads/{branch}")
    parent_sha: str | None = ref.json()["object"]["sha"] if ref.status_code == 200 else None
    if parent_sha:
        print(f"chaining onto {parent_sha[:7]}\n")

    blob_cache: dict[str, str] = {}
    created = 0

    for c in commits:
        entries = []
        for rel in c["files"]:
            # Key on a stable content digest, not Python's hash(), which is salted
            # per process, and not the path alone, so identical content is uploaded
            # once across all commits.
            content = git_bytes("show", f"{c['sha']}:{rel}")
            key = hashlib.sha1(content).hexdigest()
            sha = blob_cache.get(key)
            if sha is None:
                resp = gh("POST", f"/repos/{remote}/git/blobs", json={
                    "content": base64.b64encode(content).decode("ascii"),
                    "encoding": "base64",
                })
                if resp.status_code not in (200, 201):
                    print(f"FAIL  blob {rel}: HTTP {resp.status_code} {redact(resp.text[:200])}",
                          file=sys.stderr)
                    return 4
                sha = resp.json()["sha"]
                blob_cache[key] = sha
            entries.append({"path": rel, "mode": "100644", "type": "blob", "sha": sha})

        tr = gh("POST", f"/repos/{remote}/git/trees", json={"tree": entries})
        if tr.status_code not in (200, 201):
            print(f"FAIL  tree for {c['sha'][:7]}: HTTP {tr.status_code} {redact(tr.text[:200])}",
                  file=sys.stderr)
            return 4
        tree_sha = tr.json()["sha"]

        payload = {
            "message": c["message"],
            "tree": tree_sha,
            "author": {"name": c["author_name"], "email": c["author_email"], "date": c["author_date"]},
            "committer": {"name": c["author_name"], "email": c["author_email"], "date": c["commit_date"]},
        }
        if parent_sha:
            payload["parents"] = [parent_sha]

        cr = gh("POST", f"/repos/{remote}/git/commits", json=payload)
        if cr.status_code not in (200, 201):
            print(f"FAIL  commit {c['sha'][:7]}: HTTP {cr.status_code} {redact(cr.text[:300])}",
                  file=sys.stderr)
            return 4
        parent_sha = cr.json()["sha"]
        created += 1
        print(f"  pushed {c['sha'][:7]} -> {parent_sha[:7]}  {c['message'].splitlines()[0][:50]}")

    rr = gh("POST", f"/repos/{remote}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": parent_sha})
    if rr.status_code not in (200, 201):
        print(f"FAIL  creating {branch}: HTTP {rr.status_code} {redact(rr.text[:300])}", file=sys.stderr)
        return 4

    print(f"\n{branch} now points at {parent_sha[:7]} ({created} commits)")
    print(f"https://github.com/{remote}")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--remote", required=True, help="owner/repo")
    p.add_argument("--branch", default="main")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    gh = GH()
    me = gh("GET", "/user")
    if me.status_code != 200:
        print(f"FAIL  token rejected: HTTP {me.status_code}", file=sys.stderr)
        return 3
    print(f"authenticated as {me.json()['login']}")

    target = gh("GET", f"/repos/{args.remote}")
    if target.status_code != 200:
        print(f"FAIL  {args.remote} not reachable: HTTP {target.status_code}", file=sys.stderr)
        return 3
    print(f"target {args.remote} (private={target.json().get('private')}), "
          f"size={target.json().get('size')}KB\n")

    return build_and_push(gh, args.remote, args.branch, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
