#!/bin/sh
# Fake `claude` for tests: logs argv to $FAKE_CLAUDE_LOG and answers from the environment.
#   agents --json [--all]  cat $FAKE_AGENTS_JSON (else []); $FAKE_AGENTS_SLEEP hangs, $FAKE_AGENTS_FAIL exits 1
#   --bg --resume <sid>    prints "started a copy as ${FAKE_BG_ID:-1be4ed48}" (the 2.1.312 wording)
#   stop / rm              exit 0
[ -n "$FAKE_CLAUDE_LOG" ] && echo "$*" >> "$FAKE_CLAUDE_LOG"
case "$1" in
  agents)
    [ -n "$FAKE_AGENTS_SLEEP" ] && exec sleep "$FAKE_AGENTS_SLEEP"  # a hung daemon: never answers
    [ -n "$FAKE_AGENTS_FAIL" ] && { echo "agents: daemon not reachable" >&2; exit 1; }
    if [ -n "$FAKE_AGENTS_JSON" ]; then cat "$FAKE_AGENTS_JSON"; else echo '[]'; fi
    exit 0;;
  --bg)
    echo "started a copy as ${FAKE_BG_ID:-1be4ed48}"
    exit 0;;
esac
exit 0
