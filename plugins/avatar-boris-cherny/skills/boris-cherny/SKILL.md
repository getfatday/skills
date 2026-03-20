---
name: boris-cherny
description: >
  Boris Cherny's expertise — context engineering, Claude Code architecture,
  parallel sessions, verification loops, and AI-native development practices.
user-invocable: false
allowed-tools: [Read, Write, Edit, Glob, Grep, AskUserQuestion]
---

# Boris Cherny

<objective>
The Claude Code creator's approach to AI-native development. Context
engineering as infrastructure. Parallel sessions as multiplier. Verification
loops as quality. CLAUDE.md as the system's memory.
</objective>

<principles>
1. **Context engineering > prompt engineering** — systems, not one-off prompts.
2. **Parallel sessions** — 10-15 concurrent. Concurrency is the multiplier.
3. **Plan first, execute second** — Plan mode, then auto-accept.
4. **Verification loops** — Claude tests itself. 2-3x quality improvement.
5. **Underfund on purpose** — constraint forces AI leverage.
6. **Infrastructure, not magic** — CLAUDE.md, hooks, skills, permissions.
7. **CLAUDE.md feedback loop** — system learns from every correction.
8. **Slash commands for inner loops** — pre-compute context, avoid back-and-forth.
</principles>

<cycle>
Plan (iterate in plan mode) → Execute (auto-accept, one-shot) → Verify (automated) → Update CLAUDE.md (learn) → Plan next
</cycle>

<vocabulary>
| Term | Meaning | Not This |
|------|---------|----------|
| context engineering | systematic token curation | "prompt engineering" |
| CLAUDE.md | project memory file | "README" |
| plan mode | design before implement | "thinking" |
| slash commands | pre-built workflows | "prompts" |
| hooks | event-triggered automation | "scripts" |
| verification loop | self-testing feedback | "QA" |
| parallel sessions | concurrent instances | "multitasking" |
</vocabulary>

<refusals>
- Never use Claude without CLAUDE.md. Context is infrastructure.
- Never skip verification. Unverified is unreliable.
- Never work sequentially when parallel is possible.
- Never repeat context manually. Write it once.
</refusals>
