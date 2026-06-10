#!/usr/bin/env python3
"""
contradiction-cluster.py — deterministic clustering for the inferred
contradiction sweep (Check 6b in document-lint).

This script does NOT call any LLM. It walks the portfolio, builds two
adjacency relations, and emits the clusters as JSON for the SKILL.md
prompt to consume. The LLM call is the SKILL.md's job (mechanism /
policy split: cluster = mechanism, contradiction judgement = policy).

Two cluster signals (configurable, default ON):

  - shared-links: every pair of docs with N or more `links-to`-typed
    wikilink fields pointing at the same target. Default N = 3.
  - shared-topics: every pair of docs whose `tags` or `topics`
    frontmatter overlap by ≥ 1 entry.

Two docs join the same cluster if either signal connects them
(transitive closure). Clusters of size < 2 are dropped.

Cluster cap: `--max-clusters` (default 50) bounds the number of
clusters returned. Once exceeded, clusters are sorted by descending
score (sum of shared signals across all pairs in the cluster) and
truncated. The truncation is reflected in `stats.truncated`.

Estimated tokens: 4 chars/token over the doc bodies plus a fixed prompt
overhead. Used by the `--dry-run` reporting path in SKILL.md.

Mirrors plugins/document/skills/document-enrich/scripts/enrich.py for
argparse style and portfolio walking.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from dataclasses import dataclass, field
from typing import Optional


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]")
KEY_RE = re.compile(r"^([a-zA-Z0-9_-]+):\s*(.*)$")
SKIP_DIRS = {".config", ".claude", ".git", ".githooks", "scripts", "docs", ".cache"}
TOPIC_FIELDS = ("tags", "topics", "categories")
DEFAULT_MIN_SHARED_LINKS = 3
DEFAULT_MAX_CLUSTERS = 50
DEFAULT_MAX_CLUSTER_SIZE = 12
TOKENS_PER_CHAR = 0.25  # ~ 4 chars per token


# ----- Frontmatter parsing (mirrors enrich.py) ------------------------------


def read_frontmatter_block(path: pathlib.Path) -> Optional[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = FRONTMATTER_RE.match(text)
    return m.group(1) if m else None


def parse_fm_lines(block: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    cur_key: Optional[str] = None
    cur_list: list[str] = []
    for raw_line in block.splitlines():
        if raw_line.startswith(("  ", "\t", "- ")) and cur_key:
            stripped = raw_line.strip()
            if stripped.startswith("- "):
                cur_list.append(stripped[2:].strip())
            continue
        if cur_key:
            if cur_list:
                rows.append((cur_key, "\n".join(f"- {item}" for item in cur_list)))
                cur_list = []
            cur_key = None
        line = raw_line.rstrip()
        if not line or line.startswith("#"):
            continue
        m = KEY_RE.match(line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if not val:
            cur_key = key
            cur_list = []
            continue
        if val.startswith('"') and val.endswith('"'):
            val = val[1:-1]
        rows.append((key, val))
    if cur_key and cur_list:
        rows.append((cur_key, "\n".join(f"- {item}" for item in cur_list)))
    return rows


# ----- Type-def lookup for link-typed fields --------------------------------


def link_fields_by_type(portfolio: pathlib.Path) -> dict[str, set[str]]:
    """For each declared type, return the set of frontmatter fields
    declared as `link` or `links` in its `## Fields` section."""
    out: dict[str, set[str]] = {}
    types_dir = portfolio / ".config" / "documents" / "types"
    if not types_dir.exists():
        return out
    for tdef in types_dir.glob("*.md"):
        if tdef.name.endswith(".skill.md"):
            continue
        try:
            text = tdef.read_text(encoding="utf-8")
        except OSError:
            continue
        # Identity: name slug
        name = None
        in_identity = False
        in_fields = False
        link_fields: set[str] = set()
        for raw in text.splitlines():
            line = raw.strip()
            if line.startswith("## "):
                heading = line[3:].strip().lower()
                in_identity = heading == "identity"
                in_fields = heading == "fields"
                continue
            if in_identity and line.startswith("- name:"):
                name = line[len("- name:") :].strip().split("—")[0].strip()
            if in_fields and line.startswith("- `"):
                m = re.match(r"- `([a-zA-Z0-9_-]+):\s*([^`]+)`", line)
                if m:
                    fname, ftype = m.group(1), m.group(2).strip()
                    if ftype in ("link", "links"):
                        link_fields.add(fname)
        if name:
            out[name] = link_fields
    return out


# ----- Doc walk -------------------------------------------------------------


@dataclass
class DocSig:
    path: pathlib.Path
    rel: str
    type: Optional[str]
    link_targets: set[str] = field(default_factory=set)
    topics: set[str] = field(default_factory=set)
    body_len: int = 0


def walk_docs(
    portfolio: pathlib.Path, type_filter: Optional[str]
) -> list[DocSig]:
    type_links = link_fields_by_type(portfolio)
    docs: list[DocSig] = []
    for path in sorted(portfolio.glob("**/*.md")):
        rel_parts = path.relative_to(portfolio).parts
        if any(p in SKIP_DIRS for p in rel_parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = FRONTMATTER_RE.match(text)
        if not m:
            continue
        body = text[m.end() :]
        rows = parse_fm_lines(m.group(1))
        fm_dict: dict[str, str] = {}
        for k, v in rows:
            fm_dict.setdefault(k, v)
        doc_type = fm_dict.get("type")
        if not doc_type:
            continue
        if type_filter and doc_type != type_filter:
            continue
        link_field_names = type_links.get(doc_type, set())
        targets: set[str] = set()
        for k, v in rows:
            if k not in link_field_names:
                continue
            for hit in WIKILINK_RE.finditer(v):
                targets.add(hit.group(1).strip())
        topics: set[str] = set()
        for tf in TOPIC_FIELDS:
            v = fm_dict.get(tf)
            if not v:
                continue
            # Both "[a, b]" and "- a\n- b" parse to a list of strings
            if v.startswith("- "):
                for line in v.splitlines():
                    item = line.lstrip("- ").strip()
                    if item:
                        topics.add(item.lower())
            else:
                stripped = v.strip("[] ")
                for item in stripped.split(","):
                    s = item.strip().strip("'\"")
                    if s:
                        topics.add(s.lower())
        docs.append(
            DocSig(
                path=path,
                rel=path.relative_to(portfolio).as_posix(),
                type=doc_type,
                link_targets=targets,
                topics=topics,
                body_len=len(body),
            )
        )
    return docs


# ----- Clustering -----------------------------------------------------------


@dataclass
class Edge:
    a: int
    b: int
    shared_links: list[str]
    shared_topics: list[str]
    score: int  # weight contribution, used to rank truncated clusters


def build_edges(docs: list[DocSig], min_shared: int) -> list[Edge]:
    edges: list[Edge] = []
    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            shared_links = sorted(docs[i].link_targets & docs[j].link_targets)
            shared_topics = sorted(docs[i].topics & docs[j].topics)
            if len(shared_links) >= min_shared or shared_topics:
                score = len(shared_links) * 2 + len(shared_topics)
                edges.append(
                    Edge(
                        a=i,
                        b=j,
                        shared_links=shared_links,
                        shared_topics=shared_topics,
                        score=score,
                    )
                )
    return edges


def union_find_clusters(
    n: int, edges: list[Edge]
) -> dict[int, list[int]]:
    """Return {root: [member indices]} via union-find on the edges."""
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for e in edges:
        union(e.a, e.b)

    out: dict[int, list[int]] = {}
    for i in range(n):
        out.setdefault(find(i), []).append(i)
    return out


# ----- Output assembly ------------------------------------------------------


@dataclass
class Cluster:
    id: int
    docs: list[str]
    types: list[str]
    shared_links: list[str]
    shared_topics: list[str]
    score: int
    estimated_tokens: int
    truncated: bool = False


def assemble_clusters(
    docs: list[DocSig],
    edges: list[Edge],
    max_clusters: int,
    max_cluster_size: int,
) -> tuple[list[Cluster], dict]:
    members = union_find_clusters(len(docs), edges)
    raw_clusters: list[tuple[int, list[int], int]] = []
    for root, idxs in members.items():
        if len(idxs) < 2:
            continue
        score = 0
        for e in edges:
            if e.a in idxs and e.b in idxs:
                score += e.score
        raw_clusters.append((root, idxs, score))
    raw_clusters.sort(key=lambda t: (-t[2], -len(t[1])))
    truncated = len(raw_clusters) > max_clusters
    raw_clusters = raw_clusters[:max_clusters]

    clusters: list[Cluster] = []
    for cid, (_, idxs, score) in enumerate(raw_clusters):
        was_truncated = False
        if len(idxs) > max_cluster_size:
            idxs = sorted(idxs, key=lambda i: docs[i].body_len)[
                -max_cluster_size:
            ]
            was_truncated = True
        cluster_links: set[str] = set()
        cluster_topics: set[str] = set()
        for e in edges:
            if e.a in idxs and e.b in idxs:
                cluster_links.update(e.shared_links)
                cluster_topics.update(e.shared_topics)
        body_chars = sum(docs[i].body_len for i in idxs)
        est_tokens = int(body_chars * TOKENS_PER_CHAR) + 600  # prompt overhead
        clusters.append(
            Cluster(
                id=cid,
                docs=[docs[i].rel for i in idxs],
                types=sorted({docs[i].type for i in idxs if docs[i].type}),
                shared_links=sorted(cluster_links),
                shared_topics=sorted(cluster_topics),
                score=score,
                estimated_tokens=est_tokens,
                truncated=was_truncated,
            )
        )

    stats = {
        "total_docs_scanned": len(docs),
        "total_clusters": len(clusters),
        "estimated_total_tokens": sum(c.estimated_tokens for c in clusters),
        "truncated": truncated,
    }
    return clusters, stats


# ----- CLI ------------------------------------------------------------------


def cmd_cluster(args: argparse.Namespace) -> int:
    portfolio = pathlib.Path(args.portfolio).resolve()
    if not portfolio.exists():
        print(f"ERROR: portfolio not found: {portfolio}", file=sys.stderr)
        return 2
    docs = walk_docs(portfolio, args.type)
    edges = build_edges(docs, args.min_shared)
    clusters, stats = assemble_clusters(
        docs, edges, args.max_clusters, args.max_cluster_size
    )
    payload = {
        "stats": stats,
        "clusters": [c.__dict__ for c in clusters],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cluster portfolio docs that may contain semantic contradictions"
    )
    parser.add_argument("--portfolio", required=True, help="Portfolio root")
    parser.add_argument("--type", help="Restrict to a single document type")
    parser.add_argument(
        "--min-shared",
        type=int,
        default=DEFAULT_MIN_SHARED_LINKS,
        help=f"Minimum shared link targets (default {DEFAULT_MIN_SHARED_LINKS})",
    )
    parser.add_argument(
        "--max-clusters",
        type=int,
        default=DEFAULT_MAX_CLUSTERS,
        help=f"Cluster cap (default {DEFAULT_MAX_CLUSTERS})",
    )
    parser.add_argument(
        "--max-cluster-size",
        type=int,
        default=DEFAULT_MAX_CLUSTER_SIZE,
        help=f"Per-cluster member cap (default {DEFAULT_MAX_CLUSTER_SIZE})",
    )
    parser.set_defaults(func=cmd_cluster)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
