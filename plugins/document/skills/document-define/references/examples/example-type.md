# Changelog Entry

## Identity
- name: changelog-entry
- display: Changelog Entry
- description: Individual changelog entry tracking a single user-facing change.

## Fields
- type (required): literal "changelog-entry"
- title (required): short title for the change
- status (required): enum [draft, reviewed, published]
- created (required): date, stamped on creation
- kind (optional): enum [added, changed, fixed, deprecated, removed, security]

## Sections
- Summary (required): one-paragraph user-facing description of the change
- Details (optional): implementation notes, migration steps, links

## Lifecycle
- Statuses: draft, reviewed, published
- Allowed transitions:
  - draft -> reviewed
  - reviewed -> published
  - reviewed -> draft

## Creation
- mode: template
