# Changelog

## 0.2.0

- Rehydrate picker (a mod: `hooks/register.tsx`, named under `modules` in `hooks/hooks.json` next
  to the classic SessionStart hooks). A bare `/rehydrate` on a terminal or the desktop app opens
  a pane listing dehydrated sessions and worktrees by their `claude agents` name and short id,
  grouped Today, This week, This month, Older, filtered as you type. Enter rehydrates and
  relaunches. `/rehydrate <words>`, mobile and any mod failure fall back to the skill.
- `list --picker`: flat JSON rows for the pane (one per session, age group computed in Python,
  live-copy match, `agents-cache.json` fallback when `claude agents` is slow).
- Auto-dehydrate on close (`auto_on_close`, default on): `dehydrate.py auto` sweeps ended
  background sessions from the SessionStart refresh (at most once per `auto_sweep_minutes`) and
  the mod's `session.end` kicks `auto --session <id>` detached. Only work whose branch is merged
  into the remote default branch (ancestor with own commits, merge-tree squash or rebase, or a
  merged PR at HEAD via `gh`) is dehydrated, through the normal plan with every hold. Decisions go
  to `auto.log`. Records carry an `auto` block.
- `rehydrate --launch` checks `claude agents` first and never starts a duplicate copy. It fails
  closed when the listing cannot be read, passes `-n <name>` so the copy keeps its name, parses
  the copy's new id, and records it under `launched` on the `rehydrated` event. With `--json`
  an error prints `{"error": ...}`.
- Fix: `worktreePath` and `worktreeBranch` are read from the job's `state.json` (agents rows
  never carry them on 2.1.312), so the Claude-managed-worktree guard in `apply` fires. A
  worktree path that no longer exists no longer blocks closing its session. The job's `intent`
  fills `first_prompt` when the transcript is missing.
- The last `agent-name` transcript entry is recorded as `agent_name`, the name fallback that
  tracks renames. `list <words>` also matches the repo name and launched-copy ids.
- Review fixes before release:
  - Picker: a worktree dehydrated with its session is one row (the session's); rows carry
    `restored`, and Enter on a restored item only launches it. Tags `running`, `open` (still
    listed in `claude agents`), `restored`, `in place`. A pick in flight keeps its phase when a
    list refresh or a reopen lands; the success close timer only closes the pane it was set for.
    At most 50 rows are drawn (`+N more`), rows are cut to the pane's width (repo and branch
    dropped under 60 columns), the header says `N of 500 newest (of TOTAL)`, a list output over
    4 MiB is reported, not parsed. `search` is capped at 2048 characters per row.
  - `rehydrate`: an item still restored at its path is left as it is (`already restored ...,
    nothing changed`, no new event, `--launch` still launches). A corrupt transcript copy no
    longer aborts after the worktree came back: it is a note and that session is not launched,
    and a restore that touched the disk is always recorded. Every session not launched has a
    reason in `notes` and `launched[].note` (`skipped`). A launch that prints no id is recorded
    `unconfirmed` and blocks a second copy for 10 minutes. A session still listed in
    `claude agents` (any state), or a working/blocked row without a pid, is never launched again.
    The exact agents name is a key. Text `list` shows `name (short id)` and an empty-store line.
  - Merge rule: merge-tree counts as merged only when the branch changes files that are already on
    the default branch (a commit plus its revert, or an empty commit after a squash, is not proof),
    and the reason says which (rebase or squash). The ancestor rule needs a commit of the branch's
    own still on HEAD (a reset-away commit no longer counts). `gh pr list` is pinned with
    `-R <origin>`.
  - Auto: a close kick waits for its process before it takes `.auto.lock`, then waits up to
    120 s for it; one that still cannot run is queued in `auto-pending/` and logged `deferred`, and
    the next run drains the queue. The kick ignores SIGHUP until the script's setsid, so a closing
    terminal does not kill it. A rehydrated session is not auto-dehydrated again until it runs and
    ends again.
  - Config: values are type-checked (a wrong type keeps the default and is a config error, which
    turns auto off; `"false"` in quotes no longer leaves auto on, and `"auto_apply": "true"` no
    longer applies). Unknown keys are warned about. New `dehydrate.py config [get|set|unset]` and
    `auto --status` replace the python one-liner (which ignored `$DEHYDRATE_HOME`). The first
    nudge after the upgrade says once that auto-on-close is on and how to turn it off.
  - CLI: every subcommand has a description; `auto` hides the plan-only flags. Record ids and
    `at` use one clock (UTC date, `--now` honoured).
  - `tsconfig.json` at the plugin root (the engine's `.claude-plugin/types` layout).
- Tests: the merge-rule fixtures give the local bare-remote fetch 180 s (`SLOW_FETCH_S`). On a
  loaded host the 30 s default timed out and the rule failed closed, which failed
  `test_merge_rule_scenarios`. The shipped default stays 30 s.

## 0.1.3

- `apply` no longer crashes when `git worktree remove` is slow: it runs with a 3600 s timeout and
  a timeout becomes a "not done" item (captured, not removed; rerun apply). A 330k-file worktree
  took over 120 s and the crash also skipped `worktree prune` and the index rewrite.
- `apply` isolates every item: an exception while handling one worktree, session, leftover dir or
  main checkout is recorded as "not done" and the loop continues. `worktree prune` and
  `write_index` always run (finally).
- Disk-pressure mode: `plan|apply --pressure --target-gb N`. The idle window is ignored for
  worktrees; candidates go least recently active first, then largest, one at a time, and apply
  stops as soon as free disk reaches N (exit 0, `pressure.reached` in the JSON). Every hold still
  applies. A session that is `done` or `blocked` for more than 24 h no longer protects its
  worktree and is archived and closed with it; other sessions, leftover dirs and main checkouts
  are left alone. `DEHYDRATE_FAKE_FREE_GB` feeds the stop check in tests.

## 0.1.2

- `--mains` no longer crashes when a linked worktree sits under a gitignored path inside a main
  checkout. `git add` rejects a `:(exclude)` pathspec for an already-ignored path, so ignored
  worktree paths are dropped from the exclude list (they are not captured anyway).
- One failing main checkout no longer aborts the whole `--mains` pass. It is recorded as
  `ok: false` with a `not captured: ...` error and the remaining checkouts are still snapshotted.

## 0.1.1

- Record ids hash with sha256 instead of sha1 (CodeQL `py/weak-sensitive-data-hashing`). Nothing
  secret was hashed; stored ids are unchanged.

## 0.1.0

- Initial release: `dehydrate` and `rehydrate` skills, SessionStart nudge hook, `scripts/dehydrate.py`.
