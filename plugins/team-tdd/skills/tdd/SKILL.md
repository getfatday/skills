---
name: tdd
description: >
  Shared TDD fundamentals — Red-Green-Refactor cycle, test-first discipline,
  and the relationship between tests and design.
user-invocable: false
---

# TDD (Shared Domain)

<principles>
1. **Tests come first** — write a failing test before any code. The test is the specification.
2. **Red-Green-Refactor** — the cycle. Failing test, simplest pass, clean up. Never skip refactor.
3. **Small steps** — minutes between greens, not hours. When stuck, take a smaller step.
4. **Tests enable refactoring** — without tests, refactoring is gambling. With tests, it's safe.
5. **Test behavior, not implementation** — tests coupled to internals break when you refactor.
</principles>

<cycle>
Red (write ONE failing test) → Green (write ONLY enough to pass) → Refactor (clean up) → Red → ...
</cycle>

<vocabulary>
| Term | Meaning | Not This |
|------|---------|----------|
| red | failing test, starting state of TDD cycle | "error" |
| green | passing test, simplest implementation | "done" |
| refactor | restructure without changing behavior, only when green | "rewrite" |
| test list | planned tests capturing intent before implementation | "test plan" |
| baby steps | smallest possible increment between greens | "iterations" |
</vocabulary>
