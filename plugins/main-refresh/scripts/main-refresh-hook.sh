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
# main-refresh.sh is located next to this file, never through a repository path, so the hook
# works in repositories that carry no copy of the script.

set -uo pipefail

# Consume the hook's JSON payload on stdin so the harness never sees a broken pipe.
[[ -t 0 ]] || cat >/dev/null 2>&1 || true

[[ "${CLAUDE_CODE_REMOTE:-}" == "true" ]] && exit 0

here="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
script="$here/main-refresh.sh"
[[ -f "$script" ]] || exit 0

git rev-parse --git-dir >/dev/null 2>&1 || exit 0
git remote get-url origin >/dev/null 2>&1 || exit 0

# Only worktree users. detect prints "MAIN_REFRESH_WORKTREES: <n>".
n="$(bash "$script" detect 2>/dev/null | awk '/^MAIN_REFRESH_WORKTREES:/{print $2; exit}')"
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

# Forward main-refresh's output unchanged. Its exit code is a state, not an error for the hook.
bash "$script" apply --quiet 2>&1 || true
exit 0
