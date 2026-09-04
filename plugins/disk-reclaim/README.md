# disk-reclaim

Recover disk space on a macOS developer laptop without losing anyone's work.

The disk on a machine that runs Xcode simulators, node and pnpm, Docker, many git worktrees, and
several Claude Code sessions at once fills up in ways `du ~` does not show. This plugin gives Claude
a fixed sequence: **measure** (read the APFS container, not `df`; census every known waste class,
read-only), **ask** (the other live sessions on the machine, in a fixed KEEP / SAFE / UNKNOWN
format), **decide** (the human, for anything that is evidence or unknown), **reclaim** (the row's
own command), **record** (a ledger that survives sessions).

## Install

```
/plugin marketplace add getfatday/skills
/plugin install disk-reclaim@getfatday-skills
```

Two hooks come with it, both exit 0 on every path:

- **SessionStart nudge**: one `DISK_RECLAIM:` line when free space is below `threshold-gb`
  (default 30), at most once per `cooldown-hours` (default 4) across all sessions, never while
  `snooze` is fresh. About 0.2 s.
- **Detached census**: started detached and niced from SessionStart and again at SessionEnd (the lock makes the second a no-op), refreshes `~/.claude/disk-reclaim/last-census.json` when it is
  over six hours old. Never delays a session; the first session after six hours pays nothing, the census runs behind it.

Nothing runs on Stop.

## Use

Say "we're running out of disk" or "is it safe to delete the simulators" and the skill triggers.
Or run the census by hand:

```
python3 ~/.claude/plugins/cache/getfatday-skills/disk-reclaim/*/scripts/disk_census.py
```

State and tuning files live in `~/.claude/disk-reclaim/`; see
`skills/disk-reclaim/references/hooks.md`.

## What it will not do

Delete anything classified as evidence or unknown on its own. Offer your Downloads, Documents,
app data, applications, or any worktree with unpushed work. Run the census inline in a turn you
are waiting on. Message a busy session, or message any session twice.

## Requirements

macOS, Python 3, Xcode command line tools for the simulator rows. Everything else degrades to
"not measured" rather than failing.
