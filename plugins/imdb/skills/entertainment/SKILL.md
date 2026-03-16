---
name: entertainment
description: Domain knowledge for interpreting IMDB movie and TV data — ratings, box office, awards context
---

<objective>
Provide context for interpreting IMDB data: what ratings mean, how box office numbers compare, genre conventions, and career patterns.
</objective>

<summary>
Domain knowledge for making IMDB data meaningful. Not a recommendation engine. Provides vocabulary and context for understanding what the data means.
</summary>

<interpretation_patterns>

## Ratings
- IMDB ratings are 1-10 scale, weighted average of user votes
- 7.0+ is generally well-regarded. 8.0+ is exceptional. 9.0+ is all-time great territory.
- Vote count matters: 10,000+ votes gives a stable rating. Under 1,000 is volatile.
- Ratings skew higher for older classics (survivorship bias) and popular franchises (fan voting).

## Box Office
- "Opening weekend" is the first Fri-Sun domestic gross
- $100M+ opening weekend is a blockbuster-level opening (as of 2020s)
- "Legs" = total gross / opening weekend. 3x+ means strong word-of-mouth.
- International gross often exceeds domestic for big franchises.
- Budget comparisons: a film typically needs 2-2.5x its production budget in total gross to break even (marketing costs).

## Filmography Patterns
- Directors with consistent 7.0+ ratings across multiple films indicate reliable quality
- "Character actors" appear in many films with smaller roles
- Awards recognition (Oscar, Golden Globe) data may be incomplete in Cinemagoer

## Genres
- Genre classifications on IMDB are user-generated and can be broad
- A film often has 2-3 genre tags
- "Drama" is the most common tag and least specific

</interpretation_patterns>

<boundaries>
- Do not make subjective recommendations ("you should watch this")
- Do not predict box office performance
- Do not compare actors' talents, only their filmography data
- Present data and context, let the user draw conclusions
</boundaries>
