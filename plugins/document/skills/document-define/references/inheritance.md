# Parent-Field Inheritance

Hierarchical document types (sessions → sessions, tasks → tasks via
`parent-task`, initiatives → initiatives, epics → stories) benefit from
auto-inheriting fields from their parent — `project:`, `health:`, or any
other "sticky" value — so child documents don't have to restate context
that's already on the parent.

Inheritance is a `post-create` concern: after the child document is written,
look up the parent and fold in selected fields. The sidecar's post-create
hook performs the work **inline as skill instructions** — no script call.
This keeps the generated Tier-3 artifact self-sufficient: it doesn't reference
`${CLAUDE_PLUGIN_ROOT}` and runs in any repo, with or without the plugin
installed.

See `custom-logic-schema.md` for the sidecar grammar.

## The Pattern in Two Steps

1. **Spawn capture (PreToolUse hook, project-level).** When the user invokes
   an operation that creates a child document (e.g. `workmux add`), a
   PreToolUse hook writes a marker file to
   `$HOME/.document-spawn-context/pending.{type}` recording:
   - parent identifier (filename stem or ID)
   - timestamp (`written_at: <unix-epoch>`)
   - max-age window (default 120 seconds)

   This hook lives OUTSIDE the plugin — consumers write it because different
   projects spawn children differently.

2. **Child creation (post-create hook, sidecar-level).** The child type's
   `{type}.skill.md` declares a `post-create` hook whose body instructs the
   generated skill (the `create` operation, after the document is written) to:

   1. Check `$HOME/.document-spawn-context/pending.{type}` exists and is
      no older than its `max_age_seconds`.
   2. If absent or stale: do nothing; delete the marker if it exists.
   3. If fresh: read the `parent: <identifier>` line; locate the parent
      document under the parent's collection directory; read its frontmatter;
      for each field in the inherit list, copy the parent's value into the
      child's frontmatter (preferring any user-entered value over the
      inherited one); add a `parent-{type}: <wikilink>` back-reference and
      `inferred: true`.
   4. Delete the marker on every invocation so a second create never re-
      consumes it.

## Sidecar Declaration

Add a `post-create` hook to the child type's sidecar — instructions only, no
script invocation:

```markdown
# Session — Custom Logic

## Hooks

### post-create

After writing the new session document, fold in the parent session's context:

1. If `$HOME/.document-spawn-context/pending.session` exists and is newer
   than 120 seconds, read its `parent: <id>` line. Otherwise stop.
2. Look up the parent session under `Sessions/<id>.md` (or its index.md).
3. Read the parent's `project:` field. If set, write it into this session's
   frontmatter as `project:` — but only if the field is currently empty
   (prefer any user-entered value).
4. Add `parent-session: "[[Sessions/<id>|<id>]]"` as a back-reference.
5. Set `inferred: true` so `document-verify-inferred` prompts the user
   later.
6. Delete `$HOME/.document-spawn-context/pending.session` on every
   invocation, even when no inheritance happens, so a second create never
   re-consumes a stale marker.
```

The splicer copies this hook verbatim into the generated skill's `create`
operation, between the Steps list and the Output line. The hook is plain
markdown instructions Claude follows — no script dependency, no
`${CLAUDE_PLUGIN_ROOT}` reference.

## Why this is inline, not a script call

Earlier drafts of this reference invoked
`${CLAUDE_PLUGIN_ROOT}/scripts/inherit-parent-fields.sh` from the sidecar.
That call leaks `${CLAUDE_PLUGIN_ROOT}` into a generated Tier-3 artifact,
violating the FACTORY.md self-sufficiency rule (a materialized artifact must
run with no plugin installed). Inlining the logic resolves the leak. The
trade-off is determinism: Claude executes the lookup, where a shell script
would be byte-deterministic. For an inherit-from-parent operation that runs
once per child-document creation, the lookup is simple enough that inline
instructions are acceptable; if a project genuinely needs deterministic
inheritance, materialize a helper script into `.claude/skills/{type}/scripts/`
via `/document:upgrade` and reference it by a repo-relative path
rooted at `$(git rev-parse --show-toplevel)`.

## Example: Session → Session Inheritance

Project setup:

1. **PreToolUse hook** (`~/.claude/hooks/pre-tool-workmux-spawn.sh`,
   user-level — outside the plugin):

   ```bash
   #!/bin/bash
   # Detects `workmux add` and writes the spawn marker.
   input=$(cat)
   [ "$(echo "$input" | jq -r '.tool_name')" = "Bash" ] || exit 0
   cmd=$(echo "$input" | jq -r '.tool_input.command // ""')
   case "$cmd" in *"workmux add "*) ;; *) exit 0 ;; esac
   [ -z "${WM_HANDLE:-}" ] && exit 0
   mkdir -p ~/.document-spawn-context
   cat > ~/.document-spawn-context/pending.session <<EOF
   parent: $WM_HANDLE
   written_at: $(date +%s)
   max_age_seconds: 120
   EOF
   ```

2. **Session sidecar** (`.config/documents/types/session.skill.md`) — use the
   inline-instructions form above, naming `Sessions` as the parent
   collection directory and `project` as the inherited field.

3. **Result.** A child session spawned inside a workmux parent window
   inherits `project:` plus a `parent-session:` back-reference plus
   `inferred: true`. A root session (no parent context) writes with no
   inheritance. A stale marker (user sat in shell for 10 minutes) behaves
   like a root session.

## Why a Sidecar (Not the Type Definition)?

- **Inheritance rules are policy, not structure.** The type definition
  describes shape (a session HAS a `parent-session` field). The sidecar
  describes behavior (a session INHERITS `project:` from its parent when
  spawned in-context).
- **Project-specific.** Which fields to inherit depends on how the consumer
  uses the type. The sidecar stays inside the consuming project; the type
  definition stays portable.
- **Survives regeneration.** Type-definition-only rules would lose the
  inheritance logic on every `/document:define` run; sidecar hooks persist.

## Related Reading

- `custom-logic-schema.md` — complete sidecar grammar, including
  `## Hooks` → `pre-*` / `post-*` mechanism
- `status-transitions.md` — sidecar hooks for lifecycle transitions
- `type-definition-schema.md` — reserved `inferred: boolean` field
  convention (inheritance sets this)
