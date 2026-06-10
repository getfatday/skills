# Enrichment Sidecar Examples

`document-enrich` uses defaults out of the box. Per-type customization lives
in `.config/documents/types/{name}.skill.md` under a `## Enrichment` block.
The backbone (`scripts/enrich.py`) reads the sidecar at scan time; the
skill body never parses it directly. If the block is absent, defaults
apply.

See `custom-logic-schema.md` in the `document-define` skill for the full
sidecar grammar. This reference shows working `## Enrichment` blocks for
the common cases.

## Minimum useful sidecar

No customization — scan uses built-in stopwords (none), threshold (30),
and scans every `links-to` relationship:

```markdown
# Session — Custom Logic
## Enrichment
```

The empty block is a signal to the scanner that the sidecar is
intentional. For types that need no customization at all, omit the
`.skill.md` file entirely.

## Case 1: Skip fields the hook already populates

Scenario: `parent-session` is populated by a PreToolUse spawn hook
(see `inheritance.md`). Fuzzy-matching that field would produce noisy
self-referential proposals.

```markdown
# Session — Custom Logic

## Enrichment
- skip_fields: [parent-session]
```

Result: scan only runs on `project:` and any other relationship field
NOT in the skip list.

## Case 2: Add stopwords for noisy filenames

Scenario: every session filename starts with a date prefix
(`2026-04-18_...`). Those numeric tokens overlap between unrelated
sessions and inflate the score. Also: words like "workmux" appear in
every handle but aren't meaningful matches.

```markdown
# Session — Custom Logic

## Enrichment
- stopwords: [workmux, session, the, a, and, of, to, for, with, by]
```

Result: the scorer ignores these tokens when computing overlap. Dates
are already filtered (the tokenizer keeps only alphabetic runs).

## Case 3: Bias toward a preferred target token

Scenario: sessions about "egds" should preferentially match the `EGDS`
project when multiple candidates tie.

```markdown
# Session — Custom Logic

## Enrichment
- extra_weight:
    token:egds: 25
```

Result: any candidate whose tokenized name contains `egds` gets +25
score. Combine multiple entries for multiple biases. Keys must follow
`token:<word>` format.

## Case 4: Raise the confidence floor for a noisy type

Scenario: `task` instances have short filenames that produce weak
matches; you want only strong proposals to surface.

```markdown
# Task — Custom Logic

## Enrichment
- score_threshold: 50
```

Result: the scorer still computes scores for every candidate, but
proposals below the threshold are dropped. Default is 30; higher =
stricter.

## Case 5: Composite — real-world session sidecar

Combining the above:

```markdown
# Session — Custom Logic

## Enrichment
- stopwords: [workmux, session, and, the, a, of, with, for]
- score_threshold: 40
- skip_fields: [parent-session, related-sessions]
- extra_weight:
    token:egds: 20
    token:portfolio: 15
```

This is roughly the configuration the expedia vault uses. Tokens like
`egds` and `portfolio` get bumped; weak matches below 40 are hidden;
fields populated by hooks are skipped.

## What the scan output looks like

Regardless of sidecar config, the proposal YAML is identical in shape:

```yaml
proposals:
  - instance_file: Sessions/2026-04-12_asset-cache-core.md
    type: session
    field: project
    current_value: "[[Egds Asset Cache]]"
    proposed_value: "[[Projects/Egds Asset Cache/index|Egds Asset Cache]]"
    proposed_create: null
    reason: normalize_legacy_wikilink
    confidence: high
    confirmed: false  # ← user flips to true to apply
```

The `reason` trace shows which scorer contributed (`token_overlap`,
`source_contains_target`, `pref_egds` for an extra-weight hit, etc.).
Useful for debugging false positives and tuning thresholds.

## When a sidecar is wrong

The scanner silently ignores malformed entries (unknown keys, bad
types, missing values). It does NOT error. If proposals look off:

1. Print the effective config by running the backbone with
   `--type {name}` and inspecting the first few proposals' `reason`
   field.
2. If `reason` shows scoring from a token you put in `stopwords`, the
   sidecar wasn't parsed correctly — check for typos and indentation
   (two-space indent under `extra_weight:`).
3. Default config always wins over a malformed override.
