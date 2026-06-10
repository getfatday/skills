# Cross-IDE target output formats

This reference doc captures the per-target output formats `rulesync` produces
from a canonical Claude Code source. It is consulted by `/document:upgrade` as
the **AI-driven fallback** when the deterministic path (invoking
`npx -y rulesync generate …`) is unavailable — typically because Node.js +
`npx` aren't installed on the consumer's machine.

The fallback contract: given the canonical Claude Code form at
`.claude/skills/<name>/SKILL.md` and the configured target list, Claude writes
the cross-IDE mirror files by hand, faithfully reproducing what rulesync would
have produced. Once Node is available, a future `/document:upgrade` re-runs
the deterministic path; the AI-produced files are overwritten with byte-identical
output (rulesync's format is the source of truth).

## Skills — the common rule

For every supported target, the *skills* output is a near-verbatim copy of the
canonical SKILL.md into a target-specific directory:

| Target | Output path | Notes |
|---|---|---|
| `cursor` | `.cursor/skills/<name>/SKILL.md` | identical body + frontmatter (description normalised to one line) |
| `codexcli` | `.codex/skills/<name>/SKILL.md` | identical body + frontmatter |
| `copilot` | `.github/skills/<name>/SKILL.md` | identical body + frontmatter |
| `cline` | `.cline/skills/<name>/SKILL.md` | identical body + frontmatter |
| `windsurf` | `.windsurf/skills/<name>/SKILL.md` | identical body + frontmatter |
| `geminicli` | `.gemini/skills/<name>/SKILL.md` | identical body + frontmatter |
| `aider` | (no skills output — feature unsupported) | skip silently |

**Frontmatter shape** for every skill target:

```yaml
---
name: <skill-name>
description: <one-line description>
---
```

Only `name` and `description` are carried across. Other canonical-form
frontmatter fields (`materialized`, `tier`, `factory`, `factory-version`,
`generated-by`, `generator-version`, `source`, `targets`, `allowed-tools`,
`trigger-phrases`, `user-invocable`, …) are dropped from the mirror —
target IDEs don't read them. The provenance block stays on the canonical
`.claude/skills/<name>/SKILL.md` only.

If the canonical `description:` is a multi-line `>`-folded block, collapse it
to a single line by replacing newlines with a single space (this is what
`rulesync` does and what `materialize.py`'s `_extract_description` already
produces).

## Commands — per-target variants

Commands are where the targets diverge.

### `cursor` — `.cursor/commands/<name>.md`

Same shape as a Claude Code command: full frontmatter (description,
argument-hint, allowed-tools) + body, written verbatim.

```markdown
---
description: <one-line>
argument-hint: <hint>
allowed-tools: [...]
---
<body>
```

### `codexcli` — `.codex/skills/<name>/SKILL.md`

OpenAI Codex CLI doesn't have a distinct commands concept — `rulesync` emits
the command as a skill under `.codex/skills/<name>/SKILL.md`. Same shape as
the skills rule above (name + description frontmatter + body).

### `copilot` — `.github/prompts/<name>.prompt.md`

GitHub Copilot prompt files. Reduced frontmatter — only `description` is
carried. `argument-hint`, `allowed-tools` are dropped.

```markdown
---
description: <one-line>
---
<body>
```

### `cline` — `.clinerules/workflows/<name>.md`

Cline workflow file. Markdown with the same frontmatter shape as Copilot
(just `description`).

```markdown
---
description: <one-line>
---
<body>
```

### `geminicli` — `.gemini/commands/<name>.toml`

Gemini CLI uses TOML. Body becomes the `prompt` value (newlines escaped via
TOML string syntax).

```toml
description = "<one-line>"
prompt = "<body-with-\n-escapes>"
```

### `windsurf` — no commands output

Windsurf doesn't have a distinct commands concept that rulesync targets.
Skip.

### `aider` — no commands output

Same as above.

## AI fallback procedure

When `materialize.py` returns `{status: "deferred", ...}` because `npx` is
missing, run the fallback for each configured target:

1. **Read the canonical source** at `.claude/skills/<name>/SKILL.md` and any
   command file at `.claude/commands/<name>.md` (if it exists).
2. **For each target** in the configured list:
   a. Read the per-target output path and frontmatter rules from this doc.
   b. Strip the canonical frontmatter down to the per-target subset (skill
      → name + description; command → as documented per target).
   c. Write the file at the target's output path with the canonical body.
   d. For non-markdown formats (`.gemini/commands/*.toml`), translate
      accordingly — escape body newlines as `\n` in a TOML double-quoted
      string.
3. **Don't write target outputs the target doesn't support** — `windsurf`
   and `aider` have no commands output; skip them silently.
4. After writing, report to the user which targets were materialized via the
   AI fallback (vs the deterministic rulesync path) so they know the
   provenance.

## Why this matters

The AI fallback preserves the **frozen-but-functional** guarantee
(`FACTORY.md`): a consuming repo gets fully working cross-IDE output even
when the materializer's optional Node dependency isn't available. The
trade-off: AI-generated outputs may drift from upstream rulesync if rulesync
changes its emitted format — re-running `/document:upgrade` once Node is
available restores rulesync's output as the source of truth.
