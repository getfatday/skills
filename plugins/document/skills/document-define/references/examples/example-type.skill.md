# Changelog Entry — Custom Logic

## Operations

### publish
**Inputs:** changelog entry name or path.

**Steps:**

1. Read the entry. Confirm status is `reviewed`.
2. Append the entry's Summary to the project CHANGELOG.md under the current unreleased heading.
3. Update the entry frontmatter: set `status: published` and add `published: {today}`.
4. Report the updated CHANGELOG.md path.

**Output:** updated CHANGELOG.md path, updated entry path.

## Hooks

### pre-update-status
Before transitioning to `published`, verify the Summary section is non-empty. If empty, refuse with: "Cannot publish: Summary is empty."

### post-create
After writing a new changelog entry, append a row to `Changelog.md`'s `## Pending` table with the entry's title, kind, and status. Save the index.
