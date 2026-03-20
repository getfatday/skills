---
name: avatar-recruit
description: "Find expert candidates for a domain — research who has enough published material to become a high-quality avatar"
disable-model-invocation: true
user-invocable: true
allowed-tools: [Read, Glob, Grep, WebSearch, AskUserQuestion]
---

# Avatar Recruitment

You are a skill that finds expert candidates worth turning into avatars. You research a domain, identify thought leaders with dense published material, score them on avatar viability, and present a ranked list for the user to choose from.

Parse the domain or topic from `$ARGUMENTS` (e.g., "devops", "leadership", "systems thinking"). If no argument, ask the user what domain they want to explore.

---

## Step 1: Check Existing Coverage

Read `plugins/dream-team/marketplace.json` to see what avatars and domains already exist. Report the current state:

- "You have N avatars covering these domains: [list]"
- "The domain '{input}' is {covered by X / not yet covered}."

If the domain is already covered, note which avatars cover it. The user may still want additional perspectives.

## Step 2: Research Candidates

Use WebSearch to find thought leaders in the requested domain. Search for:

- "{domain} thought leaders authors"
- "{domain} best books practitioners"
- "{domain} conference keynote speakers"
- "{domain} methodology framework creators"

For each candidate found, gather:

- **Name**
- **Books**: count and titles of published books
- **Blog/Newsletter**: active? URL? Post frequency?
- **Talks**: YouTube presence? TED talks? Conference keynotes?
- **Named frameworks**: specific models people reference by name
- **Domain coverage**: what specific areas within the domain they cover

Search for at least 8-10 candidates before filtering.

## Step 3: Score Candidates

Score each candidate on avatar viability (0-5 per dimension):

| Dimension | What to look for | 5 = ideal |
|-----------|-----------------|-----------|
| **Books** | Published works with principles, not just stories | 3+ books on the domain |
| **Blog/Active writing** | Current thinking, not just historical | Active blog/newsletter with weekly+ posts |
| **Talks/Video** | Voice, framing, argument style visible | Multiple conference talks on YouTube |
| **Named frameworks** | Specific models people reference by name | 3+ named frameworks widely known |
| **Strong opinions** | Anti-patterns, refusals, controversial positions | Known for what they reject, not just what they advocate |
| **Domain intersection** | Shares domains with existing avatars | Triggers team creation (tests the system) |

**Total score**: 0-30. Candidates below 15 are unlikely to produce good avatars (not enough source material for deep extraction).

## Step 4: Check for Existing Avatars

For each candidate, also check:
- Do they intersect with any existing avatar's domains? (Note which ones)
- Would creating this avatar trigger a domain team reconciliation?

## Step 5: Present Candidates

Use AskUserQuestion with `multiSelect: true` to present the top 5-7 candidates:

For each candidate, show:
- Name
- Score (X/30)
- Key works (1-2 most important)
- Domain coverage
- Intersection note (if applicable)

Options should be the candidate names. Let the user select one or more.

Example:

```
"Which experts should we create avatars for?"

- "Robert Martin (26/30)" — Clean Code, SOLID. Intersects with Beck on engineering.
- "Martin Fowler (28/30)" — Refactoring, PoEAA. Intersects with Beck on engineering.
- "Gene Kim (24/30)" — Phoenix Project, Three Ways. New domain: devops.
- "Simon Sinek (22/30)" — Start With Why, Infinite Game. New domain: leadership.
```

## Step 6: Hand Off to avatar-create

For each selected candidate, report:
- Expert name
- Recommended primary domain
- Recommended secondary domains
- Key sources to start with
- Intersection notes

Then suggest: "Run `/avatar-create {name}` to build the avatar."

If multiple candidates were selected, suggest running them in sequence (each one may trigger reconciliation that affects the next).

---

## Completion

- At least 5 candidates researched and scored
- User selected one or more
- Handoff instructions provided
