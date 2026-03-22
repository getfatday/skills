# Team Charter

## Identity
- name: team-charter
- display: Team Charter
- description: A team charter defining mission, scope, and membership

## Fields

### Required
- `type: string` — always "team-charter"
- `name: string` — team name
- `mission: string` — team mission statement
- `created: date` — creation date

### Optional
- `status: enum(draft, active, archived)` — charter lifecycle stage

## Sections

### Required
- `## Mission` — detailed mission statement and purpose
- `## Scope` — team responsibilities and boundaries

### Optional
- `## Team` — team members and roles

## Relationships

(none)

## Lifecycle
- status-field: status
- values: draft, active, archived
- transitions:
  - draft -> active — charter is ratified by the team
  - active -> archived — team is disbanded or charter superseded

## Creation
- mode: template
- template-sections: Mission (prompt user), Scope (prompt user), Team (leave empty)
