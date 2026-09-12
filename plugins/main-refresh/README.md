# main-refresh

Keep a local `main` checkout equal to `origin/main` without losing local work. Built for people
who do their branch work in Claude worktrees: main is a parity copy that sessions read hooks,
rules and CLAUDE.md from, not a workbench. The script decides safety before acting, fast-forwards
only when no local file is touched, and parks anything in the way on an ordinary branch.

## Install

```
claude plugin install main-refresh@getfatday-skills --scope user
```

## Commands

`${CLAUDE_PLUGIN_ROOT}` only resolves inside a hook or a skill's own execution. From a person's
shell, use the resolved install path instead:

```
~/.claude/plugins/cache/getfatday-skills/main-refresh/<version>/scripts/main-refresh.sh
```

Every `MAIN_REFRESH_FIX` line the script prints already carries its own absolute path (`self_path`
in the script), so copying a FIX line and running it always works, no matter where the plugin is
installed or which shell you are in.

```
bash "${CLAUDE_PLUGIN_ROOT}/scripts/main-refresh.sh" detect   # count Claude worktrees
bash "${CLAUDE_PLUGIN_ROOT}/scripts/main-refresh.sh" check    # classify, change nothing
bash "${CLAUDE_PLUGIN_ROOT}/scripts/main-refresh.sh" apply    # fast-forward only when SAFE
bash "${CLAUDE_PLUGIN_ROOT}/scripts/main-refresh.sh" park     # branch local work off, land main
```

With no argument, the script defaults to `check`. Any other command name is rejected before
anything else runs: it prints `SKIP unknown command '<cmd>' (detect|check|apply|park)` and exits 50.

States and exit codes: UP_TO_DATE 0, SAFE 0, APPLIED 0, BLOCKED 20, DIVERGED 30, LOCKED 40,
SKIP 50. Every output line starts with `MAIN_REFRESH`. Works from the main checkout or any worktree.

SKIP covers several reasons, all exit 50: not a git repository, no origin remote, no local main
branch, main checked out on some other branch, origin/main not fetched yet, or an unknown command.

A `MAIN_REFRESH_FIX` line ends with a `   # comment` after the command, explaining what the
command does. If you are consuming these lines programmatically and matching on the exact
command, strip the trailing `# comment` first.

## Hook

`UserPromptSubmit` runs `main-refresh-hook.sh`: skips cloud sessions, non-git directories and
repositories without an origin or a Claude worktree, debounces a background `git fetch` to once
per 300 s, then runs `apply --quiet` and forwards the output. Exit 0 on every path.

## Invariants

Never stash. Never delete a lock. Never reset main without parking first. Parked work lives on
`wip/main-<date>-<n>`, a plain branch with its own worktree under `.claude/worktrees/`, so every
step is reversible with ordinary git.

## Evidence

Vault hypotheses H-DRAFT-9977584e (plugin location independence) and H-DRAFT-d170cdbe (DIVERGED
park). Product-portfolio lab hypotheses H-DRAFT-42bcb836, cb3183ee and 8e6ccda1.
