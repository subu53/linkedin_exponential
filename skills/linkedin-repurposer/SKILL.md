---
name: linkedin-repurposer
description: "Turn content from another platform - a tweet, thread, YouTube video, blog, or newsletter - into a native LinkedIn post: re-hook for the fold, expand to the 900-1300 character sweet spot, move links to the first comment, and run the humanizer. Use to adapt existing content for LinkedIn."
version: 1.0.0
---

# LinkedIn Repurposer (DeepSeek build)

## Read this first

- **Instructions:** `../../vendor/skills/linkedin-repurposer/SKILL.md`
- **References:** `../../vendor/references/hook-formulas.md`,
  `../../vendor/references/voice-rules.md`

Host notes: [REFERENCE.md](REFERENCE.md) ·
Approval rules: [../../references/approval-and-voice.md](../../references/approval-and-voice.md)

## Inputs

The source content itself, pasted or described. If it is a URL you cannot fetch
(there is no read layer for X, YouTube, or blogs), ask the operator to paste it.

## The native-ness rules

- **Re-hook.** The source's opening was built for another feed. Write a new first
  line for the LinkedIn fold (~210 characters), then keep the body.
- **Expand, do not shrink.** 900-1,300 characters is the default target. A short
  tweet usually needs the argument spelled out, not padded.
- **Strip cross-platform artifacts.** "Thread 🧵", "RT if", "link in bio",
  numbering conventions, and platform-specific slang all read as imported.
- **External links leave the body.** Move them to the first comment, and say so.

## Honesty rule

Keep every claim, number, and name exactly as the source had it. Do not
strengthen a claim to make the repost land harder.
