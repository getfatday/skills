#!/usr/bin/env bash
# PostToolUse:Write hook — after a markdown file is written in the portfolio
# tree, check for the most common lint issues and warn Claude so it can
# self-correct before the user has to ask.
#
# Checks:
# 1. Typed document missing required sections (type drift signal)
# 2. People-reference fields with plain-text names (unlinked people)
# 3. File not referenced from the nearest index.md (orphan risk)
#
# Exits 0 always (advisory, never blocks). Warnings go to stderr so
# Claude sees them in the tool output.

set -euo pipefail

INPUT=$(cat)

# Extract file_path from JSON
FILE_PATH=$(echo "$INPUT" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"//;s/"$//' || true)

# Quick exits
[[ -z "$FILE_PATH" || "$FILE_PATH" != *.md ]] && exit 0
[[ ! -f "$FILE_PATH" ]] && exit 0

# Only check files inside a portfolio with a document system
REPO_ROOT=$(git -C "$(dirname "$FILE_PATH")" rev-parse --show-toplevel 2>/dev/null || true)
[[ -z "$REPO_ROOT" ]] && exit 0
[[ ! -d "$REPO_ROOT/.config/documents/types" ]] && exit 0

# Skip infrastructure files
case "$FILE_PATH" in
  */.config/* | */.claude/* | */.githooks/* | */scripts/* | */docs/* | */CLAUDE.md | */CODEOWNERS)
    exit 0 ;;
esac

# Read file frontmatter
FRONTMATTER=$(sed -n '/^---$/,/^---$/p' "$FILE_PATH" 2>/dev/null || true)
[[ -z "$FRONTMATTER" ]] && exit 0

# Get type field
DOC_TYPE=$(echo "$FRONTMATTER" | grep '^type:' | head -1 | sed 's/type:[[:space:]]*//' || true)
[[ -z "$DOC_TYPE" ]] && exit 0

WARNINGS=""

# --- Check 1: Missing required sections ---
TYPE_DEF="$REPO_ROOT/.config/documents/types/$DOC_TYPE.md"
if [[ -f "$TYPE_DEF" ]]; then
  # Extract required section names from type definition
  IN_REQUIRED=false
  while IFS= read -r line; do
    if [[ "$line" == "### Required" ]]; then
      IN_REQUIRED=true
      continue
    fi
    if [[ "$line" == "### Optional" || "$line" == "##"* ]]; then
      IN_REQUIRED=false
      continue
    fi
    if $IN_REQUIRED && [[ "$line" == "- \`## "* ]]; then
      SECTION=$(echo "$line" | sed 's/- `## //;s/`.*//')
      if ! grep -q "^## $SECTION" "$FILE_PATH" 2>/dev/null; then
        WARNINGS="${WARNINGS}[document-lint] Missing required section '## ${SECTION}' for type '${DOC_TYPE}'. "
      fi
    fi
  done < <(sed -n '/^## Sections$/,/^## [^S]/p' "$TYPE_DEF")
fi

# --- Check 2: Unlinked people references ---
PEOPLE_FIELDS="author lead owner assignee deciders engineering_leader"
for FIELD in $PEOPLE_FIELDS; do
  VALUE=$(echo "$FRONTMATTER" | grep "^${FIELD}:" | head -1 | sed "s/${FIELD}:[[:space:]]*//" || true)
  if [[ -n "$VALUE" && "$VALUE" != *"["* ]]; then
    WARNINGS="${WARNINGS}[document-lint] Field '${FIELD}' has unlinked plain-text value '${VALUE}'. Use markdown link syntax to link to a People file. "
  fi
done

# --- Check 3: Orphan risk ---
DIR=$(dirname "$FILE_PATH")
BASENAME=$(basename "$FILE_PATH")
if [[ "$BASENAME" != "index.md" && -f "$DIR/index.md" ]]; then
  if ! grep -q "$BASENAME" "$DIR/index.md" 2>/dev/null; then
    WARNINGS="${WARNINGS}[document-lint] This file is not referenced from $(dirname "$FILE_PATH")/index.md — it may be orphaned. Add it to the index. "
  fi
elif [[ "$BASENAME" != "index.md" && ! -f "$DIR/index.md" ]]; then
  WARNINGS="${WARNINGS}[document-lint] No index.md exists in $(dirname "$FILE_PATH") — documents here may be undiscoverable. "
fi

# Emit warnings
if [[ -n "$WARNINGS" ]]; then
  echo "$WARNINGS" >&2
fi

exit 0
