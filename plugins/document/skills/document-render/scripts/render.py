#!/usr/bin/env python3
"""
Portable Dataview-DQL-subset parser + renderer.

Reads a markdown file, finds ` ```dataview ` code blocks, parses a subset
of the Dataview Query Language, executes queries against the frontmatter
of `.md` files in the portfolio, and emits a rendered markdown document.

Supported DQL surface:

  TABLE WITHOUT ID col1, col2, ... FROM "folder"
    WHERE expr
    SORT col [ASC|DESC]
    LIMIT N
    GROUP BY expr

Expressions:
  field                  — frontmatter value
  file.name              — filename without extension
  file.folder            — parent directory path
  file.link              — wikilink to the file
  file.mtime             — file modification time
  file.ctime             — file creation time
  "literal"              — string literal
  123                    — number literal
  a = b, a != b          — equality
  a > b, a < b, a >= b, a <= b — numeric compare
  a AND b, a OR b, NOT a — boolean combinators
  contains(a, b)         — substring / list membership test
  choice(cond, if, else) — ternary
  date(today)            — today's date (iso)

Output modes:
  --write-companion   Write rendered output to {input}.rendered.md
  --rewrite-inline    Overwrite the input in place (use with care)
  (default)           Write to stdout

This module runs without Obsidian and without any third-party library.
"""
from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Optional


# ----- Frontmatter parsing ----------------------------------------------------

FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
KV_RE = re.compile(r"^([a-zA-Z0-9_-]+):\s*(.*)$")


def parse_frontmatter(text: str) -> dict:
    m = FM_RE.match(text)
    if not m:
        return {}
    out: dict = {}
    lines = m.group(1).splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        if not line or line.startswith("#"):
            i += 1
            continue
        kv = KV_RE.match(line)
        if not kv:
            i += 1
            continue
        key, val = kv.group(1), kv.group(2).strip()
        # Multi-line list: `key:` followed by `  - item` lines
        if val == "":
            items: list = []
            j = i + 1
            while j < len(lines) and re.match(r"^\s+-\s*", lines[j]):
                item = re.sub(r"^\s+-\s*", "", lines[j]).strip()
                if item.startswith('"') and item.endswith('"'):
                    item = item[1:-1]
                items.append(item)
                j += 1
            if items:
                out[key] = items
                i = j
                continue
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            if inner:
                out[key] = [p.strip().strip('"') for p in inner.split(",") if p.strip()]
            else:
                out[key] = []
        else:
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            out[key] = val
        i += 1
    return out


# ----- File model -------------------------------------------------------------


@dataclass
class FileRec:
    path: pathlib.Path
    root: pathlib.Path
    fm: dict

    @property
    def name(self) -> str:
        return self.path.stem if self.path.name != "index.md" else self.path.parent.name

    @property
    def folder(self) -> str:
        return str(self.path.parent.relative_to(self.root))

    @property
    def link(self) -> str:
        rel = self.path.relative_to(self.root).with_suffix("")
        return f"[[{rel}|{self.name}]]"

    @property
    def mtime(self) -> str:
        return datetime.datetime.fromtimestamp(self.path.stat().st_mtime).date().isoformat()

    @property
    def ctime(self) -> str:
        return datetime.datetime.fromtimestamp(self.path.stat().st_ctime).date().isoformat()


def load_files(root: pathlib.Path, subfolder: Optional[str] = None) -> list:
    """Walk the root (or a subfolder of it) collecting frontmatter+path."""
    base = root / subfolder if subfolder else root
    if not base.exists():
        return []
    out = []
    for p in base.glob("**/*.md"):
        rel = p.relative_to(root)
        # Skip infrastructure
        skip_parts = (".config", ".claude", ".git", ".githooks", "scripts", "docs")
        if any(part in skip_parts for part in rel.parts):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm = parse_frontmatter(text)
        if not fm:
            continue
        out.append(FileRec(path=p, root=root, fm=fm))
    return out


# ----- Query AST --------------------------------------------------------------


@dataclass
class Query:
    select: list  # list of (expr_str, display)
    without_id: bool
    source: Optional[str]  # folder / "all"
    where: Optional[str]
    sort: Optional[tuple]  # (expr, "ASC"|"DESC")
    limit: Optional[int]
    group_by: Optional[str]


# ----- Tokenizer & Parser -----------------------------------------------------


def tokenize(text: str) -> list:
    toks = []
    i = 0
    while i < len(text):
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c == '"':
            j = i + 1
            while j < len(text) and text[j] != '"':
                if text[j] == "\\" and j + 1 < len(text):
                    j += 1
                j += 1
            toks.append(("STR", text[i + 1 : j]))
            i = j + 1
            continue
        if c.isdigit() or (c == "-" and i + 1 < len(text) and text[i + 1].isdigit()):
            j = i + 1
            while j < len(text) and (text[j].isdigit() or text[j] == "."):
                j += 1
            toks.append(("NUM", text[i:j]))
            i = j
            continue
        if c in "(),":
            toks.append(("PUNC", c))
            i += 1
            continue
        # Operators: = != <= >= < >
        for op in ("!=", "<=", ">=", "=", "<", ">"):
            if text[i : i + len(op)] == op:
                toks.append(("OP", op))
                i += len(op)
                break
        else:
            # Identifier or keyword
            j = i
            while j < len(text) and (text[j].isalnum() or text[j] in "._-"):
                j += 1
            if j > i:
                toks.append(("ID", text[i:j]))
                i = j
            else:
                i += 1
    return toks


def parse_query(text: str) -> Query:
    text = text.strip()
    upper = text.upper()
    # Must start with TABLE
    if not upper.startswith("TABLE"):
        raise ValueError(
            f"Only TABLE queries supported; got: {text[:40]}"
        )

    # Split into clauses by top-level keyword scanning
    # Keywords: FROM, WHERE, SORT, LIMIT, GROUP BY
    clauses: dict = {"SELECT": "", "FROM": "", "WHERE": "", "SORT": "", "LIMIT": "", "GROUP BY": ""}

    # Strip TABLE / TABLE WITHOUT ID prefix
    m = re.match(r"TABLE\s+(WITHOUT\s+ID\s+)?", text, re.IGNORECASE)
    without_id = bool(m.group(1))
    rest = text[m.end() :]

    # Token scan for clause keywords (not inside quotes)
    clause_keywords = ["FROM", "WHERE", "SORT", "LIMIT", "GROUP BY"]
    current_clause = "SELECT"
    buf = ""
    i = 0
    while i < len(rest):
        # Try matching a clause keyword
        matched = None
        if rest[i] != '"':
            for kw in clause_keywords:
                # word boundary match, case-insensitive
                upper_rest = rest[i : i + len(kw) + 1].upper()
                if (
                    upper_rest.startswith(kw + " ")
                    or upper_rest.startswith(kw + "\n")
                    or upper_rest.startswith(kw + "\t")
                    or upper_rest == kw
                ):
                    matched = kw
                    break
        if matched:
            clauses[current_clause] = buf.strip()
            current_clause = matched
            buf = ""
            i += len(matched)
            continue
        if rest[i] == '"':
            # Skip to end of string
            j = i + 1
            while j < len(rest) and rest[j] != '"':
                if rest[j] == "\\" and j + 1 < len(rest):
                    j += 1
                j += 1
            buf += rest[i : j + 1]
            i = j + 1
            continue
        buf += rest[i]
        i += 1
    clauses[current_clause] = buf.strip()

    # Parse SELECT
    select_raw = clauses["SELECT"].strip()
    select = parse_select_list(select_raw)

    # Parse FROM: "folder"
    source = None
    if clauses["FROM"]:
        fm_raw = clauses["FROM"].strip()
        if fm_raw.startswith('"') and fm_raw.endswith('"'):
            source = fm_raw[1:-1]
        else:
            source = fm_raw or None

    where = clauses["WHERE"].strip() or None

    sort = None
    if clauses["SORT"]:
        sp = clauses["SORT"].strip().split()
        if len(sp) == 1:
            sort = (sp[0], "ASC")
        elif len(sp) >= 2:
            direction = sp[-1].upper()
            expr = " ".join(sp[:-1])
            if direction in ("ASC", "DESC"):
                sort = (expr, direction)
            else:
                sort = (clauses["SORT"].strip(), "ASC")

    limit = None
    if clauses["LIMIT"]:
        try:
            limit = int(clauses["LIMIT"].strip())
        except ValueError:
            limit = None

    group_by = clauses["GROUP BY"].strip() or None

    return Query(
        select=select,
        without_id=without_id,
        source=source,
        where=where,
        sort=sort,
        limit=limit,
        group_by=group_by,
    )


def parse_select_list(raw: str) -> list:
    """Split SELECT list respecting quotes, parens, and AS clauses."""
    items = []
    depth = 0
    in_str = False
    buf = ""
    for c in raw:
        if in_str:
            buf += c
            if c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
            buf += c
            continue
        if c == "(":
            depth += 1
            buf += c
            continue
        if c == ")":
            depth -= 1
            buf += c
            continue
        if c == "," and depth == 0:
            items.append(buf.strip())
            buf = ""
            continue
        buf += c
    if buf.strip():
        items.append(buf.strip())

    out = []
    for item in items:
        # Split AS clause case-insensitively
        m = re.split(r"\s+AS\s+", item, flags=re.IGNORECASE)
        if len(m) == 2:
            expr = m[0].strip()
            label = m[1].strip().strip('"')
        else:
            expr = item.strip()
            label = expr
        out.append((expr, label))
    return out


# ----- Expression evaluator ---------------------------------------------------


def eval_expr(expr: str, rec: FileRec) -> Any:
    """Evaluate a DQL expression against a single record.

    Precedence: OR > AND > NOT > comparisons > function calls / atoms.
    Implemented recursively with hand-coded parser.
    """
    parser = ExprParser(expr)
    return parser.parse_or().eval(rec)


@dataclass
class Node:
    kind: str
    value: Any = None
    children: list = field(default_factory=list)

    def eval(self, rec: FileRec) -> Any:
        k = self.kind
        if k == "STR":
            return self.value
        if k == "NUM":
            try:
                return float(self.value) if "." in str(self.value) else int(self.value)
            except ValueError:
                return 0
        if k == "ID":
            return resolve_identifier(self.value, rec)
        if k == "CALL":
            fn_name = self.value.lower()
            args = [c.eval(rec) for c in self.children]
            return call_function(fn_name, args)
        if k == "NOT":
            return not _truthy(self.children[0].eval(rec))
        if k == "AND":
            return _truthy(self.children[0].eval(rec)) and _truthy(
                self.children[1].eval(rec)
            )
        if k == "OR":
            return _truthy(self.children[0].eval(rec)) or _truthy(
                self.children[1].eval(rec)
            )
        if k == "OP":
            op = self.value
            a = self.children[0].eval(rec)
            b = self.children[1].eval(rec)
            return compare(op, a, b)
        return None


def _truthy(v: Any) -> bool:
    if v is None or v == "" or v == 0 or v is False:
        return False
    if isinstance(v, (list, tuple)):
        return len(v) > 0
    return True


def resolve_identifier(name: str, rec: FileRec) -> Any:
    if name.startswith("file."):
        sub = name[5:]
        if sub == "name":
            return rec.name
        if sub == "folder":
            return rec.folder
        if sub == "link":
            return rec.link
        if sub == "mtime":
            return rec.mtime
        if sub == "ctime":
            return rec.ctime
    # Frontmatter lookup — case-sensitive; fall back to case-insensitive
    if name in rec.fm:
        return rec.fm[name]
    lc = name.lower()
    for k, v in rec.fm.items():
        if k.lower() == lc:
            return v
    return None


def call_function(fn: str, args: list) -> Any:
    if fn == "contains":
        if len(args) != 2:
            return False
        haystack, needle = args
        if haystack is None:
            return False
        if isinstance(haystack, list):
            return any((_to_str(v) == _to_str(needle)) or (_to_str(needle) in _to_str(v)) for v in haystack)
        return _to_str(needle).lower() in _to_str(haystack).lower()
    if fn == "choice":
        if len(args) != 3:
            return ""
        cond, a, b = args
        return a if _truthy(cond) else b
    if fn == "date":
        if not args:
            return None
        a = args[0]
        if _to_str(a).lower() == "today":
            return datetime.date.today().isoformat()
        return _to_str(a)
    if fn == "length":
        if not args:
            return 0
        v = args[0]
        if v is None:
            return 0
        if isinstance(v, list):
            return len(v)
        return len(_to_str(v))
    if fn == "lower":
        return _to_str(args[0] if args else "").lower()
    if fn == "upper":
        return _to_str(args[0] if args else "").upper()
    raise ValueError(f"unsupported function: {fn}()")


def compare(op: str, a: Any, b: Any) -> bool:
    # Numeric compares: coerce both to float if possible
    try:
        fa = float(a)
        fb = float(b)
        if op == "=":
            return fa == fb
        if op == "!=":
            return fa != fb
        if op == "<":
            return fa < fb
        if op == "<=":
            return fa <= fb
        if op == ">":
            return fa > fb
        if op == ">=":
            return fa >= fb
    except (TypeError, ValueError):
        pass
    sa = _to_str(a)
    sb = _to_str(b)
    if op == "=":
        return sa == sb
    if op == "!=":
        return sa != sb
    if op == "<":
        return sa < sb
    if op == "<=":
        return sa <= sb
    if op == ">":
        return sa > sb
    if op == ">=":
        return sa >= sb
    return False


def _to_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return ", ".join(_to_str(x) for x in v)
    return str(v)


class ExprParser:
    """Recursive-descent parser for the DQL expression grammar."""

    def __init__(self, text: str):
        self.tokens = tokenize(text)
        self.pos = 0

    def peek(self, k: int = 0) -> Optional[tuple]:
        return self.tokens[self.pos + k] if self.pos + k < len(self.tokens) else None

    def consume(self) -> Optional[tuple]:
        t = self.peek()
        if t:
            self.pos += 1
        return t

    def accept(self, kind: str, value: Optional[str] = None) -> bool:
        t = self.peek()
        if not t:
            return False
        if t[0] != kind:
            return False
        if value is not None and t[1].upper() != value.upper():
            return False
        self.consume()
        return True

    def parse_or(self) -> Node:
        left = self.parse_and()
        while self.peek() and self.peek()[0] == "ID" and self.peek()[1].upper() == "OR":
            self.consume()
            right = self.parse_and()
            left = Node(kind="OR", children=[left, right])
        return left

    def parse_and(self) -> Node:
        left = self.parse_not()
        while self.peek() and self.peek()[0] == "ID" and self.peek()[1].upper() == "AND":
            self.consume()
            right = self.parse_not()
            left = Node(kind="AND", children=[left, right])
        return left

    def parse_not(self) -> Node:
        if self.peek() and self.peek()[0] == "ID" and self.peek()[1].upper() == "NOT":
            self.consume()
            child = self.parse_not()
            return Node(kind="NOT", children=[child])
        return self.parse_compare()

    def parse_compare(self) -> Node:
        left = self.parse_atom()
        t = self.peek()
        if t and t[0] == "OP":
            op = t[1]
            self.consume()
            right = self.parse_atom()
            return Node(kind="OP", value=op, children=[left, right])
        return left

    def parse_atom(self) -> Node:
        t = self.peek()
        if not t:
            return Node(kind="STR", value="")
        kind, val = t
        if kind == "STR":
            self.consume()
            return Node(kind="STR", value=val)
        if kind == "NUM":
            self.consume()
            return Node(kind="NUM", value=val)
        if kind == "PUNC" and val == "(":
            self.consume()
            inner = self.parse_or()
            self.accept("PUNC", ")")
            return inner
        if kind == "ID":
            self.consume()
            # Function call?
            nxt = self.peek()
            if nxt and nxt[0] == "PUNC" and nxt[1] == "(":
                self.consume()
                args: list = []
                while True:
                    if self.peek() and self.peek()[0] == "PUNC" and self.peek()[1] == ")":
                        break
                    args.append(self.parse_or())
                    if self.peek() and self.peek()[0] == "PUNC" and self.peek()[1] == ",":
                        self.consume()
                    else:
                        break
                self.accept("PUNC", ")")
                return Node(kind="CALL", value=val, children=args)
            return Node(kind="ID", value=val)
        self.consume()
        return Node(kind="STR", value=val)


# ----- Query execution --------------------------------------------------------


def run_query(query: Query, portfolio: pathlib.Path) -> list:
    files = load_files(portfolio, query.source)

    # WHERE
    if query.where:
        files = [f for f in files if _truthy(eval_expr(query.where, f))]

    # GROUP BY — flatten to one row per (group_key, count) record for table
    rows: list = []
    if query.group_by:
        groups: dict = {}
        for f in files:
            key = _to_str(eval_expr(query.group_by, f))
            groups.setdefault(key, []).append(f)
        for key, members in groups.items():
            rows.append({
                "__group__": key,
                "__count__": len(members),
                "__members__": members,
                "__fileref__": members[0] if members else None,
            })
    else:
        for f in files:
            rows.append({"__fileref__": f})

    # SORT
    if query.sort:
        expr, direction = query.sort
        def sort_key(row):
            # Meta-identifiers — group metadata, not per-file evaluation
            if expr == "__count__" or expr.lower() == "length(rows)":
                return (0, float(row.get("__count__", 0)))
            if expr == "__group__":
                return (1, _to_str(row.get("__group__", "")))
            ref = row.get("__fileref__")
            if ref is None:
                return (1, "")
            v = eval_expr(expr, ref)
            try:
                return (0, float(v))
            except (TypeError, ValueError):
                return (1, _to_str(v))
        rows.sort(key=sort_key, reverse=(direction == "DESC"))

    # LIMIT
    if query.limit is not None:
        rows = rows[: query.limit]

    return rows


def render_rows(query: Query, rows: list) -> str:
    headers = [label for _, label in query.select]
    leading_cols: list = []
    if query.group_by:
        leading_cols.append(query.group_by)
        headers = [query.group_by] + headers
    elif not query.without_id:
        leading_cols.append("__file__")
        headers = ["File"] + headers

    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        ref = row.get("__fileref__")
        cells = []
        for lead in leading_cols:
            if lead == "__file__":
                cells.append(ref.link if ref else "")
            else:
                cells.append(_to_str(row.get("__group__", "")))
        for expr, _ in query.select:
            if expr == "__count__" or expr.lower() == "length(rows)":
                cells.append(str(row.get("__count__", 0)))
            else:
                v = eval_expr(expr, ref) if ref else None
                if isinstance(v, list):
                    v = ", ".join(_to_str(x) for x in v)
                cells.append(_to_str(v).replace("\n", " "))
        lines.append("| " + " | ".join(cells) + " |")
    if len(rows) == 0:
        lines.append("| " + " | ".join(["_(no matches)_"] * len(headers)) + " |")
    return "\n".join(lines)


# ----- File walker ------------------------------------------------------------


DATAVIEW_FENCE = re.compile(r"^```dataview\s*\n(.*?)^```\s*$", re.MULTILINE | re.DOTALL)


def render_document(text: str, portfolio: pathlib.Path) -> str:
    def replace(m: re.Match) -> str:
        body = m.group(1)
        try:
            q = parse_query(body)
            rows = run_query(q, portfolio)
            return render_rows(q, rows)
        except Exception as e:  # noqa: BLE001
            return f"> [!error] document-render: {type(e).__name__}: {e}\n> Source:\n> ```\n> {body.strip()}\n> ```"

    return DATAVIEW_FENCE.sub(replace, text)


# ----- CLI --------------------------------------------------------------------


def find_portfolio_root(start: pathlib.Path) -> Optional[pathlib.Path]:
    p = start.resolve()
    for _ in range(12):
        if (p / ".config" / "documents" / "root.md").exists():
            return p
        if p.parent == p:
            return None
        p = p.parent
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="Markdown file to render")
    parser.add_argument("--portfolio", help="Portfolio root (defaults to upward search)")
    parser.add_argument(
        "--write-companion",
        action="store_true",
        help="Write output to {file}.rendered.md",
    )
    parser.add_argument(
        "--rewrite-inline",
        action="store_true",
        help="Overwrite the input file in place",
    )
    args = parser.parse_args()

    input_path = pathlib.Path(args.file).resolve()
    if not input_path.exists():
        print(f"ERROR: file not found: {input_path}", file=sys.stderr)
        return 2

    portfolio = (
        pathlib.Path(args.portfolio).resolve()
        if args.portfolio
        else find_portfolio_root(input_path.parent)
    )
    if portfolio is None:
        print(
            "ERROR: could not find a portfolio root (no .config/documents/root.md up the tree)",
            file=sys.stderr,
        )
        return 2

    text = input_path.read_text(encoding="utf-8")
    out = render_document(text, portfolio)

    if args.rewrite_inline:
        input_path.write_text(out, encoding="utf-8")
        print(f"Rewrote {input_path}")
    elif args.write_companion:
        companion = input_path.with_suffix(input_path.suffix + ".rendered")
        companion = companion.with_name(companion.stem + ".md")
        # Build {name}.rendered.md explicitly
        companion = input_path.with_name(input_path.stem + ".rendered.md")
        companion.write_text(out, encoding="utf-8")
        print(f"Wrote {companion}")
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
