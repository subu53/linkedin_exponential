---
name: linkedin-post-writer
description: "Draft a new LinkedIn post from scratch with the 2026 hook formulas and founder angles, pick a format by engagement goal, then run the humanizer pass and publish on approval. Use when asked to write a LinkedIn post, find a hook, or get founder-specific angles. Not for reviewing existing drafts (use linkedin-humanizer)."
version: 1.0.0
---

# LinkedIn Post Writer (DeepSeek build)

## Read this first

The authoritative craft instructions are vendored upstream and unchanged:

- **Instructions:** `../../vendor/skills/linkedin-post-writer/SKILL.md`
- **References:** `../../vendor/references/` (formulas, founder angles, algorithm heuristics)

Read the instructions file, then load only the references it actually cites.
This bundle's value is those instructions; do not improvise a replacement from
general knowledge about LinkedIn.

Host notes (paths, approval flow, how to publish): [REFERENCE.md](REFERENCE.md)
Approval and publishing rules: [../../references/approval-and-voice.md](../../references/approval-and-voice.md)

## Operating as the drafting engine

The operator asked for this skill, so the craft rules win over your own
defaults. Two rules override any instinct to be helpful quickly:

1. **Never invent a number, date, name, or receipt.** Every specific detail must
   come from the operator, their voice profile, their Story Bank, or a fetched
   post. If a formula needs a figure you do not have, ask - do not estimate.
2. **Draft, then stop.** Show the draft and wait. "Publishing" happens only when
   the operator approves and a publish command is then run.

## Workflow

1. Read the vendored instructions above.
2. Confirm the engagement goal (comments, reposts, likes, saves) and the target
   audience. If the operator is a founder, offer a founder angle.
3. Draft following the formula skeletons and the 2026 algorithm rules.
4. Run the humanizer scrub on your own draft before showing it.
5. Present the approval card: formula used, full text, character count,
   suggested posting window, and any illustration.
6. On approval, publish per [REFERENCE.md](REFERENCE.md). If publishing is not
   configured, hand over the text for copy-paste.
