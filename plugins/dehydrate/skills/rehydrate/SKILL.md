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

## Steps

1. **Find it.** `D list <words>` searches ids, descriptions, session names and titles, first
   prompts, branches, paths and session ids (all words must match, case-insensitive). With no
   words it lists the most recent 50. `--kind worktree|session|orphan|main-snapshot` narrows it.
   Show the user the candidates with their dates and one-line descriptions. If several match,
   let them pick (AskUserQuestion with the top few) rather than guessing. `D show <id>` prints
   one full record.

2. **Rehydrate.** `D rehydrate <id>`. The key can also be a session id (or its first 8
   characters), a background session id, a branch or the original path, as long as it matches
   one record.
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
     anything and says which file. Report that; do not work around it.

3. **Resume.** The output prints one `cd <dir> && claude --resume <session-id>` per session.
   Give the user those commands. If they want it running now, rerun with `--launch` to start
   each as a background session (`claude --bg --resume`), which then shows up in `claude agents`.
   Do not launch a resume for a session that is still listed as running in `claude agents`:
   resuming a live session starts a copy.

4. **Verify and report.** Check that the printed path exists and `git -C <path> status` shows the
   expected changes. Report the path, the branch, any notes (renamed branch, restored ignored
   files), and the resume commands. A `WARNING:` note (restored files or tree differ from what was
   captured) means something did not round-trip, so show `git status` and say so plainly.

Rehydrating never deletes the archive. The same item can be rehydrated again later (after the
worktree is removed again), and the manifest records each rehydration.
