---
name: hello-claw
description: Minimal read-only smoke test that verifies OpenClaw can load a SKILL.md authored by Claude and report a deterministic result for README.md
---

# Hello Claw

A minimal smoke test for the Claude ↔ OpenClaw handoff convention in this
workspace. The goal is NOT to do real work — it is only to confirm that:

1. OpenClaw can discover and load a `SKILL.md` placed at
   `<workspace>/skills/hello-claw/SKILL.md`.
2. OpenClaw can follow instructions written as plain Markdown by Claude.
3. The result is deterministic, so a human can verify it trivially.

## Purpose

Run this skill once after installing OpenClaw (or after changing how Claude
writes skill files) to confirm the handoff pipeline still works end-to-end.
If this skill cannot be loaded or executed, no other Claude-authored skill
in this workspace should be trusted either — fix this one first.

## Instructions

Perform exactly the following steps, in order, and nothing else:

1. Read the file `README.md` located at the workspace root.
2. Compute the file size of `README.md` in bytes.
3. Compute the SHA-256 hash of the raw bytes of `README.md`, in lowercase hex.
4. Extract the first line of `README.md` (everything before the first `\n`).
5. Print the result to stdout using exactly this format, one field per line:

   ```
   size: <bytes>
   sha256: <lowercase-hex>
   first-line: <content>
   ```

6. Exit successfully.

## Constraints

The following are hard rules. If any of them cannot be satisfied, abort the
skill, report the reason, and make no other changes.

- Do NOT modify, create, move, or delete any file in this workspace.
- Do NOT run any shell command other than what is strictly required to read
  `README.md` and compute its size and SHA-256 hash.
- Do NOT access the network.
- Do NOT read any file other than `README.md`.
- Do NOT invoke any other skill.
- Do NOT require elevated privileges.

## Expected output (example)

The exact values will differ — only the shape matters:

```
size: 373
sha256: 0000000000000000000000000000000000000000000000000000000000000000
first-line: - 👋 Hi, I'm @unbias38
```

## How to verify manually

A human can reproduce the expected values from a trusted shell:

```
wc -c < README.md
sha256sum README.md
head -n 1 README.md
```

If OpenClaw's output matches these three values, the handoff works.
