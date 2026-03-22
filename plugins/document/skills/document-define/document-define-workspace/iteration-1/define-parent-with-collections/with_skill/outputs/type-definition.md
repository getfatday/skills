# Program

## Identity
- name: program
- display: Program
- description: A strategic program that hosts initiatives and epics as child collections

## Fields

### Required
- `type: string` — always "program"
- `name: string` — program name
- `status: enum(active, paused, completed)` — lifecycle stage
- `created: date` — creation date

### Optional
- `quarter: string` — target quarter (e.g., Q1 2026)

## Sections

### Required
- `## Overview` — program description, goals, and strategic context

### Optional
- `## Roadmap` — timeline and milestones

## Relationships
- linked-from: initiative via program — initiatives reference this program
- linked-from: epic via program — epics reference this program

## Collections
| Collection | Type | Key | Path |
|------------|------|-----|------|
| initiatives | initiative | name | ./initiatives/{name}.md |
| epics | epic | name | ./epics/{name}.md |

## Lifecycle
- status-field: status
- values: active, paused, completed
- transitions:
  - active -> paused — program temporarily halted
  - paused -> active — program resumed
  - active -> completed — all initiatives complete
  - paused -> completed — program closed while paused

## Creation
- mode: template
- template-sections: Overview (prompt user), Roadmap (leave empty)
