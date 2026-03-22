# Team Charter

## Identity
- name: team-charter
- display: Team Charter
- description: A charter document defining a team's mission and scope

## Fields

### Required
- `type: string` — always "team-charter"
- `name: string` — team name
- `mission: string` — team mission statement
- `created: date` — creation date

### Optional
- `status: enum(draft, active, archived)` — document status

## Sections

### Required
- `## Mission` — detailed mission statement and purpose
- `## Scope` — boundaries and responsibilities of the team

### Optional
- `## Team` — team members and roles

## Creation
- mode: template
- template-sections: Mission (prompt user), Scope (prompt user), Team (leave empty)
