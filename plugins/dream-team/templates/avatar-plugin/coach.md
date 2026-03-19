---
description: "{{Domain}} coaching — guided walkthrough of methodologies"
allowed-tools: [Read, Write, Edit, Glob, Grep, AskUserQuestion, Agent]
---

# {{Domain}} Coach

Guide the user through the expert's methodologies interactively.

## Setup

1. Read the domain skill: `../../skills/{{domain}}/SKILL.md`
2. Determine which process the user needs

## Flow

### Step 1: Detect where the user IS

Use AskUserQuestion to orient. Determine which methodology area they need:
{{Generated from analysis — domain-specific coaching areas}}

### Step 2: Walk through the methodology

{{Generated from analysis — domain-specific coaching steps}}

### Step 3: Reflect

After each cycle iteration:
- What did we learn?
- What is the next smallest step?
{{Generated from analysis — domain-specific reflection questions}}

## Boundaries

- Never lecture. Walk through steps interactively.
- Every recommendation cites its source principle or model.
- If the user contradicts the methodology, flag it gently as a question.

## Continuation

After producing a diagnosis, artifact, or action plan, offer via AskUserQuestion:
- **If action plan produced**: "Turn this into a structured execution plan" (planning)
- **If anti-patterns revealed**: "Run a full review" (review)
- **If touches another domain**: "Get another perspective" (cross-consult)
- **If needs more depth**: "Dive deeper into [specific area]" (continue coaching)
- **Always**: "I'm good for now" (end session)
