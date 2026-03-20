---
description: "Engineering plan with Kent Beck — domain gray areas, TDD-influenced decomposition, principled verification"
---

# Engineering Plan (Kent Beck)

## Setup

1. Read `skills/kent-beck/SKILL.md`
2. Read `skills/kent-beck/references/principles.md`
3. Read `AVATAR.md`

## Flow

Create an engineering-informed plan. Beck's planning approach:

### Gray Areas (Beck would ask these)
Surface 3-4 questions Beck would ask before starting:
- "What phase are you in? Explore, Expand, or Extract?"
- "Where is the coupling? What changes together?"
- "What's the smallest experiment that would reduce uncertainty?"
- "Do you have tests? Can you refactor safely?"

Walk through each with AskUserQuestion.

### Decomposition (TDD-influenced)
Break work into tasks that follow Red-Green-Refactor:
- Each task starts with "write a test for..."
- Tasks are small enough to complete in one TDD cycle
- Structure changes (tidyings) are separate tasks from behavior changes

### Verification (principled)
Each task has a verify criterion grounded in Beck's principles:
- "Tests pass and cover the new behavior"
- "No coupling introduced between X and Y"
- "Structure and behavior are in separate commits"


ARGUMENTS: $ARGUMENTS
