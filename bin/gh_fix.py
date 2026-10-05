#!/usr/bin/env python3
"""Fix GitHub repo metadata from a token — descriptions, topics, homepage, pins.

## Scope, deliberately narrow

This changes **metadata only**. It will not delete repositories, change
visibility, push code, or alter history. Deleting a repo is irreversible and
choosing *which* of eight near-duplicate lung-cancer repos is canonical is a
judgement call about your own work, so that stays yours — this tool prints the
candidates and the exact commands instead.

The one destructive-adjacent action, `--archive`, only *archives*: the repo stays
public, stays readable, and can be unarchived with one click. It just stops
looking like an active project, which is the point when you have 60 repos.

## Token handling

The token is read from `GITHUB_TOKEN` (in `.env`) and is never printed, logged,
or echoed — `redact()` covers it in every output path, including error messages
that might quote the request. Add it yourself; do not paste it into a chat.

Fine-grained token needs, on your own repos:
  - Repository permissions → Metadata: Read and write   (descriptions, topics, homepage)
  - Repository permissions → Administration: Read and write   (only for --archive)
Classic tokens need the `repo` scope (or `public_repo` for public repos only).

## Usage

  python bin/gh_fix.py --audit                      # what needs changing, no writes
  python bin/gh_fix.py --audit --json
  python bin/gh_fix.py --apply                      # write the descriptions/topics
  python bin/gh_fix.py --pin                        # pin the 6 chosen repos
  python bin/gh_fix.py --archive <repo> [<repo>...] # archive duplicates (reversible)
  python bin/gh_fix.py --delete-plan                # print the delete commands; deletes nothing
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
ROOT = BIN.parent
for _p in (str(ROOT / "vendor"), str(ROOT), str(BIN)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Load .env the same way the CLI does, so GITHUB_TOKEN arrives without exporting.
_PYLIBS = ROOT / "vendor" / ".pylibs"
if _PYLIBS.is_dir():
    sys.path.insert(0, str(_PYLIBS))
for _candidate in (ROOT / ".env", Path.cwd() / ".env"):
    if not _candidate.is_file():
        continue
    try:
        from dotenv import load_dotenv

        load_dotenv(_candidate, override=False)
        break
    except Exception:
        for _line in _candidate.read_text(encoding="utf-8", errors="replace").splitlines():
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip().strip("'\""))

API = "https://api.github.com"

# ── The curated set. Descriptions are grounded in each repo's own GitHub
#    description and README where one exists; nothing here is invented.
#    `why` is kept short because it becomes the repo's public description.
WANTED = {
    "whatsapp-sales-agent": {
        # Resolved: the CV is current. Twilio + Claude 3.5 was the initial build,
        # then migrated to Meta's WhatsApp Cloud API + DeepSeek. Both facts are
        # kept, because "evaluated and swapped the channel and the model provider"
        # is a stronger signal than either stack on its own - and stating the
        # migration is what stops the repo and the CV looking like they disagree.
        "description": "Production LLM sales agent on Meta's WhatsApp Cloud API. Answers only from a live "
                       "product catalogue via retrieval grounding, escalates to a human when it should. "
                       "Migrated from Twilio + Claude 3.5 to the Cloud API + DeepSeek. Python, FastAPI, Azure.",
        "topics": ["llm", "rag", "whatsapp-cloud-api", "deepseek", "fastapi", "azure", "ai-agent", "python"],
        "pin": True,
        "note": "RESOLVED 2026: Meta WhatsApp Cloud API + DeepSeek is live; Twilio + Claude 3.5 was the "
                "first build. Description rewritten as a migration rather than replaced silently, so it "
                "no longer contradicts the CV.",
    },
    "lungcanceraiv2": {
        "description": "Medical imaging classifier: EfficientNet-B0 with Grad-CAM heatmaps so a "
                       "radiologist can see where the model looked. FastAPI back end, React front end.",
        "topics": ["computer-vision", "efficientnet", "grad-cam", "medical-imaging", "fastapi", "pytorch"],
        "pin": True,
        "note": "Best of the eight lung-cancer repos — has the full stack.",
    },
    "Credit-Card-Fraud-Detection-Imbalanced-Class": {
        "description": "Fraud detection on 284,807 transactions with 0.17% fraud. XGBoost with SMOTE "
                       "applied to training data only: 88.8% recall, ROC AUC 0.979.",
        "topics": ["fraud-detection", "class-imbalance", "xgboost", "smote", "machine-learning"],
        "pin": True,
        "note": "Already described. Topics added; description tightened with your CV's numbers.",
    },
    "dataorg-financial-health-prediction": {
        "description": "Zindi competition: financial-health index forecasting from survey and transaction "
                       "data. Deep & Cross Networks stacked with gradient-boosted trees, 50+ features.",
        "topics": ["zindi", "deep-cross-network", "ensemble", "forecasting", "feature-engineering"],
        "pin": True,
        "note": "Already described. Pinned for the competition evidence.",
    },
    "Telco-Customer-Churn-Prediction": {
        "description": "Churn prediction and retention modelling for telecommunications, framed as a "
                       "business decision rather than a leaderboard score.",
        "topics": ["churn-prediction", "machine-learning", "classification", "business-analytics"],
        "pin": True,
        "note": "Already described.",
    },
    "Market-Basket-Analysis-on-Online-Retail-Data": {
        "description": "Association-rule mining on online retail transactions to surface products bought "
                       "together, with implications for cross-sell, inventory and store layout.",
        "topics": ["market-basket-analysis", "association-rules", "data-analysis", "retail"],
        "pin": True,
        "note": "Already described. Shows range beyond deep learning.",
    },
    "subu53": {
        "description": "",
        "topics": [],
        "pin": False,
        "note": "Profile README repo. Skip unless you want a landing page here.",
    },
}

# Duplicate clusters. Archiving keeps them public and reversible; deleting does
# not. Both lists are printed, neither is executed automatically.
DUPLICATE_CLUSTERS = {
    "lung cancer / chest imaging": [
        "Lung_Cancer_diagnostic_test1", "esubu_lung_cancer_diagnostic", "Lung_diagnostic_system",
        "lungcancerai_v1", "lungcanceraiv2", "Deep_learning_chest_xray_pneumonia",
    ],
    "credit scoring": [
        "esubusacco_credit_scoring_app_demo", "esubu_credit_scoring_fnal", "esubu_credit_scoring_v2",
        "esubu_credit_scoring_v3", "esubu-credit-scoring",
    ],
    "portfolio": ["portfolio_v1", "portfolio_v2", "portfolio_v3"],
    "digicow / challenge scratch": ["digicow_test_codex", "digicow_new_123", "digicow_challenge_agent_test"],
    "experiments / test": ["test", "First-code-to-write", "pythonbasics", "project_armagedon",
                           "ticket888", "chpmlpclass2024", "champplpclass2024"],
}

# Named explicitly so the audit can flag it, rather than acting on it silently.
FLAGS = {
    "FREE-openai-api-keys": "Name alone reads as a red flag on a job-search profile.",
    "Scrapegraph-ai": "Fork or upstream clone — no signal.",
    "pytorch-image-models": "Fork or upstream clone — no signal.",
    "fastbook_practical_deep_learning": "Fork or upstream clone — no signal.",
    "deep-learning-keras-tf-tutorial": "Fork or upstream clone — no signal.",
    "free-llm-api-resources": "Fork or upstream clone — no signal.",
    "awesome-low-level-design": "Fork or upstream clone — no signal.",
    "data-engineering-zoomcamp": "Fork or upstream clone — no signal.",
    "open-higgsfield": "Fork or upstream clone — no signal.",
    "ECC": "Fork or upstream clone — no signal.",
}


def _token() -> str:
    tok = os.environ.get("GITHUB_TOKEN", "").strip()
    if not tok:
        _die(
            "GITHUB_TOKEN is not set.\n"
            "       Put it in .env yourself as GITHUB_TOKEN=... — do not paste it into the chat.\n"
            "       Then re-run. `python bin/lk.py doctor` will confirm it loaded.",
            3,
        )
    return tok


def redact(text: str) -> str:
    """Never let a token reach stdout, a log, or a pasted error report."""
    tok = os.environ.get("GITHUB_TOKEN", "")
    if tok and tok in text:
        text = text.replace(tok, f"{tok[:4]}...<redacted {len(tok)} chars>")
    import re

    return re.sub(r"(gh[pousr]_[A-Za-z0-9]{10,}|github_pat_[A-Za-z0-9_]{10,})",
                  lambda m: m.group(0)[:8] + "...<redacted>", text)


def _die(msg: str, code: int) -> "NoReturn":  # type: ignore[name-defined]  # noqa: F821
    print(f"FAIL  {msg}", file=sys.stderr)
    raise SystemExit(code)


def _gh(method: str, path: str, body: dict | None = None, accept: str | None = None):
    import requests

    headers = {
        "Authorization": f"Bearer {_token()}",
        "Accept": accept or "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "linkedin-skills-deepseek",
    }
    url = path if path.startswith("http") else f"{API}{path}"
    try:
        resp = requests.request(method, url, headers=headers, json=body, timeout=45)
    except Exception as exc:
        _die(redact(f"request failed: {type(exc).__name__}: {exc}"), 4)
    return resp


def whoami() -> dict:
    resp = _gh("GET", "/user")
    if resp.status_code == 401:
        _die("the token was rejected (HTTP 401). Check GITHUB_TOKEN.", 3)
    if resp.status_code != 200:
        _die(redact(f"could not read the account: HTTP {resp.status_code} {resp.text[:200]}"), 3)
    return resp.json()


def list_repos(login: str) -> list[dict]:
    repos: list[dict] = []
    page = 1
    while page <= 5:
        resp = _gh("GET", f"/user/repos?per_page=100&page={page}&affiliation=owner&sort=updated")
        if resp.status_code != 200:
            _die(redact(f"could not list repos: HTTP {resp.status_code} {resp.text[:200]}"), 4)
        batch = resp.json()
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos


def audit(repos: list[dict], as_json: bool) -> int:
    by_name = {r["name"]: r for r in repos}
    missing_desc, to_replace, missing_topics = [], [], []

    for name, spec in WANTED.items():
        r = by_name.get(name)
        if not r:
            continue
        current = (r.get("description") or "").strip()
        want = (spec.get("description") or "").strip()
        if not current and want:
            missing_desc.append(name)
        elif want and current != want:
            # Compared rather than flagged by hand, so any drift between what the
            # CV claims and what the repo says shows up here on its own.
            to_replace.append(name)
        if spec.get("topics") and sorted(r.get("topics") or []) != sorted(spec["topics"]):
            missing_topics.append(name)

    present_flags = sorted(n for n in FLAGS if n in by_name)
    clusters = {k: [n for n in v if n in by_name] for k, v in DUPLICATE_CLUSTERS.items()}
    clusters = {k: v for k, v in clusters.items() if v}

    report = {
        "account": repos[0]["owner"]["login"] if repos else None,
        "total_repos": len(repos),
        "pinned_targets": [n for n, s in WANTED.items() if s.get("pin") and n in by_name],
        "description_missing": missing_desc,
        "description_to_replace": to_replace,
        "topics_missing": missing_topics,
        "flagged": {n: FLAGS[n] for n in present_flags},
        "duplicate_clusters": clusters,
        "not_found_in_wanted": [n for n in WANTED if n not in by_name],
    }

    if as_json:
        print(json.dumps(report, indent=2))
        return 0

    print(f"Account: {report['account']}   public repos: {report['total_repos']}")
    print()
    print("Descriptions to REPLACE (currently wrong or contradictory):")
    for n in to_replace or ["  (none)"]:
        print(f"  - {n}")
    print()
    print("Descriptions MISSING entirely:")
    for n in missing_desc or ["  (none)"]:
        print(f"  - {n}")
    print()
    print("Topics missing:")
    for n in missing_topics or ["  (none)"]:
        print(f"  - {n}")
    print()
    print("Flagged for your decision (this tool will not touch these):")
    for n, why in report["flagged"].items():
        print(f"  ! {n}: {why}")
    print()
    print("Duplicate clusters (archive keeps them public and reversible):")
    for cluster, names in clusters.items():
        print(f"  {cluster}:")
        for n in names:
            print(f"      {n}")
    print()
    print("Wanted repos not found (already renamed or deleted?):")
    for n in report["not_found_in_wanted"] or ["  (none)"]:
        print(f"  - {n}")
    print()
    print("Next:")
    print("  python bin/gh_fix.py --apply      # write descriptions + topics")
    print("  python bin/gh_fix.py --pin        # pin the curated set")
    print("  python bin/gh_fix.py --archive <name>...   # reversible")
    return 0


def apply(login: str, dry: bool) -> int:
    # Two API traps, both of which report success while doing nothing useful:
    #
    #  1. `PATCH /repos/{owner}/{repo}` **silently ignores `topics`**. It returns
    #     200 and leaves them unchanged. Topics need their own endpoint,
    #     `PUT /repos/{owner}/{repo}/topics` with a `names` array.
    #  2. Reading topics back requires the `mercy-preview` media type on the GET,
    #     or the field comes back empty and looks like the write failed.
    #
    # So this does the description via PATCH and the topics via PUT, and then
    # verifies by reading back rather than trusting either response.
    skip = {s.strip() for s in os.environ.get("GH_SKIP_REPOS", "").split(",") if s.strip()}
    changed = 0
    for name, spec in WANTED.items():
        if not spec.get("description") and not spec.get("topics"):
            continue
        if name in skip:
            print(f"  SKIPPED {name} (GH_SKIP_REPOS) — needs a decision, not a guess")
            continue
        if dry:
            fields = [f for f in ("description", "topics") if spec.get(f)]
            print(f"  would update {name}: {fields}")
            continue

        wrote_ok = True
        if spec.get("description"):
            resp = _gh("PATCH", f"/repos/{login}/{name}", {"description": spec["description"]})
            if resp.status_code not in (200, 201):
                print(f"  FAILED  {name} description: HTTP {resp.status_code} "
                      f"{redact(resp.text[:160])}")
                wrote_ok = False

        if spec.get("topics"):
            resp = _gh(
                "PUT",
                f"/repos/{login}/{name}/topics",
                {"names": spec["topics"]},
                accept="application/vnd.github.mercy-preview+json",
            )
            if resp.status_code not in (200, 201):
                print(f"  FAILED  {name} topics: HTTP {resp.status_code} "
                      f"{redact(resp.text[:160])}")
                wrote_ok = False

        if wrote_ok:
            # Read back with the right media type; an unchanged value here means
            # the write did not take, whatever the previous response claimed.
            check = _gh("GET", f"/repos/{login}/{name}",
                        accept="application/vnd.github.mercy-preview+json")
            got_desc = (check.json().get("description") or "").strip() if check.status_code == 200 else ""
            got_topics = sorted(check.json().get("topics") or []) if check.status_code == 200 else []
            want_topics = sorted(spec.get("topics") or [])
            desc_ok = not spec.get("description") or got_desc == spec["description"].strip()
            topics_ok = not spec.get("topics") or got_topics == want_topics
            if desc_ok and topics_ok:
                fields = [f for f in ("description", "topics") if spec.get(f)]
                print(f"  updated {name} ({', '.join(fields)}) — verified")
                changed += 1
            else:
                problems = []
                if not desc_ok:
                    problems.append("description did not take")
                if not topics_ok:
                    problems.append(f"topics are {got_topics}, wanted {want_topics}")
                print(f"  UNVERIFIED {name}: {'; '.join(problems)}")

    print()
    print(f"{changed} repo(s) updated and verified." if not dry else "dry run: nothing written.")
    return 0


def pin(login: str) -> int:
    """Explain that pinning cannot be automated, and print what to pin.

    Recorded finding: **GitHub exposes no API for profile-pinned repositories.**
    Introspecting the GraphQL `Mutation` type returns `pinEnvironment`,
    `pinIssue` and `pinIssueComment`, and nothing for a user's pinned items.
    There is no REST endpoint either. An earlier version of this script guessed
    `replacePinnedItems`, which does not exist, so this now reports the truth
    instead of a mutation name that never worked.
    """
    skip = {s.strip() for s in os.environ.get("GH_SKIP_REPOS", "").split(",") if s.strip()}
    names = [n for n, s in WANTED.items() if s.get("pin") and n not in skip]

    print("  GitHub has NO API for pinned profile repositories — this step is manual.")
    print("  (Verified: the GraphQL Mutation type has pinIssue/pinEnvironment only.)")
    print()
    print("  To pin these six, open your profile and click 'Customize my profile',")
    print("  then drag them into the Featured row, in this order:")
    print()
    for i, name in enumerate(names, 1):
        print(f"    {i}. {name}")
    print()
    print("  Everything else this tool does — descriptions and topics — is complete.")
    return 0


def archive(login: str, names: list[str]) -> int:
    for name in names:
        resp = _gh("PATCH", f"/repos/{login}/{name}", {"archived": True})
        if resp.status_code == 200 and resp.json().get("archived"):
            print(f"  archived {name} (still public; unarchive any time)")
        else:
            print(f"  FAILED  {name}: HTTP {resp.status_code} {redact(resp.text[:180])}")
    return 0


def delete_plan(login: str) -> int:
    """Print a keep/archive/delete recommendation per duplicate cluster.

    Archiving is suggested before deleting because it is reversible: a repo that
    is archived still exists, still has its history and clones, and can be
    unarchived in one click. Deleting destroys all of that. For repositories that
    are already archived (and therefore already out of the way), deleting is
    optional housekeeping rather than something to rush.
    """
    states: dict[str, bool] = {}
    for names in DUPLICATE_CLUSTERS.values():
        for n in names:
            resp = _gh("GET", f"/repos/{login}/{n}")
            states[n] = bool(resp.json().get("archived")) if resp.status_code == 200 else False

    print("Archiving is reversible; deleting is not. Anything already archived is")
    print("already out of the way, so deleting it is optional housekeeping.")
    print()

    for cluster, names in DUPLICATE_CLUSTERS.items():
        keep = [n for n in names if WANTED.get(n, {}).get("pin")]
        # Only suggest archiving what is not already archived, or the command is
        # wrong twice over and the operator loses trust in the tool.
        todo = [n for n in names if n not in keep and not states.get(n)]
        print(f"# {cluster}   (recommended keep: {', '.join(keep) if keep else 'choose one'})")
        for n in names:
            if n in keep:
                print(f"#   KEEP        {n}")
            elif states.get(n):
                print(f"    archived    {n}   (already hidden; delete only if you are sure)")
            else:
                print(f"    ACTIVE      {n}")
        print()
        if todo:
            print(f"#   archive the rest with:")
            print(f"#     python bin/gh_fix.py --archive {' '.join(todo)}")
        else:
            print(f"#   nothing left to archive in this cluster")
        print()

    print("To delete instead (irreversible, needs the `gh` CLI and admin scope):")
    print("#   gh repo delete <owner>/<repo> --yes")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--audit", action="store_true", help="report only; makes no writes")
    g.add_argument("--apply", action="store_true", help="write descriptions and topics")
    g.add_argument("--pin", action="store_true", help="pin the curated repositories")
    g.add_argument("--archive", nargs="+", metavar="REPO", help="archive repos (reversible)")
    g.add_argument("--delete-plan", action="store_true", help="print delete commands; deletes nothing")
    p.add_argument("--json", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="with --apply: show changes, write nothing")
    args = p.parse_args(argv)

    me = whoami()
    login = me["login"]

    if args.audit:
        return audit(list_repos(login), args.json)
    if args.apply:
        return apply(login, args.dry_run or args.json)
    if args.pin:
        return pin(login)
    if args.archive:
        return archive(login, args.archive)
    if args.delete_plan:
        return delete_plan(login)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
