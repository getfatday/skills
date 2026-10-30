#!/bin/sh
# Fake `gh` for tests: `gh pr list ...` prints the canned JSON in $FAKE_GH_JSON; without it, exits 1 (like gh
# with no auth), so a test can never reach the real gh. Logs argv to $FAKE_GH_LOG.
[ -n "$FAKE_GH_LOG" ] && echo "$*" >> "$FAKE_GH_LOG"
[ -n "$FAKE_GH_JSON" ] || { echo "fake gh: no FAKE_GH_JSON" >&2; exit 1; }
printf '%s\n' "$FAKE_GH_JSON"
