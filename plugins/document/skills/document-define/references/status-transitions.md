# Status Transitions via `{type}.skill.md` Sidecars

Status transitions run through `update-status`, a default operation
every generated type skill provides. Project-specific behavior —
additional guards, side effects, notifications — belongs in the
`{type}.skill.md` sidecar as `pre-update-status` and
`post-update-status` hooks. `document-define` regenerates the skill
on every run, so hooks written in the sidecar survive regeneration;
hooks written directly into the generated `SKILL.md` would be lost.

See `custom-logic-schema.md` for the full sidecar grammar. This
reference shows the common transition patterns.

## The Two Hooks That Matter for Lifecycle

Within `## Hooks` in a `{type}.skill.md`:

- **`### pre-update-status`** — content spliced in before the Steps
  list of `update-status`. Use it to enforce project-specific guards
  that block a transition unless preconditions hold.
- **`### post-update-status`** — content spliced in after the Steps
  list (before the Output line). Use it to trigger project-specific
  side effects once the status has flipped: send a summary prompt,
  update a parent document, notify a channel.

Multiple `pre-update-status` or `post-update-status` hooks concatenate
in file order. Use this to separate concerns (one hook for validation,
one for logging, etc.).

## Lifecycle-Hooks Table vs Sidecar Hooks

Two complementary mechanisms:

| Where declared | What it's for | Portability |
|----------------|---------------|-------------|
| `## Lifecycle Hooks` in `{type}.md` | Declarative per-transition guards, actions, notifications with wildcards and skill refs | Fully portable — ships with the type |
| `pre-update-status` / `post-update-status` in `{type}.skill.md` | Free-form, project-specific behavior | Vault-local — survives regeneration |

Prefer the `## Lifecycle Hooks` table when the rule is inherent to the
type (every PRD needs sections filled before review). Prefer the
sidecar when the rule is about *this project's tooling* (this vault
runs `workstream-summarizer` after a root session closes).

## Pattern 1: Block a Transition Without a Required Field

```markdown
## Hooks

### pre-update-status

If the target status is `approved`, verify that the document's
`approver` field is non-empty. If missing, refuse the transition
with: "Cannot approve: `approver` field is required."

If the target status is `shipped`, verify that the document's
`released-on` field is a valid ISO date. If missing, refuse with:
"Cannot ship: `released-on` field must be set to an ISO date."
```

Both rules are evaluated by Claude reading the frontmatter before
running the default transition steps. The refusal message is surfaced
to the user; no status change occurs.

## Pattern 2: Fan-Out Notifications After a Transition

```markdown
## Hooks

### post-update-status

If the old status was `active` and the new status is `completed`:

1. Read the document's `project:` wikilink.
2. Open the linked project hub.
3. Append a line to its `## Recent Activity` section:
   `- [[{doc}|{title}]] completed on {today}`
4. Save the project hub.
```

Post-hooks run after the status is already updated. Failures here
don't roll the transition back — surface them but leave the frontmatter
changed.

## Pattern 3: Summarize on Transition to Terminal State

```markdown
## Hooks

### post-update-status

If the new status is a terminal state (`completed`, `abandoned`,
`shipped`), and the document has a recent edit history (`## Outcomes`
or similar), generate a one-line summary by invoking
`workstream-summarizer summarize {name}` and write the result to a
`summary:` field in the frontmatter.
```

The hook is free-form markdown. It may reference other skills, but
unlike the `## Lifecycle Hooks` table there's no structured grammar
— it's instructions Claude follows when executing the splice.

## Pattern 4: Wildcard Exit Traps

```markdown
## Hooks

### pre-update-status

Regardless of target status, if the transition is to a terminal state
(`abandoned`, `archived`) AND the `workstream-next-action` field is
empty, refuse with: "Populate `workstream-next-action` before
transitioning to a terminal state — future-you will thank you."
```

Wildcard-style policy belongs here rather than in the type-definition
table, which prefers explicit transitions. Project conventions (like
"always record the next step before abandoning") live in the sidecar.

## Merge Order and Precedence

When a type has BOTH `## Lifecycle Hooks` in its type definition AND
`pre-update-status` / `post-update-status` in its sidecar:

1. Type-definition guards run first (structured, declarative).
2. Sidecar pre-hook runs next (free-form, project-specific).
3. Default Steps list runs (validates and updates the status field).
4. Type-definition actions run after the status change.
5. Sidecar post-hook runs last.
6. Notifications fire last, always.

Any guard failure in steps 1 or 2 aborts the transition and leaves
the file unchanged.

## Block-Direct-Edit Advisory

The plugin ships `hooks/check-status-edit.sh` — a PreToolUse hook that
blocks direct frontmatter edits to `status:`. When it fires, the
advisory message now points users here: "declare project-specific
behavior in `{type}.skill.md` under `pre-update-status` or
`post-update-status`". That keeps users on the sanctioned path.

## Related Reading

- `custom-logic-schema.md` — the complete sidecar grammar
- `type-definition-schema.md` — the declarative `## Lifecycle Hooks`
  table (portable)
- `inheritance.md` — inheritance hooks (`post-create`) for parent-field
  propagation
