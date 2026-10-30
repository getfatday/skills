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

State lives in `$DEHYDRATE_HOME` or `~/.claude/dehydrated/` (`manifest.jsonl`, `index.md`, `archive/`,
`config.json`). A SessionStart hook prints one line a day when there is something to dehydrate.
`dehydrate.py config` shows the settings and `config set <key> <value>` changes one (type-checked,
other keys kept). `config set auto_apply true` makes the background refresh apply on its own.

Picker: a bare `/rehydrate` on a terminal or the desktop app opens a pane (a mod) listing every
dehydrated session and worktree by the name and short id `claude agents` showed, grouped by age
(Today, This week, This month, Older). A worktree dehydrated with its session is one row, the
session's. Type to search name, first prompt, description, branch and repo. Enter restores the row
and relaunches it with `claude --bg --resume`, so it shows up in `claude agents` again under the same
name. Tags: `running` (a copy runs, not started twice), `open` (still listed in `claude agents`:
attach it), `restored` (already back at its path: Enter only launches it), `in place` (never
removed). The pane draws 50 rows at a time and searches the 500 newest; `/rehydrate <words>` runs
the skill over everything.

Auto-dehydrate on close (on by default): when a session ends and its worktree branch is merged into
the remote default branch (contained in it with commits of its own, its changes already there from
a squash or rebase merge, or a merged PR at its HEAD), it is dehydrated on its own, so its disk state
is saved and the picker can bring it back. The SessionStart sweep catches background sessions
stopped from `claude agents`, and the mod kicks it when an interactive session exits. Unmerged or
live work is never touched, and an item you rehydrate waits until it runs and ends again. Every
decision is logged to `auto.log`. `dehydrate.py auto --status` says whether it is on; turn it off
with `python3 scripts/dehydrate.py config set auto_on_close false`.

Disk pressure: `dehydrate.py apply --yes --pressure --target-gb 20` ignores the idle window and
dehydrates worktrees one at a time, least recently active first, until 20 GB are free, with every
hold still in force, plus two of its own: a worktree inside a live session's job dir
(`~/.claude/jobs/<id>/`) and one touched in the last 2 hours. Apply re-reads `config.json` and every
hold right before each capture and each removal, so an exclusion added mid-run is honoured.
disk-reclaim's automatic mode calls exactly this.

Script: `scripts/dehydrate.py` (stdlib only, `--help` on every subcommand).
Mod: `hooks/register.tsx` (named under `modules` in `hooks/hooks.json`, beside the classic
SessionStart hooks), state contract in `types/index.d.ts`, `tsconfig.json` for the engine's
`.claude-plugin/types` layout.
Tests: `python3 -m unittest discover -s tests` and `claude plugin test .` for the mod.
