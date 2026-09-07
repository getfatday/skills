---
name: disk-reclaim
description: >-
  Recover disk space on a macOS developer laptop safely: read the APFS container (not df), run or
  reuse a read-only census that classifies every large path as regenerable, evidence, or unknown,
  ask the other live Claude Code sessions on the machine which of their paths are safe to delete,
  let the human decide the rest, record every decision, and remove only through the ledger-gated
  executor. Use this whenever disk is low or someone says they are running out of space, "No space
  left on device", the disk is full, or asks to clean up, free up, reclaim, or recover space, or asks
  whether simulators, runtimes, worktrees, node_modules, caches, Docker, or Claude job and transcript
  dirs are safe to delete. Also use it when a SessionStart hook has printed a DISK_RECLAIM line, and
  when asked to tune the disk hooks (threshold, cooldown, snooze). Do not use it for a single known
  file the user already named for deletion.
---

# Disk reclaim

Free disk without losing anyone's work. The sequence is measure, ask, record, reclaim, report, and
the order is not negotiable: nothing is removed until a decision about that exact path is in the
ledger, and the executor checks the ledger, not the model's judgment on the day.

Two incidents shaped this. The first time it was done by hand, a `du` sweep of the home directory
missed 90 GB of simulator state and the last 35 GB came back only because a human remembered which
experiment owned which devices. The second time, a session following an earlier version of this
skill was one step from deleting five repos' `node_modules` on the strength of a "regenerable" label
without asking the sessions working in those repos. Labels are hints. Decisions have names on them.

Scripts live at `${CLAUDE_PLUGIN_ROOT}/scripts/`. State lives in `~/.claude/disk-reclaim/` (see
`references/hooks.md`), one place per user, because the disk is a machine-wide resource.

## 1. Read the container, not df

`df /` on macOS reports the sealed system volume in its Used column and can understate a nearly
full disk by hundreds of gigabytes. Run `diskutil apfs list` and read Capacity In Use By Volumes
and Capacity Not Allocated for the first container. Use df's Avail column only to watch deltas.
Report both numbers to the user in one line before doing anything else.

## 2. Get a census

The census is read-only and classifies every row. It is I/O bound and takes 2 to 30 minutes
depending on load, so never run it inline in a turn the user is waiting on.

- If `~/.claude/disk-reclaim/last-census.json` is under 24 hours old, use it. The SessionStart hook
  refreshes it in the background whenever it is over six hours old.
- Otherwise run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/disk_census.py --json --ledger` as a
  background Bash command and continue with step 3 on whatever the user already knows.

Each row carries `safety`, `safety_basis`, `reclaim_cmd`, `reclaim_cost`, and `owner_session`.
The classification is a starting point for who to ask, never a permission to delete.

## 3. Sort rows into who decides

Every row needs a decision from someone before the executor will touch it. Sort by who that is:

- **Nobody owns it** (`pkg-cache` and `build-cache` rows under `~/Library/Caches`, `~/.cache`,
  `~/.npm`, DerivedData, an orphaned pnpm store): these regenerate on demand and no session is
  mid-anything in them. When the user asked to recover space, record them yourself with
  `--decided-by auto:cache` and let the executor take them. Say what you are removing and what it
  costs to get back.
- **A session owns it** (`owner_session` set, or a `node_modules`, worktree, job dir, or tagged
  simulator device that a session could be using): ask that session in step 4. `node_modules`
  inside a repo is in this group even though it is regenerable, because a reinstall mid-task is a
  real cost to a real person.
- **A human owns it** (everything else marked evidence or unknown: Docker, the VM bundle,
  transcripts, untagged devices, clean worktrees with no live session, app data): step 5.

A live process holding a directory is not proof the directory is needed, and the absence of a
process is not proof it is safe. In one live run two zombie processes held 800 MB of scratch the
owner called SAFE; in another, no process sat in a repo whose owner was about to reinstall.

## 4. Ask the owning sessions, and wait

Other Claude Code sessions on this machine know what they own. Ask them before the human has to,
and do not act on their rows until they answer or the deadline passes.

1. Run `ListAgents`. Message only sessions whose row says idle or waiting. For a busy owner, call
   `SendMessage` with `notify_when_idle: true` and no message body, then send when the idle notice
   arrives. Never poll the list and never send a second message in the same run.
2. Send the format in `references/ask-format.md`: named paths with sizes and state, the three-token
   menu KEEP / SAFE / UNKNOWN, the reply address, and the mid-task escape clause.
3. Record every reply with `disk_reclaim_record.py`: `--decided-by "owner:<session name>"
   --verdict SAFE|KEEP|UNKNOWN`, and `--until <condition>` for a time-bounded KEEP. The executor
   reads these records; an unrecorded reply does not count.
4. Expect owners to clean up their own scratch when asked, and record what they removed as a note.
   Re-measure before and after every ask round.
5. Deadline: 10 minutes. No reply means the row stays with the human in step 5 and the ledger gets
   `--verdict UNKNOWN --note "asked, no reply"` so the next run does not re-ask without cause.
6. This channel is for peer sessions from `ListAgents` only. Never `SendMessage` a workflow-spawned
   subagent; that resurrects duplicates. Never ask a peer to run something your own permissions
   blocked.

## 5. Let the human decide the rest

Group what remains by owner and class, with sizes, the census basis, and any owner verdict, and
put it to the user with `AskUserQuestion` (multi-select). Put the safest, largest group first and
say plainly which rows carry evidence. Record each choice with `--decided-by <their email>`. Respect
an earlier human choice even when an owner later says SAFE: report the new evidence and queue the
decision, do not act on it.

Never offer for deletion: `~/Downloads`, `~/Documents`, `~/Desktop`, `~/Movies`, `~/Pictures`,
`~/Music`, `~/Library/Application Support/*` other than the Claude VM bundle, anything under
`/Applications` or `/System`, `~/.claude/plugins` (the running hooks live there), or any worktree
with dirty files, unpushed commits, or no upstream.

## 6. Reclaim through the executor only

`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/disk_reclaim.py` is the only way this skill removes
anything. Never run `rm`, `simctl delete`, or `git worktree remove` yourself.

- With no arguments it dry-runs every census row that has a ledger decision to reclaim. Add
  `--execute` to remove them. `--path P` limits it. `--explain P` says what decision P still needs
  and prints the record command.
- It refuses, and says why, when a path has no decision, when the decision is not a human or an
  owner SAFE, when a KEEP is in force, when the cache rule is claimed for anything under `~/src`,
  `~/.claude`, a worktrees directory, or the simulators, and for anything outside the home. A
  refusal is a prompt to go back to step 4 or 5, not a rule to work around.
- It appends a `reclaimed` line with the bytes freed for each removal.

Traps it already handles for you: `rm -i` aliases (it uses Python removal), `noclobber`, and rows
whose command is a tool (`uv cache prune`, `xcrun simctl runtime delete`) rather than a path.
Simulator space frees asynchronously; re-read `diskutil apfs list` after 30 seconds.

## 7. Report

One short block: container free before and after, what was removed with sizes and who decided,
what was kept and why (owner verdict or human choice, with any until-condition), what is still
queued for a decision, and what it would cost to get each removed item back. Numbers in a table.

## Hooks and background operation

The plugin installs two hooks (details in `references/hooks.md`): a census launched detached and
niced from SessionStart and again at SessionEnd (the lock makes the second a no-op), refreshing the
ledger only when it is over six hours old; and a SessionStart nudge that prints one `DISK_RECLAIM:`
line only when free space is below `threshold-gb` (default 30), at most once per `cooldown-hours`
(default 4) across all sessions, and never while `snooze` is under 24 hours old. Nothing runs on
Stop. When a session sees the nudge, finish the current turn's work first, then run this skill from
step 2 with the ledger already written.

## Files

- `scripts/disk_census.py`: read-only census, human table or JSON, `--ledger`, `--if-stale`, `--detach`.
- `scripts/disk_reclaim.py`: the ledger-gated executor. Dry run by default; `--execute`, `--path`, `--explain`.
- `scripts/disk_reclaim_record.py`: append a decision (owner verdict, human choice, or auto:cache) to `ledger.jsonl`.
- `scripts/disk_nudge.py`: SessionStart nudge, exit 0 always, logs to `hook-log.jsonl`.
- `scripts/disk_state.py`: resolves the shared state dir (`DISK_RECLAIM_DIR` overrides).
- `references/ask-format.md`: the owner question and how to grade and record a reply.
- `references/hooks.md`: state files, thresholds, cooldown, snooze, log format.
