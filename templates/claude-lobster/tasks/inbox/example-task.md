# Task: Inventory all markdown files

**Status:** EXAMPLE — do not run in production
**Written by:** Claude session 1 (2026-04-15)
**Expected output file:** `tasks/outbox/inventory-markdown-files.md`

This file is a reference example of the format Claude should use when
writing a task spec for OpenClaw in `tasks/inbox/`. The format is
deliberately defensive — OpenClaw honors STOP rules literally, which
is exactly what we want when the user is remote.

When Claude writes a real task, it should look structurally like this:
HARD RULES at the top, numbered STEPS with explicit STOP conditions,
a clear output file, and a final consolidated report.

---

## Hard rules

- Do NOT modify, create, move, or delete any file except the single
  output file at `tasks/outbox/inventory-markdown-files.md`.
- Do NOT access the network at all.
- Do NOT read any file outside this workspace.
- Do NOT invoke any skill.
- Do NOT require sudo or elevated privileges.
- If any step fails or produces unexpected output, STOP immediately
  and report verbatim what happened. Do not improvise. Do not "fix"
  anything. Do not skip ahead.

## Steps

### STEP 1 — Confirm you are in the correct workspace

- Run: `git -C . remote -v`
- The output MUST contain `unbias38/claude-lobster`. If it does not,
  STOP and report the full output.

### STEP 2 — Confirm the working tree is clean

- Run: `git -C . status --porcelain`
- If the output is non-empty, STOP and paste it verbatim. Do not
  continue — someone else may have work in progress.

### STEP 3 — Fast-forward to the latest remote state

- Run: `git -C . fetch origin`
- Run: `git -C . pull --ff-only`
- If either command fails, STOP and paste the error.

### STEP 4 — List all markdown files

- Run: `find . -name '*.md' -type f -not -path './.git/*'`
- Report the list of paths found.

### STEP 5 — For each markdown file, compute size and line count

For each file found in STEP 4, compute:

- Size in bytes (`wc -c <file>`)
- Line count (`wc -l <file>`)

Collect results into a single in-memory table. Do not write anywhere
yet.

### STEP 6 — Write the result file

Create `tasks/outbox/inventory-markdown-files.md` with this exact
shape (and nothing else):

    # Inventory: markdown files

    **Task:** tasks/inbox/inventory-markdown-files.md
    **Run at:** <UTC timestamp in ISO 8601>
    **Run by:** OpenClaw on <whoami>@<hostname>
    **Status:** OK

    | Path | Bytes | Lines |
    |------|------:|------:|
    | ./CLAUDE.md | 4821 | 142 |
    | ... | ... | ... |

    **Total files:** <N>
    **Total bytes:** <sum>
    **Total lines:** <sum>

    ## Warnings / errors

    None.

If any step above failed, instead write `**Status:** FAILED` and
paste the error output verbatim in the warnings section.

### STEP 7 — Commit the result file

- Run: `git -C . add tasks/outbox/inventory-markdown-files.md`
- Run: `git -C . commit -m "result: inventory-markdown-files"`
- Run: `git -C . push`
- If push fails, STOP and paste the error. Do NOT force-push.

### STEP 8 — Final report

Send the user a single short Telegram message containing:

- The workspace path (`pwd`)
- The commit hash from STEP 7 (`git rev-parse --short HEAD`)
- The totals (files, bytes, lines)
- Any warnings or errors along the way, verbatim

That's it. Do not continue past STEP 8.
