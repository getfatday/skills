#!/usr/bin/env bash
# Determine version bump level from towncrier fragment types.
# Usage: bash scripts/bump-version.sh CLI_DIR
# Output: "minor" or "patch" to stdout
set -euo pipefail

CLI_DIR="${1:?Usage: $0 CLI_DIR}"
FRAGMENTS_DIR="$CLI_DIR/newsfragments"

if [ ! -d "$FRAGMENTS_DIR" ]; then
  echo "Error: $FRAGMENTS_DIR does not exist" >&2
  exit 1
fi

# Check for any non-.gitkeep files (actual fragments)
FRAGMENT_COUNT=$(find "$FRAGMENTS_DIR" -type f ! -name '.gitkeep' | wc -l | tr -d ' ')
if [ "$FRAGMENT_COUNT" -eq 0 ]; then
  echo "none"
  exit 0
fi

# Feature fragments -> minor bump, otherwise patch
if find "$FRAGMENTS_DIR" -type f -name '*.feature' | grep -q .; then
  echo "minor"
else
  echo "patch"
fi
