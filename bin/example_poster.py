#!/usr/bin/env python3
"""A working custom poster for the `diy` tier.

`lib.publish` can delegate publishing to a program of your own instead of
Publora. This file is that program, and it is deliberately the smallest useful
one: it is both a runnable poster and the specification for the protocol.

Wire it up by putting this in `.env`:

    LINKEDIN_SKILLS_CUSTOM_POSTER=python bin/example_poster.py

`.env.example` section 5 explains when that is the right choice. Keep in mind
that this tier *executes* whatever the variable points at, every time a draft is
approved. Only ever point it at code you have read.

## The protocol (`lib/backend_selector.publish`, `diy` branch)

The parent process runs:

    <LINKEDIN_SKILLS_CUSTOM_POSTER> <kind> <target_url>

with this JSON on **stdin**:

    {
      "kind":        "post" | "comment" | "reply" | "reshare",
      "draft_text":  "<the approved draft>",
      "target_url":  "<where it goes>",
      ...            # backend-specific extras, e.g. post_urn, parent_comment,
                     # platforms, scheduled_time, media_urls, parent
    }

and expects:

  * exit code 0 for success, non-zero for failure
  * anything you print on stdout is captured and shown to the operator
  * `unpublish` is called the same way with kind "unpublish"

## Why this is draft-only-plus, not a LinkedIn login

This script does **not** log into LinkedIn. It cannot, and neither can anything
else in this bundle: LinkedIn has no public posting API for third-party apps
without a partner integration, so there is no supported way to hand it an
account and have it post. Point your own poster at whatever authorized path you
actually use - an internal service, a browser session you drive yourself, a
partner API - and understand the terms and ban risk of that choice yourself.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "testing" / "custom-poster.log.jsonl"


def main() -> int:
    payload = {}
    if not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as exc:
                print(f"stdin was not valid JSON: {exc}", file=sys.stderr)
                return 2

    kind = sys.argv[1] if len(sys.argv) > 1 else payload.get("kind", "post")
    target = sys.argv[2] if len(sys.argv) > 2 else payload.get("target_url", "")

    if kind == "unpublish":
        # The parent passes the post group id as argv[2] for this kind.
        print(f"unpublish requested for {target or '(no id given)'} - nothing to do in this example")
        return 0

    draft = payload.get("draft_text", "")
    if not draft:
        print("nothing to publish: no draft_text in the payload", file=sys.stderr)
        return 2

    # ------------------------------------------------------------------
    # Replace this block with your real posting call.
    #
    # For example, POST to an internal service:
    #
    #   import requests
    #   resp = requests.post(
    #       "https://your-service.example/publish",
    #       json={"kind": kind, "text": draft, "target": target},
    #       headers={"Authorization": f"Bearer {os.environ['MY_SERVICE_TOKEN']}"},
    #       timeout=60,
    #   )
    #   resp.raise_for_status()
    #   print(resp.json())
    #
    # Until you do, this example records the call and reports success, so the
    # tier can be exercised end to end without touching a real account.
    # ------------------------------------------------------------------
    LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "at": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "target": target,
        "chars": len(draft),
        "draft": draft,
    }
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(
        json.dumps(
            {
                "mode": "diy-example",
                "kind": kind,
                "target": target,
                "chars": len(draft),
                "logged_to": str(LOG),
                "note": "This example poster records the draft and does NOT post it. "
                        "Edit bin/example_poster.py to call your real endpoint.",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
