#!/usr/bin/env python3
"""Deterministic scaffold for the lab-loop plugin (run by /lab-loop:init).

Usage: init-scaffold.py [repo-root]
                        [--hypotheses-dir P] [--runs-dir P]
                        [--template-file P] [--preflight-file P]

lab-loop extends lab-intake: the journal and capture discipline live
in the base plugin, so this scaffold refuses to run (exit 1, with instructions,
writing nothing) until the base is initialized in the repository.

Idempotent and re-runnable. Creates what is missing, repairs the plugin-owned
artifacts (the config file, the installed preflight script, the CLAUDE.md
marker block), and never overwrites consumer-owned content (registered specs,
run artifacts, or a spec template the consumer has edited). Prints one line
per artifact: created / updated / unchanged / kept.

Everything written is rendered from the plugin's templates and shipped scripts
with the chosen paths. Output contains no timestamps or randomness, so
re-running with the same inputs is byte-stable. Stdlib only.
"""
import argparse
import json
import os
import sys

PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULTS = {
    "hypotheses_dir": "hypotheses",
    "runs_dir": "experiments/runs",
    "template_file": "hypotheses/TEMPLATE.md",
    "preflight_file": "experiments/preflight.py",
}

BASE_CONFIG_RELPATH = os.path.join(".claude", "lab-intake.json")

REFUSAL = """\
lab-loop: the lab-intake base plugin is not initialized in this repository
(missing .claude/lab-intake.json).

This plugin extends lab-intake — the journal and capture discipline live there.
  1. Install the lab-intake plugin (declared in this plugin's manifest dependencies).
  2. Run /lab-intake:init in this repository.
  3. Re-run /lab-loop:init.

No files were written."""


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
        print("kept      %s  (%s — differs from the plugin canonical; left as-is)"
              % (relpath, label))


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
        print("created   CLAUDE.md  (with the lab-loop rules block)")
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

    # 0. Base check: refuse, writing nothing, until lab-intake is initialized.
    if not os.path.isfile(os.path.join(root, BASE_CONFIG_RELPATH)):
        print(REFUSAL)
        return 1

    # 1. Config file (plugin-owned; canonical for the chosen paths).
    ensure_file(root, os.path.join(".claude", "lab-loop.json"),
                json.dumps(cfg, indent=2, sort_keys=True) + "\n",
                "path configuration", overwrite=True)

    # 2. Directories.
    ensure_dir(root, cfg["hypotheses_dir"], "hypothesis specs, one file each")
    ensure_dir(root, cfg["runs_dir"],
               "run artifacts: <id>/fixture/ shared inputs, <id>/run-<k>/ outputs")

    # 3. Consumer-owned seed (never overwritten once created).
    ensure_file(root, cfg["template_file"],
                render(template("HYPOTHESIS-TEMPLATE.md"), cfg), "spec template")

    # 4. Plugin-owned executable (repaired to canonical).
    preflight_src = read(os.path.join(PLUGIN_ROOT, "scripts", "preflight.py"))
    if preflight_src is not None:
        ensure_file(root, cfg["preflight_file"], preflight_src,
                    "deterministic spec pre-flight", overwrite=True)

    # 5. CLAUDE.md marker block (plugin-owned block inside a consumer file).
    install_claude_block(root, render(template("CLAUDE-block.md"), cfg))

    print("done. Review with git status / git diff, then commit the scaffold "
          "as one attributed commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
