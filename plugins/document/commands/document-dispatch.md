---
name: document:dispatch
description: Route an event to subscribed document types and apply caps
argument-hint: "<emit|subscriptions|replay> [--event <name>] [--payload <json>] [--trace <file>] [--depth N]"
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
---

<objective>
Resolve which subscribed types should receive an event, evaluate
condition expressions against the payload, apply caps from
`.config/documents/root.md`, append a trace line to
`.cache/document-dispatch.log`, and return the resolved invocation list.

Mechanism only — this command does NOT emit events on its own.
Consumers (commands, hooks, manual integrations) decide when to emit.
</objective>

<context>
Arguments: $ARGUMENTS
</context>

<workflow>
Route to `skills/document-dispatch/SKILL.md`:

- `/document:dispatch emit --event <name> --payload <json>` → `emit`
  operation (resolve subscribers, apply caps, write trace, invoke
  backing handler scripts when present)
- `/document:dispatch emit --event <name> --payload <json> --depth N`
  → same, with cascade depth N (used when a handler re-emits)
- `/document:dispatch subscriptions` → `subscriptions` operation
  (list every (type, event, handler, condition) tuple in the portfolio)
- `/document:dispatch replay --trace <file>` → `replay` operation
  (re-fire events from a recorded trace log in order)

Reserved events: `document-created`, `document-updated`,
`link-created`, `entity-mentioned`, `lifecycle-changed`. Payload
contracts and condition grammar live in
`skills/document-dispatch/references/event-schema.md`.

The skill resolves the portfolio root by walking up from CWD until
`.config/documents/root.md` is found, or honors an explicit
`--portfolio <path>`.
</workflow>
