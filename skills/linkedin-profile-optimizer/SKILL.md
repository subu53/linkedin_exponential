---
name: linkedin-profile-optimizer
description: "Rewrite a LinkedIn headline, About section, Featured section, and Experience entries for 2026 conversion patterns and inbound leads. Use to optimize a profile. Not for writing posts or comments on the feed (use linkedin-post-writer or linkedin-comment-drafter)."
version: 1.0.0
---

# LinkedIn Profile Optimizer (DeepSeek build)

## Read this first

- **Instructions:** `../../vendor/skills/linkedin-profile-optimizer/SKILL.md`
- **References:** `../../vendor/references/voice-profile.md`,
  `../../vendor/references/voice-rules.md`

Host notes: [REFERENCE.md](REFERENCE.md) ·
Approval rules: [../../references/approval-and-voice.md](../../references/approval-and-voice.md)

## Inputs

The operator's current profile text. A profile URL does **not** give you the
profile: the read layer fetches posts, comments, and engagers, not profile
bodies. Ask the operator to paste their headline, About, and role history.

## Field limits matter here

LinkedIn truncates: the headline cuts at roughly 220 characters and the About
section is capped at 2,600, with only the first ~3 lines visible before "see
more". Write to the visible fold, then to the cap. State the character count for
every field you return, so the operator can see it fits before pasting.

## Honesty rule

Do not invent titles, metrics, employers, or client names. If the current
profile lacks a number that would carry the section, ask for it or leave a
clearly marked blank - never fill it with a plausible-sounding figure.
