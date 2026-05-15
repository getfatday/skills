#!/usr/bin/env bash
# Generic parent-field inheritance helper.
#
# Reads a spawn-context marker (written by a PreToolUse hook) and prints
# YAML frontmatter fragments that the caller can splice into a newly
# created document's frontmatter, inheriting the named fields from the
# parent document. Also always emits `inferred: true` so the marker
# survives for later review via `/document:verify-inferred`.
#
# Exit 0 in all non-fatal cases. The script prints nothing (and exits 0)
# if the marker is missing or stale — the consuming skill treats that as
# "no parent context; create a root document".
#
# Inputs (flags):
#   --marker <path>              required — absolute or ~-relative path
#   --max-age <seconds>          optional — default 120
#   --portfolio <dir>            required — portfolio root (for parent
#                                  document lookup)
#   --parent-dir <relative>      required — directory under portfolio
#                                  containing parent documents
#   --inherit-fields <csv>       required — comma-separated field names
#   --self-type <string>         optional — sets `type:` on output (if
#                                  the child isn't already typed)
#   --parent-field <name>        optional — default `parent-{self-type}`
#
# Output: YAML lines on stdout, e.g.:
#   project: "[[Projects/Foo/index|Foo]]"
#   parent-session: "[[Sessions/2026-01-01_bar|bar]]"
#   inferred: true
#
# The marker file is consumed (deleted) on every invocation — stale or
# fresh.

set -euo pipefail

MARKER=""
MAX_AGE="120"
PORTFOLIO=""
PARENT_DIR=""
INHERIT_FIELDS=""
SELF_TYPE=""
PARENT_FIELD=""

while [ $# -gt 0 ]; do
  case "$1" in
    --marker) MARKER="$2"; shift 2 ;;
    --max-age) MAX_AGE="$2"; shift 2 ;;
    --portfolio) PORTFOLIO="$2"; shift 2 ;;
    --parent-dir) PARENT_DIR="$2"; shift 2 ;;
    --inherit-fields) INHERIT_FIELDS="$2"; shift 2 ;;
    --self-type) SELF_TYPE="$2"; shift 2 ;;
    --parent-field) PARENT_FIELD="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Expand ~ in marker path
MARKER="${MARKER/#\~/$HOME}"

# No marker? Nothing to inherit — exit quietly.
[ -z "$MARKER" ] && exit 0
[ ! -f "$MARKER" ] && exit 0

# Parse marker
parent=$(grep -E '^parent:' "$MARKER" 2>/dev/null | head -1 | awk '{print $2}' || true)
written_at=$(grep -E '^written_at:' "$MARKER" 2>/dev/null | head -1 | awk '{print $2}' || echo 0)
marker_max=$(grep -E '^max_age_seconds:' "$MARKER" 2>/dev/null | head -1 | awk '{print $2}' || echo "$MAX_AGE")

# Always consume the marker. Stale or fresh.
rm -f "$MARKER"

# Empty parent? Nothing to do.
[ -z "$parent" ] && exit 0

# Staleness
now=$(date +%s)
age=$(( now - written_at ))
[ "$age" -gt "$marker_max" ] && exit 0

# Validate required inputs for the lookup
[ -z "$PORTFOLIO" ] && exit 0
[ -z "$PARENT_DIR" ] && exit 0

# Find the parent document. Prefer a file containing the parent handle
# in the filename (e.g., `2026-01-01_foo-bar.md` matches `foo-bar`).
parent_file=""
search_dir="$PORTFOLIO/$PARENT_DIR"
if [ -d "$search_dir" ]; then
  parent_file=$(ls -1t "$search_dir" 2>/dev/null | grep -E "_${parent}\.md\$|/${parent}\.md\$|/${parent}/index\.md\$" | head -1 || true)
  if [ -n "$parent_file" ]; then
    parent_file="$search_dir/$parent_file"
  fi
  # Try other shapes
  if [ -z "$parent_file" ] && [ -f "$search_dir/$parent.md" ]; then
    parent_file="$search_dir/$parent.md"
  fi
  if [ -z "$parent_file" ] && [ -f "$search_dir/$parent/index.md" ]; then
    parent_file="$search_dir/$parent/index.md"
  fi
fi

# No parent file? Emit only the back-reference to preserve the link
# even if the parent doc is missing.
parent_link=""
if [ -n "$parent_file" ] && [ -f "$parent_file" ]; then
  rel=$(python3 -c "import os, sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))" "$parent_file" "$PORTFOLIO" 2>/dev/null || echo "$parent_file")
  rel_no_ext="${rel%.md}"
  parent_link="[[${rel_no_ext}|${parent}]]"
fi

# Effective parent-field name
if [ -z "$PARENT_FIELD" ] && [ -n "$SELF_TYPE" ]; then
  PARENT_FIELD="parent-${SELF_TYPE}"
fi

# Emit inherited fields
if [ -n "$parent_file" ] && [ -f "$parent_file" ] && [ -n "$INHERIT_FIELDS" ]; then
  IFS=',' read -ra FIELDS <<< "$INHERIT_FIELDS"
  for f in "${FIELDS[@]}"; do
    f=$(echo "$f" | tr -d ' ')
    [ -z "$f" ] && continue
    val=$(awk -v field="$f" '
      BEGIN { fm = 0 }
      /^---$/ { fm++; next }
      fm == 1 && $0 ~ "^" field ":" {
        sub("^" field ":[ \t]*", "");
        print;
        exit
      }
      fm == 2 { exit }
    ' "$parent_file" 2>/dev/null || true)
    if [ -n "$val" ]; then
      echo "$f: $val"
    fi
  done
fi

# Emit parent back-reference
if [ -n "$parent_link" ] && [ -n "$PARENT_FIELD" ]; then
  echo "$PARENT_FIELD: \"$parent_link\""
fi

# Mark as inferred so document-verify-inferred prompts later
echo "inferred: true"

exit 0
