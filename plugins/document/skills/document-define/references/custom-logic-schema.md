# Custom Logic Sidecar Schema

A sidecar file lets a document type extend the skill that `document-define` generates. It can declare extra operations, add inline pre/post hooks to the eight default operations, and subscribe to dispatched events. `document-define` always regenerates the skill from the sidecar. Users edit the sidecar, never the generated `SKILL.md`.

## File Location and Discovery

- Path: `.config/documents/types/{name}.skill.md`
- Discovery: during `generate` and `regenerate`, after reading `.config/documents/types/{name}.md`, the skill checks for a sibling file with the `.skill.md` suffix.
- If the sidecar exists: parse it and splice its contents into the generated skill.
- If it does not exist: generate the default skill unchanged. This is not an error.
- One sidecar per type. The sidecar shares the base name of its type definition.

## File Structure

The sidecar is plain markdown. Three H2 sections are recognized: `## Operations`, `## Hooks`, and `## Subscriptions`. All are optional individually, but the file must contain at least one of them to be meaningful.

```markdown
# {Display Name} — Custom Logic

## Operations
### {extra-op-name}
{operation body in the style of the default operations: Inputs, Steps, Output}

## Hooks
### pre-{op-name}
{markdown guidance to run before the target op's Steps list}

### post-{op-name}
{markdown guidance to run after the target op's Steps list}

## Subscriptions
| event             | handler         | condition                              |
|-------------------|-----------------|----------------------------------------|
| document-created  | on-source       | source-type in {web, slack, pdf}       |
| entity-mentioned  | hot-memory      | always                                 |
```

Rules:

- Top-level H1 is optional and ignored by the splicer. It exists for humans.
- `## Operations` may contain zero or more H3 items. Each H3 is an operation name.
- `## Hooks` may contain zero or more H3 items. Each H3 is a hook name following the `pre-{op}` or `post-{op}` grammar.
- `## Subscriptions` is a single markdown table — header row, divider row, then one row per subscription. Columns: `event`, `handler`, `condition`.
- Any H2 other than `## Operations`, `## Hooks`, or `## Subscriptions` is ignored with a warning.
- Content under an H2 that is not inside an H3 (Operations / Hooks) or a table row (Subscriptions) is ignored.

## Allowed H3 Names

### Under `## Operations`

The H3 is the operation name. It must not collide with any default operation:

```
store, create, get, list, validate, update-status, split, merge
```

Extra op names should be kebab-case, match the spelling used in the generated command routes, and should not duplicate another H3 in the same sidecar.

### Under `## Hooks`

The H3 must match `pre-{op}` or `post-{op}` exactly. The `{op}` suffix must reference either:

- A default operation (`store`, `create`, `get`, `list`, `validate`, `update-status`, `split`, `merge`), OR
- A custom operation declared in the same sidecar's `## Operations` section.

Multiple hooks on the same operation are allowed. They are concatenated in file order (top to bottom). `pre` and `post` are independent: `pre-create` and `post-create` can both exist.

## Splice Rules

The splicer reads the sidecar and produces a single `SKILL.md` file. Splice happens during skill generation, never at runtime.

### Extra operations

- Each H3 under `## Operations` becomes a new `<{op-name}_operation>` block inside the generated `<operations>` section.
- The block is appended after the eight default operation blocks, in the order declared in the sidecar.
- The body of the H3 is copied verbatim into the new block.
- A new row is added to the generated command routes in `.claude/commands/{name}.md`: `/{name} {op-name} → {op-name} operation`.

### Hooks on existing operations

For each H3 under `## Hooks`:

1. Parse the H3 as `{position}-{target-op}` where `{position}` is `pre` or `post`.
2. Find the generated operation block for `{target-op}`.
3. Locate the `**Steps:**` list in that block. Every default and extra operation follows the Inputs / Steps / Output convention.
4. Splice:
   - `pre-{op}`: insert the hook body immediately before the Steps list, prefixed with a `**Pre-hook:**` label. If multiple `pre-{op}` hooks exist, concatenate in file order under one `**Pre-hook:**` label.
   - `post-{op}`: insert the hook body immediately after the Steps list and before the `**Output:**` line, prefixed with a `**Post-hook:**` label. If multiple `post-{op}` hooks exist, concatenate in file order under one `**Post-hook:**` label.
5. Hook bodies are copied verbatim. The splicer does not reformat markdown inside them.

### Subscriptions

`## Subscriptions` declares which dispatched events this type wants to receive and which handler operation to run when they fire. Recognized event names and the closed condition grammar are documented in `skills/document-dispatch/references/event-schema.md`.

For each row under `## Subscriptions`:

1. Validate the `event` column against the reserved event names (`document-created`, `document-updated`, `link-created`, `entity-mentioned`, `lifecycle-changed`). Unknown events abort generation with file path and row number.
2. Validate the `condition` column against the closed grammar. Parse failures abort generation with file path and row number, BEFORE any files are written. The grammar is `always` | `<field> <op> <literal>` | `<field> in {<lit>, ...}` where `<op>` is `==` or `!=`. No `and`, `or`, `not`, or parentheses.
3. Resolve the `handler` column against the union of (a) the eight default operations, (b) custom operations declared in the same sidecar's `## Operations`, and (c) handler names that don't yet exist anywhere — these become stub operations.
4. Splice into the generated SKILL.md:
   - **Handler precedence:** if the handler name already names a default op or a sidecar-declared extra op, the subscription reuses that op. No new block is generated; the splicer is a no-op for that operation block.
   - **Stub generation:** if the handler name is not a default op and not declared in `## Operations`, append a new `<{handler}_operation>` block to the generated SKILL.md, AFTER all default blocks AND after all sidecar-declared extra-op blocks. The body is `**Inputs:** event payload (JSON on stdin).`, then `**Steps:**` with one item `1. # TODO: implement {handler} — payload schema documented in references/event-schema.md.`, then `**Output:** describe the side effect.`. The user fills in the body. Stub generation never overwrites existing content because the generated SKILL.md is rewritten in full each `generate`/`regenerate`.
   - **`<subscriptions>` block:** append a `<subscriptions>` block AFTER the `<operations>` block (sibling, not nested). It lists the type's subscriptions in source order so `/{type}` users can see which events the skill listens to. Format:
     ```
     <subscriptions>
     ## Subscriptions

     | event              | handler            | condition |
     |--------------------|--------------------|-----------|
     | entity-mentioned   | log-mention        | always    |
     </subscriptions>
     ```
   - **Command routes:** for each handler that became a stub op (case c above), add a route to `.claude/commands/{name}.md`: `/{name} {handler} → {handler} operation`. Default-op and existing-extra-op handlers reuse their existing routes.

### Idempotency

Regenerating from the same type definition and sidecar must produce byte-identical output, with one exception: the `materialized:` provenance date. The splicer does not depend on existing skill contents, and the generated `SKILL.md` is rewritten in full each time — but `regenerate` preserves the existing `materialized` value when the rest of the file is unchanged (see the `regenerate` operation in the `document-define` SKILL.md). So a no-op regeneration is byte-identical including `materialized`; a regeneration that genuinely changes the body updates `materialized` to the current date. A type with no `## Subscriptions` section produces no `<subscriptions>` block and no stub handler operations.

## Complete Example

Given a PRD type at `.config/documents/types/prd.md`, a sidecar at `.config/documents/types/prd.skill.md` looks like this.

```markdown
# PRD — Custom Logic

## Operations

### publish
**Inputs:** PRD name or path.

**Steps:**

1. Read the PRD. Confirm status is `approved`.
2. Render the PRD to HTML using the project's publish tool.
3. Copy the rendered file to the configured publish target directory.
4. Update the PRD frontmatter: add `published: {today}`.
5. Report the publish target path.

**Output:** published file path, updated PRD path.

## Hooks

### pre-update-status
Before transitioning status, verify the `approver` field is set when the target status is `approved`. If missing, refuse the transition with: "Cannot approve: `approver` field is empty."

### post-create
After writing the new PRD file, read the parent product hub identified by the `product` frontmatter link. Append a row to the product hub's `## PRDs` table with the new PRD's name, status, and created date. Save the product hub.
```

## Example Generated Output

The splice produces an excerpt like the following inside the generated `.claude/skills/prd/SKILL.md`.

```markdown
<operations>

## create — Create a new document interactively.

<create_operation>
**Inputs:** frontmatter fields.

**Steps:**

1. Resolve location.
2. Stamp a file from the template or walk through conversational phases.
3. Write the document.
4. Update indexes and backlinks.

**Post-hook:** After writing the new PRD file, read the parent product hub identified by the `product` frontmatter link. Append a row to the product hub's `## PRDs` table with the new PRD's name, status, and created date. Save the product hub.

**Output:** file created, fields set, relationships linked.
</create_operation>

## update-status — Transition a document's lifecycle status.

<update_status_operation>
**Inputs:** document name, new status.

**Pre-hook:** Before transitioning status, verify the `approver` field is set when the target status is `approved`. If missing, refuse the transition with: "Cannot approve: `approver` field is empty."

**Steps:**

1. Validate the transition against the ALLOWED TRANSITIONS table.
2. If not allowed, respond with the rejection message and return.
3. If allowed, update the status field.
4. Report the transition.

**Output:** transition report line.
</update_status_operation>

## publish — Publish an approved PRD.

<publish_operation>
**Inputs:** PRD name or path.

**Steps:**

1. Read the PRD. Confirm status is `approved`.
2. Render the PRD to HTML using the project's publish tool.
3. Copy the rendered file to the configured publish target directory.
4. Update the PRD frontmatter: add `published: {today}`.
5. Report the publish target path.

**Output:** published file path, updated PRD path.
</publish_operation>

</operations>
```

Note the placement: `**Pre-hook:**` sits between `**Inputs:**` and `**Steps:**`. `**Post-hook:**` sits between the last Steps item and `**Output:**`. The `publish` block is appended after all default operations.

The generated command file gains a route:

```markdown
- `/{name} publish {identifier}` → publish operation
```

## Error Cases

The splicer reports and refuses to generate when any of the following occur. It never silently ignores a malformed sidecar.

- **Sidecar lacks required content.** The file exists but contains neither `## Operations`, `## Hooks`, nor `## Subscriptions` sections with any rows. Report: "Sidecar {path} has no Operations, Hooks, or Subscriptions. Remove the file or add content."
- **Unknown H2 section.** Any H2 other than `## Operations`, `## Hooks`, or `## Subscriptions`. Warn: "Ignoring unknown H2 '{heading}' in {path}. Only '## Operations', '## Hooks', and '## Subscriptions' are recognized."
- **Unknown subscription event.** The `event` column under `## Subscriptions` is not one of the reserved event names. Report: "Subscription on row {n} of {path} targets unknown event '{name}'. Known events: {list}."
- **Bad subscription condition.** The `condition` column does not parse against the closed grammar. Report: "Subscription on row {n} of {path} has unparseable condition '{expr}'. Allowed: 'always' | <field> <op> <literal> | <field> in {<lit>, ...}."
- **Malformed hook name.** An H3 under `## Hooks` does not match `pre-{op}` or `post-{op}`. Report: "Hook '{heading}' in {path} does not match 'pre-{op}' or 'post-{op}' grammar."
- **Hook references an unknown op.** The `{op}` portion of a hook H3 is neither a default op nor a custom op declared in the same sidecar. Report: "Hook '{heading}' targets unknown operation '{op}'. Known ops: {default list}, {sidecar custom list}."
- **Duplicate op name within the sidecar.** Two H3s under `## Operations` share the same name. Report: "Duplicate operation '{op}' declared twice in {path}. Remove one."
- **Extra op collides with a default op.** An H3 under `## Operations` uses one of `store`, `create`, `get`, `list`, `validate`, `update-status`, `split`, `merge`. Report: "Operation '{op}' collides with a default operation. Overrides are not supported in v1. Use a hook or rename."
- **Duplicate hook name within the sidecar.** Two H3s under `## Hooks` share the same name. This is not an error. Concatenate in file order.

On any error above, generation aborts before any files are written. The existing generated skill is left unchanged. Fix the sidecar and re-run `generate` or `regenerate`.

## Versioning

The generated `SKILL.md` frontmatter records the generator version. Bumping the generator version when splice rules change lets `list-types` flag stale skills for regeneration. Sidecars themselves do not carry a version field. They are source-of-truth text.
