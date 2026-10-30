---
name: rehydrate
description: >-
  Bring back a session or worktree that the dehydrate skill archived: find it in the user-level
  manifest by words from what it was about, its branch, path or session id, recreate the worktree
  on its branch with every uncommitted, untracked and gitignored file exactly as it was, restore
  the session transcript if Claude Code already swept it, and resume the conversation. Use this
  whenever the user wants an old or closed session back, asks "what was that session about the
  X thing", wants to find or reopen a dehydrated or archived worktree, lost work after a cleanup,
  or says rehydrate, restore, revive, reopen or resume something that was closed out. Also use it
  to list or search what has been dehydrated.
---

# Rehydrate

The inverse of dehydrate. Everything it needs is in `~/.claude/dehydrated/`: `manifest.jsonl`
(one record per dehydrated item, append-only), `index.md` (a readable table), and
`archive/<id>/` (snapshot bundle, gitignored-files tarball, gzipped transcripts, job dir).

`D` = `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dehydrate.py`.

**The picker.** On a terminal or the desktop app, a bare `/rehydrate` never reaches this skill.
The plugin's mod opens a picker pane instead: every dehydrated session and worktree under the
name `claude agents` showed for it and its short id, grouped Today, This week, This month and
Older, filtered as the user types (name, first prompt, description, branch, repo, ids). A
worktree dehydrated with its session is one row, the session's. Enter rehydrates the row and
relaunches its session in the background; a row tagged `restored` is already back, so Enter only
launches it. The pane searches the 500 newest rows; words reach everything. This skill runs when the user
gives words (`/rehydrate auth flow`), on mobile, when the mod is not loaded, or when the user
asks in plain words. Then follow the steps below.

## Steps

1. **Find it.** `D list <words>` searches ids, descriptions, session names and titles, first
   prompts, branches, paths and session ids (all words must match, case-insensitive). With no
   words it lists the most recent 50, each with its sessions as `name (short id)`.
   `--kind worktree|session|orphan|main-snapshot` narrows it.
   Show the user the candidates with their dates and one-line descriptions. If several match,
   let them pick (AskUserQuestion with the top few) rather than guessing. `D show <id>` prints
   one full record. `D list --picker [words]` prints what the picker shows, one row per session
   with its agents name, short id, age group and whether a copy is already running (`running`),
   for scripted use.

2. **Rehydrate.** `D rehydrate <id>`. The key can also be a session id (or its first 8
   characters), a background session id, the exact `claude agents` name, a branch or the original
   path, as long as it matches one record (a session record wins over its own worktree record).
   Running it again on an item that is still restored at its path changes nothing and says
   `already restored at <path>, nothing changed` (edits made since are kept); with `--launch` it
   then only launches.
   - A worktree comes back at its original path on its original branch, exactly as it was:
     staged changes staged, unstaged changes unstaged, untracked files untracked, deletions
     re-applied, file bytes and modes as captured (CRLF, 0600, symlinks), and the archived
     gitignored files restored. Pure tool output (node_modules, .venv, __pycache__ and the like)
     was never archived, so rebuild it the usual way.
     If the branch moved since, or is checked out elsewhere, it comes back on a new branch
     `<branch>-rehydrated-<date>` at the snapshot's parent, and the output says so. If the local
     ref is gone (gc, another machine), the bundle is fetched from the archive.
   - If the original path is taken, pass `--path <dir>`.
   - A session record restores its linked worktree first (when one was dehydrated with it),
     then its transcript. `--session-only` skips the worktree.
   - A main-snapshot is never restored over the checkout. It needs `--path <dir>` and lands as a
     separate worktree there.
   - If an archive file is missing or fails its checksum, rehydrate stops before changing
     anything and says which file. Report that; do not work around it. A transcript copy that
     fails its checksum is the exception: the worktree still comes back, that session is not
     restored or launched, and a note says so.

3. **Resume.** The output prints one `cd <dir> && claude --resume <session-id>` per session.
   Give the user those commands. If they want it running now, use `--launch` (on the first run or
   a rerun) to start each as a background session (`claude --bg --resume <id> -n <name>`).
   `--launch` checks `claude agents` first. A session that is still listed under its own id or
   a copy an earlier `--launch` started (in any state: `still open in claude agents as <id>`, attach
   it or `claude rm` it first), or a live session (a pid, or working or blocked) with the same name
   in the same directory, is not started again (`already running as <id>`). When `claude agents`
   cannot be read it launches nothing and prints the command instead, so a duplicate copy is never
   started. A launch that exits 0 without printing the copy's id is recorded as unconfirmed, and
   for 10 minutes another `--launch` of that session is refused (check `claude agents` first).
   Every session not launched has a reason in the output (`notes`, and `launched[].note` with
   `skipped: true` in `--json`), including `no transcript archived; resume will fail`. A launched copy
   keeps the session's name in `claude agents` but gets a new short id, which the output prints
   and the manifest records (the original short id does not come back). `claude attach <id>`
   opens it.

4. **Verify and report.** Check that the printed path exists and `git -C <path> status` shows the
   expected changes. Report the path, the branch, any notes (renamed branch, restored ignored
   files), and the resume commands. A `WARNING:` note (restored files or tree differ from what was
   captured) means something did not round-trip, so show `git status` and say so plainly.

Rehydrating never deletes the archive. The same item can be rehydrated again later (after the
worktree is removed again), and the manifest records each rehydration.
