#!/usr/bin/env python3
"""Shared configuration helpers for the lab-intake hook scripts.

Consumer repositories may override the default paths by writing
`.claude/lab-intake.json` at the repo root (the init step does this).
All paths are repo-root-relative and use forward slashes. Stdlib only;
`load_config` never raises — hook scripts must fail open, because a crashing
hook is worse than a missed check.
"""
import json
import os

DEFAULTS = {
    "raw_dir": "research/raw",
    "notes_dir": "research/notes",
    "index_file": "research/index.md",
    "journal_dir": "experiments/journal-fragments",
    "journal_file": "experiments/journal.md",
    "compiled_file": "experiments/journal-compiled.md",
}

CONFIG_RELPATH = os.path.join(".claude", "lab-intake.json")


def resolve_root(payload):
    """Repo root: CLAUDE_PROJECT_DIR, then the hook payload's cwd, then cwd."""
    root = os.environ.get("CLAUDE_PROJECT_DIR")
    if root and os.path.isdir(root):
        return root
    cwd = (payload or {}).get("cwd")
    if cwd and os.path.isdir(cwd):
        return cwd
    return os.getcwd()


def load_config(root):
    """DEFAULTS overlaid with the consumer's config file, if any."""
    cfg = dict(DEFAULTS)
    try:
        with open(os.path.join(root, CONFIG_RELPATH), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for key in DEFAULTS:
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    cfg[key] = value.strip().strip("/")
    except Exception:
        pass
    return cfg


def rel_to_root(fpath, root):
    """Normalized repo-relative path for fpath, or None when outside the repo."""
    try:
        if not os.path.isabs(fpath):
            fpath = os.path.join(root, fpath)
        rel = os.path.relpath(os.path.normpath(fpath), os.path.normpath(root))
    except Exception:
        return None
    rel = rel.replace(os.sep, "/")
    if rel.startswith(".."):
        return None
    return rel


def in_dir(rel, directory):
    """True when repo-relative path `rel` sits at or under `directory`."""
    directory = directory.strip("/")
    return rel == directory or rel.startswith(directory + "/")


def render(text, cfg):
    """Deterministic placeholder substitution for the canonical templates."""
    for key in sorted(cfg):
        text = text.replace("{{" + key.upper() + "}}", cfg[key])
    return text
