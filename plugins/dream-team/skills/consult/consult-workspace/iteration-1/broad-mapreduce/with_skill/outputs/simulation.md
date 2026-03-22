# Consult Skill Simulation

**Prompt:** "Dream team: how should we structure our GTM plan for the design system? We need to position EGDS against teams building custom components."

---

## Step 1: Avatar Discovery

Scanning for installed avatars...

| Avatar | Description | Domains |
|--------|-------------|---------|
| April Dunford | B2B positioning authority | product-marketing, positioning, gtm-strategy, sales-enablement |
| Seth Godin | Remarkable marketing, Purple Cow | marketing, differentiation, tribes, storytelling, permission-marketing |
| Marty Cagan | Product strategy, empowered teams | product, product-strategy, team-empowerment, product-leadership |
| Teresa Torres | Continuous discovery, OST | product, product-discovery, customer-research, assumption-testing |

4 avatars discovered.

---

## Step 2: Team Selection

**Mode: Auto-select (Recommended)**

Domain matching against prompt ("GTM plan", "position", "design system", "against teams building custom"):

| Avatar | Matching Domains | Relevance |
|--------|-----------------|-----------|
| April Dunford | positioning, gtm-strategy, product-marketing | High: direct positioning and GTM expertise |
| Seth Godin | marketing, differentiation, tribes | High: differentiation strategy, internal adoption as tribe-building |
| Marty Cagan | product-strategy, product-leadership | Medium-High: internal product strategy, empowered team dynamics |
| Teresa Torres | product-discovery, customer-research | Medium: discovery of internal team needs, assumption testing for adoption |

Auto-select recommends: Dunford, Godin, Cagan, Torres (all 4).

**AskUserQuestion would present:**

> **Team Selection**
>
> For your GTM positioning question, I recommend the full panel. Here's who I'd bring in and why:
>
> - **April Dunford** -- positioning EGDS against competitive alternatives (custom components) is her core framework
> - **Seth Godin** -- internal adoption is a tribe-building problem, and differentiation is her wheelhouse
> - **Marty Cagan** -- design systems are platform products; he'll address the empowered-team dynamics
> - **Teresa Torres** -- understanding what teams actually need from a design system requires discovery
>
> **Options:**
> 1. "Go with this team" (Recommended)
> 2. "Let me pick" -- choose from all available avatars
> 3. "Everyone" -- include all installed avatars

**Simulated user response:** "Go with this team"

---

## Step 3: Pattern Selection

**Router classification:**

| Dimension | Assessment |
|-----------|------------|
| Complexity | Moderate: GTM plan with positioning component |
| Domain count | Many: positioning, marketing, product strategy, discovery (4 domains) |
| Urgency | Balanced: "how should we" signals deliberation, not speed |
| Controversy | Nuanced: multiple valid approaches to internal GTM |
| Task type | Plan |
| Dependency | Independent: each domain can contribute independently |

**Decision tree traversal:**
- Single-domain? No (4 domains).
- Contentious/high-stakes? No, nuanced but not contentious.
- Sub-tasks independent? Yes, each expert can respond to the GTM question from their domain.
- Needs decomposition? No, the question is broad but not decomposable into sequential sub-tasks.
- Result: **map-reduce**

This matches the command hint (`consult` defaults to `map-reduce`). No override needed.

> **Pattern: Map-Reduce**
> I'm using the map-reduce pattern. Each expert will give their independent perspective on your GTM plan, then I'll synthesize the agreement, disagreement, and recommendations.

---

## Step 4: Map-Reduce Execution

### April Dunford

Let's start with what matters: what are the competitive alternatives? When a team decides not to use EGDS, what do they actually do instead?

They build custom components. That's your real competition. Not another design system. Not a third-party library. It's the team saying "we'll build it ourselves." And here's the thing about that competitive alternative: it feels free. It feels like control. It feels like autonomy. You're fighting a status quo that has strong emotional appeal.

So your positioning has to start there. What differentiated capabilities does EGDS have that custom components lack? I'd bet it's something like: cross-product consistency, accessibility compliance baked in, reduced maintenance burden, faster time-to-ship for standard UI patterns. Those are capabilities.

But capabilities are not value. The differentiated value is: "Your team ships features instead of rebuilding buttons. You get accessibility compliance without an audit. Your product looks like it belongs in the portfolio, not like a side project." That's what the engineering lead and the PM care about.

Now, best-fit customers. Not every team is your best-fit. Your best-fit teams are the ones building customer-facing products with standard UI patterns, under time pressure, who have been burned by an accessibility audit or a brand consistency review. Those teams feel the pain. Start there. Don't try to convince the team building a one-off internal tool with exotic UI requirements. They're not your customer right now.

Market category: you're a platform product. Internal platform. Frame it that way. Teams know what a platform provides: stability, standards, leverage. Don't call it a "component library" because that sets the expectation of a grab bag. Call it what it is: the product platform for UI.

The sales narrative structure: lead with the market shift. "We're scaling from 3 products to 15. Every team rebuilding buttons and modals is a team not shipping features. The cost of custom components compounds." Then the pain: "Teams are spending 30% of sprint capacity on solved problems. Accessibility findings hit after launch. Brand reviews catch inconsistencies late." Then the solution, framed by your differentiated value.

Stop selling EGDS as a thing teams should use. Start teaching teams how to evaluate build-vs-adopt decisions for UI components. Teach them how to buy.

---

### Seth Godin

Who's it for? What's it for? What change are you trying to make?

If the answer is "it's for everyone" and "it's for everything," you've already lost. A design system for all teams is a design system no team talks about. It's average. It's the brown cow.

Here's the real question: which team, when they adopt EGDS, will be so delighted that they can't stop telling other teams about it? That's your smallest viable audience. Find that team. Make something so good for them that they become your evangelists. Not because you asked them to. Because they can't help it.

You don't have a marketing problem. You have a remarkable problem. Is EGDS worth making a remark about? When a developer uses an EGDS component, do they say to their teammate, "You have to see this"? If not, no amount of GTM planning fixes that.

The GTM plan for a design system is not a launch campaign. It's tribe-building. "People like us use the design system." That's the story. You need early adopters who identify with that statement. They're not adopting a library. They're joining a movement toward better, faster, more consistent product development.

Stop interrupting teams with mandates and migration deadlines. That's interruption marketing applied to internal products. It breeds resentment. Instead, earn permission. Show up where teams are already struggling. Offer help. Solve their problem with an EGDS component they didn't know existed. Do it so well they come back for more.

The dip matters here. Adopting a design system is hard. Migration is painful. Teams will hit the dip and want to quit. Your job is to make the dip survivable. Dedicated support for migrating teams. Quick wins early. Visible progress. The teams that push through the dip become your tribe leaders.

Ship the story, not the system. "EGDS helped Team X ship their feature two sprints early and pass accessibility review on the first try." That's a story worth telling. A component catalog is not a story. Outcomes are stories.

---

### Marty Cagan

Let me be direct: if you're framing this as a GTM plan, you might already be thinking about this wrong.

EGDS is a platform product. The teams consuming it are your customers. The question is: are you treating this like an empowered product team, or like a feature team that ships components and hopes people use them?

If you're an empowered team, your mission is clear: enable product teams to ship consistent, accessible, high-quality UI faster. Your success metric is their velocity and quality, not your adoption numbers. Adoption is a vanity metric if the teams using EGDS are still struggling.

Here's what I'd diagnose first. Are the teams building custom components doing it because EGDS doesn't solve their problem, or because they don't know it does? Those are completely different problems. The first is a product gap. The second is a discovery gap. You need to know which one before you build a GTM plan.

The product trio for EGDS should be doing continuous discovery with their consuming teams. Sit with them. Watch them build UI. Understand their workflow. Where do they reach for custom code? Why? Is it because the EGDS component doesn't exist, doesn't flex enough, or they didn't know about it?

Strategic context matters here. If leadership treats EGDS as a mandate, you'll get compliance, not adoption. Compliance looks like adoption in dashboards but feels like resentment in practice. Teams will wrap EGDS components in custom code to get what they actually need, and you'll have the worst of both worlds.

Instead, give teams the strategic context: "We're investing in EGDS as our UI platform because consistency, accessibility, and velocity matter at our scale. We want teams to adopt it because it makes them faster, not because they're told to." That's empowerment. That's missionaries, not mercenaries.

The GTM plan should be a product plan. Treat adoption like a product problem. What's the onboarding experience? What's the time-to-first-component? What happens when a team needs something EGDS doesn't have? Do they have a path to contribute, or do they hit a wall?

Don't build a GTM plan. Build a product strategy for a platform team.

---

### Teresa Torres

Before structuring the GTM plan, I want to ask: what assumptions are we making about why teams build custom components?

I see a whether-or-not evaluation here. We're evaluating one approach: "position EGDS against custom components and drive adoption." But what if the opportunity space is broader? What if some teams have legitimate reasons to build custom, and forcing adoption creates more problems than it solves?

Let me suggest an opportunity solution tree for this.

The desired outcome is: more teams adopt EGDS where it makes them faster and their products better. That's measurable.

The opportunities underneath that outcome might be:
- Teams don't know EGDS components exist that solve their problem
- Teams tried EGDS and found gaps that forced custom work
- Teams want to adopt but migration cost feels too high
- Teams have workflow or tooling friction with EGDS
- Teams have built custom components that are actually better than EGDS equivalents

Each of these is a different opportunity with different solutions. A GTM plan that treats them all the same will fail.

My recommendation: start with weekly touchpoints. Talk to 3-5 teams per week. Not surveys. Not Slack polls. Actual conversations. "Walk me through the last time you built a custom component instead of using EGDS. What happened?" You'll learn more in two weeks of interviews than in a month of planning.

Then compare and contrast your GTM approaches. Don't pick one strategy. Generate at least three:
1. Developer advocacy model: embedded support, office hours, migration assistance
2. Product-led model: improve onboarding, documentation, and time-to-first-component
3. Proof-of-value model: partner with one high-visibility team, show measurable results

Test your assumptions about each. What has to be true for approach 1 to work? That teams' primary barrier is awareness and support. Test that assumption before committing resources.

Define success criteria before you launch anything. "We'll know this GTM approach is working when X teams adopt Y components within Z timeframe, and their self-reported satisfaction is above N." Without pre-defined criteria, confirmation bias will convince you anything is working.

Show your work. Share the discovery findings, the opportunity tree, and the assumption tests with stakeholders. The GTM plan should be a living document informed by continuous discovery, not a one-time strategy deck.

---

## Step 5: Synthesis

### Consensus

All four experts agree on these points:

1. **Understand why teams build custom first.** Dunford frames it as identifying competitive alternatives. Torres frames it as opportunity discovery. Cagan frames it as product diagnosis. All agree: you cannot position EGDS until you understand what you're displacing and why it exists.

2. **Lead with value, not mandates.** Dunford says sell differentiated value, not features. Godin says earn permission, don't interrupt. Cagan says create missionaries, not compliance. Torres says validate that adoption actually helps teams. The consensus is clear: top-down mandates will backfire.

3. **Start narrow, not broad.** Dunford says find best-fit customers. Godin says find the smallest viable audience. Cagan says pilot first. Torres says talk to 3-5 teams. Nobody recommends a broad rollout. Find teams where EGDS wins decisively and start there.

4. **Adoption is a product problem, not a marketing problem.** Every expert, in their own language, says that if EGDS doesn't genuinely make teams faster and better, no positioning or GTM plan will fix that.

### Divergence

1. **Framing: marketing vs. product strategy.** Dunford and Godin frame this as a positioning and marketing challenge. Cagan pushes back and says calling it GTM is itself a mistake: it's a product strategy problem. Torres bridges the two by grounding both in discovery. This tension is productive, not contradictory. You need both product excellence and clear positioning.

2. **Category framing.** Dunford says call it a "product platform for UI" to set expectations. Godin would resist any category label and instead focus on making it remarkable enough that the category doesn't matter. This is a real strategic choice: platform framing sets professional expectations, while remarkable framing drives word-of-mouth.

3. **Role of stories vs. structure.** Godin emphasizes narrative and tribe-building as the primary GTM mechanism. Dunford emphasizes a structured sales narrative with a specific pitch flow. Torres emphasizes evidence-based discovery. These are complementary approaches at different stages of maturity.

### Recommendations

1. **Run discovery before building the GTM plan.** Interview 10-15 teams over the next 2-3 weeks. Understand why they build custom. Map the opportunity space. (Torres's approach, endorsed by all.)

2. **Define your positioning foundation.** Once you have discovery data, run Dunford's positioning exercise: competitive alternatives (custom components, third-party libraries, doing nothing), differentiated capabilities, differentiated value, best-fit customers, and market category.

3. **Pick 2-3 best-fit teams as pilots.** Find teams where EGDS's differentiated value is strongest. Partner deeply with them. Make their adoption experience remarkable. (Cagan's pilot approach + Godin's smallest viable audience.)

4. **Build the sales narrative.** Structure it as: market shift (scaling products, compounding cost of custom), pain of the old way (duplicated effort, accessibility gaps, brand inconsistency), solution framed by differentiated value (ship features, not components).

5. **Measure outcomes, not adoption.** Track whether EGDS teams ship faster, pass accessibility reviews more easily, and report higher satisfaction. Adoption without outcomes is a vanity metric.

6. **Earn adoption through service, not mandates.** Office hours, embedded support for migrating teams, fast response to component requests. Permission marketing applied to internal platforms.

---

## Step 6: Checkpoint

**AskUserQuestion would present:**

> The team has weighed in. Here's where you can go next:
>
> **Options:**
> 1. **"Dig deeper with April Dunford"** -- run the full positioning exercise for EGDS (competitive alternatives, differentiated value, best-fit customers, market category, sales narrative)
> 2. **"Dig deeper with Teresa Torres"** -- build the opportunity solution tree for EGDS adoption and design assumption tests
> 3. **"Dig deeper with Marty Cagan"** -- diagnose whether EGDS is operating as an empowered platform team and design the product strategy
> 4. **"Dig deeper with Seth Godin"** -- develop the tribe-building strategy and internal storytelling approach
> 5. **"Debate this point"** -- is this a marketing problem or a product strategy problem? (Dunford/Godin vs. Cagan)
> 6. **"Get a different team's take"** -- bring in different experts
> 7. **"Apply the recommendations"** -- start executing on the synthesis
> 8. **"I'm good"** -- end consultation
