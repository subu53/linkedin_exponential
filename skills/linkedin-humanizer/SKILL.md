---
name: linkedin-humanizer
description: "Remove the AI tells human readers and LinkedIn's 2026 slop filter react to, or audit a draft before publishing. Scores AI vocabulary by paragraph density, caps em dashes, breaks staccato fragments and stacked triads, and runs a pre-publish algorithm check. Use to humanize a draft or review one before it goes out. Not for writing a post from scratch (use linkedin-post-writer)."
version: 1.0.0
---

# LinkedIn Humanizer (DeepSeek build)

## Read this first

- **Instructions:** `../../vendor/skills/linkedin-humanizer/SKILL.md`
- **Sub-skills:** `../../vendor/skills/linkedin-humanizer/sub-skills/`
  (post-audit, emoji-detector, detector-tester, rules-explainer)
- **References:** `../../vendor/references/voice-rules.md`

Host notes: [REFERENCE.md](REFERENCE.md) ·
Approval rules: [../../references/approval-and-voice.md](../../references/approval-and-voice.md)

## Two modes

- **Rewrite (default):** scrub AI tells from the text the operator pasted.
- **`--mode audit`:** review a draft against algorithm rules without rewriting it.
  Ask which the operator wants if it is ambiguous.

## The one thing this skill must not do

It must not promise the text will beat an AI detector. No edit reliably does,
and the upstream instructions say so explicitly. Report what was changed and
why; do not claim the result "reads as 100% human" or will pass GPTZero.

## Rules that beat your instincts

- Preserve every number, name, and date exactly. A scrub that "tidies" a figure
  is a failed scrub - that figure was the credibility.
- Cap em dashes at roughly one per 100 words. Do not ban them.
- Never add AI vocabulary while removing it. Watch for "leverage",
  "streamline", "delve", "unlock", "harness", "foster", "fundamentally".
- Keep the operator's meaning. Removing a tell must not remove the claim.
