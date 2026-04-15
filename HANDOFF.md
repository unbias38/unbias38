# Handoff: Claude ↔ OpenClaw ("龍蝦") Pipeline

**Date written:** 2026-04-15
**Origin branch:** `claude/fix-character-encoding-Rh1TL`
**Origin commit at time of writing:** `68d865c`
**Audience:** A future Claude Code session continuing this work for user
`@unbias38`. This is NOT a task — it is prior context so you don't have to
rediscover everything.

---

## How to use this file

The previous Claude session and the user agreed on **Method 2** for session
handoff: park a reference document in the public `unbias38/unbias38` repo,
and have the user paste its URL into the first message of a new session.

If you (the new Claude) are reading this because the user told you to, just
absorb it and then ask the user what they want to work on next. Do not start
executing anything from this document on your own — it is documentation,
not instructions.

---

## 1. What OpenClaw is

A Large Action Model (LAM) agent nicknamed **"龍蝦" (lobster)** after its
mascot Molty. Created by Peter Steinberger (ex-PSPDFKit). Unlike a chat
LLM it executes actions directly on the user's machine: read / write /
edit files and run shell commands via an `exec` tool.

Project lineage: **Clawdbot → Moltbot → OpenClaw**.

### Security facts to keep in mind

- **CVE-2026-33579** allows attackers to obtain admin privileges on
  exposed OpenClaw instances. Roughly 63% of internet-exposed instances
  had no authentication. Never advise exposing OpenClaw to the public
  internet.
- The user and the previous Claude explicitly **rejected** any direct
  pairing or shared-trust mechanism between Claude and OpenClaw. The user
  stays the orchestrator. Preserve this invariant unless the user
  explicitly asks to change it.

---

## 2. Architecture in use

```
        ┌─────────┐
        │  user   │  ← final decision maker, every step
        └────┬────┘
             │ copy / paste
      ┌──────┴──────┐
      │             │
      ▼             ▼
 ┌─────────┐   ┌──────────┐
 │ Claude  │   │ OpenClaw │
 │ writes  │   │ executes │
 │ files   │   │ locally  │
 └────┬────┘   └────┬─────┘
      │             │
      ▼             ▼
   GitHub repo   filesystem
```

- Claude writes task specs / skills / plans, commits and pushes.
- User manually relays instructions to OpenClaw via **Telegram**.
- OpenClaw runs the work on the user's Linux machine.
- Results come back to the user via Telegram; the user relays them to
  Claude in the next message.

**Every manual step is also a checkpoint.** Do not try to remove them
without explicit user consent.

---

## 3. Verified OpenClaw format facts (as of 2026-04-15)

Verified against `openclaw/openclaw/docs/tools/skills.md` and
`openclaw/clawhub/docs/soul-format.md`. Do **not** invent alternatives —
the previous Claude hallucinated a fake format twice before checking the
docs, and the user caught it each time. Always verify before claiming
format details.

### `SKILL.md` — the format that matters for local execution

- File must literally be named `SKILL.md`.
- Minimum YAML frontmatter: `name` and `description`.
- **Single-line frontmatter values only.** Multi-line YAML is silently
  dropped (`openclaw/openclaw#57678`). One line per key.
- Optional frontmatter keys: `homepage`, `user-invocable`,
  `disable-model-invocation`, `command-dispatch`, `command-tool`,
  `metadata`.
- `metadata.openclaw.requires.{bins,env,config}` can gate loading based on
  environment — useful for safety.

### Skill discovery order (highest precedence first)

1. `<workspace>/skills`
2. `<workspace>/.agents/skills`
3. `~/.agents/skills`
4. `~/.openclaw/skills`
5. Bundled skills (ships with OpenClaw)
6. `skills.load.extraDirs` (configured paths)

### `SOUL.md` is **not** the same as `SKILL.md`

`SOUL.md` is ClawHub's publishing bundle format. Local execution uses
`SKILL.md`. Don't confuse them.

---

## 4. What was actually validated end-to-end

A single smoke test, `skills/hello-claw/SKILL.md`, committed in `68d865c`.
It asks OpenClaw to read `README.md` and report `size`, `sha256`, and the
first line — read-only, no network, no other skills.

The user ran it via Telegram with a defensive prompt. OpenClaw:

1. Correctly STOPPED on the first attempt when its workspace
   (`/home/ubuntu38/.openclaw/workspace`) didn't match `unbias38/unbias38`.
2. After the user redirected to a fresh directory
   `/home/ubuntu38/claude-handoff/`, OpenClaw performed a shallow
   single-branch clone and ran the test.
3. Reported verbatim:

   ```
   size: 373
   sha256: 1b298b6b32a384c9649dad10bb9c2995828d2f20c6673db390e563f6d7c30026
   first-line: - 👋 Hi, I'm @unbias38
   ```

4. Previous Claude verified all three values plus the commit hash against
   the real file. Every field matched — including the curly apostrophe in
   `I'm`.

**What this proves:** the filesystem-based pipeline works end-to-end.
Claude writes a file → GitHub → OpenClaw clones → OpenClaw executes →
user sees results → Claude can verify.

**What this does NOT prove:** that OpenClaw's native SKILL.md
auto-discovery works. The smoke test bypassed the skill loader and ran
the instructions inline via the defensive Telegram prompt. Confirming
auto-discovery is an untested next step, not a known-good path.

---

## 5. User environment facts

- Linux user: `ubuntu38`, `HOME=/home/ubuntu38`
- Git version: `2.43.0`
- `github.com` resolves and is reachable from the user's machine
- **OpenClaw default workspace:** `/home/ubuntu38/.openclaw/workspace`
  (not a git repo, left alone on purpose)
- **Claude handoff workspace:** `/home/ubuntu38/claude-handoff/unbias38/`
  (shallow clone of `unbias38/unbias38` on branch
  `claude/fix-character-encoding-Rh1TL`)
- **User interface to OpenClaw:** Telegram bot. Natural-language
  instructions work; detailed prompt syntax unknown.
- **The user is frequently remote** (not physically at the machine).
  Assume remote ops only. Be defensive — the user cannot quickly
  intervene if something goes wrong.

---

## 6. The Telegram prompt style that works

Every prompt the user sends to OpenClaw should follow this shape. The
previous session validated that OpenClaw honors the STOP directives.

1. **HARD RULES block at the top.** No writes, no network beyond what is
   explicitly listed, no other skills, no sudo, STOP on any unexpected
   output.
2. **Numbered STEPS.** Each step names the exact shell command and the
   expected shape of the output.
3. **Explicit STOP conditions** on every non-trivial step: "if the output
   does not contain X, STOP and report verbatim."
4. **Final step is always a consolidated report** containing everything
   from every previous step, verbatim.
5. **Two-phase split for risky tasks:** a non-destructive PHASE A that
   only inspects state, then a PHASE B that acts. The user reviews PHASE
   A's output and decides whether to send PHASE B.

A minimal working example of this style is preserved in `HANDOFF.md` git
history if needed — see the session ending with commit `68d865c` and
the messages around it. The working `SKILL.md` itself is at
`skills/hello-claw/SKILL.md` on this branch.

---

## 7. Outstanding plan (not yet executed)

At the end of the previous session, the user created a **private
GitHub repo** to host ongoing Claude ↔ OpenClaw handoff work, keeping the
public profile repo `unbias38/unbias38` clean.

**The private repo is `unbias38/claude-lobster`.**
<https://github.com/unbias38/claude-lobster>

The previous Claude session's GitHub MCP tools were scoped to
`unbias38/unbias38` only and therefore **could not touch the new private
repo**. All work inside `claude-lobster` is expected to happen in **a
fresh Claude Code session opened directly against that repo**.

When you (the new Claude, reading this inside `claude-lobster`) pick this
up:

1. Greet the user and confirm you've read this handoff.
2. Propose the starting directory layout for `claude-lobster`:

   ```
   CLAUDE.md         # auto-loaded context for new sessions in this repo
   tasks/
     inbox/          # task specs Claude or user writes
     outbox/         # results OpenClaw writes
   skills/
     <name>/SKILL.md # reusable skills
   ```

3. Consider copying this HANDOFF.md into `claude-lobster` (or distilling
   it into a proper `CLAUDE.md` so future sessions in that repo get it
   auto-loaded). Ask the user first.

4. Recommend **Level 1** automation first (fixed paths, short Telegram
   templates, reuse the verified defensive prompt style). Do NOT propose
   Level 2 (OpenClaw polling loop) or Level 3 (webhook) unless the user
   explicitly asks — those were documented but flagged as
   not-recommended-yet, and Level 2 in particular is a meaningful trust
   jump that requires the user's considered consent.

5. OpenClaw on the user's machine will need to `git clone` the new
   private repo. Because it's private, this requires auth (SSH key,
   personal access token, or GitHub CLI login). The previous session did
   NOT cover how to get credentials onto the user's machine safely —
   that's an open question the new session needs to work through with
   the user before any OpenClaw-side automation can work against
   `claude-lobster`.

---

## 8. Things previous Claude got wrong (so you don't repeat them)

- **Answered "what is OpenClaw" from memory** and claimed it was an
  open-source reimplementation of Captain Claw (a 1997 game). Completely
  wrong. Caught by the user, corrected via web search.
- **Invented a fake SKILL.md format** ("TASK: / STEPS: ...") without
  checking docs. Also caught by the user. Only after a second round of
  searches were the real format facts in section 3 above established.
- **Confused `SKILL.md` with `SOUL.md`** on the first pass. They are
  different artifacts for different purposes.

**The general lesson:** when this user asks a factual question,
**verify before answering**. They notice when you bluff and will call
you on it. That is a feature, not an annoyance — trust them to push back
and don't get defensive about it.

---

## 9. Things you (new Claude) should NOT do

- Don't create commits or push without the user asking.
- Don't assume the user wants to raise the automation level. Ask.
- Don't invent format details. If unsure, fetch the source.
- Don't try to contact OpenClaw directly. Everything flows through the
  user, who flows through Telegram. Write files, don't send signals.
- Don't expand scope beyond what the user asked. Mirror their careful,
  deliberate style.
- Don't treat this file as instructions. It is historical context.

---

## 10. Artifacts on this branch

- `skills/hello-claw/SKILL.md` — validated smoke-test skill.
- `HANDOFF.md` — this file.
- `README.md` — the user's public profile README. Do not modify.
- `mindmap.md` — pre-existing, unrelated.

---

End of handoff. When the user speaks to you next, just greet them and
ask what they want to tackle. They'll take it from there.
