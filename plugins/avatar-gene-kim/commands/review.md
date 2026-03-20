---
description: "Engineering review with Gene Kim — anti-pattern scan and principle alignment check"
---

# Engineering Review (Gene Kim)

## Setup

1. Read `skills/gene-kim/SKILL.md`
2. Read `skills/gene-kim/references/anti-patterns.md`
3. Read `AVATAR.md`

## Flow

Review the user's code, design, or plan against Kim's anti-patterns and principles.

1. Read the work to review (file, PR, plan, or description)
2. Run through the challenger's checklist (see `agents/challenger.md`)
3. For each finding, explain WHY it matters using Kim's principles
4. Recommend the smallest possible fix for each issue
5. Summarize: what's solid, what needs attention

## Output

```
## Review: {what was reviewed}

### What's solid
- {things that align with Kim's principles}

### Findings
1. **{anti-pattern}** — {where} — {correction}
...

### Recommended action
{smallest next step}
```


ARGUMENTS: $ARGUMENTS
