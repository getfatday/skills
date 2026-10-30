# disk-reclaim

Recover disk space on a macOS developer laptop without losing anyone's work.

Nothing is deleted on a label. Every removal goes through `scripts/disk_reclaim.py`, which refuses any
path that has no recorded decision in `~/.claude/disk-reclaim/ledger.jsonl`: an owner session's SAFE, a
human's choice, `auto:cache` for ownerless caches, or `auto:<class>` for the few Claude waste classes
below, and only after that class's live checks pass again at the moment of acting. `node_modules`,
worktrees, simulators, and whole job dirs always need an owner or a human, however regenerable they look.

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
  Afterwards (and even when the census was fresh) it starts the automatic pass if free space is under `target-gb`.

Nothing runs on Stop.

## Automatic reclaim (on by default)

When the detached census sees container free space under `target-gb` (default 15), it runs
`disk_reclaim.py --auto --execute` on its own: one lock, niced, never inside a session's turn. It works
in a fixed order until free space reaches `target-gb + headroom-gb` (default 5) and then stops:

1. `hook-spool-rotation`: append-only spool files over 1 GB (default list:
   `~/.claude/observatory/spool.jsonl`) are renamed and gzipped in place, with a line in
   `README-rotation.txt` next to them. Nothing is deleted.
2. `claude-cli-versions`: old Claude Code builds in `~/.local/share/claude/versions/` that are not
   the target of `~/.local/bin/claude`, not newer than it, and not used by any running process.
3. `claude-job-scratch`: `~/.claude/jobs/<id>/tmp` (largest first) of sessions that are not
   working or busy, with nothing modified in 24 hours and nothing open. Only `tmp/` goes.
4. `stale-worktrees`: delegated to the dehydrate plugin (0.2.1 or later), `apply --pressure`,
   which snapshots each worktree before removing it and keeps every one of its holds (live
   sessions' job dirs, trees touched in the last 2 hours, exclusions re-read before each removal).
   The dry run names the worktrees dehydrate's pressure plan would take; the ledger outcome lists
   the ones it removed under `targets`.

It never touches the Claude desktop VM bundle (`claude-desktop-vm`, report-only) or anything else.
Every action is a ledger decision `auto:<class>` plus its outcome, and a line in `free-log.jsonl`;
the next session's SessionStart prints one `DISK_RECLAIM_AUTO:` line saying what it did.
Turn it off with `echo false > ~/.claude/disk-reclaim/auto`.

## Unattended

`scripts/orchestrate.sh` is one locked, capped, transcript-less firing that asks live owners, records
the dead, gates everything in dry run, and writes `~/.claude/disk-reclaim/decision-card.md`. It
deletes nothing. Every ask and reply lands in `asks.jsonl`; `scripts/disk_asks.py status` shows them.

## Use

Say "we're running out of disk" or "is it safe to delete the simulators" and the skill triggers.
Or run the census by hand:

```
python3 ~/.claude/plugins/cache/getfatday-skills/disk-reclaim/*/scripts/disk_census.py
```

State and tuning files live in `~/.claude/disk-reclaim/`; see
`skills/disk-reclaim/references/hooks.md`.

## What it will not do

Delete anything without a ledger decision for that exact path. Delete anything classified as evidence or
unknown on its own; automatic mode acts only on the four classes above, re-checking each right before it acts. Offer your Downloads, Documents,
app data, applications, or any worktree with unpushed work. Run the census inline in a turn you
are waiting on. Message a busy session, or message any session twice.

## Requirements

macOS, Python 3, Xcode command line tools for the simulator rows. Everything else degrades to
"not measured" rather than failing.
