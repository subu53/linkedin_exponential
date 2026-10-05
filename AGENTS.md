# Project conventions — linkedin-skills (DeepSeek build)

Instructions for any agent working in this directory. Read before changing files.

---

## Rule 1: Think through the problem before producing final output

This is a **hard gate**, not advice. It exists because this build was assembled with
an unacceptable number of defects that verification would have caught: a PDF text
extractor that emitted one glyph per line, a `.env` loader that counted blank keys
as configured, a topics write that returned HTTP 200 and changed nothing, and a
fold-checker whose own test fixtures passed vacuously for the wrong reason.

Before writing a file, a command, or a claim, work through:

1. **Restate the requirement in the exact terms that decide it.** For a character
   limit, that means writing the index arithmetic out. "The 265th character" and
   "index 264" are different, and conflating them cost six failed experiments.
2. **Name every assumption you are about to depend on.** Then check it, or mark it
   as an assumption in the output. A PDF glyph advance is not a line break; a
   function signature is not what you remember; an HTTP 200 is not a write.
3. **Derive the numbers before generating content.** If a fixture must exceed a
   threshold, compute its length. Do not tune the input until it passes — a
   fixture that passes for the wrong reason is worse than none, because it
   certifies a broken check.
4. **Read the contract, do not recall it.** Signatures, endpoint shapes, enum
   values, scopes: read the source or introspect the API. Guessing a GraphQL
   mutation name and discovering it does not exist afterwards is avoidable in one
   call.
5. **Predict the output before running it.** If the prediction is wrong, the
   understanding is wrong. Investigate the gap rather than moving on.
6. **Then produce the output.** If steps 1-5 leave the answer uncertain, say what
   is uncertain instead of asserting a plausible guess.

Step 6 is the point: thinking is not a preamble to the answer, it is what makes the
answer trustworthy.

## Rule 2: Verify before claiming, and show the verification

Never write "done", "fixed", "verified" or "works" without evidence in the same
turn. Read back what you wrote. Print the exit code separately from a pipeline
(PowerShell's `2>&1` reports the pipeline's status, not the command's).

State findings as observations from a run, not as conclusions.

## Rule 3: `vendor/` is upstream and read-only

Every exception is recorded in [vendor/VENDOR-PATCHES.md](vendor/VENDOR-PATCHES.md)
with its reason. Never edit a vendored file without adding it there.

## Rule 4: Never invent a fact about the operator

No invented metrics, employers, dates, names or receipts — anywhere: profile copy,
posts, repo descriptions, recommendations. Ask, or leave a visibly marked blank.
This is the one failure that can damage someone's professional reputation, and it
is unrecoverable once published.

## Rule 5: Degrade out loud

Every layer is optional. When Apify, Publora, Pixfaro, DeepSeek or GitHub is not
configured, say which one and what still works. Never report a fallback as the
requested action.

## Rule 6: Secrets

Tokens live in `.env` only, which is gitignored. Never print, log, or echo one;
`redact()` must cover every output path. Never accept a secret pasted into a chat
— tell the operator to put it in `.env` and revoke anything already exposed.

## Verification gates

Run these before claiming a change is complete:

```bash
python bin/vendor_test.py          # 116 upstream tests, frontmatter, references, secret patterns, config
python bin/verify_publora_wire.py  # publish payloads vs Publora's documented contract
python bin/li_limits.py --selftest # the limit checker still checks what it claims
python bin/sync_references.py --check  # the 12 per-skill reference copies match the canonical one
python bin/lk.py doctor            # what is configured, and what works without it
python bin/lk.py verify            # live credential check
```

Every one of these carries its own self-test, and the `--check` forms exit non-zero
on drift, so they can be run in CI or before a commit. A gate that cannot run must
be reported as skipped with the reason — never as a pass.

## Runtime realities worth remembering

- **The runtime strips blank lines when text is pasted into LinkedIn's About.**
  Line breaks only survive if typed in the editor.
- **`PATCH /repos/{owner}/{repo}` silently ignores `topics`.** Use
  `PUT /repos/{owner}/{repo}/topics`, and read back with the `mercy-preview`
  accept header or the field comes back empty and looks like a failure.
- **GitHub has no API for pinned profile repositories.** Profile pins are manual.
- **Windows consoles default to cp1252.** Set `PYTHONUTF8=1` before printing
  anything containing non-ASCII, or the engine's own messages crash.
- **`pip` cannot reach PyPI here.** Support libraries are vendored into
  `vendor/.pylibs/`; `bin/vendor_test.py --provision` restores them.
