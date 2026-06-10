# Event Schema

Reserved event names that `document-dispatch` knows how to route. A type's
sidecar declares which of these events it cares about under `## Subscriptions`.
Dispatch resolves subscriptions, invokes the named handler operation on each
subscribed type's generated skill, and writes a trace line for every event.

The plugin is mechanism only. It does NOT emit these events itself. Consumers
wire emission from wherever they want — a `/capture` command, a SessionEnd
hook, a manual `dispatch.py emit` call.

## Reserved Event Names

| event              | payload                                          | when emitted                                     |
|--------------------|--------------------------------------------------|--------------------------------------------------|
| `document-created` | `{path, type}`                                   | a typed document is created                      |
| `document-updated` | `{path, type, changed-fields}`                   | frontmatter or body changes after creation       |
| `link-created`     | `{from, to, field}`                              | a new wikilink appears in a relationship field   |
| `entity-mentioned` | `{entity-path, in-doc-path}`                     | an entity's display name appears in another doc's body |
| `lifecycle-changed`| `{path, type, from-status, to-status}`           | status transition succeeds                       |

Payload fields are case-sensitive. Dispatch reads payloads as JSON. Unknown
fields in a payload are passed through to the handler unchanged. Missing
required fields fail the dispatch with a clear error before any handler runs.

### Payload field reference

- `path` — portfolio-relative path to a typed document, e.g. `Notes/Foo.md`
- `type` — the document's `type:` frontmatter value, e.g. `note`
- `changed-fields` — array of frontmatter or section names that changed
- `from`, `to` — portfolio-relative paths (link source and link target)
- `field` — the relationship field carrying the new link, e.g. `links-to`
- `entity-path` — portfolio-relative path to the entity whose display name was mentioned
- `in-doc-path` — portfolio-relative path to the doc that mentioned the entity
- `from-status`, `to-status` — lifecycle status values, e.g. `draft`, `final`

Custom event names are NOT supported in v1. Dispatch rejects emit calls for
unknown events with `error: unknown event '{name}'. Known events: {list}.`

## Subscription Format (sidecar `## Subscriptions`)

A type opts in to receive events by listing them in its sidecar at
`.config/documents/types/{name}.skill.md` under `## Subscriptions`.

```markdown
## Subscriptions

| event             | handler         | condition                              |
|-------------------|-----------------|----------------------------------------|
| document-created  | on-source       | source-type in {web, slack, pdf}       |
| entity-mentioned  | hot-memory      | always                                 |
| link-created      | back-reference  | always                                 |
```

Columns:

- **event** — must be one of the reserved event names above.
- **handler** — names an operation on the type's generated skill. Handlers can
  be (a) a default operation (`store`, `create`, `get`, `list`, `validate`,
  `update-status`, `split`, `merge`), (b) a custom operation declared in the
  same sidecar's `## Operations` section, or (c) a new handler name — in which
  case `document-define generate` scaffolds a stub `<{handler}_operation>`
  block with `# TODO: implement {handler}` for the user to fill in.
- **condition** — a boolean expression evaluated against the event payload at
  dispatch time. The handler runs only when the condition is true.

## Condition Grammar

The grammar is intentionally tiny and closed. Unknown grammar fails loudly at
generation time (in `document-define`) AND at dispatch time (in
`dispatch.py`). It is not a Turing-complete DSL.

```
condition := "always"
           | comparison
           | membership

comparison := <field> <op> <literal>
op         := "==" | "!="
literal    := quoted-string | bare-word | number

membership := <field> "in" "{" <literal> ("," <literal>)* "}"

field      := one of the payload fields documented above
            | a frontmatter field of the document referenced by `path`
              (only valid for events that carry `path`)
```

Examples:

- `always` — handler always runs
- `from-status == "draft"` — only when transitioning out of draft
- `source-type in {web, slack, pdf}` — only for these source types
- `type != "entity"` — every type except entity
- `field == links-to` — only when the link is in the `links-to` field

Bare words are treated as strings (no quoting required for simple identifiers).
Sets use `{a, b, c}` syntax. There is no `and`, `or`, `not`, or parentheses.
A condition is one expression. Anything else is rejected with a clear error.

## Trace Log

Every dispatch invocation appends one JSON line to
`.cache/document-dispatch.log` at the portfolio root. The directory is created
on first write. Consumers add `.cache/` to `.gitignore` by convention; the
plugin does not enforce this.

```json
{"ts":"2026-05-02T20:30:00","event":"document-created","payload":{"path":"Notes/Foo.md","type":"note"},"handlers":["entity:on-source"],"caps":{}}
{"ts":"2026-05-02T20:30:01","event":"entity-mentioned","payload":{...},"handlers":["entity:log-mention","memory:hot-memory"],"caps":{"max-fanout":1,"hit":"max-fanout"}}
```

Fields:

- `ts` — ISO-8601 timestamp (seconds precision, local time)
- `event` — the event name
- `payload` — the input payload, verbatim
- `handlers` — list of `{type}:{handler}` tuples that were invoked
- `caps` — record of caps in effect for this dispatch and which one was hit
  (`hit: max-fanout` means dispatch stopped early because fanout was capped)

`replay --trace {file}` re-fires the events from a trace log in order. Use it
to reproduce dispatch sequences in fixtures and tests.
