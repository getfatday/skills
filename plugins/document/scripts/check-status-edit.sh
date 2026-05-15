#!/usr/bin/env bash
# Safety net: block direct edits to a document's status field and
# redirect to the update-status operation where guards and actions run.
#
# PreToolUse:Edit hook — receives the tool input as JSON on stdin.
# If the edit changes a "status:" frontmatter field in a managed
# document, exits with code 2 (block) and writes a reason to stderr.
# Claude sees the stderr message and can retry via update-status.
#
# No external dependencies — uses grep/sed instead of jq so this
# works on any system with a POSIX shell.

set -euo pipefail

INPUT=$(cat)

# Extract file_path from JSON using grep/sed (avoids jq dependency).
# Matches: "file_path": "/some/path.md"
FILE_PATH=$(echo "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"//;s/"$//' || true)

# Quick exit if no file path or not a markdown file
[[ -z "$FILE_PATH" || "$FILE_PATH" != *.md ]] && exit 0

# Check if this file looks like a managed document (has type: in frontmatter)
head -20 "$FILE_PATH" 2>/dev/null | grep -q '^type:' || exit 0

# Check if old_string and new_string both contain a status: field change.
# We check the raw JSON since the field values are inline strings.
# Match "old_string" value containing "status:" at start of a line.
OLD_HAS_STATUS=$(echo "$INPUT" | grep -o '"old_string"[[:space:]]*:[[:space:]]*"[^"]*"' | grep -c 'status:' || true)
NEW_HAS_STATUS=$(echo "$INPUT" | grep -o '"new_string"[[:space:]]*:[[:space:]]*"[^"]*"' | grep -c 'status:' || true)

if [[ "$OLD_HAS_STATUS" -gt 0 && "$NEW_HAS_STATUS" -gt 0 ]]; then
  echo "Direct \`status:\` edits are blocked — use the update-status operation so lifecycle guards + actions run. Example: /{type} status {name} {new-status}. To add project-specific behavior to a transition, declare pre-update-status / post-update-status hooks in \`.config/documents/types/{type}.skill.md\` under \`## Hooks\`. See references/status-transitions.md and references/custom-logic-schema.md for the sidecar grammar." >&2
  exit 2
fi
