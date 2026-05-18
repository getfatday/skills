#!/usr/bin/env python3
"""
Generic document enrichment backbone.

Scans instances of a document type for missing or legacy-format
relationship-field values and proposes replacements via fuzzy-match
against candidate target-type instances. Parameterized entirely by
the type's declared relationships in `.config/documents/types/{type}.md`
— zero hardcoded type names.

Modes:
  python3 enrich.py --portfolio <root> --type <name> [--field <f>]
      Emit YAML proposals to stdout (dry-run).

  python3 enrich.py --portfolio <root> --apply <mapping.yaml>
      Apply confirmed proposals from the edited YAML file.

  python3 enrich.py --portfolio <root> --type <name> --apply-dry-run
      (Reserved) simulate apply without writing.

A per-type scoring override can live at
`.config/documents/types/{name}.skill.md` under a `## Enrichment` block
— keys `extra_weight`, `stopwords`, `score_threshold`. This module
loads it if present; otherwise uses defaults.

Idempotent: sessions whose relationship fields already resolve to
existing instances produce no proposal.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional, Iterable


# ----- Frontmatter parsing ----------------------------------------------------

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
KEY_RE = re.compile(r"^([a-zA-Z0-9_-]+):\s*(.*)$")


def read_frontmatter(path: pathlib.Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        km = KEY_RE.match(line)
        if km:
            key, val = km.group(1), km.group(2).strip()
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            fm[key] = val
    return fm


# ----- Type definition parsing ------------------------------------------------


@dataclass
class Relationship:
    field_name: str
    target_type: str
    cardinality: str  # "one" or "many"


@dataclass
class TypeDef:
    name: str
    display: str
    fields: dict  # field name -> type (e.g., "link", "links", "string")
    relationships: list  # list of Relationship
    raw_path: pathlib.Path


def parse_type_def(path: pathlib.Path) -> Optional[TypeDef]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    name = display = None
    fields: dict = {}
    rels: list = []

    in_identity = False
    in_fields = False
    in_rels = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            heading = line[3:].strip().lower()
            in_identity = heading == "identity"
            in_fields = heading == "fields"
            in_rels = heading == "relationships"
            continue

        if in_identity and line.startswith("- "):
            body = line[2:].strip()
            if body.startswith("name:"):
                name = body[5:].strip().split("—")[0].strip()
            elif body.startswith("display:"):
                display = body[8:].strip().split("—")[0].strip()

        if in_fields and line.startswith("- `"):
            # - `field: type` — description
            m = re.match(r"- `([a-zA-Z0-9_-]+):\s*([^`]+)`", line)
            if m:
                fname, ftype = m.group(1), m.group(2).strip()
                fields[fname] = ftype

        if in_rels and line.startswith("- links-to:"):
            # - links-to: target-type via field — cardinality — description
            m = re.match(
                r"- links-to:\s*([a-zA-Z0-9_-]+)\s+via\s+([a-zA-Z0-9_-]+)\s*(?:—\s*(one|many))?",
                line,
            )
            if m:
                rels.append(
                    Relationship(
                        field_name=m.group(2),
                        target_type=m.group(1),
                        cardinality=m.group(3) or "one",
                    )
                )

    if not name:
        return None

    return TypeDef(
        name=name,
        display=display or name,
        fields=fields,
        relationships=rels,
        raw_path=path,
    )


def parse_sidecar(path: pathlib.Path) -> dict:
    """Parse {type}.skill.md for Enrichment overrides.

    Looks for a `## Enrichment` section with key-value lines.
    Returns a dict — possibly empty.
    """
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    out: dict = {}
    in_section = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            in_section = line[3:].strip().lower() == "enrichment"
            continue
        if in_section and line.startswith("- "):
            body = line[2:].strip()
            m = re.match(r"([a-z_]+):\s*(.+)$", body)
            if m:
                k, v = m.group(1), m.group(2).strip()
                if v.startswith("[") and v.endswith("]"):
                    out[k] = [i.strip() for i in v[1:-1].split(",") if i.strip()]
                else:
                    try:
                        out[k] = int(v)
                    except ValueError:
                        out[k] = v
    return out


# ----- Path resolution --------------------------------------------------------


def load_root(portfolio: pathlib.Path) -> dict:
    root_path = portfolio / ".config" / "documents" / "root.md"
    if not root_path.exists():
        return {}
    text = root_path.read_text(encoding="utf-8")
    out = {}
    in_conf = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            in_conf = line[3:].strip().lower() == "configuration"
            continue
        if in_conf and line.startswith("- "):
            body = line[2:].strip()
            m = re.match(r"([a-zA-Z0-9_-]+):\s*(.+)$", body)
            if m:
                out[m.group(1)] = m.group(2).strip()
    return out


def parse_collections_table(type_def_path: pathlib.Path) -> list:
    """Return list of dicts: {collection, type, key, path}"""
    if not type_def_path.exists():
        return []
    text = type_def_path.read_text(encoding="utf-8")
    rows = []
    in_coll = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            h = line[3:].strip().lower()
            in_coll = h == "collections"
            continue
        if in_coll and line.startswith("|") and "---" not in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 4 and cells[0].lower() != "collection":
                rows.append(
                    {
                        "collection": cells[0],
                        "type": cells[1],
                        "key": cells[2],
                        "path": cells[3],
                    }
                )
    return rows


def resolve_instances_glob(portfolio: pathlib.Path, type_name: str) -> list:
    """Return absolute Path objects for every instance of `type_name`.

    Falls back to scanning the portfolio for files with `type: {type_name}`
    in frontmatter when path resolution is ambiguous.
    """
    types_dir = portfolio / ".config" / "documents" / "types"
    results: set = set()

    # Strategy 1: look through every type definition's Collections table
    # for rows where type == type_name, resolve the path pattern's parent.
    if types_dir.exists():
        for tdef in types_dir.glob("*.md"):
            if tdef.name.endswith(".skill.md"):
                continue
            for row in parse_collections_table(tdef):
                if row["type"] == type_name:
                    # Pattern: `./Sessions/{key}.md` → parent dir `Sessions`
                    path_pattern = row["path"].lstrip("./")
                    parent = path_pattern.split("/")[0] if "/" in path_pattern else ""
                    if parent:
                        for f in (portfolio / parent).glob("**/*.md"):
                            if f.name == "index.md":
                                continue
                            results.add(f)

    # Strategy 2 (fallback): scan portfolio for `type: {type_name}` files
    if not results:
        for f in portfolio.glob("**/*.md"):
            parts = f.relative_to(portfolio).parts
            if any(
                p in (".config", ".claude", ".git", ".githooks", "scripts", "docs")
                for p in parts
            ):
                continue
            fm = read_frontmatter(f)
            if fm.get("type") == type_name:
                results.add(f)

    return sorted(results)


# ----- Fuzzy matching ---------------------------------------------------------


def slug_simplify(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def tokenize(s: str) -> set:
    return set(re.findall(r"[a-z]+", (s or "").lower()))


@dataclass
class MatchConfig:
    stopwords: set = field(default_factory=lambda: set())
    score_threshold: int = 30
    extra_weight: dict = field(default_factory=dict)
    skip_fields: set = field(default_factory=set)


def fuzzy_match_target(
    source_hints: list, targets: list, config: MatchConfig
) -> Optional[tuple]:
    """Score each target against the concatenated source hints.

    Returns (target_name, reason, confidence) for the best match, or None.
    """
    if not targets:
        return None

    # Canonical slug of the joined source hints, for exact-match scoring
    joined = " ".join(h for h in source_hints if h)
    joined_simple = slug_simplify(joined)

    # Tokenize all source hints, drop stopwords
    source_tokens: set = set()
    for hint in source_hints:
        if not hint:
            continue
        for tok in tokenize(hint):
            if tok not in config.stopwords and len(tok) > 2:
                source_tokens.add(tok)

    scored = []
    for target in targets:
        target_simple = slug_simplify(target)
        target_tokens = tokenize(target) - config.stopwords
        score = 0
        reason_parts = []

        # Exact slug match
        if joined_simple and joined_simple == target_simple:
            score += 100
            reason_parts.append("slug_exact")
        elif target_simple and target_simple in joined_simple:
            score += 60
            reason_parts.append("source_contains_target")
        elif joined_simple and joined_simple in target_simple:
            score += 40
            reason_parts.append("target_contains_source")

        common = source_tokens & target_tokens
        if len(common) >= 2:
            score += 20 + 10 * len(common)
            reason_parts.append(f"token_overlap({','.join(sorted(common))})")
        elif len(common) == 1:
            tok = next(iter(common))
            if len(tok) > 3:
                score += 15
                reason_parts.append(f"token_{tok}")

        # Per-type extra weights (e.g. handle_contains_target)
        for key, weight in config.extra_weight.items():
            if key.startswith("token:") and key[6:] in target_tokens:
                score += int(weight)
                reason_parts.append(f"pref_{key[6:]}")

        if score > 0:
            scored.append((score, target, " + ".join(reason_parts) or "weak"))

    scored.sort(reverse=True)
    if not scored:
        return None
    top_score, top_target, top_reason = scored[0]

    if top_score < config.score_threshold:
        return None

    if top_score >= 60:
        conf = "high"
    elif top_score >= 30:
        conf = "medium"
    else:
        conf = "low"
    return (top_target, top_reason, conf)


# ----- Proposal generation ----------------------------------------------------


@dataclass
class Proposal:
    instance_file: str
    type: str
    field: str
    current_value: Optional[str]
    proposed_value: Optional[str]
    proposed_create: Optional[str]
    reason: str
    confidence: str  # high / medium / low / none


def is_legacy_wikilink(val: str) -> bool:
    if not val or not val.startswith("[["):
        return False
    inner = val.strip("[]")
    return "/" not in inner and "|" not in inner


def extract_legacy_name(val: str) -> Optional[str]:
    inner = val.strip("[]")
    if "/" in inner or "|" in inner:
        return None
    return inner.strip() or None


def format_wikilink(target_path_rel: str, display: str) -> str:
    """Wrap a wikilink in quotes; assume display is non-empty."""
    return f'"[[{target_path_rel}|{display}]]"'


def target_wikilink_for(portfolio: pathlib.Path, target_type: str, target_name: str) -> str:
    """Given a target type and instance name, return the canonical wikilink.

    Strategy: locate the target type's instance file; express the link as
    `Portfolio-relative-dir/name/index|name` for hub-style types (dir
    contains index.md), else `dir/file|name`.
    """
    # Look for a matching instance in any hosting directory
    type_def = portfolio / ".config" / "documents" / "types" / f"{target_type}.md"
    for row in parse_collections_table(type_def):  # no-op if not self-host
        pass

    # Brute: search portfolio for a file matching the name
    candidates = list(portfolio.glob(f"**/{target_name}/index.md"))
    if candidates:
        rel = candidates[0].relative_to(portfolio).with_suffix("")
        return f'"[[{rel}|{target_name}]]"'
    candidates = list(portfolio.glob(f"**/{target_name}.md"))
    if candidates:
        rel = candidates[0].relative_to(portfolio).with_suffix("")
        return f'"[[{rel}|{target_name}]]"'
    return f'"[[{target_name}]]"'


def list_target_instances(portfolio: pathlib.Path, target_type: str) -> list:
    """Return display-name strings for all instances of target_type."""
    paths = resolve_instances_glob(portfolio, target_type)
    names = []
    for p in paths:
        # Hub style: Projects/EGDS Sprites/index.md → name is parent dir name
        if p.name == "index.md":
            names.append(p.parent.name)
        else:
            names.append(p.stem)
    return sorted(set(names))


def propose_for_instance(
    portfolio: pathlib.Path,
    instance: pathlib.Path,
    type_def: TypeDef,
    target_lists: dict,  # target_type -> [names]
    config: MatchConfig,
    restrict_field: Optional[str] = None,
) -> Iterable[Proposal]:
    fm = read_frontmatter(instance)
    if fm.get("type") != type_def.name:
        return

    # Build the source hints: frontmatter values excluding known link fields
    # plus the filename stem (this is usually the most informative)
    source_hints = [instance.stem]
    for key, val in fm.items():
        if type_def.fields.get(key) in ("link", "links"):
            continue
        if key in ("type", "created", "inferred", "status"):
            continue
        source_hints.append(val)

    # The current instance's own "name" (filename stem or index.md's parent)
    self_name = instance.parent.name if instance.name == "index.md" else instance.stem

    for rel in type_def.relationships:
        if restrict_field and rel.field_name != restrict_field:
            continue
        if rel.field_name in config.skip_fields:
            continue
        current = fm.get(rel.field_name)
        # Exclude self-reference: if the relationship targets the same type
        # as the source, remove the current instance from candidate targets.
        targets = [t for t in target_lists.get(rel.target_type, []) if t != self_name]

        # Case A: field missing entirely — propose fuzzy match
        if not current:
            match = fuzzy_match_target(source_hints, targets, config)
            if match:
                name, reason, conf = match
                yield Proposal(
                    instance_file=str(instance.relative_to(portfolio)),
                    type=type_def.name,
                    field=rel.field_name,
                    current_value=None,
                    proposed_value=target_wikilink_for(
                        portfolio, rel.target_type, name
                    ),
                    proposed_create=None,
                    reason=f"fuzzy_match: {reason}",
                    confidence=conf,
                )
            else:
                # No match — propose creating a new instance named after
                # the source filename (Title Case)
                proposed = " ".join(
                    w.capitalize() for w in re.split(r"[-_]+", instance.stem) if w
                )
                yield Proposal(
                    instance_file=str(instance.relative_to(portfolio)),
                    type=type_def.name,
                    field=rel.field_name,
                    current_value=None,
                    proposed_value=None,
                    proposed_create=f"{rel.target_type}:{proposed}",
                    reason="no_match — propose creating new target",
                    confidence="none",
                )
            continue

        # Case B: legacy bare wikilink [[Name]] — normalize if Name exists
        if is_legacy_wikilink(current):
            legacy = extract_legacy_name(current)
            if legacy and legacy in targets:
                yield Proposal(
                    instance_file=str(instance.relative_to(portfolio)),
                    type=type_def.name,
                    field=rel.field_name,
                    current_value=current,
                    proposed_value=target_wikilink_for(
                        portfolio, rel.target_type, legacy
                    ),
                    proposed_create=None,
                    reason="normalize_legacy_wikilink",
                    confidence="high",
                )
            elif legacy:
                yield Proposal(
                    instance_file=str(instance.relative_to(portfolio)),
                    type=type_def.name,
                    field=rel.field_name,
                    current_value=current,
                    proposed_value=None,
                    proposed_create=f"{rel.target_type}:{legacy}",
                    reason="legacy_wikilink_points_to_nonexistent_target",
                    confidence="low",
                )
            continue

        # Case C: already normalized — nothing to do
        continue


# ----- Apply ------------------------------------------------------------------


def apply_mapping(portfolio: pathlib.Path, mapping_file: pathlib.Path, dry_run: bool = False) -> dict:
    text = mapping_file.read_text(encoding="utf-8")
    blocks = re.split(r"^\s*-\s*instance_file:", text, flags=re.MULTILINE)
    changes = {"applied": 0, "skipped": 0, "created": 0, "errors": []}
    for block in blocks[1:]:
        lines = block.splitlines()
        data = {"instance_file": lines[0].strip() if lines else ""}
        for line in lines[1:]:
            m = re.match(r"\s{4,}([a-z_]+):\s*(.*)$", line)
            if m:
                k, v = m.group(1), m.group(2).strip()
                data[k] = None if v == "null" else v

        if str(data.get("confirmed", "false")).lower() != "true":
            changes["skipped"] += 1
            continue

        instance_path = portfolio / data["instance_file"]
        if not instance_path.exists():
            changes["errors"].append(f"instance not found: {data['instance_file']}")
            continue

        new_value = data.get("proposed_value")
        create_spec = data.get("proposed_create")
        field_name = data.get("field")

        if create_spec and not new_value and ":" in create_spec:
            target_type, new_name = create_spec.split(":", 1)
            # Scaffold a new hub: portfolio/<TitleCase target type>/<name>/index.md
            # (or the portfolio's configured path pattern if discoverable)
            target_dir = portfolio / f"{target_type.title()}s"
            instance_dir = target_dir / new_name
            if not instance_dir.exists():
                if not dry_run:
                    instance_dir.mkdir(parents=True, exist_ok=True)
                    (instance_dir / "index.md").write_text(
                        f'---\ntype: {target_type}\nname: "{new_name}"\nstatus: Planned\ncreated: {_today()}\n---\n\n# {new_name}\n\n',
                        encoding="utf-8",
                    )
                changes["created"] += 1
            new_value = f'"[[{target_type.title()}s/{new_name}/index|{new_name}]]"'

        if new_value and field_name:
            if not dry_run:
                rewrite_field(instance_path, field_name, new_value)
            changes["applied"] += 1

    return changes


def _today() -> str:
    import datetime

    return datetime.date.today().isoformat()


def rewrite_field(path: pathlib.Path, field_name: str, new_value: str) -> None:
    """Rewrite a frontmatter field and add `inferred: true` marker."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return

    new_fm: list = []
    saw_field = False
    saw_inferred = False
    for line in lines[1:end_idx]:
        if line.startswith(f"{field_name}:"):
            new_fm.append(f"{field_name}: {new_value}")
            saw_field = True
        elif line.startswith("inferred:"):
            new_fm.append("inferred: true")
            saw_inferred = True
        else:
            new_fm.append(line)
    if not saw_field:
        new_fm.append(f"{field_name}: {new_value}")
    if not saw_inferred:
        new_fm.append("inferred: true")

    out = ["---", *new_fm, "---", *lines[end_idx + 1 :]]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


# ----- CLI --------------------------------------------------------------------


def print_proposals(proposals: list) -> None:
    print("# Document enrichment proposals")
    print(f"# {len(proposals)} proposals generated")
    print("")
    print("proposals:")
    for p in proposals:
        d = asdict(p)
        print(f"  - instance_file: {d['instance_file']}")
        print(f"    type: {d['type']}")
        print(f"    field: {d['field']}")
        print(f"    current_value: {d['current_value'] or 'null'}")
        print(f"    proposed_value: {d['proposed_value'] or 'null'}")
        print(f"    proposed_create: {d['proposed_create'] or 'null'}")
        print(f"    reason: {d['reason']}")
        print(f"    confidence: {d['confidence']}")
        print("    confirmed: false  # ← change to true to apply this proposal")
        print("")


def run_scan(portfolio: pathlib.Path, type_name: str, field_name: Optional[str]) -> int:
    type_def_path = portfolio / ".config" / "documents" / "types" / f"{type_name}.md"
    type_def = parse_type_def(type_def_path)
    if not type_def:
        print(f"ERROR: cannot parse type definition at {type_def_path}", file=sys.stderr)
        return 2
    sidecar = parse_sidecar(
        portfolio / ".config" / "documents" / "types" / f"{type_name}.skill.md"
    )
    config = MatchConfig(
        stopwords=set(sidecar.get("stopwords", [])),
        score_threshold=int(sidecar.get("score_threshold", 30)),
        extra_weight=sidecar.get("extra_weight", {}) if isinstance(sidecar.get("extra_weight"), dict) else {},
        skip_fields=set(sidecar.get("skip_fields", [])),
    )

    # Preload target instances for every relationship
    target_lists: dict = {}
    for rel in type_def.relationships:
        target_lists[rel.target_type] = list_target_instances(portfolio, rel.target_type)

    proposals: list = []
    for instance in resolve_instances_glob(portfolio, type_name):
        proposals.extend(
            propose_for_instance(
                portfolio, instance, type_def, target_lists, config, field_name
            )
        )

    print_proposals(proposals)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--portfolio", required=True, help="Path to portfolio root")
    parser.add_argument("--type", help="Document type to scan (e.g., session, epic)")
    parser.add_argument("--field", help="Restrict scan to a single relationship field")
    parser.add_argument("--apply", metavar="MAPPING_FILE", help="Apply confirmed proposals from a YAML file")
    parser.add_argument("--apply-dry-run", action="store_true", help="Simulate apply without writing")
    args = parser.parse_args()

    portfolio = pathlib.Path(args.portfolio).resolve()
    if not portfolio.exists():
        print(f"ERROR: portfolio not found: {portfolio}", file=sys.stderr)
        return 2

    if args.apply:
        result = apply_mapping(
            portfolio, pathlib.Path(args.apply), dry_run=args.apply_dry_run
        )
        print(f"[{'DRY' if args.apply_dry_run else 'APPLY'}] Results:", result)
        return 0

    if not args.type:
        print("ERROR: --type is required when not applying", file=sys.stderr)
        return 2

    return run_scan(portfolio, args.type, args.field)


if __name__ == "__main__":
    sys.exit(main())
