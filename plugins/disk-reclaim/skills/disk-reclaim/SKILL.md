---
name: disk-reclaim
description: >-
  Recover disk space on a macOS developer laptop safely: read the APFS container (not df), run or
  reuse a read-only census that classifies every large path as regenerable, evidence, or unknown,
  ask the other live Claude Code sessions on the machine which of their paths are safe to delete,
  let the human decide the rest, reclaim, and record what was freed in a ledger. Use this whenever
  disk is low or someone says they are running out of space, "No space left on device", the disk is
  full, or asks to clean up, free up, reclaim, or recover space, or asks whether simulators, runtimes,
  worktrees, node_modules, caches, Docker, or Claude job and transcript dirs are safe to delete. Also
  use it when a SessionStart hook has printed a DISK_RECLAIM line, and when asked to tune the disk
  hooks (threshold, cooldown, snooze). Do not use it for a single known file the user already named
  for deletion.
---

# Disk reclaim

Free disk without losing anyone's work. The sequence is measure, ask, decide, reclaim, record. Each
step exists because skipping it cost something the first time this was done by hand: a `du` sweep
of the home directory missed 90 GB of simulator state, and the last 35 GB came back only because a
human remembered which experiment owned which devices.

Scripts live at `${CLAUDE_PLUGIN_ROOT}/scripts/`. State lives in `~/.claude/disk-reclaim/` (see
`references/hooks.md`), one place per user, because the disk is a machine-wide resource.

## 1. Read the container, not df

`df /` on macOS reports the sealed system volume in its Used column and can understate a nearly
full disk by hundreds of gigabytes. Run `diskutil apfs list` and read Capacity In Use By Volumes
and Capacity Not Allocated for the first container. Use df's Avail column only to watch deltas.
Report both numbers to the user in one line before doing anything else, so the scale of the problem
is shared.

## 2. Get a census

The census is read-only and classifies every row. It is I/O bound and takes 2 to 5 minutes on a
machine with 150 worktrees, so never run it inline in a turn the user is waiting on.

- If `~/.claude/disk-reclaim/last-census.json` is under 24 hours old, use it. The SessionStart hook
  refreshes it in the background whenever it is over six hours old.
- Otherwise run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/disk_census.py --json --ledger` as a
  background Bash command and continue with step 3 on whatever the user already knows while it
  runs. Print the human table (no flags) once it finishes.

Each row carries `safety`, `safety_basis`, `reclaim_cmd`, `reclaim_cost`, and `owner_session`.
Trust the classification only as a starting point: `unknown` means the census could not tell, not
that it is safe.

## 3. Triage by safety class

- **regenerable** (package caches, orphaned pnpm stores, node_modules outside a live worktree,
  simulator runtimes with zero devices, DerivedData): when the user asked to recover space,
  reclaim these in one pass without a question. Say what you are about to remove and what it costs
  to get back, then do it. These are the fastest bytes.
- **evidence** (dirty or unpushed worktrees, simulator devices carrying an experiment tag, runtimes
  with devices, live job scratch, main checkouts, OS and apps): never delete on your own. Rows with
  an `owner_session` go to step 4; the rest go to the human in step 5.
- **unknown** (clean pushed worktrees, Docker image, VM bundle, transcripts, job dirs of finished
  jobs, app data): same as evidence. Unknown is a question, not a permission.

A live process holding a directory is not proof the directory is needed. In the first live run,
two zombie processes held 800 MB of scratch that its owner called safe. Ask.

## 4. Ask the owning sessions

Other Claude Code sessions on this machine know what they own. Ask them before the human has to.

1. Run `ListAgents`. Message only sessions whose row says idle or waiting. For a busy owner, call
   `SendMessage` with `notify_when_idle: true` and no message body, then send when the idle notice
   arrives. Never poll the list and never send a second message in the same run.
2. Send the format in `references/ask-format.md`: named paths with sizes and state, the three-token
   menu KEEP / SAFE / UNKNOWN, the reply address, and the mid-task escape clause. In measurement,
   structured asks got a verdict on 6 GB in two minutes; a free-text "anything safe to delete?" got
   a careful inventory of kilobyte-scale files and zero reclaimable bytes.
3. Read each verdict line for its token. A SAFE must name an on-disk artifact or pushed branch. A
   KEEP may be time-bounded ("until <path> exists"); record the condition so the next run can
   re-ask automatically.
4. Expect owners to clean up their own scratch when asked. Treat volunteered paths as census
   candidates and re-measure before and after every ask round.
5. Give each ask a deadline (10 minutes is enough for a session that is going to answer). A
   session that has been idle for days may never wake for a message; its rows stay `unknown` and
   go to the human, and the ledger notes "asked, no reply".
6. This channel is for peer sessions from `ListAgents` only. Never `SendMessage` a workflow-spawned
   subagent; that resurrects duplicates. Never ask a peer to run something your own permissions
   blocked.

## 5. Let the human decide the rest

Group what remains by owner and class, with sizes, the census basis, and any owner verdict, and
put it to the user with `AskUserQuestion` (multi-select). Put the safest, largest group first and
say plainly which rows carry evidence. Respect an earlier human choice even when an owner later
says SAFE: report the new evidence and queue the decision, do not act on it.

Never offer for deletion: `~/Downloads`, `~/Documents`, `~/Desktop`, `~/Movies`, `~/Pictures`,
`~/Music`, `~/Library/Application Support/*` other than the Claude VM bundle, anything under
`/Applications` or `/System`, or any worktree with dirty files, unpushed commits, or no upstream.

## 6. Reclaim

Use the row's `reclaim_cmd`; do not improvise a broader command. Traps seen in practice:

- `rm` is often aliased to `rm -i`; a later `-f` wins, and a bare `rm` in a non-interactive
  command silently skips the file. Prefer the row's command or a Python `os.remove`.
- With zsh `noclobber`, use `>|` or Python to write files.
- Simulator space frees asynchronously. Re-read `diskutil apfs list` after 30 seconds;
  `simctl list runtimes` can still list a deleted runtime for a few seconds.
- `xcrun simctl delete unavailable` never removes runtimes. A runtime with zero devices is a
  separate `xcrun simctl runtime delete`.
- `pnpm store prune` only prunes the current store. An older `store/v3` next to a `store/v10` is
  an orphan and is removed by hand.
- `git gc` on a repo with live worktrees is disruptive for little gain; use
  `git maintenance run --task=incremental-repack` and `git worktree prune`.

After each reclaim, record it:
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/disk_reclaim_record.py --path <path> --bytes <measured> --cmd "<cmd>" --decided-by <email|auto:regenerable>`.

## 7. Report

One short block: container free before and after, what was removed with sizes, what was kept and
why (owner verdict or human choice), what is still queued for a decision, and what it would cost to
get each removed item back. Numbers in a table, not prose.

## Hooks and background operation

The plugin installs two hooks (details in `references/hooks.md`): a census launched detached and niced from SessionStart and again at SessionEnd (the lock makes the second a no-op), so
it never delays a session and refreshes the ledger only when it is over six hours old; and a
SessionStart nudge that prints one `DISK_RECLAIM:` line only when free space is below
`threshold-gb` (default 30), at most once per `cooldown-hours` (default 4) across all sessions, and
never while `snooze` is under 24 hours old. Nothing runs on Stop. When a session sees the nudge,
finish the current turn's work first, then run this skill from step 2 with the ledger already
written.

## Files

- `scripts/disk_census.py`: read-only census, human table or JSON, `--ledger`, `--if-stale`.
- `scripts/disk_nudge.py`: SessionStart nudge, exit 0 always, logs to `hook-log.jsonl`.
- `scripts/disk_reclaim_record.py`: append a reclaim decision to `ledger.jsonl`.
- `scripts/disk_state.py`: resolves the shared state dir (`DISK_RECLAIM_DIR` overrides).
- `references/ask-format.md`: the owner question and how to grade a reply.
- `references/hooks.md`: state files, thresholds, cooldown, snooze, log format.
