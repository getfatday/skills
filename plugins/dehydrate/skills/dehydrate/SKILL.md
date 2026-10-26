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

`~/.claude/dehydrated/config.json` overrides defaults: `days`, `roots` (default `["~/src"]`),
`exclude_globs`, the caps (`untracked_cap_mb`, `ignored_cap_mb`, `orphan_cap_mb`), `disk_floor_gb`,
`nudge_cooldown_hours`, and `auto_apply`. The plugin's SessionStart hook prints one DEHYDRATE line
at most once a day when the cached plan has work, and refreshes that cache in the background.
With `"auto_apply": true` the background refresh also applies, which makes cleanup fully
passive. It is off by default, and you turn it on only when the user asks for that.

See `references/storage.md` for the manifest fields and archive layout.
