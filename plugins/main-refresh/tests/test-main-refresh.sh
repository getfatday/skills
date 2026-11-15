#!/usr/bin/env bash
# Shell tests for the main-refresh plugin. Run: bash plugins/main-refresh/tests/test-main-refresh.sh
#
# 1. Which main-refresh.sh the prompt hook runs, in five repository layouts.
# 2. What the plugin's own park prints after it parks commits from a diverged main.
#
# Every scratch repository lives under one temporary directory that the script removes on exit.
# The hook is copied into a scratch "plugin" directory beside a stub main-refresh.sh, so the
# plugin's own copy is told apart from the repository's copies by what they print.

set -uo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/main-refresh-test.XXXXXX")"
trap '/bin/rm -rf "$tmp"' EXIT

# Keep git quiet and independent of the person's own configuration.
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@example.com GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@example.com
unset CLAUDE_CODE_REMOTE

pass=0
fail=0
check() { # name expected actual
  if [[ "$2" == "$3" ]]; then pass=$((pass+1)); echo "ok   $1"
  else fail=$((fail+1)); echo "FAIL $1"; echo "     expected: $2"; echo "     actual:   $3"; fi
}

# ---- scratch plugin: the real hook plus a stub script that names itself ---------------------
plugin="$tmp/plugin/scripts"
mkdir -p "$plugin"
/bin/cp -f "$root/scripts/main-refresh-hook.sh" "$plugin/main-refresh-hook.sh"
cat >| "$plugin/main-refresh.sh" <<'EOF'
#!/usr/bin/env bash
case "${1:-}" in
  detect) echo "MAIN_REFRESH_WORKTREES: $(git worktree list --porcelain | awk '/^worktree /{print substr($0,10)}' | grep -c '/\.claude/worktrees/')" ;;
  *) echo "RAN plugin" ;;
esac
EOF

stub() { # path label
  mkdir -p "$(dirname "$1")"
  printf '#!/usr/bin/env bash\necho "RAN %s"\n' "$2" >| "$1"
}

# new_repo <name>: bare origin, a clone with one commit on main and one worktree under
# .claude/worktrees/w. Prints nothing; sets $main and $wt.
new_repo() {
  local name="$1"
  /usr/bin/git init -q --bare -b main "$tmp/$name-origin.git"
  /usr/bin/git clone -q "$tmp/$name-origin.git" "$tmp/$name" 2>/dev/null
  main="$tmp/$name"
  echo base >| "$main/README"
  /usr/bin/git -C "$main" add README
  /usr/bin/git -C "$main" commit -q -m base
  /usr/bin/git -C "$main" push -q origin main 2>/dev/null
  /usr/bin/git -C "$main" worktree add -q -b work "$main/.claude/worktrees/w" 2>/dev/null
  wt="$main/.claude/worktrees/w"
}

run_hook() { # cwd
  ( cd "$1" && bash "$plugin/main-refresh-hook.sh" </dev/null 2>&1 ); echo "exit=$?"
}

# ---- 1. which script runs -------------------------------------------------------------------
new_repo both
stub "$main/scripts/main-refresh.sh" main-worktree
echo x >| "$main/scripts/main-refresh-paths.txt"
stub "$wt/scripts/main-refresh.sh" working-checkout
echo x >| "$wt/scripts/main-refresh-paths.txt"
out="$(run_hook "$wt")"
check "paths file in both: the main worktree's copy runs" $'RAN main-worktree\nexit=0' "$out"

new_repo wtonly
stub "$main/scripts/main-refresh.sh" main-worktree          # old copy, no paths file beside it
stub "$wt/scripts/main-refresh.sh" working-checkout
echo x >| "$wt/scripts/main-refresh-paths.txt"
out="$(run_hook "$wt")"
check "paths file only in the working checkout: its copy runs" $'RAN working-checkout\nexit=0' "$out"

new_repo mainonly
stub "$main/scripts/main-refresh.sh" main-worktree
echo x >| "$main/scripts/main-refresh-paths.txt"
stub "$wt/scripts/main-refresh.sh" working-checkout         # old copy, no paths file beside it
out="$(run_hook "$wt")"
check "paths file only in the main worktree: its copy runs" $'RAN main-worktree\nexit=0' "$out"

new_repo nopaths
stub "$main/scripts/main-refresh.sh" main-worktree
stub "$wt/scripts/main-refresh.sh" working-checkout
out="$(run_hook "$wt")"
check "paths file nowhere: today's order, the working checkout's copy" $'RAN working-checkout\nexit=0' "$out"

new_repo none
out="$(run_hook "$wt")"
check "repository ships no copy: the plugin's copy runs" $'RAN plugin\nexit=0' "$out"

# ---- 1b. unchanged behavior of the hook -------------------------------------------------------
out="$( cd "$tmp" && bash "$plugin/main-refresh-hook.sh" </dev/null 2>&1; echo "exit=$?" )"
check "outside a git repository: silent, exit 0" "exit=0" "$out"

out="$( cd "$wt" && CLAUDE_CODE_REMOTE=true bash "$plugin/main-refresh-hook.sh" </dev/null 2>&1; echo "exit=$?" )"
check "cloud session: silent, exit 0" "exit=0" "$out"

out="$( cd "$wt" && echo '{"prompt":"hi"}' | bash "$plugin/main-refresh-hook.sh" 2>&1; echo "exit=$?" )"
check "JSON on stdin is consumed, exit 0" $'RAN plugin\nexit=0' "$out"

# A repository with no Claude worktree is skipped even when it ships a script.
/usr/bin/git init -q --bare -b main "$tmp/plain-origin.git"
/usr/bin/git clone -q "$tmp/plain-origin.git" "$tmp/plain" 2>/dev/null
stub "$tmp/plain/scripts/main-refresh.sh" repo
echo x >| "$tmp/plain/scripts/main-refresh-paths.txt"
out="$(run_hook "$tmp/plain")"
check "no Claude worktree: skipped, exit 0" "exit=0" "$out"

# A failing repository script still gives exit 0.
new_repo failing
mkdir -p "$main/scripts"
printf '#!/usr/bin/env bash\necho "MAIN_REFRESH: BLOCKED x"\nexit 20\n' >| "$main/scripts/main-refresh.sh"
echo x >| "$main/scripts/main-refresh-paths.txt"
out="$(run_hook "$main")"
check "script exit 20: line forwarded unchanged, hook exits 0" $'MAIN_REFRESH: BLOCKED x\nexit=0' "$out"

# ---- 2. park from a diverged main -------------------------------------------------------------
/usr/bin/git init -q --bare -b main "$tmp/dv-origin.git"
/usr/bin/git clone -q "$tmp/dv-origin.git" "$tmp/dv" 2>/dev/null
echo base >| "$tmp/dv/README"
/usr/bin/git -C "$tmp/dv" add README
/usr/bin/git -C "$tmp/dv" commit -q -m base
/usr/bin/git -C "$tmp/dv" push -q origin main 2>/dev/null
echo local >| "$tmp/dv/local.txt"
/usr/bin/git -C "$tmp/dv" add local.txt
/usr/bin/git -C "$tmp/dv" commit -q -m local-only
# Move origin/main ahead with a different commit so local main diverges.
/usr/bin/git clone -q "$tmp/dv-origin.git" "$tmp/dv-other" 2>/dev/null
echo up >| "$tmp/dv-other/up.txt"
/usr/bin/git -C "$tmp/dv-other" add up.txt
/usr/bin/git -C "$tmp/dv-other" commit -q -m upstream
/usr/bin/git -C "$tmp/dv-other" push -q origin main 2>/dev/null
/usr/bin/git -C "$tmp/dv" fetch -q origin
out="$( cd "$tmp/dv" && bash "$root/scripts/main-refresh.sh" park 2>&1; echo "exit=$?" )"
day="$(date -u +%Y-%m-%d)"
branch="wip/main-$day-1"
echo "$out" | sed 's/^/     | /'
case "$out" in *"PARKED 0 path(s) and 1 commit(s) on branch $branch"*) r=yes;; *) r=no;; esac
check "park names the branch in the PARKED line" yes "$r"
case "$out" in *"WARNING the 1 local-only commit(s) are now only on branch $branch"*"pull request"*) r=yes;; *) r=no;; esac
check "park says the commits are only on that branch and need a pull request" yes "$r"
case "$out" in *"MAIN_REFRESH_FIX: git -C "*"push -u origin $branch"*) r=yes;; *) r=no;; esac
check "park prints a push hint for the branch" yes "$r"
check "park still exits 0" "exit=0" "$(echo "$out" | tail -1)"
check "the local-only commit is reachable from the parked branch" "local-only" "$(/usr/bin/git -C "$tmp/dv" log -1 --format=%s "$branch")"
check "main equals origin/main after park" "$(/usr/bin/git -C "$tmp/dv" rev-parse origin/main)" "$(/usr/bin/git -C "$tmp/dv" rev-parse main)"

echo "== hook budget and docs"
plugin_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
t="$(python3 -I -c 'import json,sys;print(json.load(open(sys.argv[1]))["hooks"]["UserPromptSubmit"][0]["hooks"][0]["timeout"])' "$plugin_dir/hooks/hooks.json")"
if [[ "$t" -ge 120 ]]; then r=yes; else r=no; fi
check "hook timeout covers three passes of the repository's script (>= 120 s)" yes "$r"
if grep -q "well under a second" "$plugin_dir/hooks/hooks.json"; then r=stale; else r=ok; fi
check "hooks.json description no longer claims under a second" ok "$r"
if grep -q "^## When the repository ships its own script" "$plugin_dir/skills/main-refresh/SKILL.md"; then r=yes; else r=no; fi
check "SKILL.md has the repository-script section" yes "$r"

echo
echo "passed=$pass failed=$fail"
[[ "$fail" -eq 0 ]]
