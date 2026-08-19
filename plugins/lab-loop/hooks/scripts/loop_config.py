#!/usr/bin/env python3
"""Shared configuration helpers for the lab-loop hook scripts.

Consumer repositories may override the default paths by writing
`.claude/lab-loop.json` at the repo root (the init step does this).
All paths are repo-root-relative and use forward slashes. Stdlib only;
`load_config` never raises — hook scripts must fail open, because a crashing
hook is worse than a missed check.
"""
import json
import os

DEFAULTS = {
    "hypotheses_dir": "hypotheses",
    "runs_dir": "experiments/runs",
    "template_file": "hypotheses/TEMPLATE.md",
    "preflight_file": "experiments/preflight.py",
}

CONFIG_RELPATH = os.path.join(".claude", "lab-loop.json")


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
