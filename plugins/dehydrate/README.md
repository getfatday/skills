# dehydrate

Close out stale Claude Code sessions and worktrees without losing anything, and bring them back.

- `/dehydrate`: sessions and worktrees idle for 7 days (or `--days N`) are captured and closed.
  Each worktree becomes `refs/dehydrated/<id>` plus a git bundle. The worktree's branch never
  moves, nothing is committed to main, nothing is pushed. Gitignored real files go into a
  tarball. Transcripts and job dirs are archived. Then the worktree is removed and the session
  closed with `claude stop` / `claude rm`.
- `/rehydrate <words>`: find the item in the manifest and restore it: same path, same branch,
  same uncommitted state, transcript restored if Claude Code swept it, plus a ready
  `claude --resume` command.

State lives in `~/.claude/dehydrated/` (`manifest.jsonl`, `index.md`, `archive/`). A SessionStart
hook prints one line a day when there is something to dehydrate. Set `"auto_apply": true` in
`~/.claude/dehydrated/config.json` to make the background refresh apply on its own.

Script: `scripts/dehydrate.py` (stdlib only, `--help` on every subcommand).
Tests: `python3 -m unittest discover -s tests`.
