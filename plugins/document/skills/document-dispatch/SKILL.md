---
name: document-dispatch
tier: 1-plugin
description: >
  Routes events to subscribed document types. When a typed document is
  created, updated, links to another doc, mentions an entity, or
  changes lifecycle state, dispatch resolves which types subscribed to
  that event (declared in their sidecar's `## Subscriptions` table),
  evaluates each subscription's condition against the event payload,
  applies caps from `.config/documents/root.md` (max-fanout, max-depth,
  max-stubs), writes a JSON-line trace to `.cache/document-dispatch.log`,
  and returns the resolved (type, handler) list. Trigger when the user
  wants to fan out an event across subscribed types, inspect the
  current subscription map, replay a recorded trace for testing, or any
  ingest-orchestration task that names "dispatch", "subscriptions",
  "fanout", "event routing", or "/document:dispatch". The plugin is
  mechanism only — it does NOT emit events itself; consumers wire
  emission from /capture commands, SessionEnd hooks, or manual calls.
materialized: "2026-05-02"
user-invocable: true
trigger-phrases:
  - "dispatch event"
  - "document dispatch"
  - "fan out event"
  - "list subscriptions"
  - "replay trace"
  - "document-dispatch"
allowed-tools: [Read, Bash, Glob, Grep]
---

# document-dispatch

<objective>
Resolve which type subscriptions match an event, apply caps, write a
trace, and return the resolved invocation list. The dispatcher is
mechanism only — it never emits events of its own. Consumers (a
`/capture` command, a SessionEnd hook, or any manual integration) call
`emit` with an event name and payload; dispatch handles the routing.

The backbone is `scripts/dispatch.py`. Subscriptions are declared by
each type in its sidecar `.config/documents/types/{name}.skill.md` under
`## Subscriptions`. Events and payload shapes are documented in
`references/event-schema.md` (5 reserved names; closed grammar).
</objective>

## When to Run

- A consumer hook or command needs to emit an event after creating,
  updating, linking, mentioning, or transitioning a typed document.
- The user wants to inspect the subscription graph (which types listen
  to which events).
- A recorded trace log needs to be replayed for testing or
  reproduction.

## How the Backbone Works

The skill wraps `scripts/dispatch.py`. Runtime inputs:

- **Portfolio root** — resolved by walking up from CWD until
  `.config/documents/root.md` is found, or passed via `--portfolio`.
- **Event name** — one of the reserved names listed in
  `references/event-schema.md`; unknown events fail loudly.
- **Payload** — JSON object whose required fields are documented per
  event in `references/event-schema.md`. Missing required fields fail
  before any handler runs.
- **Caps** — read from `.config/documents/root.md` `## Configuration`:
  `max-fanout` (default 12), `max-depth` (default 1), `max-stubs`
  (default 5). Cap-hits are recorded in the trace.

For each subscription that matches the event, dispatch:

1. Compiles and evaluates the condition expression against the payload.
   Conditions follow a tiny closed grammar (see `event-schema.md`).
2. Selects matching subscriptions in stable order (sorted by event,
   type name, handler) so dispatch is deterministic regardless of
   filesystem walk order.
3. Caps the fanout at `max-fanout`. If exceeded, drops the tail and
   records `cap-hit: max-fanout` in the trace.
4. Looks for a backing handler script at
   `.claude/skills/{type}/handlers/{handler}` (with `.sh`, `.py`, or no
   extension; must be executable). If found, runs it with the payload
   JSON on stdin; exit 0 is success, non-zero is logged and the
   cascade continues. If no backing script exists, the handler is
   recorded as `deferred` — the consumer (Claude in a session) is
   expected to invoke the matching operation on the per-type generated
   skill manually.
5. Appends one JSON line to `.cache/document-dispatch.log`. The
   `.cache/` directory is created on first write; consumers add it to
   `.gitignore` by convention.

## Cap Discipline

- **`max-fanout`** — limits how many handlers run for a single emit.
  Prevents one event from accidentally fanning out to dozens of types.
- **`max-depth`** — limits cascade depth. When a handler emits another
  event (by re-invoking dispatch with `--depth N+1`), depth is
  incremented. At `depth > max-depth`, dispatch refuses with
  `cap-hit: max-depth`. This is the only termination guarantee for
  handler-emits-event cycles.
- **`max-stubs`** — reserved for handler-driven stub creation; tracked
  per-invocation (not per-session). Consumers that auto-create stub
  pages from handlers should consult the cap.

## Operations

<emit_operation>
**Inputs:** event name, payload (JSON object), optional portfolio root,
optional depth.

**Steps:**

1. Validate the event is a reserved name; abort cleanly if not.
2. Validate the payload contains the required fields for the event.
3. Discover all subscriptions across `.config/documents/types/*.skill.md`.
4. Filter to subscriptions for this event; evaluate each condition
   against the payload.
5. Apply `max-fanout` cap; record cap-hits.
6. For each selected subscription, invoke the backing handler script
   if present, else record as `deferred`.
7. Append one JSON line to `.cache/document-dispatch.log` with
   timestamp, event, payload, handlers list, and caps record.
8. Print resolved selection (selected, skipped, handlers) as JSON.

**CLI:**
```bash
python3 scripts/dispatch.py emit \
  --event entity-mentioned \
  --payload '{"entity-path":"Foo.md","in-doc-path":"Bar.md"}' \
  --portfolio /path/to/portfolio
```

**Output:** JSON object on stdout describing the dispatch; one line
appended to `.cache/document-dispatch.log`.
</emit_operation>

<subscriptions_operation>
**Inputs:** optional portfolio root.

**Steps:**

1. Walk `.config/documents/types/*.skill.md`.
2. Parse each sidecar's `## Subscriptions` table.
3. Print all subscriptions in stable order (event, type, handler).

**CLI:**
```bash
python3 scripts/dispatch.py subscriptions --portfolio /path/to/portfolio
```

**Output:** A table listing `type`, `event`, `handler`, `condition` for
every subscription in the portfolio. Useful for auditing the dispatch
graph and confirming a sidecar change took effect.
</subscriptions_operation>

<replay_operation>
**Inputs:** path to a trace log file, optional portfolio root.

**Steps:**

1. Read the trace file line by line.
2. For each line, parse the JSON record and re-emit the event with the
   recorded payload at depth 0.
3. Print one section per replayed event.

**CLI:**
```bash
python3 scripts/dispatch.py replay \
  --trace /path/to/.cache/document-dispatch.log \
  --portfolio /path/to/portfolio
```

**Output:** Per-event dispatch results, identical in shape to `emit`.
Replay does NOT clear the original trace; it appends new entries.
</replay_operation>

## Error Cases

- **Unknown event** — `emit --event unknown-thing` fails with a clear
  message listing the reserved events. No trace line is written.
- **Missing payload field** — `emit` for an event whose payload lacks a
  required field fails before any handler runs. No trace line is
  written.
- **Bad condition syntax** — sidecar parsing fails at `discover` time
  with the file path, line number, and the unrecognized expression.
  Aborts the dispatch.
- **No subscribers** — `emit` for an event with zero matching
  subscribers writes a trace line with empty `handlers` and exits 0.
- **Backing script timeout** — a handler script that doesn't return
  within 30 seconds is recorded with `status: timeout` and the cascade
  continues.
- **Backing script non-zero exit** — recorded with `status: invoked`
  and the actual `exit` code; cascade continues.

## Dependencies

reads_from:
  - .config/documents/root.md (caps from ## Configuration)
  - .config/documents/types/*.skill.md (subscriptions)
  - .claude/skills/{type}/handlers/* (optional backing handler scripts)
writes_to:
  - .cache/document-dispatch.log (append-only JSON-lines trace)
consumed_by:
  - Generated per-type skills' handler operations (when stdout is
    piped back into a Claude session that runs the named operation)

## Skill Boundaries

| Concern | Owner |
|---------|-------|
| Subscription declaration format | sidecar (`## Subscriptions`), parsed here |
| Reserved event names + payload contracts | `references/event-schema.md` |
| Condition grammar | `references/event-schema.md` |
| Handler operation generation (stubs) | **document-define** (splice rules) |
| Event emission triggers (when to call emit) | **consumer** (commands, hooks) |
| Routing, cap enforcement, trace logging | **document-dispatch** (this skill) |
