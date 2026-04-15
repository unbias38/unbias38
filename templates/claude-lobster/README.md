# `claude-lobster` starter template

This folder is a starter skeleton for the private repo
**`unbias38/claude-lobster`**, which will host the ongoing Claude ↔
OpenClaw ("龍蝦") handoff workflow for user `@unbias38`.

## Why this lives here (in the public repo)

The Claude session that wrote this template had its GitHub MCP tools
scoped to `unbias38/unbias38` only — it could not write directly into
`unbias38/claude-lobster`. So the template was parked here so that:

1. A **new** Claude Code session, opened against `claude-lobster`, can
   fetch these files via `WebFetch` and recreate them there.
2. The user can also manually copy them via GitHub's web UI on mobile.

## What's inside

```
templates/claude-lobster/
├── README.md                       # this file
├── CLAUDE.md                       # auto-loaded context for new sessions
├── tasks/
│   ├── inbox/
│   │   └── example-task.md         # reference task-spec format
│   └── outbox/
│       └── example-result.md       # reference result-report format
└── skills/
    └── hello-claw/
        └── SKILL.md                # validated smoke-test skill
```

## How to deploy this into `claude-lobster`

### Option 1: via a new Claude Code session (recommended)

Open a new Claude Code session pointed at `unbias38/claude-lobster` and
paste this as your first message:

> Please do the following, in order:
>
> 1. Use `WebFetch` to read
>    `https://raw.githubusercontent.com/unbias38/unbias38/claude/fix-character-encoding-Rh1TL/HANDOFF.md`
>    — that is the full context from our previous session.
> 2. Then fetch each of these files and create them at the equivalent
>    paths in **this** repo (drop the `templates/claude-lobster/`
>    prefix). Do not add or remove anything:
>    - `templates/claude-lobster/CLAUDE.md` → `CLAUDE.md`
>    - `templates/claude-lobster/tasks/inbox/example-task.md` →
>      `tasks/inbox/example-task.md`
>    - `templates/claude-lobster/tasks/outbox/example-result.md` →
>      `tasks/outbox/example-result.md`
>    - `templates/claude-lobster/skills/hello-claw/SKILL.md` →
>      `skills/hello-claw/SKILL.md`
>
>    Raw-URL prefix for all of the above:
>    `https://raw.githubusercontent.com/unbias38/unbias38/claude/fix-character-encoding-Rh1TL/`
>
> 3. Commit the five files in one commit with the message
>    `chore: bootstrap from unbias38/unbias38 template`.
> 4. Show me the diff before pushing. Do NOT push without my OK.

The new Claude will have MCP access to `claude-lobster` and can use
`mcp__github__push_files` or `mcp__github__create_or_update_file` to
create the tree in one go.

### Option 2: by hand via GitHub web UI

If you prefer to do it yourself on mobile:

1. Open each file in this folder on github.com.
2. Click "Raw" to view raw content.
3. In `claude-lobster`, use "Add file → Create new file".
4. Type the target path (e.g. `CLAUDE.md`, then `tasks/inbox/example-task.md`).
5. Paste, commit.

This is tedious but works without any new Claude session.

## Important constraints

- `claude-lobster` is a **private** repo. OpenClaw on the user's machine
  will need credentials (SSH key, personal access token, or `gh` CLI
  login) to clone it. **Credential plumbing was not solved in session 1
  and is an open question for the new session.**
- Once deployed, `CLAUDE.md` in `claude-lobster` will be auto-loaded by
  every new Claude Code session opened against that repo. Do not put
  secrets or task-specific data in it.
