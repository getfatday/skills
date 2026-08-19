#!/usr/bin/env python3
"""SessionStart standing-rules pointer + drift check (lab-intake).

Prints a short context block: the standing capture-rules pointer, plus a
byte-compare of the consumer-owned durable artifacts against the plugin's
canonical templates — the CLAUDE.md marker block, the settings deny rules,
and GOVERNANCE.md (when installed). Advisory only: always exits 0, and any
internal error degrades to silence rather than blocking session start.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from intake_config import load_config, render, resolve_root

REPAIR = "re-run /lab-intake:init to restore the canonical version"


def plugin_root():
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env and os.path.isdir(env):
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(here))


def read(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def extract_block(text, begin, end):
    """The marker-delimited block (inclusive), or None."""
    if text is None:
        return None
    start = text.find(begin)
    if start == -1:
        return None
    stop = text.find(end, start)
    if stop == -1:
        return None
    return text[start:stop + len(end)]


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    root = resolve_root(payload)
    proot = plugin_root()
    cfg = load_config(root)

    template = read(os.path.join(proot, "templates", "CLAUDE-block.md"))
    if template is None:
        sys.exit(0)  # plugin tree unreadable; stay silent
    canonical = render(template, cfg).strip()
    lines = canonical.splitlines()
    begin, end = lines[0], lines[-1]

    installed_block = extract_block(read(os.path.join(root, "CLAUDE.md")), begin, end)
    config_installed = os.path.isfile(
        os.path.join(root, ".claude", "lab-intake.json"))

    if installed_block is None and not config_installed:
        print("lab-intake: not initialized in this repository — run "
              "/lab-intake:init to scaffold capture (raw/notes/index/journal) "
              "and install the durable guard rules.")
        sys.exit(0)

    print("lab-intake: capture rules active — raw write-once at %s/, notes "
          "at %s/, index at %s, journal fragments at %s/. New knowledge enters "
          "via the intake skill."
          % (cfg["raw_dir"], cfg["notes_dir"], cfg["index_file"],
             cfg["journal_dir"]))

    drift = []

    if installed_block is None:
        drift.append("CLAUDE.md is missing the lab-intake rules block")
    elif installed_block.strip() != canonical:
        drift.append("the CLAUDE.md rules block differs from the plugin canonical")

    deny_template = read(os.path.join(proot, "templates", "settings-deny.json"))
    if deny_template is not None:
        try:
            wanted = json.loads(render(deny_template, cfg))["permissions"]["deny"]
        except Exception:
            wanted = []
        try:
            with open(os.path.join(root, ".claude", "settings.json"),
                      encoding="utf-8") as f:
                have = json.load(f).get("permissions", {}).get("deny", [])
        except Exception:
            have = []
        missing = [rule for rule in wanted if rule not in have]
        if missing:
            drift.append(".claude/settings.json is missing deny rules: %s"
                         % ", ".join(missing))

    gov_template = read(os.path.join(proot, "templates", "GOVERNANCE.md"))
    gov_installed = read(os.path.join(root, "GOVERNANCE.md"))
    if gov_template is not None and gov_installed is not None:
        if gov_installed.strip() != gov_template.strip():
            drift.append("GOVERNANCE.md differs from the plugin canonical "
                         "(kept as-is; delete it and re-run init to restore)")

    if drift:
        for item in drift:
            print("lab-intake DRIFT: %s — %s." % (item, REPAIR))
    else:
        print("lab-intake drift check: clean.")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
