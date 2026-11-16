#!/usr/bin/env bash
# UserPromptSubmit hook for the main-refresh plugin.
#
# Keeps the local main checkout at origin/main for people who branch through Claude worktrees.
# Runs on every prompt, exits 0 on every path, and prints nothing unless main-refresh.sh has
# something to say. Steps:
#   1. skip in cloud sessions, outside a git repository, or when there is no origin remote
#   2. act only when the repository has at least one Claude worktree (the rule is for worktree users)
#   3. debounce a detached background fetch of origin (once per 300 s, marker in the git common dir)
#   4. run main-refresh.sh apply --quiet and forward its output unchanged
#
# Which main-refresh.sh runs: the repository's own scripts/main-refresh.sh wins, because the
# repository knows its own paths and spools. The rule is the one the repository's
# .claude/hooks/auto-sync.sh uses:
#   a. a copy that has scripts/main-refresh-paths.txt beside it; when the working checkout and
#      the main worktree both have one, the main worktree's copy (apply keeps it at origin/main)
#   b. when neither has the paths file, the working checkout's copy, then the main worktree's
#   c. when the repository ships no copy, the plugin's own copy next to this file
# Only `detect` always runs the plugin's copy: it counts worktrees and needs nothing from the repo.

set -uo pipefail

# Consume the hook's JSON payload on stdin so the harness never sees a broken pipe.
[[ -t 0 ]] || cat >/dev/null 2>&1 || true

[[ "${CLAUDE_CODE_REMOTE:-}" == "true" ]] && exit 0

here="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
plugin_script="$here/main-refresh.sh"
[[ -f "$plugin_script" ]] || exit 0

git rev-parse --git-dir >/dev/null 2>&1 || exit 0
git remote get-url origin >/dev/null 2>&1 || exit 0

# Only worktree users. detect prints "MAIN_REFRESH_WORKTREES: <n>".
n="$(bash "$plugin_script" detect 2>/dev/null | awk '/^MAIN_REFRESH_WORKTREES:/{print $2; exit}')"
case "$n" in
  ''|*[!0-9]*) exit 0 ;;
esac
[[ "$n" -ge 1 ]] || exit 0

# Debounced background fetch so origin/main is fresh for the next prompt, not this one.
common_dir="$(git rev-parse --git-common-dir 2>/dev/null || true)"
if [[ -n "$common_dir" ]]; then
  [[ "$common_dir" = /* ]] || common_dir="$(pwd)/$common_dir"
  marker="$common_dir/main-refresh-fetch-stamp"
  now=$(date +%s)
  if [[ -e "$marker" ]]; then
    mtime=$(stat -f %m "$marker" 2>/dev/null || stat -c %Y "$marker" 2>/dev/null || echo 0)
  else
    mtime=0
  fi
  if (( now - mtime > 300 )); then
    touch "$marker" 2>/dev/null || true
    ( git fetch origin --quiet >/dev/null 2>&1 & )
  fi
fi

# Pick the script. The repository's copy first (see the header), the plugin's copy last.
repo_top="$(git rev-parse --show-toplevel 2>/dev/null || true)"
main_wt="$(git worktree list --porcelain 2>/dev/null | awk '/^worktree /{print substr($0,10); exit}')"
script=""
for cand in "$main_wt/scripts/main-refresh.sh" "$repo_top/scripts/main-refresh.sh"; do
  [[ "$cand" == /scripts/* ]] && continue
  if [[ -f "$cand" && -f "$(dirname "$cand")/main-refresh-paths.txt" ]]; then script="$cand"; break; fi
done
if [[ -z "$script" ]]; then
  for cand in "$repo_top/scripts/main-refresh.sh" "$main_wt/scripts/main-refresh.sh"; do
    [[ "$cand" == /scripts/* ]] && continue
    if [[ -f "$cand" ]]; then script="$cand"; break; fi
  done
fi
[[ -n "$script" ]] || script="$plugin_script"

# Forward main-refresh's output unchanged. Its exit code is a state, not an error for the hook.
bash "$script" apply --quiet 2>&1 || true
exit 0
