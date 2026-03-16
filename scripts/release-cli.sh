#!/usr/bin/env bash
# Full release orchestration for a single CLI.
# Usage: bash scripts/release-cli.sh CLI_DIR
set -euo pipefail

CLI_DIR="${1:?Usage: $0 CLI_DIR}"
CLI_NAME=$(basename "$CLI_DIR")  # e.g., "monarch-cli"

# Step 1: Determine bump level from fragment types
BUMP=$(bash scripts/bump-version.sh "$CLI_DIR")
if [ "$BUMP" = "none" ]; then
  echo "No news fragments found in $CLI_DIR/newsfragments/ — skipping release."
  exit 0
fi
echo "Bump level: $BUMP"

# Step 2: Bump version in pyproject.toml
cd "$CLI_DIR"
uv run bump-my-version bump "$BUMP"
NEW_VERSION=$(uv run bump-my-version show current_version)
echo "New version: $NEW_VERSION"
cd - > /dev/null

# Step 3: Generate changelog with towncrier
uv run towncrier build --dir "$CLI_DIR" --version "$NEW_VERSION" --yes

# Step 4: Build wheel and sdist
uv build --package "gfd-${CLI_NAME}"

# Step 5: Git commit, tag
git add "$CLI_DIR/"
git commit -m "release: ${CLI_NAME} v${NEW_VERSION}"
git tag "${CLI_NAME}-v${NEW_VERSION}"

echo "Release prepared: ${CLI_NAME} v${NEW_VERSION}"
echo "Tag: ${CLI_NAME}-v${NEW_VERSION}"
echo "Artifacts in dist/"
