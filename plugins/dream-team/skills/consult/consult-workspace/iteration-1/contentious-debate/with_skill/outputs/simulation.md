# Consult Simulation: Custom vs. Existing Component Framework

**Prompt:** "Dream team: should we build a custom component framework or adopt an existing one? This is a major investment decision that affects the next 2 years."

---

## Step 1: Avatar Discovery

Scanned avatar directories. Found 3 installed avatars:

| Avatar | Domains |
|--------|---------|
| Kent Beck | engineering, tdd, software-design, extreme-programming, empirical-design |
| Robert C. Martin | engineering, tdd, software-design, clean-code, solid, software-architecture |
| Martin Fowler | engineering, software-design, software-architecture, refactoring, microservices |

---

## Step 2: Team Selection

**AskUserQuestion:**

> How would you like to assemble your team?
>
> 1. **Auto-select (Recommended)** -- orchestrator picks the most relevant avatars
> 2. **Let me pick** -- choose from all available avatars
> 3. **Everyone** -- include all installed avatars

**Simulated user response:** "Auto-select (Recommended)"

**Auto-select analysis:** The question involves engineering strategy, software architecture, and a high-stakes design decision. All three avatars have overlapping domains (engineering, software-design, software-architecture). This is a foundational technology decision. All three are relevant.

**AskUserQuestion (confirmation):**

> Based on your question, I recommend the full panel:
>
> - **Kent Beck** -- empirical design, incremental approach, phase-appropriate practices
> - **Robert C. Martin** -- clean architecture, SOLID, framework independence
> - **Martin Fowler** -- evolutionary architecture, patterns, build-vs-buy tradeoffs
>
> Options:
> 1. **"Looks good, proceed"**
> 2. **"Remove someone"**
> 3. **"Add someone"**

**Simulated user response:** "Looks good, proceed"

---

## Step 3: Pattern Selection

**Router classification:**

| Dimension | Value | Reasoning |
|-----------|-------|-----------|
| Complexity | complex | Multi-year investment, multiple sub-questions (cost, team capability, maintenance, ecosystem) |
| Domain count | many | Hits engineering, software-design, software-architecture across all avatars |
| Urgency | balanced | No time pressure signals, but "major investment" implies thoroughness |
| Controversy | contentious | "Custom vs. adopt" is a classic build-vs-buy with strong trade-offs, and the user flagged it as a "major investment decision" |
| Task type | decide | Binary decision with long-term consequences |
| Dependency | independent | Each perspective can be formed independently |

**Decision tree traversal:**
- Single-domain? No (multi-domain).
- Contentious / high-stakes? Yes ("major investment decision that affects the next 2 years").
- Result: **debate**

The command hint is `map-reduce`, but the router overrides because the classification strongly favors debate: contentious topic, high stakes, decision task type.

> **Pattern selected: Debate**
> Your question involves a contentious, high-stakes decision with strong trade-offs on both sides. I'm using the debate pattern to stress-test each position through structured argumentation. Each expert will take a clear stance, critique the others, and I'll synthesize the strongest arguments into a recommendation.

---

## Step 4: Debate Execution

### Opening Positions

---

### Kent Beck: Start with what you have. Adopt, then adapt.

I've watched teams build custom frameworks more times than I'd like to count. Here's what happens: you spend six months building something that solves the problems you know about today. Then the problems change, and you've got a framework that's perfectly optimized for yesterday.

The question isn't "custom or existing?" The question is "what phase are we in?" If you're in Explore, you need to move fast and learn. An existing framework lets you do that. You get the collective learning of thousands of teams baked into the API. You get a community that's already made the mistakes you're about to make.

Build custom when you have evidence that existing solutions can't work. Not a hunch. Not a whiteboard argument. Evidence. Run a spike. Time-box it to two weeks. Try to build your hardest component in React, or Vue, or Solid, or whatever the candidates are. Measure the friction. If the friction is real and structural, not just unfamiliarity, then you have a case for custom.

But I'll bet you a beer: the friction you're imagining is smaller than the friction of maintaining your own framework for two years with a team that could be building product instead.

Small steps. Adopt something. Tidy it toward your needs. Keep your optionality open.

---

### Robert C. Martin: Frameworks are details. Architect so the choice doesn't matter.

Let me tell you what happens when a team adopts a framework without thinking about architecture. The framework becomes the architecture. Every component inherits from FrameworkBaseComponent. Every module imports FrameworkRouter. Every test needs FrameworkTestUtils. You haven't adopted a framework. The framework has adopted you.

Build or adopt? Wrong question. The right question is: can we structure our application so the component framework is a plugin?

Clean Architecture tells us: business rules at the center, UI framework at the periphery. Your components should be thin adapters that delegate to framework-independent use cases and presenters. If you do this, the framework decision becomes reversible. And reversible decisions are cheap decisions.

Now, should you build custom? Almost certainly not. Building a component framework is building a framework, and the first rule of frameworks is: don't build them unless your business IS frameworks. But you should wrap whatever you adopt behind boundaries you control. Depend on abstractions you own, not concretions someone else ships.

The only way to go fast is to go well. Adopt a framework, but don't let it invade your architecture. Put boundaries in place from day one. Use Dependency Inversion. Your application should scream its domain, not "React" or "Vue."

---

### Martin Fowler: It depends -- and here's exactly what it depends on.

I've seen teams succeed with both approaches, and I've seen teams fail with both. The key tradeoff isn't technical at all. It's organizational.

There are several factors to consider:

**Team size and tenure.** A custom framework needs dedicated maintainers. Not part-time. Not "the person who built it." At least two engineers whose primary job is framework development, documentation, and support. If you can't commit those headcount for the full two years, adopt.

**Differentiation.** Does your component framework create competitive advantage? For most product companies, the answer is no. Your users don't care whether you use React or a custom renderer. They care about the features you ship. An existing framework lets you redirect engineering effort toward differentiation.

**Migration cost.** You already have a codebase. What's in it today? If you're deeply embedded in an existing framework, building custom means a big-bang rewrite or a Strangler Fig migration. I've seen both. The Strangler Fig works, but it takes patience. The big-bang rewrite fails more often than it succeeds.

**Ecosystem.** An existing framework gives you a package ecosystem, hiring pipeline, and community knowledge base. A custom framework gives you exactly what you build and nothing more.

My instinct is to adopt, but with a clear evolutionary architecture strategy. Define fitness functions that validate your architectural boundaries. If the adopted framework starts violating your fitness functions, you have early warning and can course-correct incrementally.

---

### Checkpoint 1: After Opening Positions

**AskUserQuestion:**

> The panel has stated their opening positions. All three lean toward adopting an existing framework, but for different reasons:
>
> - **Beck:** Empirical evidence first. Spike before deciding. Keep steps small.
> - **Martin:** Framework is a detail. Architect boundaries so the choice is reversible.
> - **Fowler:** Organizational capacity matters more than technical capability. Staff the decision.
>
> How would you like to proceed?
>
> 1. **"Continue the debate"** -- proceed to critique rounds
> 2. **"Steer the discussion toward {topic}"** -- focus on a specific aspect (e.g., performance, team autonomy, migration)
> 3. **"Add an avatar to the debate"** -- bring in another perspective
> 4. **"I've heard enough"** -- skip to judgment

**Simulated user response:** "Continue the debate"

---

### Round 1: Critiques

---

### Kent Beck responds to Robert Martin:

Bob, I agree with your conclusion but I worry about your mechanism. "Wrap everything behind boundaries you control" sounds like big upfront design to me. You're asking teams to build an abstraction layer on day one, before they know what the abstraction should look like.

I've seen this play out. The team builds a FrameworkAdapter interface with twenty methods. Six months later, twelve of those methods are unused and three are wrong. They spent weeks designing an abstraction that predicted the future, and the future disagreed.

Here's my alternative: start coupled. Use the framework directly. When you see actual coupling pain, tidy it. Extract an interface around the specific point of friction. Not the whole framework. The one spot where change is expensive.

Three uses before you abstract. Evidence before architecture. You'll end up with boundaries, but they'll be the right boundaries because they emerged from real pain, not predicted pain.

---

### Kent Beck responds to Martin Fowler:

Martin, your analysis is thorough and I agree with the factors. But I'd push back on one thing: you're treating this as a decision to be analyzed when it might be a decision to be experimented with.

Rather than listing factors and weighing them, what if we just tried it? Run two spikes in parallel. Two weeks each. Team A builds the hardest feature in the top existing framework candidate. Team B prototypes a minimal custom approach for the same feature. Compare the results. The experiment costs a month. The wrong decision costs two years.

More experiments, more care.

---

### Robert Martin responds to Kent Beck:

Kent, I hear you on the "start coupled" approach, and in many contexts I'd agree. But this is a two-year decision affecting the entire team. This isn't a module. This isn't a feature. This is the foundation.

Starting coupled with your component framework means every component in your application directly depends on that framework's API. When you say "tidy it later," you're talking about thousands of files. The cost of change isn't linear. It's exponential with coupling.

You don't need twenty methods in your adapter on day one. You need one principle: Dependency Inversion. Your business logic depends on interfaces you define. Your components implement those interfaces using whatever framework you chose. That's not big upfront design. That's basic professional discipline.

A surgeon doesn't say "I'll wash my hands when I notice an infection." The practice comes before the evidence of its absence.

---

### Robert Martin responds to Martin Fowler:

Martin, your factors are reasonable, but you're missing the most important one: architecture. You listed team size, differentiation, migration cost, ecosystem. All valid. But none of them address whether the team's architecture will survive contact with the framework.

Fitness functions are fine, but they're reactive. They tell you when something's gone wrong. Clean Architecture boundaries are proactive. They prevent the framework from invading your business rules in the first place.

I've seen teams with excellent fitness functions that still ended up married to their framework because nobody drew the boundary line on day one. The fitness function said "coupling is increasing" and nobody did anything about it because the coupling was already everywhere.

Draw the line. Enforce it. Then your choice of framework truly becomes a detail.

---

### Martin Fowler responds to Kent Beck:

Kent, I like the parallel spike idea. It's practical and evidence-based. But I'd add structure to it. A spike without evaluation criteria is just two teams having fun for two weeks.

Define what you're measuring before you start. Rendering performance under load? Developer velocity for a new team member? Accessibility compliance effort? Bundle size? The spike should answer specific questions, not generate general vibes.

I'd also note that two weeks isn't enough to evaluate the maintenance dimension. A framework feels great in week two. The pain shows up in month six when you need to upgrade, or when you hire someone who's never seen your custom solution. The spike can test build cost, but not own cost.

---

### Martin Fowler responds to Robert Martin:

Bob, I think we're closer than it sounds. Your Dependency Inversion boundary and my fitness functions serve the same purpose: preventing framework lock-in. The difference is in timing and enforcement.

Your approach says: draw the boundary on day one, enforce it through architecture. Mine says: define the fitness function on day one, let the boundary emerge, and alert when it's violated.

The practical risk with your approach is over-abstraction. I've seen teams build such thick boundaries around their framework that they lose the benefits of having chosen that framework in the first place. You pick React for its component model, then wrap it so heavily that your developers can't use hooks, can't use the ecosystem, can't read the documentation. You've built a custom framework anyway, just with React underneath where nobody can see it.

The pragmatic path is somewhere in the middle. Thin boundaries at the known risk points. Fitness functions for the rest. And the discipline to respond when the fitness functions fire.

---

### Checkpoint 2: After Round 1

**AskUserQuestion:**

> Round 1 is complete. The debate has sharpened around a central tension:
>
> - **Beck vs. Martin:** Should boundaries emerge from evidence (tidy when it hurts) or be established upfront (Dependency Inversion from day one)?
> - **Fowler vs. Martin:** Are thick architectural boundaries worth the cost, or do they negate the benefits of adopting a framework?
> - **All three agree:** Adopt, don't build. The disagreement is about how to protect yourself after adopting.
>
> How would you like to proceed?
>
> 1. **"Another round"** -- continue the debate
> 2. **"I'm convinced by {Beck/Martin/Fowler}"** -- end debate with that position
> 3. **"Steer toward {topic}"** -- refocus (e.g., "steer toward practical implementation of boundaries")
> 4. **"Move to judgment"** -- skip remaining rounds and synthesize

**Simulated user response:** "Move to judgment"

---

### Judgment

**The unanimous verdict: adopt an existing framework. Do not build custom.**

All three experts converged on this conclusion, each from their own principles. The debate was never really about build vs. adopt. It was about what to do after you adopt.

**Strongest arguments for adopting:**

1. **Opportunity cost (Beck).** Every engineer maintaining a custom framework is an engineer not shipping product. For a two-year horizon, this compounds significantly. The framework isn't your differentiator.

2. **Framework as detail (Martin).** A well-architected application treats its component framework as a plugin. This makes the decision lower-stakes and reversible, which further supports adopting rather than investing in custom.

3. **Organizational capacity (Fowler).** A custom framework requires dedicated maintainers, documentation, onboarding materials, and upgrade paths. Most product teams underestimate this cost by 3-5x.

**Strongest arguments for the minority position (build custom):**

1. If your performance requirements are genuinely extreme and measurably unmet by existing frameworks (Beck's spike would reveal this).
2. If your business IS the framework (e.g., you're building a design system product).
3. If you have an existing custom framework with significant institutional knowledge that would be lost in migration.

None of these were present in the prompt.

**The real debate -- how to protect yourself after adopting:**

| Approach | Advocate | Strength | Risk |
|----------|----------|----------|------|
| Emerge boundaries from evidence | Beck | Right-sized boundaries, no wasted abstraction | May be too late for foundation-level coupling |
| Upfront Dependency Inversion | Martin | Prevents structural coupling early | Over-abstraction, losing framework benefits |
| Fitness functions + thin boundaries | Fowler | Balanced, measurable, adaptive | Requires discipline to act on alerts |

**Recommendation:** A synthesis of all three positions.

1. **Adopt an existing framework** based on team familiarity, ecosystem size, and a time-boxed spike (Beck).
2. **Draw thin boundaries** at known integration points: state management, routing, data fetching. Not the component model itself. Don't wrap React's hooks. Do wrap your API layer (Martin, moderated by Fowler).
3. **Define fitness functions** for coupling metrics and enforce them in CI. When coupling to the framework crosses your threshold, that's the signal to extract a boundary (Fowler).
4. **Spike first** (Beck). Two weeks. Build your hardest component in the top two candidate frameworks. Measure against predefined criteria (Fowler). Then decide which framework, with confidence.

**Confidence:** High. The panel converged. The remaining disagreements are about implementation strategy, not direction.

---

## Step 5: Final Checkpoint

**AskUserQuestion:**

> The debate is complete. The panel unanimously recommends adopting an existing framework with architectural safeguards. Here's what you can do next:
>
> 1. **"Dig deeper with one of these experts"** -- go 1:1 with Beck, Martin, or Fowler on a specific concern
> 2. **"Debate this point"** -- pick a specific disagreement (e.g., upfront boundaries vs. emergent boundaries) for another round
> 3. **"Get a different team's take"** -- re-run with different avatars
> 4. **"I'm good"** -- end the consultation
