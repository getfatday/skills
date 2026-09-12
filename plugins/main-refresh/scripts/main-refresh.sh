#!/usr/bin/env bash
# Keep the local main checkout in step with origin/main without ever losing local work.
#
# Local main is a parity copy for people who do their branch work in Claude worktrees: it is
# where the project's hooks, rules, plugin list and CLAUDE.md are read from when a session
# starts in the main checkout. It is not a workbench. This script decides, before touching
# anything, whether main can move to origin/main safely, says so in one line, and names the
# exact file in the way when it cannot. It never stashes: the stash stack is shared by every
# worktree and session, so a bare stash can be popped by someone else.
#
# This copy ships inside the user-level Claude Code plugin "main-refresh" and is run as
#   bash "${CLAUDE_PLUGIN_ROOT}/scripts/main-refresh.sh" <command> [--quiet]
# from any checkout of any repository. Every MAIN_REFRESH_FIX hint prints this script's own
# absolute path, so the hint is correct wherever the plugin is installed.
#
# Commands:
#   detect   print how many Claude worktrees (.claude/worktrees/*) this repository has
#   check    classify without changing anything; exit code is the state (see below)
#   apply    fast-forward main when, and only when, check says SAFE
#   park     move dirty tracked files and colliding untracked files into a new worktree on
#            a wip/main-<date>-<n> branch, commit them there, then fast-forward main.
#            When main is DIVERGED, the same branch is created at the current local main
#            HEAD so every local-only commit stays reachable from it; the dirty and colliding
#            files are committed on top; then main is reset to origin/main (a fast-forward is
#            impossible when diverged). Nothing is lost: the parked branch is an ordinary branch.
#
# Works from the main checkout or from inside any worktree: every git command targets the
# main worktree, found from `git worktree list`.
#
# States and exit codes (check):
#   0  SAFE        fast-forward will succeed and touch no dirty or untracked file
#   0  UP_TO_DATE  main already equals origin/main
#   0  APPLIED     (apply/park only) main moved to origin/main
#   20 BLOCKED     a dirty tracked file or an untracked file sits on a path upstream changed
#   30 DIVERGED    local main has commits origin/main does not (check/apply stop; park handles it)
#   40 LOCKED      .git/index.lock exists, is older than an hour, and no git process is running
#   50 SKIP        no origin, no main branch, or main checked out nowhere
#
# Every line of output starts with MAIN_REFRESH so a hook can forward it unchanged.
# Rule: CLAUDE.md "Local main". Evidence: product-portfolio hypotheses H-DRAFT-42bcb836,
# cb3183ee, 8e6ccda1; vault hypotheses H-DRAFT-9977584e (plugin) and H-DRAFT-d170cdbe
# (DIVERGED park).

set -uo pipefail

cmd="${1:-check}"
quiet=false
[[ "${2:-}" == "--quiet" ]] && quiet=true

# This script's own absolute path, for the MAIN_REFRESH_FIX hints.
self_path="$(cd "$(dirname "$0")" 2>/dev/null && pwd)/$(basename "$0")"

say() { echo "MAIN_REFRESH: $*"; }
fix() { echo "MAIN_REFRESH_FIX: $*"; }

case "$cmd" in
  detect|check|apply|park) ;;
  *) say "SKIP unknown command '$cmd' (detect|check|apply|park)"; exit 50 ;;
esac

git rev-parse --git-dir >/dev/null 2>&1 || { say "SKIP not a git repository"; exit 50; }

# The main worktree is the first entry of `git worktree list --porcelain`.
main_wt="$(git worktree list --porcelain | awk '/^worktree /{print substr($0,10); exit}')"
[[ -n "$main_wt" ]] || { say "SKIP cannot find the main worktree"; exit 50; }
g() { git -C "$main_wt" "$@"; }

# ---- detect -----------------------------------------------------------------------------
claude_worktrees() {
  git worktree list --porcelain | awk '/^worktree /{print substr($0,10)}' | grep -c '/\.claude/worktrees/' || true
}
if [[ "$cmd" == "detect" ]]; then
  n="$(claude_worktrees)"
  echo "MAIN_REFRESH_WORKTREES: $n"
  exit 0
fi

# ---- preconditions ------------------------------------------------------------------------
g remote get-url origin >/dev/null 2>&1 || { say "SKIP no origin remote"; exit 50; }
g show-ref --verify --quiet refs/heads/main || { say "SKIP no local main branch"; exit 50; }
main_branch="$(g branch --show-current 2>/dev/null || true)"
if [[ "$main_branch" != "main" ]]; then
  say "SKIP main worktree is on '$main_branch', not main"
  exit 50
fi

# Stale lock: a crashed process leaves an empty .git/index.lock and every later git write
# fails. Report it, never remove it: deciding that is the person's call.
common_dir="$(g rev-parse --git-common-dir)"
[[ "$common_dir" = /* ]] || common_dir="$main_wt/$common_dir"
lock="$common_dir/index.lock"
if [[ -e "$lock" ]]; then
  now=$(date +%s)
  mtime=$(stat -f %m "$lock" 2>/dev/null || stat -c %Y "$lock" 2>/dev/null || echo "$now")
  age=$(( now - mtime ))
  if (( age > 3600 )) && ! pgrep -x git >/dev/null 2>&1; then
    say "LOCKED $lock is $(( age / 60 )) minutes old with no git process running"
    fix "/bin/rm -f '$lock'   # then rerun: $self_path $cmd"
    exit 40
  fi
fi

local_sha="$(g rev-parse HEAD)"
remote_sha="$(g rev-parse origin/main 2>/dev/null || true)"
[[ -n "$remote_sha" ]] || { say "SKIP origin/main not fetched yet"; exit 50; }

if [[ "$local_sha" == "$remote_sha" ]]; then
  $quiet || say "UP_TO_DATE main is at origin/main ${remote_sha:0:9}"
  exit 0
fi

# DIVERGED: local main has commits origin/main does not. check and apply stop here and point
# at park; park continues, branches the local-only commits off, and resets main.
diverged=false
ahead=0
if ! g merge-base --is-ancestor HEAD origin/main; then
  diverged=true
  ahead=$(g rev-list --count origin/main..HEAD)
  if [[ "$cmd" != "park" ]]; then
    say "DIVERGED local main has $ahead commit(s) origin/main does not"
    fix "$self_path park   # branches the local-only commits off to wip/main-<date>-<n>, then resets main to origin/main"
    exit 30
  fi
fi

behind=$(g rev-list --count HEAD..origin/main)

# ---- collision analysis -------------------------------------------------------------------
# Upstream paths: everything the fast-forward would write.
upstream_changed="$(g diff --name-only HEAD origin/main)"
# Dirty tracked files (modified, deleted, renamed, staged) in the main checkout.
dirty_tracked="$(g status --porcelain --untracked-files=no | awk '{print $NF}')"
# Untracked files (not ignored) in the main checkout. Linked worktrees live under
# .claude/worktrees/ inside the main checkout; they are other checkouts, not local work,
# and scanning them file by file is slow, so they are left out.
untracked="$(g status --porcelain --untracked-files=all -- . ':(exclude).claude/worktrees' | awk '$1=="??"{print $2}')"

blocking_tracked=()
while IFS= read -r p; do
  [[ -z "$p" ]] && continue
  if grep -Fxq -- "$p" <<<"$upstream_changed"; then blocking_tracked+=("$p"); fi
done <<<"$dirty_tracked"

blocking_untracked=()
while IFS= read -r p; do
  [[ -z "$p" ]] && continue
  if grep -Fxq -- "$p" <<<"$upstream_changed"; then blocking_untracked+=("$p"); fi
done <<<"$untracked"

blocked=$(( ${#blocking_tracked[@]} + ${#blocking_untracked[@]} ))

report_blocked() {
  say "BLOCKED main is $behind behind origin/main; $blocked local path(s) sit where upstream wrote"
  for p in "${blocking_tracked[@]+"${blocking_tracked[@]}"}"; do echo "MAIN_REFRESH_BLOCKING: dirty tracked  $p"; done
  for p in "${blocking_untracked[@]+"${blocking_untracked[@]}"}"; do echo "MAIN_REFRESH_BLOCKING: untracked      $p"; done
  fix "$self_path park   # moves these into their own worktree, then fast-forwards main"
}

if [[ "$cmd" == "check" ]]; then
  if (( blocked > 0 )); then report_blocked; exit 20; fi
  say "SAFE main is $behind behind origin/main; fast-forward touches no local file"
  fix "$self_path apply"
  exit 0
fi

# ---- apply --------------------------------------------------------------------------------
do_ff() {
  if g merge --ff-only --quiet origin/main 2>/dev/null; then
    say "APPLIED main fast-forwarded $behind commit(s) to ${remote_sha:0:9}"
    return 0
  fi
  if [[ -e "$lock" ]]; then
    # A lock younger than an hour, or one with some git process alive somewhere on the
    # machine, is not called stale above. If the merge still failed, the lock is the reason.
    say "LOCKED $lock is present and the fast-forward could not take the index"
    fix "/bin/rm -f '$lock'   # only if no git command of yours is running; then rerun: $self_path $cmd"
    return 40
  fi
  say "FAILED fast-forward did not complete; run the check for detail"
  fix "$self_path check"
  return 1
}

if [[ "$cmd" == "apply" ]]; then
  if (( blocked > 0 )); then report_blocked; exit 20; fi
  do_ff; exit $?
fi

# ---- park ---------------------------------------------------------------------------------
if [[ "$cmd" == "park" ]]; then
  if [[ "$diverged" == false && -z "$dirty_tracked" && "$blocked" -eq 0 ]]; then
    say "NOTHING_TO_PARK main has no dirty tracked files and no colliding untracked files"
    do_ff; exit $?
  fi
  day="$(date -u +%Y-%m-%d)"
  n=1
  while g show-ref --verify --quiet "refs/heads/wip/main-$day-$n"; do n=$((n+1)); done
  branch="wip/main-$day-$n"
  wt_dir="$main_wt/.claude/worktrees/wip-main-$day-$n"
  # Base the parking branch at the CURRENT local HEAD so the dirty files apply as they are and,
  # when diverged, every local-only commit is reachable from the branch.
  if ! g worktree add --quiet -b "$branch" "$wt_dir" HEAD 2>/dev/null; then
    say "FAILED could not create worktree $wt_dir"; exit 1
  fi
  moved=0
  # Dirty tracked: copy modified files over; mirror deletions; then restore main's copy.
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    code="${line:0:2}"; p="${line:3}"
    case "$code" in
      *D*) rm -f "$wt_dir/$p"; git -C "$wt_dir" rm --quiet --cached -- "$p" 2>/dev/null || true ;;
      *)   mkdir -p "$wt_dir/$(dirname "$p")"; cp -p "$main_wt/$p" "$wt_dir/$p" ;;
    esac
    moved=$((moved+1))
  done < <(g status --porcelain --untracked-files=no)
  # Colliding untracked: move (not copy) so main's path is clear for the fast-forward.
  for p in "${blocking_untracked[@]+"${blocking_untracked[@]}"}"; do
    mkdir -p "$wt_dir/$(dirname "$p")"
    mv "$main_wt/$p" "$wt_dir/$p"
    moved=$((moved+1))
  done
  git -C "$wt_dir" add -A >/dev/null 2>&1
  if [[ -n "$(git -C "$wt_dir" status --porcelain --untracked-files=no)" ]]; then
    if ! git -C "$wt_dir" -c user.name="${GIT_AUTHOR_NAME:-$(g config user.name || echo main-refresh)}" \
          -c user.email="${GIT_AUTHOR_EMAIL:-$(g config user.email || echo main-refresh@localhost)}" \
          commit --quiet --no-verify -m "wip: parked from local main on $day

Moved by main-refresh park so main could fast-forward. $moved path(s)." >/dev/null 2>&1; then
      say "FAILED nothing committed in $wt_dir; main left untouched"; exit 1
    fi
  elif [[ "$diverged" == false ]]; then
    # Not diverged and nothing staged: the branch would carry nothing main does not already have.
    say "FAILED nothing committed in $wt_dir; main left untouched"; exit 1
  fi
  # Now clear main's tracked changes. The bytes are safe in the parked commit.
  g checkout --quiet -- . 2>/dev/null || true
  g reset --quiet --hard HEAD >/dev/null 2>&1
  if [[ "$diverged" == true ]]; then
    # A fast-forward is impossible when diverged. The local-only commits are reachable from
    # $branch, so resetting main is lossless.
    if ! g reset --quiet --hard origin/main >/dev/null 2>&1; then
      say "FAILED could not reset main to origin/main; local commits are on $branch at $wt_dir"; exit 1
    fi
    say "PARKED $moved path(s) and $ahead commit(s) on branch $branch at $wt_dir"
    say "APPLIED main reset to origin/main ${remote_sha:0:9}"
    exit 0
  fi
  say "PARKED $moved path(s) on branch $branch at $wt_dir"
  do_ff; exit $?
fi
