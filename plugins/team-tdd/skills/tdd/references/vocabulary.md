# TDD Vocabulary (Shared)

| Term | Definition | Use This | Not This |
|------|-----------|---------|----------|
| Red | A failing test. Starting state of every TDD cycle. The specification of intent. | "The test is red" | "The test failed" |
| Green | A passing test. Achieved with the simplest possible implementation. Green is not done. | "Get to green" | "It works" |
| Refactor | Restructure code without changing behavior. Only performed when green. | "Refactor to remove duplication" | "Rewrite" or "clean up" |
| Test list | A planned sequence of tests capturing intent before implementation. | "Add it to the test list" | "Test plan" |
| Baby steps | Smallest possible increment. Minutes between greens, not hours. | "Take a baby step" | "Small iteration" |
| Fake it | Return a constant to pass the test, then generalize. Gets to green fast. | "Fake it till you make it" | "Hardcode it" |
| Triangulation | Write a second test that forces generalization. Two specifics drive the general. | "Triangulate" | "Add another test" |
