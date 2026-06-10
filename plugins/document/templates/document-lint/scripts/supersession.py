#!/usr/bin/env python3
"""
supersession.py — declared-supersession integrity checker.

Walks a typed-document portfolio for `supersedes:` / `superseded-by:`
frontmatter and reports four classes of violation:

  - missing-back-link  — A says `supersedes: [[B]]` but B has no
    matching `superseded-by: [[A]]`.
  - missing-forward    — B has `superseded-by: [[A]]` but A has no
    matching `supersedes: [[B]]`.
  - orphan-back-link   — `superseded-by: [[X]]` set on a doc but X is
    missing from disk.
  - cycle              — A → B → A (or longer chain returning to a
    visited node). Cycles are reported, never auto-repaired.

In `fix` mode the script writes the missing reciprocal field, marks the
superseder with `supersedes-propagated: true` (the idempotency guard),
and sets the prior doc's `status: superseded` ONLY when the prior doc's
type definition declares `superseded` as a valid status.

Mirrors plugins/document/skills/document-enrich/scripts/enrich.py for
argparse style, frontmatter parsing, and portfolio root discovery.

Stdlib-only. Atomic writes via tempfile + os.replace. Always exits 0
unless argument parsing fails.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import tempfile
from dataclasses import dataclass, field, asdict
from typing import Optional


# ----- Frontmatter helpers (mirrors enrich.py for parser, but preserves
# original line ordering so atomic-write round-trips cleanly) ----------------

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]")
KEY_RE = re.compile(r"^([a-zA-Z0-9_-]+):\s*(.*)$")
SKIP_DIRS = {".config", ".claude", ".git", ".githooks", "scripts", "docs", ".cache"}


def split_frontmatter(text: str) -> tuple[Optional[list[str]], str]:
    """Return (fm_lines, rest). fm_lines is None when no frontmatter."""
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end < 0:
        # tolerate trailing --- with no newline
        end = text.find("\n---", 4)
        if end < 0:
            return None, text
        return text[4:end].split("\n"), text[end + 4 :]
    return text[4:end].split("\n"), text[end + 5 :]


def get_fm_value(fm_lines: list[str], key: str) -> Optional[str]:
    pat = re.compile(rf"^{re.escape(key)}:\s*(.*)$")
    for line in fm_lines:
        if line.startswith(" ") or line.startswith("\t"):
            continue
        m = pat.match(line)
        if m:
            v = m.group(1).strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
                v = v[1:-1]
            return v
    return None


def set_fm_value(
    fm_lines: list[str], key: str, value: str, quote: bool = False
) -> bool:
    """Set or replace a frontmatter scalar. Returns True if the value
    actually changed (used for idempotency reporting)."""
    pat = re.compile(rf"^{re.escape(key)}:\s*(.*)$")
    rendered = f'{key}: "{value}"' if quote else f"{key}: {value}"
    for i, line in enumerate(fm_lines):
        if line.startswith(" ") or line.startswith("\t"):
            continue
        m = pat.match(line)
        if m:
            current = m.group(1).strip()
            if len(current) >= 2 and current[0] == current[-1] and current[0] in ('"', "'"):
                current = current[1:-1]
            if current == value:
                return False
            fm_lines[i] = rendered
            return True
    fm_lines.append(rendered)
    return True


def atomic_write(path: pathlib.Path, content: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-supersede.", suffix=".md")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def parse_link(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    m = WIKILINK_RE.search(value)
    return m.group(1).strip() if m else None


# ----- Type-def lookup for `status: superseded` validity --------------------


def parse_lifecycle_values(type_def_path: pathlib.Path) -> set[str]:
    """Return the set of valid status values declared in a type def's
    Lifecycle section, or empty set when no Lifecycle is declared."""
    if not type_def_path.exists():
        return set()
    try:
        text = type_def_path.read_text(encoding="utf-8")
    except OSError:
        return set()
    in_lifecycle = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            in_lifecycle = line[3:].strip().lower() == "lifecycle"
            continue
        if in_lifecycle and line.startswith("- values:"):
            body = line[len("- values:") :].strip()
            return {v.strip() for v in body.split(",") if v.strip()}
    return set()


def type_allows_superseded_status(
    portfolio: pathlib.Path, type_name: Optional[str]
) -> bool:
    if not type_name:
        return False
    type_def = portfolio / ".config" / "documents" / "types" / f"{type_name}.md"
    return "superseded" in parse_lifecycle_values(type_def)


# ----- Portfolio-wide scan --------------------------------------------------


@dataclass
class DocRecord:
    path: pathlib.Path
    rel: str
    type: Optional[str]
    supersedes: Optional[str]  # parsed wikilink target (relative path no .md)
    superseded_by: Optional[str]
    propagated: bool

    def link_to(self, portfolio: pathlib.Path) -> str:
        return self.path.relative_to(portfolio).with_suffix("").as_posix()


def scan_portfolio(
    portfolio: pathlib.Path, type_filter: Optional[str] = None
) -> dict[str, DocRecord]:
    """Walk the portfolio, return {link_target: DocRecord} for any doc
    that mentions supersedes/superseded-by. Filters to one type when
    `type_filter` is set."""
    records: dict[str, DocRecord] = {}
    for path in sorted(portfolio.glob("**/*.md")):
        rel_parts = path.relative_to(portfolio).parts
        if any(p in SKIP_DIRS for p in rel_parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm_lines, _ = split_frontmatter(text)
        if fm_lines is None:
            continue
        supersedes_raw = get_fm_value(fm_lines, "supersedes")
        superseded_by_raw = get_fm_value(fm_lines, "superseded-by")
        if not supersedes_raw and not superseded_by_raw:
            continue
        doc_type = get_fm_value(fm_lines, "type")
        if type_filter and doc_type != type_filter:
            continue
        propagated_raw = get_fm_value(fm_lines, "supersedes-propagated")
        link = path.relative_to(portfolio).with_suffix("").as_posix()
        records[link] = DocRecord(
            path=path,
            rel=path.relative_to(portfolio).as_posix(),
            type=doc_type,
            supersedes=parse_link(supersedes_raw),
            superseded_by=parse_link(superseded_by_raw),
            propagated=str(propagated_raw).lower() == "true",
        )
    return records


# ----- Violation detection --------------------------------------------------


@dataclass
class Violation:
    kind: str  # missing-back-link | missing-forward | orphan-back-link | cycle
    doc: str  # link form: "Path/Name"
    detail: str
    extra: dict = field(default_factory=dict)


def detect_violations(
    portfolio: pathlib.Path, records: dict[str, DocRecord]
) -> list[Violation]:
    violations: list[Violation] = []
    in_cycle = find_cycles(records)

    for link, rec in records.items():
        if link in in_cycle:
            violations.append(
                Violation(
                    kind="cycle",
                    doc=link,
                    detail=f"supersession cycle: {' -> '.join(in_cycle[link])}",
                    extra={"chain": in_cycle[link]},
                )
            )

        # missing-back-link: A.supersedes=B but B doesn't point back to A
        if rec.supersedes:
            target = rec.supersedes
            target_path = portfolio / f"{target}.md"
            if not target_path.exists():
                violations.append(
                    Violation(
                        kind="orphan-forward",
                        doc=link,
                        detail=f"supersedes target {target!r} not found on disk",
                        extra={"target": target},
                    )
                )
            else:
                target_rec = records.get(target)
                if target_rec is None or target_rec.superseded_by != link:
                    if link not in in_cycle:
                        violations.append(
                            Violation(
                                kind="missing-back-link",
                                doc=link,
                                detail=(
                                    f"declares supersedes [[{target}]] but "
                                    f"target lacks superseded-by: [[{link}]]"
                                ),
                                extra={"target": target},
                            )
                        )

        # missing-forward / orphan-back-link
        if rec.superseded_by:
            target = rec.superseded_by
            target_path = portfolio / f"{target}.md"
            if not target_path.exists():
                violations.append(
                    Violation(
                        kind="orphan-back-link",
                        doc=link,
                        detail=f"superseded-by target {target!r} not found on disk",
                        extra={"target": target},
                    )
                )
            else:
                target_rec = records.get(target)
                if target_rec is None or target_rec.supersedes != link:
                    if link not in in_cycle:
                        violations.append(
                            Violation(
                                kind="missing-forward",
                                doc=link,
                                detail=(
                                    f"declares superseded-by [[{target}]] but "
                                    f"target lacks supersedes: [[{link}]]"
                                ),
                                extra={"target": target},
                            )
                        )
    return violations


def find_cycles(records: dict[str, DocRecord]) -> dict[str, list[str]]:
    """Return {doc_link: cycle_chain} for every doc that participates in
    a `supersedes` cycle. The chain is the cycle path beginning at the
    doc and ending at its return to itself.
    """
    out: dict[str, list[str]] = {}
    for start in records:
        chain = [start]
        seen = {start}
        cur = start
        while True:
            rec = records.get(cur)
            if not rec or not rec.supersedes:
                break
            nxt = rec.supersedes
            if nxt == start:
                chain.append(nxt)
                for node in chain[:-1]:
                    out[node] = chain
                break
            if nxt in seen:
                # cycle that doesn't include start — start isn't in cycle
                break
            chain.append(nxt)
            seen.add(nxt)
            cur = nxt
    return out


# ----- Fix application ------------------------------------------------------


@dataclass
class FixResult:
    propagated: int = 0
    skipped: int = 0
    refused: int = 0  # cycles or unfixable
    errors: list[str] = field(default_factory=list)


def _load_record(portfolio: pathlib.Path, link: str) -> Optional[DocRecord]:
    """Load a DocRecord on demand for a doc that may not carry
    supersedes/superseded-by yet (the prior doc in a back-link write)."""
    path = portfolio / f"{link}.md"
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    fm_lines, _ = split_frontmatter(text)
    if fm_lines is None:
        return None
    return DocRecord(
        path=path,
        rel=path.relative_to(portfolio).as_posix(),
        type=get_fm_value(fm_lines, "type"),
        supersedes=parse_link(get_fm_value(fm_lines, "supersedes")),
        superseded_by=parse_link(get_fm_value(fm_lines, "superseded-by")),
        propagated=str(get_fm_value(fm_lines, "supersedes-propagated")).lower()
        == "true",
    )


def apply_fixes(
    portfolio: pathlib.Path,
    records: dict[str, DocRecord],
    violations: list[Violation],
) -> FixResult:
    """Repair missing-back-link / missing-forward violations. Other
    kinds are refused (cycles, orphans) and counted as such."""
    result = FixResult()
    cycle_docs = {v.doc for v in violations if v.kind == "cycle"}

    # Build the set of (superseder_link, prior_link) pairs to repair.
    # missing-back-link and missing-forward are symmetric pointers from
    # opposite sides of the same relationship.
    repair_pairs: set[tuple[str, str]] = set()
    for v in violations:
        if v.kind == "cycle":
            result.refused += 1
            continue
        if v.doc in cycle_docs or v.extra.get("target") in cycle_docs:
            result.refused += 1
            continue
        if v.kind == "missing-back-link":
            repair_pairs.add((v.doc, v.extra["target"]))
        elif v.kind == "missing-forward":
            repair_pairs.add((v.extra["target"], v.doc))
        elif v.kind in ("orphan-back-link", "orphan-forward"):
            result.refused += 1

    for superseder_link, prior_link in sorted(repair_pairs):
        # The superseder is always in records (it carries supersedes).
        # The prior may not be, because it only carries superseded-by
        # AFTER fix runs. Load the prior from disk if needed.
        sup_rec = records.get(superseder_link) or _load_record(
            portfolio, superseder_link
        )
        prior_rec = records.get(prior_link) or _load_record(
            portfolio, prior_link
        )
        if sup_rec is None or prior_rec is None:
            result.refused += 1
            continue
        try:
            wrote_prior = _write_back_link(portfolio, sup_rec, prior_rec)
            wrote_marker = _write_propagation_marker(sup_rec)
            if wrote_prior or wrote_marker:
                result.propagated += 1
            else:
                result.skipped += 1
        except Exception as exc:
            result.errors.append(f"{prior_rec.rel}: {exc}")
    return result


def _write_back_link(
    portfolio: pathlib.Path, sup_rec: DocRecord, prior_rec: DocRecord
) -> bool:
    """Write `superseded-by: [[superseder]]` and (when valid) `status:
    superseded` to the prior doc. Returns True if anything changed."""
    text = prior_rec.path.read_text(encoding="utf-8")
    fm_lines, body = split_frontmatter(text)
    if fm_lines is None:
        raise ValueError("no frontmatter on prior doc")
    sup_link = sup_rec.link_to(portfolio)
    changed_a = set_fm_value(
        fm_lines, "superseded-by", f"[[{sup_link}]]", quote=True
    )
    changed_b = False
    if type_allows_superseded_status(portfolio, prior_rec.type):
        changed_b = set_fm_value(fm_lines, "status", "superseded", quote=False)
    if not (changed_a or changed_b):
        return False
    new_text = "---\n" + "\n".join(fm_lines) + "\n---\n" + body
    atomic_write(prior_rec.path, new_text)
    return True


def _write_propagation_marker(sup_rec: DocRecord) -> bool:
    """Set `supersedes-propagated: true` on the superseder doc."""
    if sup_rec.propagated:
        return False
    text = sup_rec.path.read_text(encoding="utf-8")
    fm_lines, body = split_frontmatter(text)
    if fm_lines is None:
        return False
    changed = set_fm_value(fm_lines, "supersedes-propagated", "true", quote=False)
    if not changed:
        return False
    new_text = "---\n" + "\n".join(fm_lines) + "\n---\n" + body
    atomic_write(sup_rec.path, new_text)
    return True


# ----- Reporting ------------------------------------------------------------


def print_scan_report(violations: list[Violation], records_count: int) -> None:
    print(f"# supersession scan: {len(violations)} violation(s) across "
          f"{records_count} doc(s) with supersedes/superseded-by")
    if not violations:
        print("# clean")
        return
    print("")
    print("violations:")
    for v in violations:
        d = asdict(v)
        print(f"  - kind: {d['kind']}")
        print(f"    doc: {d['doc']}")
        print(f"    detail: {d['detail']}")
        if d["extra"]:
            print(f"    extra: {json.dumps(d['extra'], sort_keys=True)}")
        print("")


# ----- CLI ------------------------------------------------------------------


def cmd_scan(args: argparse.Namespace) -> int:
    portfolio = pathlib.Path(args.portfolio).resolve()
    if not portfolio.exists():
        print(f"ERROR: portfolio not found: {portfolio}", file=sys.stderr)
        return 2
    records = scan_portfolio(portfolio, args.type)
    violations = detect_violations(portfolio, records)
    print_scan_report(violations, len(records))
    return 0


def cmd_fix(args: argparse.Namespace) -> int:
    portfolio = pathlib.Path(args.portfolio).resolve()
    if not portfolio.exists():
        print(f"ERROR: portfolio not found: {portfolio}", file=sys.stderr)
        return 2
    records = scan_portfolio(portfolio, args.type)
    violations = detect_violations(portfolio, records)
    result = apply_fixes(portfolio, records, violations)
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Declared-supersession integrity checker"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="Report violations only")
    p_scan.add_argument("--portfolio", required=True, help="Portfolio root")
    p_scan.add_argument("--type", help="Restrict to a single document type")
    p_scan.set_defaults(func=cmd_scan)

    p_fix = sub.add_parser("fix", help="Repair violations where safe")
    p_fix.add_argument("--portfolio", required=True, help="Portfolio root")
    p_fix.add_argument("--type", help="Restrict to a single document type")
    p_fix.set_defaults(func=cmd_fix)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
