#!/usr/bin/env python3
"""derive-events.py — derive a document change-event log from git history.

Part of the `document` Claude Code plugin. Treats git history as a write-ahead
log and derives a deterministic, content-addressed event stream over typed
documents (Markdown files carrying a `type:` frontmatter field).

The full specification — event schema, derivation algorithm, and the
determinism contract — lives in
`skills/document-define/references/event-model.md`.

Zero third-party dependencies: Python 3 standard library only. Invoke in place:

    python3 $(git rev-parse --show-toplevel)/.claude/skills/document-events/scripts/derive-events.py derive
    python3 $(git rev-parse --show-toplevel)/.claude/skills/document-events/scripts/derive-events.py log --type prd
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

__version__ = "0.1.0"

# Files under these repo-relative prefixes are plugin/config, never documents.
EXCLUDED_PREFIXES = (".config/", ".claude/")

# Field-delta record field that classifies a lifecycle transition.
STATUS_FIELD = "status"

OP_CHOICES = ("created", "updated", "deleted", "renamed", "status-changed")


class GitError(RuntimeError):
    """A git invocation failed in a way the deriver cannot recover from."""


# --------------------------------------------------------------------------
# git plumbing
# --------------------------------------------------------------------------

def _run(repo, args):
    """Run a git command. Return (returncode, stdout_bytes, stderr_text)."""
    result = subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True,
    )
    return result.returncode, result.stdout, result.stderr.decode("utf-8", "replace")


def _git_text(repo, args):
    """Run git, raising GitError on failure, returning stdout decoded as text."""
    code, out, err = _run(repo, args)
    if code != 0:
        raise GitError(f"git {' '.join(args)} failed: {err.strip()}")
    return out.decode("utf-8", "replace")


def ensure_repo(repo):
    """Raise GitError if `repo` is not inside a git working tree."""
    code, _, err = _run(repo, ["rev-parse", "--git-dir"])
    if code != 0:
        raise GitError(f"{repo!r} is not a git repository: {err.strip()}")


def list_commits(repo, rev_range=None):
    """Return commit metadata, oldest-first, --first-parent, touching *.md.

    Each record carries `parent` — the first-parent SHA, or None for the root
    commit. An empty repository (no commits yet) yields an empty list.
    """
    sep = "\x1f"
    fmt = sep.join(["%H", "%P", "%aI", "%an <%ae>", "%s"])
    args = ["log", "--first-parent", "--reverse", f"--format={fmt}"]
    if rev_range:
        args.append(rev_range)
    args += ["--", "*.md"]
    code, out, err = _run(repo, args)
    if code != 0:
        if "does not have any commits yet" in err or "bad default revision" in err:
            return []
        raise GitError(f"git log failed: {err.strip()}")
    commits = []
    for line in out.decode("utf-8", "replace").splitlines():
        if not line:
            continue
        parts = line.split(sep)
        if len(parts) != 5:
            continue
        sha, parents, ts, actor, message = parts
        first_parent = parents.split()[0] if parents.strip() else None
        commits.append({
            "sha": sha, "parent": first_parent,
            "ts": ts, "actor": actor, "message": message,
        })
    return commits


def commit_changes(repo, sha, parent):
    """Return [(status, path, old_path)] for *.md files changed in `sha`.

    The diff is computed explicitly between `parent` and `sha` (or against the
    empty tree, via --root, when `parent` is None) — so merge commits diff
    cleanly against their first parent. `status` is git's name-status code
    (A/M/D/R.../C.../T); `old_path` is set only for renames and copies.
    """
    base = ["diff-tree", "--no-commit-id", "-r", "-M", "--name-status", "-z"]
    scope = ["--", "*.md"]
    if parent:
        code, out, _ = _run(repo, base + [parent, sha] + scope)
        if code == 0:
            return _parse_name_status_z(out.decode("utf-8", "replace"))
        # The first parent is unreachable — e.g. a shallow-clone boundary
        # commit. Fall back to diffing against the empty tree; every file
        # then reads as newly added, the correct view of a boundary commit.
    return _parse_name_status_z(_git_text(repo, base + ["--root", sha] + scope))


def _parse_name_status_z(out):
    """Parse NUL-delimited `git diff-tree --name-status -z` output."""
    tokens = out.split("\0")
    changes = []
    i = 0
    while i < len(tokens):
        status = tokens[i]
        if not status:
            i += 1
            continue
        if status[0] in ("R", "C"):
            if i + 2 >= len(tokens):
                break
            changes.append((status, tokens[i + 2], tokens[i + 1]))
            i += 3
        else:
            if i + 1 >= len(tokens):
                break
            changes.append((status, tokens[i + 1], None))
            i += 2
    return changes


def file_at(repo, rev, path):
    """Return file content at `rev:path` as text, or None if it does not exist."""
    code, out, _ = _run(repo, ["show", f"{rev}:{path}"])
    if code != 0:
        return None
    return out.decode("utf-8", "replace")


# --------------------------------------------------------------------------
# markdown parsing (deterministic, lenient, stdlib only)
# --------------------------------------------------------------------------

def _unquote(value):
    """Strip a single pair of matching surrounding quotes."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("\"", "'"):
        return value[1:-1]
    return value


def _frontmatter_bounds(lines):
    """Return (start, end) line indices of the frontmatter body, or None.

    `start` is the first body line, `end` is the closing-fence line index.
    """
    if not lines or lines[0].strip() != "---":
        return None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return 1, idx
    return None


def parse_frontmatter(text):
    """Parse the leading YAML-ish frontmatter block.

    Returns {field: value} where value is a str, a list of str, or "" for an
    empty scalar. Returns {} when there is no well-formed frontmatter block.
    Supports scalars, `key: [a, b]` inline lists, and `key:` block lists of
    `  - item` lines — the shapes document frontmatter actually uses. Nested
    maps and multiline scalars are not supported.
    """
    if text is None:
        return {}
    lines = text.lstrip("\ufeff").splitlines()  # tolerate a leading UTF-8 BOM
    bounds = _frontmatter_bounds(lines)
    if bounds is None:
        return {}
    start, end = bounds
    fields = {}
    i = start
    while i < end:
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or raw[:1].isspace() or ":" not in raw:
            i += 1
            continue
        key, _, rest = raw.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest == "":
            items = []
            j = i + 1
            while j < end:
                item = lines[j].strip()
                if item == "-":
                    items.append("")
                elif item.startswith("- "):
                    items.append(_unquote(item[2:].strip()))
                else:
                    break
                j += 1
            if items:
                fields[key] = items
                i = j
                continue
            fields[key] = ""
        elif rest.startswith("[") and rest.endswith("]"):
            inner = rest[1:-1].strip()
            fields[key] = [] if not inner else [
                _unquote(part.strip()) for part in inner.split(",")
            ]
        else:
            fields[key] = _unquote(rest)
        i += 1
    return fields


def parse_sections(text):
    """Return {section_name: body_text} for H2 (`## `) sections, frontmatter
    excluded and fenced code blocks ignored. Bodies are whitespace-stripped.
    Duplicate headings collapse to the last occurrence."""
    if text is None:
        return {}
    lines = text.lstrip("\ufeff").splitlines()  # tolerate a leading UTF-8 BOM
    bounds = _frontmatter_bounds(lines)
    body_start = bounds[1] + 1 if bounds else 0
    sections = {}
    current = None
    buf = []
    in_fence = False
    for line in lines[body_start:]:
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            # A `## ` line inside a fenced code block is not a heading.
            in_fence = not in_fence
            if current is not None:
                buf.append(line)
            continue
        if not in_fence and line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = line[3:].strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()
    return sections


# --------------------------------------------------------------------------
# event derivation
# --------------------------------------------------------------------------

def diff_fields(before, after):
    """Return field-delta dicts for every changed key, sorted by field name."""
    deltas = []
    for key in sorted(set(before) | set(after)):
        old = before.get(key)
        new = after.get(key)
        if old != new:
            deltas.append({"field": key, "from": old, "to": new})
    return deltas


def diff_sections(before, after):
    """Return section-delta dicts for added/removed/modified H2 sections,
    sorted by section name."""
    deltas = []
    for name in sorted(set(before) | set(after)):
        in_before = name in before
        in_after = name in after
        if in_before and in_after:
            if before[name] != after[name]:
                deltas.append({"section": name, "change": "modified"})
        elif in_after:
            deltas.append({"section": name, "change": "added"})
        else:
            deltas.append({"section": name, "change": "removed"})
    return deltas


def _excluded(path):
    """True if `path` is plugin/config territory, not a document."""
    return path.startswith(EXCLUDED_PREFIXES)


def build_event(repo, commit, status, path, old_path):
    """Build one event for a changed file, or None if it is not a typed document."""
    code = status[0]
    parent = commit["parent"]

    if code == "A":
        before_text = None
    elif old_path is not None:
        before_text = file_at(repo, parent, old_path)
    else:
        before_text = file_at(repo, parent, path)
    after_text = None if code == "D" else file_at(repo, commit["sha"], path)

    # Defensive: an explicit two-tree diff only reports a rename whose source
    # is present in the parent tree, so this normally cannot fire. If the
    # source content is nonetheless unreadable, degrade to a creation rather
    # than emit a misleading every-field-added delta.
    if code == "R" and before_text is None:
        code = "A"

    before_fm = parse_frontmatter(before_text)
    after_fm = parse_frontmatter(after_text)
    if "type" not in before_fm and "type" not in after_fm:
        return None  # not a typed document

    doc_type = after_fm.get("type") if after_fm.get("type") else before_fm.get("type")
    field_deltas = diff_fields(before_fm, after_fm)
    section_deltas = diff_sections(parse_sections(before_text),
                                   parse_sections(after_text))

    if code == "A":
        op = "created"
    elif code == "D":
        op = "deleted"
    elif code == "R":
        op = "renamed"
    elif any(d["field"] == STATUS_FIELD for d in field_deltas):
        op = "status-changed"
    else:
        op = "updated"

    event = {
        "commit": commit["sha"],
        "ts": commit["ts"],
        "actor": commit["actor"],
        "document": path,
        "type": doc_type if doc_type else None,
        "op": op,
        "changes": [] if op in ("created", "deleted") else field_deltas + section_deltas,
        "message": commit["message"],
    }
    if op == "renamed":
        event["from-path"] = old_path
    return event


def derive(repo, rev_range=None):
    """Return the full event log for `rev_range`, oldest-first, deterministically."""
    events = []
    for commit in list_commits(repo, rev_range):
        changes = commit_changes(repo, commit["sha"], commit["parent"])
        # Sort by UTF-8 byte order so seq is identical on every clone.
        candidates = sorted(
            (c for c in changes if not _excluded(c[1])),
            key=lambda c: c[1].encode("utf-8"),
        )
        commit_events = []
        for status, path, old_path in candidates:
            event = build_event(repo, commit, status, path, old_path)
            if event is not None:
                commit_events.append(event)
        for seq, event in enumerate(commit_events):
            event["seq"] = seq
            event["id"] = f"{event['commit']}:{event['document']}:{seq}"
            events.append(event)
    return events


def emit(events):
    """Write events as a deterministic, sorted-key JSON array to stdout."""
    json.dump(events, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


# --------------------------------------------------------------------------
# command-line interface
# --------------------------------------------------------------------------

def cmd_derive(args):
    ensure_repo(args.repo)
    emit(derive(args.repo, args.range))


def cmd_log(args):
    ensure_repo(args.repo)
    events = derive(args.repo, args.range)
    selected = []
    for event in events:
        if args.document and args.document not in event["document"]:
            continue
        if args.type and event["type"] != args.type:
            continue
        if args.op and event["op"] != args.op:
            continue
        if args.since and event["ts"] < args.since:
            continue
        selected.append(event)
    emit(selected)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="derive-events.py",
        description="Derive a document change-event log from git history.",
    )
    parser.add_argument("--version", action="version",
                        version=f"derive-events.py {__version__}")
    parser.add_argument("-C", "--repo", default=".",
                        help="path to the git repository (default: current directory)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_derive = sub.add_parser("derive", help="emit the full event log as JSON")
    p_derive.add_argument("range", nargs="?", default=None,
                          help="optional git rev range, e.g. main~20..main")
    p_derive.set_defaults(func=cmd_derive)

    p_log = sub.add_parser("log", help="query and filter the event log")
    p_log.add_argument("range", nargs="?", default=None,
                       help="optional git rev range, e.g. main~20..main")
    p_log.add_argument("--document", help="substring match on the document path")
    p_log.add_argument("--type", help="exact match on the document type")
    p_log.add_argument("--op", choices=OP_CHOICES, help="exact match on the operation")
    p_log.add_argument("--since", metavar="ISO-DATE",
                       help="keep events whose timestamp sorts >= this ISO prefix")
    p_log.set_defaults(func=cmd_log)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except GitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
