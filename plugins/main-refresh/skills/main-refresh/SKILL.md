---
name: main-refresh
description: >-
  Keep a local main checkout equal to origin/main without losing any local work, for people who
  do their branch work in Claude worktrees. Classifies main as UP_TO_DATE, SAFE, BLOCKED, DIVERGED,
  LOCKED or SKIP before touching anything, fast-forwards only when no local file is in the way, and
  parks dirty files, colliding untracked files and local-only commits on an ordinary
  wip/main-<date>-<n> branch instead of stashing. Use this whenever local main is behind, dirty,
  stale or diverged from origin, when someone asks to sync main, refresh main, update local main
  after a merge, park main, or asks why their main is stale or still shows old files, when a
  fast-forward or pull on main fails, and whenever a hook has printed a MAIN_REFRESH or
  MAIN_REFRESH_FIX line in the conversation. Also use it when a worktree session cannot see a
  change that was just merged to origin/main. Do not use it for branch work in a worktree, and do
  not reach for git stash on main when this skill applies.
---

# main-refresh

Local main is a parity copy, not a workbench. For people who branch through Claude worktrees, the
main checkout is where a new session reads the project's hooks, rules, plugin list and CLAUDE.md.
It should always equal origin/main. Work happens on branches in `.claude/worktrees/`, lands through
a PR, and comes back to main only by fast-forward from origin.

This skill wraps one script. Run it, read the one MAIN_REFRESH line it prints, and act on the
MAIN_REFRESH_FIX line if there is one. The script decides safety before it changes anything, so
running `check` is always free.

## Run it

From any checkout of the repository (the main checkout or any worktree):

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/main-refresh.sh" check
bash "${CLAUDE_PLUGIN_ROOT}/scripts/main-refresh.sh" apply
bash "${CLAUDE_PLUGIN_ROOT}/scripts/main-refresh.sh" park
bash "${CLAUDE_PLUGIN_ROOT}/scripts/main-refresh.sh" detect
```

Every git call targets the main worktree, found from `git worktree list`, so the current directory
does not matter. Add `--quiet` to suppress the UP_TO_DATE line (the hook does this).

If origin/main looks stale, run `git fetch origin` first. The script reads the fetched ref and
never fetches on its own. The plugin's prompt hook fetches in the background once per five minutes.

## Commands and states

| Command | What it does | Prints | Exit |
| --- | --- | --- | --- |
| `detect` | Count Claude worktrees under `.claude/worktrees/` | `MAIN_REFRESH_WORKTREES: <n>` | 0 |
| `check` | Classify without changing anything | one state line, maybe a FIX line | state code |
| `apply` | Fast-forward main only when check says SAFE | `APPLIED` or the blocking state | 0 or state code |
| `park` | Move local work to a `wip/main-<date>-<n>` branch and worktree, then land main on origin/main | `PARKED` then `APPLIED` | 0 |

States and exit codes:

| State | Exit | Meaning |
| --- | --- | --- |
| `UP_TO_DATE` | 0 | main already equals origin/main |
| `SAFE` | 0 | fast-forward will touch no dirty or untracked file |
| `APPLIED` | 0 | main moved to origin/main (apply or park) |
| `BLOCKED` | 20 | a dirty tracked file or an untracked file sits on a path upstream changed; each path is listed on a `MAIN_REFRESH_BLOCKING` line |
| `DIVERGED` | 30 | local main has commits origin/main does not; check and apply stop, park handles it |
| `LOCKED` | 40 | `.git/index.lock` is over an hour old with no git process running; the script never removes it |
| `SKIP` | 50 | no origin, no main branch, main checked out nowhere, or origin/main not fetched |

## What park does

On BLOCKED: creates the branch and a worktree at `.claude/worktrees/wip-main-<date>-<n>` from the
current main HEAD, copies dirty tracked files and moves colliding untracked files there, commits
them, clears main's tracked changes, then fast-forwards main.

On DIVERGED: the same branch is created at the current main HEAD, so every local-only commit is
reachable from it. Dirty and colliding files are committed on top when there are any. Main is
then reset to origin/main, because a fast-forward is impossible when histories differ. Output is
`PARKED <n> path(s) and <k> commit(s) on branch <branch> at <dir>` followed by
`APPLIED main reset to origin/main <sha>`.

The parked branch is an ordinary branch. Nothing about it is special: rebase it, cherry-pick from
it, open a PR from it, or delete it when it has served its purpose.

## Invariants

- Never stash. The stash stack is shared by every worktree and session, and a bare stash can be
  popped by someone else. Parking uses a branch, which has a name and an owner.
- Never delete a lock. A LOCKED state names the file and the age; removing it is the person's call.
- Never reset without parking first. Main only moves after the bytes it would overwrite are in a
  commit on a named branch.
- Everything is reversible. Parked branches are plain branches; `git log <branch>` shows what was
  moved and `git worktree list` shows where.
- Every output line starts with `MAIN_REFRESH`, so hooks can forward it unchanged.

## What to tell the user after each state

- `UP_TO_DATE`: main is current. Say so in one line and move on.
- `SAFE`: run `apply` (or say the hook will on the next prompt). Report the new sha.
- `APPLIED`: report how many commits main moved and the sha. If a worktree session was waiting on
  a merged change, it can now see it from main.
- `BLOCKED`: name the colliding paths from the BLOCKING lines. Recommend `park`. Explain that park
  moves those files to a wip branch and worktree, then fast-forwards; nothing is deleted.
- `DIVERGED`: say how many local-only commits main has. Recommend `park`. Explain that park keeps
  every commit on a wip branch and then sets main to origin/main. Offer
  `git -C <main> log --oneline origin/main..HEAD` if they want to read the commits first.
- `PARKED`: give the branch name and worktree path. Say the work is committed there and main is
  now at origin/main. Ask whether they want a PR from the parked branch or to leave it.
- `LOCKED`: show the lock path and age. Ask before running the `rm` the FIX line suggests, and
  confirm no git command of theirs is running.
- `SKIP`: state the reason from the line (no origin, no main, not fetched). Run `git fetch origin`
  and rerun if the reason is an unfetched origin/main.

## When a hook printed a MAIN_REFRESH line

The plugin's UserPromptSubmit hook runs `apply --quiet` on every prompt in repositories that have
at least one Claude worktree. An `APPLIED` line means main just moved; nothing to do. A `BLOCKED`
or `DIVERGED` line means the hook changed nothing and is asking for a decision. Surface the line
to the user, explain the state in one sentence, and offer the FIX command. Do not run `park`
without telling the user what it will move.
