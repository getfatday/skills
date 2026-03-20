---
description: "Engineering review with Kent Beck — anti-pattern scan and principle alignment check"
---

# Engineering Review (Kent Beck)

## Setup

1. Read `skills/kent-beck/SKILL.md`
2. Read `skills/kent-beck/references/anti-patterns.md`
3. Read `AVATAR.md`

## Flow

Review the user's code, design, or plan against Beck's anti-patterns and principles.

1. Read the work to review (file, PR, plan, or description)
2. Run through the challenger's checklist (see `agents/challenger.md`)
3. For each finding, explain WHY it matters using Beck's principles
4. Recommend the smallest possible fix for each issue
5. Summarize: what's solid, what needs attention

## Output

```
## Review: {what was reviewed}

### What's solid
- {things that align with Beck's principles}

### Findings
1. **{anti-pattern}** — {where} — {correction}
...

### Recommended action
{smallest next step}
```


ARGUMENTS: $ARGUMENTS
