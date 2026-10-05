# Patches applied to vendored upstream files

`vendor/` is upstream code and is treated as read-only **by policy**. This file
exists because the policy has four deliberate exceptions. Each one is here so a
future re-vendor knows exactly what to re-apply, and so nothing is edited
silently.

Upstream: `sergebulaev/linkedin-skills` @ `2f00424615b9853e8b1aa003d8752179bbeabb09` (v1.1.16, MIT).

---

## 1. `vendor/SKILL.md` → `vendor/UPSTREAM-BUNDLE.md` (renamed)

**Why:** this file is the bundle's root document (`name: linkedin-marketing`),
not a skill. In this runtime, skill discovery treats *any* directory containing
`SKILL.md` as a skill, and the installed layout reaches `vendor/` through a
junction. The result was a 13th, out-of-scope `linkedin-marketing` entry in the
catalog, whose instructions duplicate and conflict with the 12 ported skills.

**Effect:** the file is unchanged in content and still ships; it is simply no
longer named `SKILL.md`, so discovery ignores it.

**Re-apply after re-vendoring:** rename it again. If you would rather keep the
upstream name, delete it instead — nothing in the port reads it.

## 2. `vendor/scripts/check_markdown_references.py`

Two changes:

- `documents()` scans `UPSTREAM-BUNDLE.md` instead of `SKILL.md` (follows from
  patch 1).
- `resolves()` now also walks the citing document's ancestor directories, up to
  (not beyond) the repo root.

**Why the second change:** the checker's original rule was "resolves relative to
the citing document, or relative to the repo root". A file at
`skills/<skill>/sub-skills/x.md` that names `` `SKILL.md` `` means *that skill's*
manifest, which is exactly how the runtime resolves it. The original two-base
rule missed the skill directory in between, so it reported three breaks that do
not exist at runtime. The walk stops at the repo root so a bare name can never
escape the bundle.

**This is a fix to the checker, not a weakening of it.** Before the change it
flagged 3 false positives and 1 real break; after it, 0 and 0.

## 3. `vendor/references/founder-topics.md` line 383

`` `SKILL.md` `` → `` `UPSTREAM-BUNDLE.md` ``. Follows from patch 1; this was the
one genuine break.

## 4. `vendor/tests/test_instruction_integrity.py` (lines 113, 188)

`ROOT / "SKILL.md"` → `ROOT / "UPSTREAM-BUNDLE.md"`. Follows from patch 1, so the
suite still covers the root document rather than skipping it. The tests fail
loudly if this is not re-applied, which is the desired behaviour.

---

## Not patched, but worth knowing

- **`active_backend()` requires BOTH credentials, which makes its own derivation
  code unreachable.** `lib/backend_selector.py` returns `"publora"` only when
  `PUBLORA_API_KEY` **and** `LINKEDIN_PLATFORM_ID` are both set. Inside
  `publish()` there is a branch that resolves a missing platform id from the key
  — but it sits in the publora branch, which that same check prevents from being
  selected. So with only the key set, publishing silently downgrades to
  copy-paste while the engine's own documented behaviour ("the bundle works the
  platform id out from the key on its own") never runs.

  **Not patched in `vendor/`.** `bin/lk.py` resolves the id itself and exports
  `LINKEDIN_PLATFORM_ID` for the run, because `publish()` dispatches on the
  environment and ignores a `platform_id=` kwarg on the manual path. This is a
  genuine upstream defect worth reporting: either the gate should accept a
  derivable id, or `publish()` should resolve before dispatching. Both halves are
  pinned by checks in `bin/verify_publora_wire.py` so a future re-vendor surfaces
  it immediately.

- **`reference_read_text_without_encoding`** — several `read_text()` calls in
  `tests/test_instruction_integrity.py` omit `encoding=`, which raises
  `UnicodeDecodeError` on a Windows cp1252 console. **Not patched**, because
  `PYTHONUTF8=1` fixes it without touching upstream, and `bin/lk` sets that
  variable itself. If you run the suite by hand on Windows, set it:
  `$env:PYTHONUTF8=1`.
- **`Il Giornale`/PyYAML** — six tests need `yaml`, which is a dev-only
  dependency (`vendor/requirements-dev.txt`). Since `pip` cannot reach PyPI in
  this environment, the `cp312-win_amd64` wheel was fetched over Node's `fetch`
  and extracted into `vendor/.pylibs/`. `bin/lk` and `bin/vendor_test.py` add that
  directory to `sys.path` automatically. It is gitignored; re-provision with
  `python bin/vendor_test.py --provision`.
- **`skills/linkedin-post-writer/SKILL.md:76`** cites `` `references/founder-topics.md` ``
  where the file is actually at the bundle root. Upstream's own checker cannot
  catch it, because that reference also resolves against the repo root. Harmless
  in practice; flagged here for an upstream report.
- **`vendor/lib/_env.py`** silently no-ops when `python-dotenv` is missing
  (`except ImportError: pass`). **Not patched** — `bin/lk` loads the bundle's
  `.env` itself before importing the engine, which fixes the observable problem
  without diverging from upstream.
- **`linkedin-humanizer` is an imaginary CLI.** Six upstream skills invoke
  `linkedin-humanizer --mode audit` (and `--mode profile`, `strict`, `forensic`,
  `all`) as if it were a binary. **No such entry point exists upstream.** Not
  patched in `vendor/`; instead `bin/linkedin-humanizer` implements the documented
  surface so those instructions work. See `bin/linkedin-humanizer --help`.
