#!/usr/bin/env python3
"""
Document dispatch — subscription resolver and event router.

Resolves which type subscriptions match an event, evaluates conditions
against the payload, applies caps from .config/documents/root.md, writes
a trace line per event to .cache/document-dispatch.log, and emits the
resolved (type, handler, payload) list to stdout for the caller to act on.

The dispatcher is mechanism, not policy. It does NOT emit events itself.
Consumers wire emission from wherever they want (a /capture command,
a SessionEnd hook, a manual call). The plugin only resolves and routes.

Subscription source: each type's sidecar at
.config/documents/types/{name}.skill.md, parsed for the `## Subscriptions`
H2 (table format documented in references/event-schema.md).

Reserved events: document-created, document-updated, link-created,
entity-mentioned, lifecycle-changed.

Modes:
  dispatch.py emit --event <name> --payload <json> [--portfolio <root>] [--depth N]
      Resolve subscribers, apply caps, write trace, print invoked handlers.

  dispatch.py subscriptions [--portfolio <root>]
      List all (type, event, handler, condition) tuples in stable order.

  dispatch.py replay --trace <file> [--portfolio <root>]
      Re-fire the events recorded in a trace log, in order.

If a backing handler script exists at
.claude/skills/<type>/handlers/<handler>(.sh|.py|<no-ext>) and is
executable, dispatch runs it with the payload JSON on stdin. Exit 0 is
success; non-zero is logged and the cascade continues. If no backing
script exists, the handler is recorded in the trace as "deferred" and
the consumer (Claude in a session) is expected to invoke the matching
operation on the per-type generated skill from stdout.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ----- Reserved events --------------------------------------------------------

RESERVED_EVENTS = {
    "document-created": ["path", "type"],
    "document-updated": ["path", "type", "changed-fields"],
    "link-created": ["from", "to", "field"],
    "entity-mentioned": ["entity-path", "in-doc-path"],
    "lifecycle-changed": ["path", "type", "from-status", "to-status"],
}

DEFAULT_CAPS = {"max-fanout": 12, "max-depth": 1, "max-stubs": 5}


# ----- Frontmatter parsing (mirrors enrich.py) --------------------------------

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
    fm: dict = {}
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


# ----- Root document & caps ---------------------------------------------------


def load_root_config(portfolio: pathlib.Path) -> dict:
    """Read .config/documents/root.md ## Configuration into a dict."""
    root_path = portfolio / ".config" / "documents" / "root.md"
    if not root_path.exists():
        return {}
    text = root_path.read_text(encoding="utf-8")
    out: dict = {}
    in_conf = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            in_conf = line[3:].strip().lower() == "configuration"
            continue
        if in_conf and line.startswith("- "):
            body = line[2:].split("#", 1)[0].strip()
            m = re.match(r"([a-zA-Z0-9_-]+):\s*(.+)$", body)
            if m:
                out[m.group(1)] = m.group(2).strip()
    return out


def resolve_caps(portfolio: pathlib.Path) -> dict:
    """Return {max-fanout, max-depth, max-stubs} merged with defaults."""
    cfg = load_root_config(portfolio)
    caps = dict(DEFAULT_CAPS)
    for k in caps:
        if k in cfg:
            try:
                caps[k] = int(cfg[k])
            except ValueError:
                print(
                    f"WARN: cap '{k}' in root.md is not an int: {cfg[k]!r}; "
                    f"using default {caps[k]}",
                    file=sys.stderr,
                )
    return caps


# ----- Subscription parsing ---------------------------------------------------


@dataclass
class Subscription:
    type_name: str
    event: str
    handler: str
    condition: str
    sidecar_path: pathlib.Path
    line_no: int


def _parse_table_rows(text: str, heading: str) -> list:
    """Yield (line_no, [cells]) for rows under ## {heading} table.

    Skips header row and divider row (---).
    """
    rows: list = []
    in_section = False
    saw_header = False
    for idx, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("## "):
            in_section = stripped[3:].strip().lower() == heading.lower()
            saw_header = False
            continue
        if not in_section:
            continue
        if not stripped.startswith("|"):
            continue
        if "---" in stripped and set(stripped.replace("|", "").strip()) <= set("-: "):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not saw_header:
            saw_header = True
            continue
        if not any(cells):
            continue
        rows.append((idx, cells))
    return rows


def parse_subscriptions(sidecar_path: pathlib.Path, type_name: str) -> list:
    """Read a sidecar file, return list[Subscription] from ## Subscriptions."""
    if not sidecar_path.exists():
        return []
    text = sidecar_path.read_text(encoding="utf-8")
    out: list = []
    for line_no, cells in _parse_table_rows(text, "subscriptions"):
        if len(cells) < 2:
            raise SubscriptionError(
                f"{sidecar_path}:{line_no}: subscription row must have at least"
                f" event and handler columns; got: {cells!r}"
            )
        event = cells[0]
        handler = cells[1]
        condition = cells[2] if len(cells) > 2 and cells[2] else "always"
        if event not in RESERVED_EVENTS:
            raise SubscriptionError(
                f"{sidecar_path}:{line_no}: unknown event '{event}'. "
                f"Known: {sorted(RESERVED_EVENTS)}"
            )
        # Validate condition grammar at parse time (fail fast).
        try:
            _compile_condition(condition)
        except ConditionError as e:
            raise SubscriptionError(
                f"{sidecar_path}:{line_no}: bad condition {condition!r}: {e}"
            ) from e
        out.append(
            Subscription(
                type_name=type_name,
                event=event,
                handler=handler,
                condition=condition,
                sidecar_path=sidecar_path,
                line_no=line_no,
            )
        )
    return out


class SubscriptionError(Exception):
    """Raised on malformed subscription rows or unknown events."""


class ConditionError(Exception):
    """Raised on unparseable condition expressions."""


def discover_subscriptions(portfolio: pathlib.Path) -> list:
    """Walk .config/documents/types/*.skill.md and collect all subscriptions.

    Returns subscriptions sorted by (event, type_name, handler) for
    deterministic dispatch order regardless of filesystem walk order.
    """
    types_dir = portfolio / ".config" / "documents" / "types"
    if not types_dir.exists():
        return []
    subs: list = []
    for sidecar in sorted(types_dir.glob("*.skill.md")):
        type_name = sidecar.name[: -len(".skill.md")]
        subs.extend(parse_subscriptions(sidecar, type_name))
    subs.sort(key=lambda s: (s.event, s.type_name, s.handler))
    return subs


# ----- Condition grammar ------------------------------------------------------

# Tiny, closed grammar:
#   condition := "always" | <field> <op> <literal> | <field> "in" "{" <set> "}"
#   op        := "==" | "!="
#   literal   := quoted-string | bare-word | number
#
# Anything else is rejected with a clear error.

_FIELD_RE = r"[a-zA-Z_][a-zA-Z0-9_-]*"
_LITERAL_RE = r'"[^"]*"|[a-zA-Z0-9_./-]+'

_COMPARE_RE = re.compile(rf"^({_FIELD_RE})\s*(==|!=)\s*({_LITERAL_RE})\s*$")
_MEMBERSHIP_RE = re.compile(
    rf"^({_FIELD_RE})\s+in\s+\{{\s*({_LITERAL_RE}(?:\s*,\s*{_LITERAL_RE})*)\s*\}}\s*$"
)


def _strip_literal(lit: str) -> str:
    if lit.startswith('"') and lit.endswith('"'):
        return lit[1:-1]
    return lit


@dataclass
class CompiledCondition:
    kind: str  # "always" | "compare" | "membership"
    field_name: Optional[str] = None
    op: Optional[str] = None
    literal: Optional[str] = None
    members: list = field(default_factory=list)
    raw: str = ""


def _compile_condition(expr: str) -> CompiledCondition:
    expr = (expr or "").strip()
    if not expr or expr.lower() == "always":
        return CompiledCondition(kind="always", raw=expr or "always")

    m = _COMPARE_RE.match(expr)
    if m:
        return CompiledCondition(
            kind="compare",
            field_name=m.group(1),
            op=m.group(2),
            literal=_strip_literal(m.group(3)),
            raw=expr,
        )

    m = _MEMBERSHIP_RE.match(expr)
    if m:
        members_raw = m.group(2)
        members = [
            _strip_literal(x.strip()) for x in re.split(r"\s*,\s*", members_raw)
        ]
        return CompiledCondition(
            kind="membership", field_name=m.group(1), members=members, raw=expr
        )

    raise ConditionError(
        f"unrecognized condition syntax: {expr!r}. "
        f"Allowed: 'always' | <field> <==|!=> <literal> | "
        f"<field> in {{<lit>, ...}}"
    )


def evaluate_condition(
    cc: CompiledCondition, payload: dict, portfolio: pathlib.Path
) -> bool:
    if cc.kind == "always":
        return True

    field_name = cc.field_name or ""
    val = payload.get(field_name)

    # If the field isn't in the payload but the payload has `path`, peek
    # frontmatter (lets conditions reference the doc's frontmatter fields).
    if val is None and "path" in payload and field_name not in payload:
        doc_path = portfolio / payload["path"]
        if doc_path.exists():
            val = read_frontmatter(doc_path).get(field_name)

    if cc.kind == "compare":
        rhs = cc.literal
        if cc.op == "==":
            return str(val) == str(rhs)
        if cc.op == "!=":
            return str(val) != str(rhs)
        return False

    if cc.kind == "membership":
        return str(val) in [str(m) for m in cc.members]

    return False


# ----- Trace log --------------------------------------------------------------


def trace_log_path(portfolio: pathlib.Path) -> pathlib.Path:
    return portfolio / ".cache" / "document-dispatch.log"


def append_trace(
    portfolio: pathlib.Path,
    event: str,
    payload: dict,
    handlers: list,
    caps: dict,
) -> None:
    """Append one JSON line. Atomic for writes under PIPE_BUF on POSIX."""
    log_path = trace_log_path(portfolio)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "event": event,
        "payload": payload,
        "handlers": handlers,
        "caps": caps,
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


# ----- Backing handler invocation --------------------------------------------


def find_handler_script(
    portfolio: pathlib.Path, type_name: str, handler: str
) -> Optional[pathlib.Path]:
    """Look for an executable handler script at
    .claude/skills/<type>/handlers/<handler>(.sh|.py|<no-ext>)."""
    base = portfolio / ".claude" / "skills" / type_name / "handlers"
    if not base.exists():
        return None
    for candidate in (handler, f"{handler}.sh", f"{handler}.py"):
        p = base / candidate
        if p.exists() and os.access(p, os.X_OK):
            return p
    return None


def run_handler(script: pathlib.Path, payload: dict) -> int:
    """Run handler with payload JSON on stdin. Return exit code."""
    proc = subprocess.run(
        [str(script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=30,
    )
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc.returncode


# ----- Validation -------------------------------------------------------------


def validate_payload(event: str, payload: dict) -> None:
    if event not in RESERVED_EVENTS:
        raise SubscriptionError(
            f"unknown event '{event}'. Known: {sorted(RESERVED_EVENTS)}"
        )
    required = RESERVED_EVENTS[event]
    missing = [k for k in required if k not in payload]
    if missing:
        raise SubscriptionError(
            f"event '{event}' payload missing required field(s): {missing}. "
            f"Required: {required}"
        )


# ----- Operations -------------------------------------------------------------


def op_subscriptions(portfolio: pathlib.Path) -> int:
    subs = discover_subscriptions(portfolio)
    if not subs:
        print("(no subscriptions declared)")
        return 0
    print(f"# {len(subs)} subscription(s) across "
          f"{len({s.type_name for s in subs})} type(s)")
    print()
    print("type             event               handler             condition")
    print("---------------- ------------------- ------------------- -------------------")
    for s in subs:
        print(f"{s.type_name:<16} {s.event:<19} {s.handler:<19} {s.condition}")
    return 0


def op_emit(
    portfolio: pathlib.Path,
    event: str,
    payload: dict,
    depth: int,
    stubs_used: int,
) -> int:
    validate_payload(event, payload)
    caps = resolve_caps(portfolio)

    # Depth cap: refuse to emit beyond max-depth.
    if depth > caps["max-depth"]:
        caps_trace = {**caps, "depth": depth, "hit": "max-depth"}
        append_trace(
            portfolio,
            event,
            payload,
            handlers=[],
            caps=caps_trace,
        )
        print(
            json.dumps(
                {
                    "event": event,
                    "payload": payload,
                    "depth": depth,
                    "caps": caps_trace,
                    "selected": [],
                    "skipped": [],
                    "handlers": [],
                },
                sort_keys=True,
                indent=2,
            )
        )
        return 0

    all_subs = [s for s in discover_subscriptions(portfolio) if s.event == event]

    selected: list = []
    skipped: list = []
    for sub in all_subs:
        cc = _compile_condition(sub.condition)
        if not evaluate_condition(cc, payload, portfolio):
            skipped.append(
                {
                    "type": sub.type_name,
                    "handler": sub.handler,
                    "condition": sub.condition,
                    "reason": "condition-false",
                }
            )
            continue
        selected.append(sub)

    cap_hit: Optional[str] = None
    if len(selected) > caps["max-fanout"]:
        cap_hit = "max-fanout"
        selected = selected[: caps["max-fanout"]]

    handlers_record: list = []
    for sub in selected:
        script = find_handler_script(portfolio, sub.type_name, sub.handler)
        if script is None:
            handlers_record.append(
                {
                    "type": sub.type_name,
                    "handler": sub.handler,
                    "status": "deferred",
                    "reason": "no backing script; consumer must invoke "
                              f"/{sub.type_name} {sub.handler}",
                }
            )
            continue
        try:
            exit_code = run_handler(script, payload)
        except subprocess.TimeoutExpired:
            handlers_record.append(
                {
                    "type": sub.type_name,
                    "handler": sub.handler,
                    "status": "timeout",
                    "exit": None,
                }
            )
            continue
        except OSError as e:
            handlers_record.append(
                {
                    "type": sub.type_name,
                    "handler": sub.handler,
                    "status": "error",
                    "error": str(e),
                }
            )
            continue
        handlers_record.append(
            {
                "type": sub.type_name,
                "handler": sub.handler,
                "status": "invoked",
                "exit": exit_code,
            }
        )

    caps_trace = {**caps, "depth": depth}
    if cap_hit:
        caps_trace["hit"] = cap_hit
    append_trace(portfolio, event, payload, handlers_record, caps_trace)

    print(
        json.dumps(
            {
                "event": event,
                "payload": payload,
                "depth": depth,
                "caps": caps_trace,
                "selected": [
                    {
                        "type": s.type_name,
                        "handler": s.handler,
                        "condition": s.condition,
                    }
                    for s in selected
                ],
                "skipped": skipped,
                "handlers": handlers_record,
            },
            sort_keys=True,
            indent=2,
        )
    )
    return 0


def op_replay(portfolio: pathlib.Path, trace_file: pathlib.Path) -> int:
    if not trace_file.exists():
        print(f"ERROR: trace file not found: {trace_file}", file=sys.stderr)
        return 2
    # Read the trace fully into memory before emitting. Replaying a live
    # trace would otherwise re-read the lines emit() appends, causing
    # exponential growth.
    with open(trace_file, encoding="utf-8") as f:
        lines = f.readlines()
    if trace_file.resolve() == trace_log_path(portfolio).resolve():
        print(
            f"WARN: replaying the live trace at {trace_file} — new emits "
            f"are being appended to the same file. Snapshot first if you "
            f"want a stable replay source.",
            file=sys.stderr,
        )
    for line_no, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            print(
                f"ERROR: trace line {line_no}: invalid JSON: {e}",
                file=sys.stderr,
            )
            return 2
        event = rec.get("event")
        payload = rec.get("payload") or {}
        if not event:
            continue
        print(f"--- replay line {line_no}: {event} ---")
        op_emit(portfolio, event, payload, depth=0, stubs_used=0)
    return 0


# ----- CLI --------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Document dispatch — subscription router."
    )
    sub = parser.add_subparsers(dest="op", required=True)

    p_emit = sub.add_parser("emit", help="Route an event to subscribers.")
    p_emit.add_argument("--event", required=True)
    p_emit.add_argument(
        "--payload", required=True, help="JSON-encoded payload object"
    )
    p_emit.add_argument(
        "--portfolio", default=".", help="Portfolio root (default: cwd)"
    )
    p_emit.add_argument(
        "--depth",
        type=int,
        default=0,
        help="Cascade depth (incremented when handler re-emits)",
    )

    p_subs = sub.add_parser(
        "subscriptions", help="List declared subscriptions."
    )
    p_subs.add_argument("--portfolio", default=".")

    p_replay = sub.add_parser("replay", help="Re-fire events from a trace log.")
    p_replay.add_argument("--trace", required=True)
    p_replay.add_argument("--portfolio", default=".")

    args = parser.parse_args()
    portfolio = pathlib.Path(args.portfolio).resolve()
    if not portfolio.exists():
        print(f"ERROR: portfolio not found: {portfolio}", file=sys.stderr)
        return 2

    try:
        if args.op == "emit":
            try:
                payload = json.loads(args.payload)
            except json.JSONDecodeError as e:
                print(f"ERROR: --payload is not valid JSON: {e}", file=sys.stderr)
                return 2
            if not isinstance(payload, dict):
                print("ERROR: --payload must be a JSON object", file=sys.stderr)
                return 2
            return op_emit(portfolio, args.event, payload, args.depth, 0)
        if args.op == "subscriptions":
            return op_subscriptions(portfolio)
        if args.op == "replay":
            return op_replay(portfolio, pathlib.Path(args.trace))
    except SubscriptionError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
