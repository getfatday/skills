#!/usr/bin/env python3
"""PreToolUse write-once guard (lab-intake).

Deterministic deny rules:
  - Edit/NotebookEdit anywhere under the raw directory: always denied — raw
    sources are never edited after creation.
  - Write under the raw directory: denied only when the target already exists,
    so write-once creation stays legal (shell heredoc creation is likewise
    untouched; this guard only sees Edit/Write/NotebookEdit).
  - The same shape over the journal fragments directory: fragments are
    write-once entries; past entries are never rewritten.
  - Edit/Write/NotebookEdit on the base journal file: always denied — it is
    append-only history, and new entries are fragments.

Fails open on any error: a crashing PreToolUse hook would block every tool
call, which is worse than a missed deny. The consumer's settings deny rules
(written by init) are the durability layer when this plugin is disabled.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from intake_config import in_dir, load_config, rel_to_root, resolve_root


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    tool = payload.get("tool_name", "")
    if tool not in ("Edit", "Write", "NotebookEdit"):
        sys.exit(0)
    tool_input = payload.get("tool_input") or {}
    fpath = (tool_input.get("file_path")
             or tool_input.get("notebook_path")
             or tool_input.get("path"))
    if not fpath or not isinstance(fpath, str):
        sys.exit(0)

    root = resolve_root(payload)
    cfg = load_config(root)
    rel = rel_to_root(fpath, root)
    if rel is None:
        sys.exit(0)
    exists = os.path.exists(os.path.join(root, rel))

    if rel == cfg["journal_file"]:
        deny("%s is the base journal file: append-only history, never edited or "
             "rewritten. New entries are write-once fragments — create "
             "%s/<id>-<slug>.md (id = highest existing + 1) and refresh the "
             "compiled view with scripts/compile-journal.py."
             % (rel, cfg["journal_dir"]))

    if in_dir(rel, cfg["raw_dir"]):
        if tool in ("Edit", "NotebookEdit"):
            deny("%s is under the raw directory (%s/): raw sources are write-once "
                 "and never edited after creation. Correct the record in a "
                 "distilled note that links here, or capture a new dated raw file."
                 % (rel, cfg["raw_dir"]))
        if exists:
            deny("%s already exists, and raw files are write-once. Create a new "
                 "dated raw file instead of overwriting." % rel)

    if in_dir(rel, cfg["journal_dir"]):
        if tool in ("Edit", "NotebookEdit"):
            deny("%s is a journal fragment: fragments are write-once and past "
                 "entries are never rewritten. Record a correction as a new "
                 "fragment with the next id." % rel)
        if exists:
            deny("%s already exists, and journal fragments are write-once. Add a "
                 "new fragment with the next id instead." % rel)

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
