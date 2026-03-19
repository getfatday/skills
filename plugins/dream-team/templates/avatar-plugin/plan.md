---
description: "Create a {{domain}}-informed execution plan"
allowed-tools: [Read, Write, Edit, Glob, Grep, AskUserQuestion, Agent]
---

# {{Domain}} Plan

Produce execution plans enriched with {{domain}} expertise.

## Flow

### Step 1: GRAY AREAS (domain-specific)

Surface domain-specific questions that must be answered before planning:
{{Generated from analysis — example gray area questions}}

Use AskUserQuestion to resolve each. Lock decisions.

### Step 2: DECOMPOSE (using domain methodology)

Break the work into phases using the expert's cycle model:
{{Generated from analysis — how cycle maps to phases}}

### Step 3: VERIFY CRITERIA (domain standards)

For each phase, define done criteria using the expert's success measures:
{{Generated from analysis — example verify criteria}}

### Step 4: CHALLENGER REVIEW

Spawn the challenger agent to review the plan:
- Load `../../agents/challenger.md`
- Anti-pattern and principle review
- Fix violations before execution begins
- Maximum 3 review loops

### Step 5: CROSS-DOMAIN (optional)

Use AskUserQuestion to offer cross-domain consultation:
- "Want a perspective from another domain's avatar?"
- "No, proceed with the plan as-is"

## Continuation

After plan is written, offer via AskUserQuestion:
- "Walk me through Phase 1 in detail" (coaching)
- "Review the plan against {{domain}} principles" (review)
- "Get another domain's perspective" (cross-consult)
- "Ready to execute" (end session)
