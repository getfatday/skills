# Contradiction-Detection Prompt Template

`document-lint --semantic` (Check 6b) calls this prompt once per
cluster returned by `contradiction-cluster.py`. The script provides
mechanism (which docs to compare); this prompt provides policy (what
counts as a contradiction).

## When to Apply

Run this prompt for every cluster reported by
`contradiction-cluster.py` whose size is ≥ 2. Skip in `--dry-run`
mode — there, the SKILL.md only echoes cluster counts and estimated
token cost from the script's `stats` block; no LLM call is made.

## Inputs

For each cluster, pass to the LLM:

- The cluster id and member doc paths
- For each member doc: `(path, frontmatter, first 200 lines of body)`
- The shared signals reported by the clustering script (
  `shared_links`, `shared_topics`)

Trim long bodies at 200 lines. The cluster cap, per-cluster member
cap, and token estimate are already enforced by
`contradiction-cluster.py`.

## Prompt

```
You are auditing a typed-document portfolio for **factual
contradictions** between documents that the clustering pass already
identified as related.

Two documents contradict each other when one asserts a claim and the
other asserts a directly incompatible claim about the same subject.

Examples that DO count:
  - Doc A: "we shipped feature X in March 2025"
    Doc B: "feature X is still in design as of June 2025"
  - Doc A: "the team reports to Lucy"
    Doc B: "the team reports to Ed"
  - Doc A: status: shipped
    Doc B (about the same project): status: planned

Examples that do NOT count:
  - One doc covers a topic in more depth than another
  - Wording differences that reduce to the same fact
  - Stale information that's clearly historical (dated entry, log entry)
  - Different perspectives on a subjective question
  - Open questions or stated alternatives
  - Documents that explicitly cite each other and disagree on purpose
    (e.g., a decision doc overriding a prior recommendation)

You will be given the docs in this cluster. For each pair of docs that
contradict each other, emit ONE JSON object:

  {"a": "<path-to-doc-A>",
   "b": "<path-to-doc-B>",
   "evidence": "<one-sentence quote or summary describing the contradiction>"}

Return all findings as a JSON array. If no contradictions exist, return
an empty array `[]`. Do not emit prose, headers, or commentary outside
the JSON.

Cluster id: {cluster_id}
Shared signals: links={shared_links} topics={shared_topics}

Documents:

----- {doc_a_path} -----
{doc_a_frontmatter_and_body}

----- {doc_b_path} -----
{doc_b_frontmatter_and_body}

(... repeat for each cluster member ...)
```

## After the LLM Responds

For each `{"a": ..., "b": ..., "evidence": ...}` object the LLM
returns:

1. Verify both `a` and `b` exist in the portfolio (defensive — the
   LLM occasionally hallucinates a path).
2. Append `[[<other-path>]]` to the `contradiction-with` field on each
   side of the pair (creating the field as a `links` list if absent).
3. Set `inferred: true` on both docs. **This marker is mandatory.**
   Without it, `document-verify-inferred` will not surface the pair
   for human review, and the contradiction is effectively buried.
4. Do NOT auto-resolve. The human owns the resolution via
   `/document:verify-inferred`.

## Cost Discipline

- Honor the cluster cap from `contradiction-cluster.py
  --max-clusters` (default 50). Do NOT loop past the JSON output.
- Per-call timeout: cap each cluster invocation at 60 seconds. If the
  LLM stalls or returns malformed JSON, log and skip the cluster.
- Skip clusters whose `estimated_tokens` exceeds 20,000 (a single
  cluster that big almost always means the clustering signals are too
  coarse — narrow `--min-shared` instead).
- `--dry-run` MUST make zero LLM calls. The dry-run path stops at the
  cluster JSON and prints the totals.

## Output Bookkeeping

After processing all clusters, emit one summary line to stdout per
flagged pair:

```
contradiction-flagged a={path-a} b={path-b} evidence="…"
```

Plus a final line:

```
semantic-sweep: clusters={N} pairs-flagged={M} llm-calls={K} skipped={S}
```

These summary lines feed directly into the unified lint report rendered
by SKILL.md.
