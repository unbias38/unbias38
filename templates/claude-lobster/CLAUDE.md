# CLAUDE.md — `unbias38/claude-lobster`

You are in the private repo `unbias38/claude-lobster`, which hosts the
Claude ↔ OpenClaw ("龍蝦") handoff workflow for user `@unbias38`.

## Read this first every session

This file is your briefing. Read it in full before replying to the
user's first message. You have no memory of previous sessions —
everything you need is in files.

For the full session-1 history and rationale, see:

  https://raw.githubusercontent.com/unbias38/unbias38/claude/fix-character-encoding-Rh1TL/HANDOFF.md

You don't have to fetch it unless the user asks a question this file
doesn't answer — but it is the source of truth if anything here is
ambiguous.

## Core invariants (do not break without user consent)

1. **The user is the orchestrator.** Claude writes files. OpenClaw
   executes them. The user manually relays messages between them via
   Telegram. Every manual step is also a checkpoint — it is a feature.
2. **No direct Claude ↔ OpenClaw coupling.** No shared auth, no API
   key sharing, no webhooks, no polling loops — unless the user
   explicitly asks to add one.
3. **Verify before claiming format facts.** Previous Claude
   hallucinated OpenClaw format details twice and was caught both
   times. When in doubt, fetch the source from `openclaw/openclaw`
   docs on GitHub.
4. **Ask before acting on anything non-trivial.** The user is careful
   and deliberate. Mirror that.

## Intended directory layout

```
CLAUDE.md                  # this file
tasks/
  inbox/                   # task specs Claude writes for OpenClaw
    example-task.md        # reference format
  outbox/                  # result reports OpenClaw writes back
    example-result.md      # reference format
skills/
  hello-claw/
    SKILL.md               # validated smoke-test skill
```

If files besides these exist, ask the user what they are before
touching them.

## Task lifecycle (Level 1 — manual flow)

1. **User asks Claude for a task.** Claude writes the spec as a
   numbered, defensive Markdown file to `tasks/inbox/<slug>.md` (see
   `tasks/inbox/example-task.md` for format). Commits. Pushes. Tells
   the user the commit is ready.
2. **User sends one short message to OpenClaw via Telegram**, e.g.:

       pull and run tasks/inbox/<slug>.md in the claude-lobster clone,
       write the result to tasks/outbox/<slug>.md, commit and push.

3. **OpenClaw** pulls, reads the task file, executes it (following the
   HARD RULES and STOP conditions inside it), writes its result to
   `tasks/outbox/<slug>.md`, commits, and pushes.
4. **User tells Claude** to check. Claude reads
   `tasks/outbox/<slug>.md` and reports back.

Do NOT attempt to collapse or automate any of these steps without
explicit user consent. Each manual step is a checkpoint; removing them
is a trust jump, not just a convenience tweak.

## Telegram prompt / task-file style essentials

Every task spec in `tasks/inbox/` and every Telegram message to
OpenClaw must follow this shape — it is what was validated to work in
session 1:

- **HARD RULES block at the top.** No writes outside the specified
  output path, no network beyond what is explicitly listed, no sudo,
  no other skills, STOP on any unexpected output.
- **Numbered STEPS.** Each step names the exact shell command and the
  expected shape of the output.
- **Explicit STOP conditions** on every non-trivial step:
  "if output does not contain X, STOP and report verbatim."
- **Final step is always a consolidated report** containing everything
  from every previous step, verbatim.
- **For risky tasks, split into PHASE A and PHASE B.** PHASE A is
  read-only inspection. PHASE B acts. The user reviews PHASE A's
  output before sending PHASE B.

See `tasks/inbox/example-task.md` for a fleshed-out example of a full
task file using this style.

### Evidence that this style works

In session 1, an earlier version of this defensive prompt was sent to
OpenClaw via Telegram and OpenClaw **correctly STOPPED at STEP 0**
because its workspace did not match `unbias38/unbias38`. That is the
intended behavior. The subsequent PHASE B (after the user redirected
to a fresh handoff directory) ran cleanly and produced a verified
sha256 match against the file Claude had just committed. End-to-end.

## Verified OpenClaw format facts (from session 1)

All verified against `openclaw/openclaw/docs/tools/skills.md` and
`openclaw/clawhub/docs/soul-format.md`. Do NOT invent alternatives.

**`SKILL.md`** (local execution format):

- File must literally be named `SKILL.md`.
- Minimum YAML frontmatter: `name` and `description`.
- **Single-line frontmatter values only.** Multi-line YAML is silently
  dropped — see `openclaw/openclaw#57678`. One line per key.
- Optional keys: `homepage`, `user-invocable`,
  `disable-model-invocation`, `command-dispatch`, `command-tool`,
  `metadata`.
- `metadata.openclaw.requires.{bins,env,config}` can gate loading based
  on environment — useful for safety.

**Skill discovery order** (highest precedence first):

1. `<workspace>/skills`
2. `<workspace>/.agents/skills`
3. `~/.agents/skills`
4. `~/.openclaw/skills`
5. Bundled skills (shipped with OpenClaw)
6. `skills.load.extraDirs`

**`SOUL.md` is NOT `SKILL.md`.** `SOUL.md` is ClawHub's publishing
bundle format. `SKILL.md` is for local execution. Don't confuse them.

## Environment facts (user's machine, as of session 1)

- Linux user: `ubuntu38`, `HOME=/home/ubuntu38`
- Git version: `2.43.0`, `github.com` reachable
- **OpenClaw default workspace:** `/home/ubuntu38/.openclaw/workspace`
  (intentionally left untouched; not a git repo)
- **Session-1 handoff workspace:**
  `/home/ubuntu38/claude-handoff/unbias38/` (shallow clone of
  `unbias38/unbias38@claude/fix-character-encoding-Rh1TL`)
- **`claude-lobster` is PRIVATE.** OpenClaw will need credentials to
  clone it. **Credential plumbing was NOT solved in session 1** — this
  is an open question. A likely destination clone path is
  `/home/ubuntu38/claude-handoff/claude-lobster/`, but confirm with the
  user before assuming anything.
- **User interface to OpenClaw:** Telegram bot, natural-language
  prompts. Detailed Telegram command syntax is unknown.
- **User is frequently NOT physically at the machine.** Assume remote
  ops only. Be defensive — the user cannot intervene quickly if
  something goes wrong.

## What to do when the user starts a new session

1. Briefly confirm you have read this file ("I've read CLAUDE.md.
   Ready."). Do not summarize it back — the user already knows.
2. Ask what they want to work on.
3. If the user refers to "the handoff doc", "session 1", or anything
   this file does not cover, fetch `HANDOFF.md` at the URL above for
   full history before answering.
4. If the user asks about OpenClaw format details and you are not 100%
   sure from what is in this file, fetch the source docs from
   `openclaw/openclaw` before answering. Do not guess.

## What NOT to do

- Don't create commits or push without the user asking.
- Don't propose auto-polling, webhook, or auto-execution schemes
  unless the user explicitly asks.
- Don't invent OpenClaw format details. Verify.
- Don't try to contact OpenClaw directly. All communication flows
  through the user via Telegram. Write files; do not send signals.
- Don't assume a clone of `claude-lobster` exists on the user's
  machine yet. Until the credential question is answered, OpenClaw
  cannot pull from this repo.
- Don't expand scope beyond what the user asked. Mirror their careful,
  deliberate style.

---

**Last validated pipeline run** (session 1):

- Upstream repo: `unbias38/unbias38`
- Branch: `claude/fix-character-encoding-Rh1TL`
- Smoke test commit: `68d865c`
- Smoke test skill: `skills/hello-claw/SKILL.md`
- Result: PASS (size 373, sha256
  `1b298b6b32a384c9649dad10bb9c2995828d2f20c6673db390e563f6d7c30026`,
  first-line matched verbatim including curly apostrophe)
- Date: 2026-04-15
