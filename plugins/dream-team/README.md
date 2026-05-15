# dream-team

Avatar framework and marketplace — create, install, recruit, and orchestrate AI expert agents. Build a team of "avatars" (Kent Beck, Marty Cagan, Don Norman, …) and consult them on real questions using composable conversation patterns (map-reduce, debate, reflection, voting, blackboard, …).

## When to use

- "Get me a product + engineering review of this design"
- "Have Kent Beck and Robert Martin debate this refactor"
- "Run a discovery review on this feature spec"
- "Recruit an expert in observability"
- "Create a new avatar from Teresa Torres' work"

The plugin handles team assembly, pattern selection, and synthesis. You bring the question.

## Components

### Commands

| Command | Purpose |
|---------|---------|
| `/consult` | Multi-avatar consult on a question (assembles a team, picks a pattern, synthesizes) |
| `/review` | Have a team review a doc, design, or PR |
| `/plan` | Have a team plan an initiative |
| `/coach` | One-on-one coaching from a single avatar |

### Skills

| Skill | Purpose |
|-------|---------|
| `assemble` | Assemble a team for a domain or question |
| `consult` | Run a multi-avatar consultation with checkpoints |
| `avatar-create` | Three-stage pipeline to create a new avatar from an expert |
| `avatar-install` | Install an avatar from a vault or path |
| `avatar-publish` | Publish an avatar to the marketplace |
| `avatar-recruit` | Discover candidate experts to fill a gap on the team |

### Agents

| Agent | Purpose |
|-------|---------|
| `orchestrator` | Team lead — coordinates discussion, synthesizes, delivers recommendations |

### Bundled avatars

19 avatars ship in `avatars/`, including Kent Beck, Robert C. Martin, Eric Evans, Martin Fowler, Lisa Crispin, Gene Kim, Boris Cherny, Peter Steinberger, Marty Cagan, Teresa Torres, Eric Ries, Don Norman, Daniele Procida, Andy Grove, Will Larson, Eliyahu Goldratt, Nir Eyal, Antonio Nieto-Rodriguez, Joshua Teter. Bundled teams: `team-engineering`, `team-product`.

### Conversation patterns

`patterns/` provides 12 composable patterns the consult skill can dispatch:

`blackboard`, `debate`, `hierarchical`, `map-reduce`, `moe-routing`, `primitives`, `reflection`, `round-robin`, `router`, `sequential`, `supervisor`, `voting`.

### Schema, templates, examples

- `schema/AVATAR.md`, `schema/TEAM.md` — structural conventions for avatars and teams
- `templates/avatar-plugin/`, `templates/analysis.md`, `templates/research-note.md` — scaffolding starters
- `examples/avatar-example/` — a worked example walking through the pattern
- `marketplace.json` — registry of avatars and teams that ship with the plugin

## Setup

No external CLI required — the plugin is self-contained. Avatars are activated by installing the plugin into Claude Code; the orchestrator agent and skills route between them.

## Lineage

This plugin is kept in sync with the upstream `xp-skills` reference implementation. See `marketplace.json` for the canonical list of avatars and teams.
