---
description: "Review work against {{domain}} criteria — anti-pattern detection"
allowed-tools: [Read, Write, Edit, Glob, Grep, AskUserQuestion, Agent]
---

# {{Domain}} Review

Review artifacts against the domain's anti-patterns and principles.

## Setup

1. Read the domain skill: `../../skills/{{domain}}/SKILL.md`
2. Read the challenger agent: `../../agents/challenger.md`

## Flow

### Step 1: Gather what to review

Use AskUserQuestion to ask what the user wants reviewed:
- A plan or design document
- A proposal or approach
- An artifact or output

### Step 2: Run the challenger

Pass the material to the challenger agent. It checks:
- All anti-patterns from the domain expert(s)
- Core principle alignment
- Vocabulary consistency

### Step 3: Present findings

Structured review report:
- **Violations** (must fix): anti-patterns detected
- **Concerns** (should discuss): principle alignment issues
- **Suggestions** (optional): methodology-aligned improvements
- **Verdict**: PASS, FIX REQUIRED, or DISCUSS

### Step 4: Iterate if needed

If FIX REQUIRED: walk through each violation, suggest corrections, re-review (max 3 loops).

## Continuation

After the verdict, offer via AskUserQuestion:
- **If FIX REQUIRED and fixed**: "Turn fixes into a plan" (planning)
- **If DISCUSS**: "Work through concerns together" (coaching)
- **If PASS**: "Get another domain's perspective" (cross-consult)
- **Always**: "I'm good for now" (end session)
