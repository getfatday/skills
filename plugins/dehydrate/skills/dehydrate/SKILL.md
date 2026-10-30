---
name: dehydrate
description: >-
  Close out stale Claude Code sessions and git worktrees without losing anything: snapshot each
  idle worktree (uncommitted, staged, untracked and gitignored-but-real files, plus unpushed
  commits) into a ref and a git bundle, archive its session transcripts and job dirs, write a
  user-level manifest with a short description of what each session was about, then remove the
  worktree and close the session so only the last week's work stays open. Use this whenever the
  user says sessions or worktrees are piling up, they lost track of open sessions, the agent list
  is cluttered, disk is filling up with worktrees, they want to "dehydrate", close out, archive,
  park or clean up old sessions or worktrees, or a SessionStart hook printed a DEHYDRATE line.
  Also use it to preview what would be closed ("what's stale?") and to change the idle window
  ("close everything older than 3 days"). The matched rehydrate skill brings any of it back.
---

# Dehydrate

Dehydrating a worktree is a stash that survives deletion: everything in it becomes one commit at
`refs/dehydrated/<id>` (parents = the branch tip and the staged index, like `git stash`, so no
branch moves and nothing lands on main), copied into a git bundle under
`~/.claude/dehydrated/archive/<id>/`, alongside a raw tarball of every changed file (exact bytes,
modes and symlinks), a tarball of gitignored files that are not tool output, and gzipped copies of
the session transcripts. The manifest record is written before anything is removed. Only
after the bundle verifies and a second capture of the tree matches the first does the worktree
get removed. The session is then closed with Claude Code's own `claude stop` / `claude rm`.
Transcripts are kept by `claude rm` but swept by `cleanupPeriodDays` (30 days by default), which
is why the archive keeps its own copy: rehydrate works months later.

The script decides; you report. Every choice (stale or not, held or not) is a fixed rule in
`dehydrate.py`, so the same machine state gives the same plan. Do not re-decide items by reading
files yourself. If the plan looks wrong, change the inputs (`--days`, `--only`, config) and
re-plan.

`D` = `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dehydrate.py`. Every subcommand has `--help`.

## Steps

1. **Plan (read-only, about 10 seconds).** Run `D plan`. Add `--days N` when the user names a
   window ("older than 3 days" means `--days 3`; the default is 7). Add `--only <name>` to
   dehydrate one specific worktree or session, and `--mains` when the user also wants
   uncommitted work in main checkouts captured (slower: it runs `git status` on every repo).
   The plan prints totals, then each worktree it will dehydrate, hold or prune, leftover dirs,
   and the sessions it will close.

2. **Show the user the plan in a few lines**: how many sessions close, how many worktrees go,
   about how much disk comes back, and every `hold` with its reason, because holds are the
   things a human may want to deal with by hand (locked, a live process inside, a nested clone,
   a dirty submodule, over a size cap). Excluded trees (another system's, like Hermes kanban
   workspaces) are counted, never touched.

3. **Apply.** If the user asked to dehydrate or clean up (not just "what's stale?"), run
   `D apply --yes` with the same flags. Apply is the user's request carried out, and every step
   it takes is reversible through rehydrate, so a second confirmation is not needed. If they
   only asked what is stale, stop after step 2 and offer to apply.
   Run it as one plain Bash call. If the permission layer or the auto-mode classifier blocks it,
   report the exact command for the user to run; do not try another route to the same effect.

4. **Report** from the apply output (it is also saved to `~/.claude/dehydrated/last-apply.json`):
   free disk before and after, what was dehydrated and closed, and anything "not done" with its
   reason. Exit code 1 means some items were not done (each is listed with why; nothing about
   them was removed). Exit code 3 means apply paused at the disk floor (default 2 GB free): say so, and
   start a monitor that re-runs apply once free space clears the floor with headroom.
   Point the user at `~/.claude/dehydrated/index.md` (the table of everything ever dehydrated)
   and tell them `/rehydrate <words>` brings any item back.

## Disk pressure

When the user needs space now ("free 20 GB", "the disk is full, clear old worktrees"), or the
disk-reclaim plugin delegates to this skill, use `D plan --pressure --target-gb N` and then
`D apply --yes --pressure --target-gb N`. Pressure mode ignores `--days` for worktrees (a
worktree touched an hour ago is a candidate), orders candidates least recently active first and
then largest, and dehydrates one at a time, stopping as soon as free disk reaches N. Every hold
below still applies, and so does every keep that is not about age: this session's cwd, a live
process inside, a working/busy or interactive session bound to it. A session that has been
`done` or `blocked` for more than 24 h no longer protects its worktree; it is archived and closed
with it. Pressure mode closes no other session and leaves leftover dirs and main checkouts alone.
The apply JSON carries `pressure: {target_gb, reached, free_checked_gb}`. Reaching the target and
running out of candidates (`reached: false`) are both exit 0 (1 if an item was not done); neither is
a pause. Pressure mode has no fixed floor (that floor stopped every item exactly when disk was lowest):
each worktree goes only when the free space read for it covers its capture estimate (changed and
untracked bytes for the raw tarball, gitignored-real bytes, and a bundle bound of unpushed commits'
objects plus those changed bytes) plus 200 MB, because the archives are written to the same disk. An
item that does not fit pauses the run (exit 3, the reason says how much it needs). Normal apply keeps
the fixed `disk_floor_gb` (default 2 GB). `--only` is refused with `--pressure`.

When `claude agents --json --all` does not answer (300 s, tried twice), plan and apply do not crash:
no session closes and every worktree bound to a session or inside a job dir is held with reason
"agents list unavailable"; the plan JSON carries `agents_unavailable`.

Sparse-checkout worktrees are captured with their skip-worktree files intact (`git add -A --sparse`
on a copy of the real index, git 2.34+), the sparse config is recorded as `worktree.sparse`, and
rehydrate checks the tree out with the same cone or patterns.
"Least recently active" is the newest of the worktree's dir, HEAD and reflog mtimes, its changed
files' mtimes, and its bound sessions' activity; a session's "more than 24 h" is measured the same
way (transcript, job state and timeline mtimes), not from when it started. Report how far it got
and what is still held.

## Automatic dehydrate on close

With `auto_on_close` (on by default) a session whose work is merged is dehydrated without anyone
running `/dehydrate`, so it lands in the manifest and the rehydrate picker.

- **When.** Every SessionStart runs the detached, niced refresh, which first sweeps
  `claude agents` (at most once per `auto_sweep_minutes`, default 10). A background session that
  ended `done` or `failed` at least `auto_grace_minutes` ago (default 10) is a candidate. A
  `claude stop` from the agents list is caught by the next sweep. The mod also kicks
  `D auto --session <id>` when a session ends (`/exit`, a signal, logout, a closed terminal),
  which waits for the process to exit and needs no grace period. A kick that meets another run
  (it waits up to 2 minutes for the lock) is queued in `auto-pending/` and logged `deferred`; the
  next run, or the next SessionStart sweep, takes it.
- **"Has merges on it"**, judged on commits only. The session's cwd is a linked worktree on a
  named branch that is not the remote default branch. After a fetch of the default branch, the
  branch is contained in it and still holds commits of its own (a branch whose own commit was
  reset away does not count), or merging it changes nothing and the files it changes are already
  there (a squash or rebase merge; a commit plus its revert, or an extra empty commit, is not
  proof), or `gh pr list -R <origin>` shows a PR from it merged into the default branch at exactly
  its HEAD. Any error or timeout means not merged. Uncommitted and untracked files are allowed because
  the snapshot keeps them (`auto_require_clean: true` refuses them).
- **Never.** Unmerged work, a live session (a pid, or state working or blocked), an interactive
  session open in the worktree, this session, a main checkout or the default branch, a worktree
  shared with a session that is not itself ready, anything a plan hold covers (locked, excluded,
  conflicts, submodules, nested repos, caps), free disk under the floor, and a session already
  dehydrated. A session with no worktree is never auto-dehydrated. A session brought back with
  rehydrate is left alone until it runs and ends again (its transcript or job state newer than the
  rehydration), so restoring a merged worktree to look at it does not lose it at the next sweep.
- **Audit.** Every decision is a line in `~/.claude/dehydrated/auto.log` (session, name,
  `dehydrated` or `refused`, reason). Read it to answer "why wasn't X dehydrated". Records it
  wrote carry an `auto` block. `D auto --dry-run` prints what a sweep would do and changes
  nothing. `D auto --status` says whether auto is on, the last sweep and the last decision.
- **Off switch**: `D config set auto_on_close false` (writes `$DEHYDRATE_HOME/config.json` or
  `~/.claude/dehydrated/config.json`, keeps other keys, checks the type). A value of the wrong type
  (`"false"` in quotes) is a config error, which turns auto off, and `auto --dry-run`, `auto
  --status`, `D config` and the nudge say so, as they do for a key this version does not know.
  The first SessionStart nudge after the upgrade says once that auto is on and how to turn it off.

## What the rules protect

- **Active means kept**: a session or worktree touched in the last `--days` days, a session in
  state working/busy, interactive sessions, and this session and its cwd. A session that has sat
  blocked on a question for longer than the window is closed like any other idle one. Its
  conversation is archived and resumes where it stopped, so mention those by name in the report.
- **Held, never removed**: locked worktrees, worktrees with a live process cwd inside, a worktree
  with another registered worktree inside it, a merge/rebase/cherry-pick in progress or index
  conflicts, a branch with no commits yet, nested git repos (also under gitignored and tool-output
  paths), submodule checkouts, dirty submodules, untracked files over 100 MB (or 500 MB total), gitignored
  files to archive over 300 MB. A held worktree's stale session still closes, since the
  conversation survives.
- **Job dirs belong to their session**: a worktree under `~/.claude/jobs/<id>/` (real paths) is held
  while session `<id>` is listed in `claude agents --json --all` and has not been done, stopped or
  failed for at least `auto_grace_minutes`, or its process still runs; the reason names the session
  ("inside the job dir of working session 8e6abbd6 ..."). An unreadable agents list holds them all.
  Under `--pressure` a worktree whose files or HEAD reflog changed in the last 2 hours is held too.
- **Re-checked right before acting**: apply reads `config.json` again and rebuilds each item's
  holds just before its capture and again just before its removal, so an exclusion or a lock added
  while a run is going stops the items it matches (reported as skipped, exit 0). An item captured
  but then held keeps its snapshot and a `left-in-place` manifest event; its tree stays.
- **Git's own `initializing` lock** (left by a killed `git worktree add`) is held and reported as an
  interrupted checkout with the `git worktree unlock <path>` that clears it, unless a git process is
  still writing that path.
- **Archived, not judged**: every gitignored file is archived except pure tool output
  (node_modules, .venv, __pycache__, DerivedData, Pods and similar). Ambiguous names like
  `build/`, `dist/` or `*.log` are archived, since a human may have put real files there.
- **Excluded**: `*/.worktrees/t_*` and `~/.hermes/*` by default (Hermes owns those). The same
  `exclude_globs` also keep `--mains` out of matching main checkouts.
- **Main checkouts** are never reset, committed to or removed. `--mains` only captures their dirt.
- **Nothing is pushed.** Snapshots are local refs plus bundles. Branches are kept.
- **`claude rm` refusals are respected.** A session that `claude rm` refuses stays open and is
  reported. Never pass `--discard-unpushed` or `--force-remove-worktree`.

## Tuning

`~/.claude/dehydrated/config.json` (or `$DEHYDRATE_HOME/config.json`) overrides defaults. Change
it with `D config set <key> <value>` (JSON values, type-checked; `D config` lists every key with
its value): `days`, `roots` (default `["~/src"]`),
`exclude_globs`, the caps (`untracked_cap_mb`, `ignored_cap_mb`, `orphan_cap_mb`), `disk_floor_gb`,
`nudge_cooldown_hours`, `auto_apply`, and the auto-on-close keys: `auto_on_close` (default
true), `auto_grace_minutes` (10), `auto_sweep_minutes` (10), `auto_use_gh` (true, false keeps
the merge check to git), `auto_fetch_timeout_s` (30) and `auto_require_clean` (false). The
plugin's SessionStart hook prints one DEHYDRATE line at most once a day when the cached plan has
work, and refreshes that cache in the background. With `"auto_apply": true` the background
refresh also applies the whole idle plan, which makes cleanup fully passive. `auto_apply` is a
separate switch from `auto_on_close`. It stays off by default, and you turn it on only when the
user asks for that.

See `references/storage.md` for the manifest fields and archive layout.
