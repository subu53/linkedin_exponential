#!/usr/bin/env python3
"""Verify the Publora write path by capturing its HTTP, with no real key.

## Why this exists

The one part of the objective that cannot be verified with a real credential is
the part that matters most: does `lk publish` actually send Publora the right
thing? A wrong `platforms` shape or a missing `postedId` fails at the API with a
400 that looks like an account problem.

So this intercepts the HTTP layer, captures the exact request the engine builds,
and asserts it against the documented contract in `vendor/AGENTS.md`:

    POST /linkedin-comments  {postedId, message, platformId[, parentComment]}
    POST /create-post        {content, platforms[list of id strings][, scheduledTime]}
    POST /linkedin-reactions {postedId, platformId, reactionType}
    POST /linkedin-reshare   {platformId, parent[, commentary][, visibility]}

Nothing is sent anywhere and no credential is read. The assertions are the point:
if upstream changes a body key, this fails loudly instead of failing in
production against a real account.

Usage:
  python bin/verify_publora_wire.py
  python bin/verify_publora_wire.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
ROOT = BIN.parent
for _p in (str(ROOT / "vendor"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

POST_URL = "https://www.linkedin.com/posts/someone-activity-7448808898326654978-iW20"
PLATFORM_ID = "linkedin-TESTCHANNEL"


class Capture:
    """Records requests instead of sending them, and returns plausible replies."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def install(self) -> None:
        import requests

        self._requests = requests
        outer = self

        class FakeResponse:
            def __init__(self, payload: dict, status: int = 200) -> None:
                self._payload = payload
                self.status_code = status
                self.text = json.dumps(payload)
                self.content = self.text.encode()

            def json(self) -> dict:
                return self._payload

            def raise_for_status(self) -> None:
                if self.status_code >= 400:
                    raise outer._requests.HTTPError(f"HTTP {self.status_code}")

        def fake_request(method, url, **kwargs):
            body = kwargs.get("json") or {}
            outer.calls.append({"method": method, "url": url, "body": body,
                                "headers": kwargs.get("headers") or {}})
            path = str(url)
            if path.endswith("/platform-connections"):
                return FakeResponse({"connections": [{"platformId": PLATFORM_ID}]})
            if path.endswith("/linkedin-comments"):
                return FakeResponse({"comment": {"id": "cmt_1", "commentUrn": "urn:li:comment:(x,1)"}})
            if path.endswith("/linkedin-reactions"):
                return FakeResponse({"success": True})
            if path.endswith("/create-post"):
                return FakeResponse({"postGroupId": "pg_test_1"})
            if path.endswith("/linkedin-reshare"):
                return FakeResponse({"reshare": {"id": "urn:li:share:999"}}, status=201)
            return FakeResponse({"ok": True})

        # Patch the CLASS, not an instance: the engine calls
        # `self._session.request(...)`, so a per-instance patch never fires and
        # the capture silently stays empty while the request goes out for real.
        requests.Session.request = lambda self, method, url, **kw: fake_request(method, url, **kw)
        requests.request = fake_request
        requests.get = lambda url, **kw: fake_request("GET", url, **kw)
        requests.post = lambda url, **kw: fake_request("POST", url, **kw)

    def session_headers(self, session) -> dict:
        """Headers the client put on its session, which is how Publora auth works."""
        return dict(getattr(session, "headers", {}) or {})

    def note(self, method: str, suffix: str) -> dict | None:
        for call in reversed(self.calls):
            if call["method"].upper() == method.upper() and str(call["url"]).endswith(suffix):
                return call
        return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    # The engine reads these; a fake key is required for the publora tier to be
    # selected at all. Nothing leaves the machine - requests is patched first.
    os.environ["PUBLORA_API_KEY"] = "sk-fake-wire-verification-only"
    os.environ["LINKEDIN_PLATFORM_ID"] = PLATFORM_ID

    cap = Capture()
    cap.install()

    import lib  # noqa: E402  (after the patch)

    results: list[dict] = []

    def check(name: str, ok: bool, detail: str) -> None:
        results.append({"check": name, "ok": bool(ok), "detail": detail})

    # ── 1. comment
    client = lib.PubloraClient()
    session_hdrs = cap.session_headers(getattr(client, "_session", None))
    lib.publish("comment", "A specific, non-generic comment about the 2026 data.",
                POST_URL, post_urn="urn:li:activity:7448808898326654978")
    call = cap.note("POST", "/linkedin-comments")
    body = (call or {}).get("body", {})
    check("comment body keys",
          set(body) >= {"postedId", "message", "platformId"},
          f"keys={sorted(body)}")
    check("comment postedId is the post URN",
          body.get("postedId") == "urn:li:activity:7448808898326654978",
          f"postedId={body.get('postedId')!r}")
    check("comment platformId is a string",
          isinstance(body.get("platformId"), str),
          f"platformId={body.get('platformId')!r}")
    # Publora auth is a header on the session, not per-request, so this is where
    # it has to be checked.
    check("auth header x-publora-key set on the session",
          bool(session_hdrs.get("x-publora-key")),
          f"session headers: {sorted(session_hdrs)}")

    # ── 2. reply must carry parentComment
    lib.publish("reply", "A reply in the thread.", POST_URL,
                post_urn="urn:li:activity:7448808898326654978",
                parent_comment="urn:li:comment:(urn:li:activity:7448808898326654978,111)")
    body = (cap.note("POST", "/linkedin-comments") or {}).get("body", {})
    check("reply parentComment is the TOP-LEVEL urn",
          body.get("parentComment", "").endswith(",111)"),
          f"parentComment={body.get('parentComment')!r}")

    # ── 3. post: the shape that silently publishes nowhere if wrong
    lib.publish("post", "A post body.", "https://www.linkedin.com/post/new/")
    body = (cap.note("POST", "/create-post") or {}).get("body", {})
    platforms = body.get("platforms")
    check("post platforms is a LIST", isinstance(platforms, list), f"platforms={platforms!r}")
    check("post platforms entries are id STRINGS (not dicts)",
          bool(platforms) and all(isinstance(x, str) for x in platforms),
          f"platforms={platforms!r}")
    check("post content present", bool(body.get("content")), "content set")

    # ── 4. reaction aliasing: INSIGHTFUL is not a real LinkedIn reaction
    lib.publish("comment", "Comment with a reaction.", POST_URL,
                post_urn="urn:li:activity:7448808898326654978", reaction_type="INSIGHTFUL")
    react = cap.note("POST", "/linkedin-reactions")
    rbody = (react or {}).get("body", {})
    check("INSIGHTFUL is aliased to INTEREST (not sent verbatim)",
          rbody.get("reactionType") == "INTEREST",
          f"reactionType={rbody.get('reactionType')!r}")

    # ── 5. platform id derivation, where it actually happens
    #
    # Recorded finding: upstream's `active_backend()` requires BOTH the key and
    # LINKEDIN_PLATFORM_ID, so with only the key set it returns "manual" and the
    # engine's own derivation branch inside `publish()` is unreachable. The
    # supported path is to resolve the id and pass it explicitly, which is what
    # `lk publish` now does. These two checks pin both halves of that down.
    mark = len(cap.calls)
    saved = os.environ.pop("LINKEDIN_PLATFORM_ID", None)
    try:
        check("upstream active_backend() needs the platform id too (documented constraint)",
              lib.active_backend() == "manual",
              f"active_backend()={lib.active_backend()!r} with only the key set")

        resolved = lib.PubloraClient().resolve_linkedin_platform_id()
        fresh = cap.calls[mark:]
        asked = any(
            c["method"].upper() == "GET" and str(c["url"]).endswith("/platform-connections")
            for c in fresh
        )
        check("resolve_linkedin_platform_id() finds the single LinkedIn channel",
              asked and resolved == PLATFORM_ID,
              f"queried connections={asked}, resolved={resolved!r}")

        # And the mechanism the CLI relies on: because `publish()` dispatches on
        # the environment, the resolved id has to be exported for it to select
        # the publora branch at all. Passing `platform_id=` alone is ignored by
        # the manual branch - that was a real bug this check caught.
        os.environ["LINKEDIN_PLATFORM_ID"] = resolved
        mark2 = len(cap.calls)
        lib.publish(
            "post", "Post with an explicitly derived platform id.",
            "https://www.linkedin.com/post/new/",
        )
        post_call = next(
            (c for c in reversed(cap.calls[mark2:])
             if c["method"].upper() == "POST" and str(c["url"]).endswith("/create-post")),
            None,
        )
        check("exported platform id reaches POST /create-post",
              post_call is not None
              and (post_call.get("body") or {}).get("platforms") == [PLATFORM_ID],
              f"platforms={(post_call or {}).get('body', {}).get('platforms')!r}")
    finally:
        if saved is not None:
            os.environ["LINKEDIN_PLATFORM_ID"] = saved

    # ── 6. no stray requests, across the whole run
    urls = {str(c["url"]) for c in cap.calls}
    check("every request went to the Publora API",
          bool(urls) and all("api.publora.com" in u for u in urls),
          f"{len(cap.calls)} call(s) across {len(urls)} endpoint(s)")

    failed = [r for r in results if not r["ok"]]
    if args.json:
        print(json.dumps({"results": results, "failed": len(failed)}, indent=2))
    else:
        print("Publora write-path verification (HTTP captured, nothing sent)")
        print("")
        for r in results:
            print(f"  [{'PASS' if r['ok'] else 'FAIL'}] {r['check']:<46} {r['detail']}")
        print("")
        if failed:
            print(f"{len(failed)} check(s) failed - the wire format does not match the contract.")
            print("This would surface as a 400 from Publora against a real account.")
        else:
            print("All checks pass: the payloads match the documented Publora contract.")
            print("A real key is the only remaining unknown.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
