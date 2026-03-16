---
name: entertainment
description: >
  Domain knowledge for interpreting IMDB movie and TV data — ratings context,
  box office benchmarks, genre conventions, filmography patterns, and career
  analysis. Use this skill whenever presenting movie or TV data, answering
  questions about films, actors, directors, ratings, box office performance,
  or any IMDB/Cinemagoer output. Also use it when the user asks about what
  a rating means, whether a movie did well, or wants context around
  entertainment data — even if they don't explicitly say "IMDB."
user-invocable: false
allowed-tools: [Read]
---

# Entertainment — IMDB Interpretation Patterns

<objective>
Provide context for interpreting IMDB data so the agent presents meaningful
analysis, not just raw numbers. Ratings, box office, and filmography data all
carry implicit context that users expect to be surfaced.
</objective>

<concepts>

## Ratings

IMDB ratings are a 1-10 weighted average of user votes. The scale is not
linear in practice — most rated films cluster between 5.0 and 8.0.

- **7.0+** is generally well-regarded. **8.0+** is exceptional. **9.0+** is
  all-time great territory (only ~20 films in the Top 250).
- **Vote count matters as much as the score.** 10,000+ votes gives a stable
  rating. Under 1,000 is volatile and should be flagged as such. Under 100
  is essentially anecdotal.
- **Survivorship bias:** Older classics rate higher because poorly-rated old
  films are forgotten. A 7.5 from 2024 and a 7.5 from 1960 don't mean the
  same thing in terms of quality relative to era.
- **Fan voting:** Popular franchises (Marvel, Star Wars, Nolan) get inflated
  ratings from dedicated fanbases, especially in the first few weeks after
  release. Mention this context when relevant.
- **TV vs film:** TV ratings tend to be slightly higher because viewers
  self-select — people who dislike a show stop watching and stop rating.

## Box Office

Box office numbers need context to be meaningful. Raw gross tells you almost
nothing without production budget and comparable films.

- **Opening weekend** = first Fri-Sun domestic (US/Canada) gross.
  - $100M+ opening: blockbuster-level (2020s benchmark)
  - $50-100M: strong wide release
  - $20-50M: solid performer
  - Under $20M: modest or limited release
- **Legs** = total domestic gross / opening weekend. This measures staying
  power and word-of-mouth.
  - Under 2x: front-loaded (often franchise/sequel pattern)
  - 2-3x: normal
  - 3x+: strong word-of-mouth or awards buzz
  - 5x+: exceptional cultural moment
- **International split:** For major releases, international gross often
  exceeds domestic. Some genres travel better (action, animation) while
  others are more domestic-heavy (comedy, drama).
- **Break-even rule of thumb:** A film typically needs 2-2.5x its production
  budget in total worldwide gross to break even, because marketing costs
  roughly equal production costs. So a $200M budget film needs ~$400-500M
  worldwide to profit.
- **Inflation:** Comparing box office across decades without inflation
  adjustment is misleading. Mention this when users compare modern films to
  classics.

## Filmography Patterns

Career data tells stories that individual film data doesn't.

- **Director consistency:** Directors with 7.0+ ratings across 5+ films
  indicate reliable quality. Directors with high variance suggest they're
  interesting but unpredictable.
- **Actor career arcs:** Look for peak periods, genre shifts, and comeback
  patterns. An actor's filmography often clusters by decade.
- **Character actors** appear in many films with smaller roles — high film
  count with few leading roles is the signature.
- **Awards data** from Cinemagoer can be incomplete, especially for non-Oscar
  awards. Caveat this when presenting it.
- **Collaboration patterns:** Recurring director-actor or actor-actor pairings
  are worth noting when they appear in filmography data.

## Genres

Genre classification on IMDB is user-generated and carries its own quirks.

- **Drama** is the most common tag and least specific. It's often paired with
  something more descriptive (Drama/Thriller, Drama/Romance).
- A film typically has 2-3 genre tags. The first listed is usually the
  primary genre.
- **Genre expectations matter for ratings.** A 6.5 horror film is above
  average for the genre (horror rates lower on average). A 6.5 drama is
  mediocre. Frame ratings relative to genre norms when possible.
- **Genre blending** has increased over time. Modern films are harder to
  classify than older ones.

## Interpretation Guidelines

1. **Context over numbers.** "$50M opening weekend" means nothing without
   knowing the budget, genre, and competition. Always frame data in context.
2. **Don't make subjective recommendations.** "You should watch this" is out
   of scope. "This is rated 8.2 with 500K votes, making it one of the
   highest-rated films of 2024" lets the user decide.
3. **Don't compare talents.** Compare filmography data, not "who is better."
4. **Flag data limitations.** Cinemagoer data can be incomplete for newer or
   less popular titles. Say so rather than presenting partial data as complete.
5. **Present data and context, let the user draw conclusions.** The skill
   provides vocabulary and benchmarks. Opinions are for the user.

</concepts>

<boundaries>
## What This Skill Does NOT Cover
- Subjective movie recommendations ("you should watch this")
- Box office predictions or forecasting
- Talent comparisons or rankings beyond data (ratings, gross)
- Streaming platform availability or pricing
- Behind-the-scenes production details not in IMDB data
- Music, games, or non-film/TV entertainment
</boundaries>
