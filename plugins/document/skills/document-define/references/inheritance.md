# Parent-Field Inheritance

Hierarchical document types (sessions → sessions, tasks → tasks via
`parent-task`, initiatives → initiatives, epics → stories) benefit from
auto-inheriting fields from their parent — `project:`, `health:`, or
any other "sticky" value — so child documents don't have to restate
context that's already on the parent.

Inheritance is a `post-create` concern: after the child document is
written, look up the parent and fold in selected fields. The plugin
ships a generic helper, `plugins/document/scripts/inherit-parent-fields.sh`,
that reads a spawn-context marker and prints the YAML fragments to
splice into the new document's frontmatter.

See `custom-logic-schema.md` for the sidecar grammar. This reference
documents the inheritance pattern.

## The Pattern in Two Steps

1. **Spawn capture (PreToolUse hook, project-level).** When the user
   invokes an operation that creates a child document (e.g.,
   `workmux add`), a PreToolUse Bash hook writes a marker file to
   `$HOME/.document-spawn-context/pending.{type}` recording:
   - parent identifier (filename stem or ID)
   - timestamp
   - max-age window (default 120 seconds)

   This hook lives OUTSIDE the plugin — it's written by the consumer
   because different projects spawn children differently (workmux,
   shell wrappers, explicit `/{type} create` with a parent flag, etc).

2. **Child creation (post-create hook, sidecar-level).** The child
   type's `{type}.skill.md` declares a `post-create` hook that calls
   `inherit-parent-fields.sh` with the marker path and the fields to
   inherit. The helper:
   - Reads the marker (if fresh)
   - Looks up the parent document
   - Prints YAML lines ready to splice into the child's frontmatter
   - Sets `inferred: true` so `document-verify-inferred` prompts the
     user later
   - Consumes the marker (deletes it) on every invocation

## Sidecar Declaration

Add a `post-create` hook to the child type's sidecar:

```markdown
# Session — Custom Logic

## Hooks

### post-create

After writing the new session document, invoke the inherit-parent-fields
helper to fold in the parent session's context. Run from the project
root:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/inherit-parent-fields.sh \
  --marker "$HOME/.document-spawn-context/pending.session" \
  --max-age 120 \
  --portfolio "$PORTFOLIO_ROOT" \
  --parent-dir "Sessions" \
  --inherit-fields "project" \
  --self-type session
```

Capture the helper's stdout as YAML fragments. Splice them into the new
session's frontmatter, preserving any user-entered values (prefer user
over inherited). If the helper outputs nothing, the child has no
parent context — leave the frontmatter unchanged.
```

The splicer copies this hook verbatim into the generated skill's
`create` operation, between the Steps list and the Output line.

## Generic Helper API

`plugins/document/scripts/inherit-parent-fields.sh` takes:

| Flag | Required? | Purpose |
|------|-----------|---------|
| `--marker <path>` | yes | spawn-context file (supports `~` expansion) |
| `--max-age <seconds>` | no (default 120) | reject marker if older |
| `--portfolio <dir>` | yes | portfolio root for parent lookup |
| `--parent-dir <relative>` | yes | directory under portfolio containing parents |
| `--inherit-fields <csv>` | yes | comma-separated field names |
| `--self-type <string>` | no | inferred type name; used to build the default parent field name |
| `--parent-field <name>` | no | defaults to `parent-{self-type}` |

Output: YAML lines on stdout, one per inherited field plus the
parent back-reference and `inferred: true`.

Behavior guarantees:

- Missing marker → exit 0 silently (child has no parent to inherit from)
- Stale marker → exit 0 silently AFTER consuming the marker
- Fresh marker with missing parent → emit only the back-reference + inferred
- Fresh marker with parent found → emit all requested inherited fields

Always deletes the marker so a second create never re-consumes it.

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

2. **Session sidecar** (`.config/documents/types/session.skill.md`):

   ```markdown
   ## Hooks

   ### post-create

   Invoke `bash ${CLAUDE_PLUGIN_ROOT}/scripts/inherit-parent-fields.sh
   --marker "$HOME/.document-spawn-context/pending.session"
   --portfolio "$PORTFOLIO_ROOT" --parent-dir Sessions
   --inherit-fields "project" --self-type session`.
   Splice stdout into the new session's frontmatter.
   ```

3. **Result.** A child session spawned inside a workmux parent window
   inherits `project:` + a `parent-session:` back-reference +
   `inferred: true`. A root session (no parent context) writes with
   no inheritance. A stale marker (user sat in shell for 10 minutes)
   behaves like a root session.

## Example: Task → Task Inheritance

Same mechanism, different marker:

```markdown
## Hooks

### post-create

Invoke the inherit helper:

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/inherit-parent-fields.sh \
  --marker "$HOME/.document-spawn-context/pending.task" \
  --max-age 60 \
  --portfolio "$PORTFOLIO_ROOT" \
  --parent-dir Tasks \
  --inherit-fields "project,priority" \
  --self-type task
```

Splice the stdout into the new task's frontmatter.
```

## Why a Sidecar (Not the Type Definition)?

- **Inheritance rules are policy, not structure.** The type definition
  describes shape (a session HAS a `parent-session` field). The
  sidecar describes behavior (a session INHERITS `project:` from its
  parent when spawned in-context).
- **Project-specific.** Which fields to inherit depends on how the
  consumer uses the type. The sidecar stays inside the consuming
  project; the type definition stays portable.
- **Survives regeneration.** Type-definition-only rules would lose the
  inheritance logic on every `/document:define` run; sidecar hooks
  persist.

## Related Reading

- `custom-logic-schema.md` — complete sidecar grammar, including
  `## Hooks` → `pre-*` / `post-*` mechanism
- `status-transitions.md` — sidecar hooks for lifecycle transitions
- `type-definition-schema.md` — reserved `inferred: boolean` field
  convention (inheritance sets this)
- `plugins/document/scripts/inherit-parent-fields.sh` — the generic
  helper script
