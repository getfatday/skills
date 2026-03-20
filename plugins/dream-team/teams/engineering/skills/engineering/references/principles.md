# Engineering Principles (Shared)

## 1. Tests Come First
Write a failing test before code. The test IS the specification. Test-after suffers from confirmation bias. Beck invented it, Martin evangelized it, both consider it non-negotiable.

## 2. Red-Green-Refactor
The cycle: failing test, simplest pass, clean up. Never skip refactor. The discipline that makes all other engineering practices safe.

## 3. Small Steps Reduce Risk
Minutes between greens, not hours. When stuck, take a smaller step. Both Beck and Martin agree: smaller is always safer.

## 4. Code Is Communication
Programs are read far more often than written. Beck ("Implementation Patterns") and Martin ("Clean Code") build entire books around this. Optimize for the reader.

## 5. Quality IS Speed
"The only way to go fast is to go well." (Martin) / "Make it work, make it right, make it fast." (Beck). Shortcuts create defects that cost more than the time saved.

## 6. Continuous Improvement
Beck's refactor step and Martin's Boy Scout Rule: never leave code worse than you found it. Small improvements compound.

## 7. Design Emerges from Discipline
Both reject big upfront design. Design emerges from TDD, refactoring, and disciplined practice. Architecture is a result, not a starting point.

## 8. Embrace Change
Cost of software ≈ cost of changing it. Build practices that make change cheap. Beck's XP and Martin's Clean Architecture both optimize for change as a constant.

## 9. Coupling Down, Cohesion Up
Minimize dependencies between components (coupling = cost). Maximize relatedness within components (cohesion = benefit). The fundamental design forces. Beck frames economically, Martin frames structurally, Evans frames as bounded contexts.

## 10. Separate Concerns
Structure vs behavior. Policy vs detail. Interface vs implementation. Keep distinct responsibilities in distinct modules.
