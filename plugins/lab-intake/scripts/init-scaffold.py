#!/usr/bin/env python3
"""Deterministic scaffold for the lab-intake plugin (run by /lab-intake:init).

Usage: init-scaffold.py [repo-root]
                        [--raw-dir P] [--notes-dir P] [--index-file P]
                        [--journal-dir P] [--journal-file P] [--compiled-file P]

Idempotent and re-runnable. Creates what is missing, repairs the plugin-owned
canonical artifacts (the CLAUDE.md marker block, the settings deny rules,
scripts/compile-journal.py), and never overwrites consumer-owned content (the
index, notes, raw files, fragments, or an existing GOVERNANCE.md). Prints one
line per artifact: created / updated / unchanged / kept.

Everything written is rendered from the plugin's templates with the chosen
paths. Output contains no timestamps or randomness, so re-running with the
same inputs is byte-stable. Stdlib only.
"""
import argparse
import json
import os
import sys

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULTS = {
    "raw_dir": "research/raw",
    "notes_dir": "research/notes",
    "index_file": "research/index.md",
    "journal_dir": "experiments/journal-fragments",
    "journal_file": "experiments/journal.md",
    "compiled_file": "experiments/journal-compiled.md",
}


def render(text, cfg):
    for key in sorted(cfg):
        text = text.replace("{{" + key.upper() + "}}", cfg[key])
    return text


def read(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def template(name):
    text = read(os.path.join(PLUGIN_ROOT, "templates", name))
    if text is None:
        sys.stderr.write("init-scaffold: missing plugin template %s\n" % name)
        sys.exit(1)
    return text


def write(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def ensure_file(root, relpath, text, label, overwrite=False):
    """created / updated / unchanged / kept, honoring consumer ownership."""
    path = os.path.join(root, relpath)
    current = read(path)
    if current is None:
        write(path, text)
        print("created   %s  (%s)" % (relpath, label))
    elif current == text:
        print("unchanged %s  (%s)" % (relpath, label))
    elif overwrite:
        write(path, text)
        print("updated   %s  (%s — restored to plugin canonical)" % (relpath, label))
    else:
        print("kept      %s  (%s — differs from the plugin canonical; the drift "
              "check will report it)" % (relpath, label))


def ensure_dir(root, reldir, label):
    path = os.path.join(root, reldir)
    keep = os.path.join(path, ".gitkeep")
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
        write(keep, "")
        print("created   %s/  (%s)" % (reldir, label))
    else:
        if not os.listdir(path):
            write(keep, "")
        print("unchanged %s/  (%s)" % (reldir, label))


def install_claude_block(root, block):
    path = os.path.join(root, "CLAUDE.md")
    lines = block.strip().splitlines()
    begin, end = lines[0], lines[-1]
    canonical = block.strip() + "\n"
    current = read(path)
    if current is None:
        write(path, "# CLAUDE.md\n\nThis file provides guidance to Claude Code "
                    "when working in this repository.\n\n" + canonical)
        print("created   CLAUDE.md  (with the lab-intake rules block)")
        return
    start = current.find(begin)
    stop = current.find(end, start) if start != -1 else -1
    if start != -1 and stop != -1:
        replaced = current[:start] + canonical.strip() + current[stop + len(end):]
        if replaced == current:
            print("unchanged CLAUDE.md  (rules block already canonical)")
        else:
            write(path, replaced)
            print("updated   CLAUDE.md  (rules block restored to plugin canonical)")
    else:
        write(path, current.rstrip("\n") + "\n\n" + canonical)
        print("updated   CLAUDE.md  (rules block appended)")


def merge_settings(root, deny_rules):
    relpath = os.path.join(".claude", "settings.json")
    path = os.path.join(root, relpath)
    current = read(path)
    if current is None:
        settings = {}
    else:
        try:
            settings = json.loads(current)
        except ValueError:
            print("kept      %s  (could not parse as JSON — add these deny rules "
                  "by hand: %s)" % (relpath, ", ".join(deny_rules)))
            return
        if not isinstance(settings, dict):
            print("kept      %s  (unexpected shape — add the deny rules by hand)"
                  % relpath)
            return
    permissions = settings.setdefault("permissions", {})
    deny = permissions.setdefault("deny", [])
    missing = [rule for rule in deny_rules if rule not in deny]
    if not missing and current is not None:
        print("unchanged %s  (deny rules present)" % relpath)
        return
    deny.extend(missing)
    write(path, json.dumps(settings, indent=2, sort_keys=False) + "\n")
    print(("created   %s  (deny rules installed)" if current is None else
           "updated   %s  (deny rules added: " + ", ".join(missing) + ")")
          % relpath)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", default=".")
    for key in DEFAULTS:
        parser.add_argument("--" + key.replace("_", "-"), dest=key)
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    cfg = dict(DEFAULTS)
    for key in DEFAULTS:
        value = getattr(args, key)
        if value:
            cfg[key] = value.strip().strip("/")

    # 1. Config file (plugin-owned; canonical for the chosen paths).
    ensure_file(root, os.path.join(".claude", "lab-intake.json"),
                json.dumps(cfg, indent=2, sort_keys=True) + "\n",
                "path configuration", overwrite=True)

    # 2. Directories.
    ensure_dir(root, cfg["raw_dir"], "raw verbatim sources, write-once")
    ensure_dir(root, cfg["notes_dir"], "distilled notes")
    ensure_dir(root, cfg["journal_dir"], "write-once journal fragments")

    # 3. Consumer-owned seeds (never overwritten).
    ensure_file(root, cfg["index_file"], template("index.md"), "wiki index seed")
    ensure_file(root, "GOVERNANCE.md", template("GOVERNANCE.md"),
                "behavioral invariants")

    # 4. Plugin-owned executable (repaired to canonical).
    compile_src = read(os.path.join(PLUGIN_ROOT, "scripts", "compile-journal.py"))
    if compile_src is not None:
        ensure_file(root, os.path.join("scripts", "compile-journal.py"),
                    compile_src, "journal compiler", overwrite=True)

    # 5. CLAUDE.md marker block (plugin-owned block inside a consumer file).
    install_claude_block(root, render(template("CLAUDE-block.md"), cfg))

    # 6. Settings deny rules (merged, never clobbering other settings).
    deny_rules = json.loads(render(template("settings-deny.json"),
                                   cfg))["permissions"]["deny"]
    merge_settings(root, deny_rules)

    print("done. Review with git status / git diff, then commit the scaffold "
          "as one attributed commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
