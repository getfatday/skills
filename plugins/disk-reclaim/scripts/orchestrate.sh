#!/usr/bin/env bash
# One transcript-less disk-reclaim orchestrator firing. Asks live owners, records the dead, gates every row in
# DRY RUN, writes ~/.claude/disk-reclaim/decision-card.md. Deletes nothing; a human (or the skill, on a recorded
# decision) runs the executor afterwards. Safe to run from a launchd timer.
# Usage: orchestrate.sh [--state-dir DIR] [--mode live-roster|all-dead] [--token-env FILE]
set -u
STATE="${DISK_RECLAIM_DIR:-$HOME/.claude/disk-reclaim}"; MODE=live-roster; TOKEN_ENV="$HOME/.claude/.crux-oauth-token.env"
while [ $# -gt 0 ]; do case "$1" in --state-dir) STATE=$2; shift 2;; --mode) MODE=$2; shift 2;; --token-env) TOKEN_ENV=$2; shift 2;; *) shift;; esac; done
HERE=$(cd "$(dirname "$0")" && pwd)
NOW=$(date -u +%FT%TZ)
PROMPT=$(sed -e "s#{{STATE_DIR}}#$STATE#g" -e "s#{{SCRIPTS}}#$HERE#g" -e "s#{{NOW}}#$NOW#g" -e "s#{{MODE}}#$MODE#g" "$HERE/orchestrator-prompt.md")
[ -f "$TOKEN_ENV" ] && source "$TOKEN_ENV"
mkdir -p "$STATE"
claude -p "$PROMPT" --max-turns 40 --max-budget-usd 1.50 --permission-mode auto --output-format text 2>>"$STATE/orchestrator.err" | tee -a "$STATE/orchestrator.log"
