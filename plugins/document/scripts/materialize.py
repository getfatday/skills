#!/usr/bin/env python3
"""materialize.py — install document-plugin operational templates as
self-sufficient repo-local skills.

Tier-1 plugin-only helper for `/document:upgrade materialize`. Reads a
template under `plugins/document/templates/<name>/`, copies SKILL.md +
scripts + evals into a consuming repo's `.claude/skills/<name>/`, injects
provenance, and writes a repo-local command at `.claude/commands/<name>.md`
(unnamespaced — e.g. `/document-events`). Also writes Cursor and Codex
mirrors so the materialized form works in all three IDEs.

Zero third-party dependencies. Python 3 stdlib only.

    python3 materialize.py [-C <repo>] --template <name> [--all] [--dry-run]
                            [--installed-plugin-root <path>]
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import shutil
import sys

__version__ = "0.1.0"

# Sentinel delimiters for the materialized-script provenance header block —
# must match upgrade-scan.py's parser exactly.
PROVENANCE_OPEN = "# --- document:provenance ---"
PROVENANCE_CLOSE = "# --- end provenance ---"


# --------------------------------------------------------------------------
# installed-plugin metadata
# --------------------------------------------------------------------------

def read_plugin_metadata(plugin_root):
    """Return the metadata the materializer stamps into each artifact:
    factory-version (from plugin.json), generator-version (from the
    document-define spec)."""
    plugin_json = json.loads(
        (plugin_root / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
    )
    define_spec = (plugin_root / "skills/document-define/SKILL.md").read_text(
        encoding="utf-8"
    )
    match = re.search(r'generator-version:\s*"([^"]+)"', define_spec)
    return {
        "factory-version": plugin_json.get("version", ""),
        "generator-version": match.group(1) if match else "",
    }


# --------------------------------------------------------------------------
# provenance injection — frontmatter (skills/commands) and script header
# --------------------------------------------------------------------------

PROVENANCE_FRONTMATTER_LINES = (
    "factory", "factory-version", "generated-by", "generator-version",
    "source", "materialized", "tier",
)


def inject_skill_frontmatter(text, *, factory_version, generator_version,
                             source, today):
    """Insert the provenance stamp into a skill or command's YAML frontmatter.

    Existing fields (e.g. `name`, `description`, `tier` already on the
    template) are preserved; provenance fields are added or updated. The
    frontmatter block must already exist and be properly delimited.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("template has no leading frontmatter block")
    end = next(i for i, ln in enumerate(lines[1:], 1) if ln.strip() == "---")

    fm = lines[1:end]
    body = lines[end + 1:]

    stamped = {
        "factory": '"document"',
        "factory-version": f'"{factory_version}"',
        "generated-by": '"document-upgrade"',
        "generator-version": f'"{generator_version}"',
        "source": f'"templates/{source}"',
        "materialized": f'"{today}"',
    }

    seen = set()
    new_fm = []
    for line in fm:
        m = re.match(r"^([a-zA-Z][a-zA-Z0-9_-]*)\s*:", line)
        if m and m.group(1) in stamped:
            new_fm.append(f"{m.group(1)}: {stamped[m.group(1)]}")
            seen.add(m.group(1))
        else:
            new_fm.append(line)
    for field in PROVENANCE_FRONTMATTER_LINES:
        if field == "tier":
            continue  # template already declares its tier
        if field not in seen and field in stamped:
            new_fm.append(f"{field}: {stamped[field]}")

    return "\n".join(["---", *new_fm, "---", *body]) + ("\n" if text.endswith("\n") else "")


def inject_script_provenance(text, *, factory_version, generator_version,
                             source, today):
    """Insert a `# --- document:provenance ---` header block into a Python
    script. Placed between the shebang and the module docstring; an existing
    provenance block is replaced in place so re-materialization is
    idempotent in shape."""
    lines = text.splitlines()
    header = [
        PROVENANCE_OPEN,
        "# factory: document",
        f"# factory-version: {factory_version}",
        "# generated-by: document-upgrade",
        f"# generator-version: {generator_version}",
        f"# source: templates/{source}",
        f"# materialized: {today}",
        "# tier: 2-materialized",
        PROVENANCE_CLOSE,
    ]

    # If a previous provenance block exists, locate and replace it.
    start_idx = next(
        (i for i, ln in enumerate(lines) if ln.strip() == PROVENANCE_OPEN), None
    )
    if start_idx is not None:
        end_idx = next(
            i for i, ln in enumerate(lines[start_idx + 1:], start_idx + 1)
            if ln.strip() == PROVENANCE_CLOSE
        )
        return "\n".join(lines[:start_idx] + header + lines[end_idx + 1:]) + (
            "\n" if text.endswith("\n") else "")

    # No existing block: insert after the shebang (and after a leading
    # docstring if no shebang).
    insert_at = 1 if lines and lines[0].startswith("#!") else 0
    return "\n".join(lines[:insert_at] + header + lines[insert_at:]) + (
        "\n" if text.endswith("\n") else "")


# --------------------------------------------------------------------------
# command + IDE-mirror generation
# --------------------------------------------------------------------------

def render_command(name, description, factory_version, generator_version,
                   today):
    """Render the repo-local command file (unnamespaced — `/<name>`)."""
    return (
        f"---\n"
        f"name: {name}\n"
        f"description: {_yaml_quote(description)}\n"
        f"factory: 'document'\n"
        f"factory-version: {_yaml_quote(factory_version)}\n"
        f"generated-by: 'document-upgrade'\n"
        f"generator-version: {_yaml_quote(generator_version)}\n"
        f"source: 'templates/{name}/SKILL.md'\n"
        f"materialized: {_yaml_quote(today)}\n"
        f"tier: 2-materialized\n"
        f"allowed-tools:\n"
        f"  - Read\n"
        f"  - Bash\n"
        f"  - Glob\n"
        f"  - Grep\n"
        f"---\n\n"
        f"<workflow>\n"
        f"Route to `.claude/skills/{name}/SKILL.md`. The skill is\n"
        f"self-sufficient — it runs without the document plugin installed.\n"
        f"</workflow>\n"
    )


def render_rulesync_skill(name, description, body):
    """Render a SKILL.md for `.rulesync/skills/<name>/`. Reduced
    frontmatter (only name + description — what every target
    propagates) + full canonical body, so rulesync's fanout produces
    rich per-target outputs.

    Replaces the old `render_mirror_skill` (3-line strawman) — the
    materializer now stages into `.rulesync/` and lets rulesync
    handle per-target translation.
    """
    one_line = " ".join(description.split())
    return (
        f"---\nname: {name}\n"
        f"description: {_yaml_quote(one_line)}\n---\n"
        f"{body.rstrip()}\n"
    )


def render_rulesync_command(name, description):
    """Render a command file for `.rulesync/commands/<name>.md`."""
    one_line = " ".join(description.split())
    return (
        f"---\ndescription: {_yaml_quote(one_line)}\n"
        f"argument-hint: \"\"\n---\n\n"
        f"<workflow>\n"
        f"Route to the repo-local `/{name}` command. The skill body is\n"
        f"in `<target-dir>/skills/{name}/SKILL.md`.\n"
        f"</workflow>\n"
    )


# --------------------------------------------------------------------------
# materialization
# --------------------------------------------------------------------------

def _yaml_quote(value):
    """Single-quoted YAML string — backslashes are literal, embedded single
    quotes are doubled. Safe for any content, including quotes the template
    description happens to use."""
    return "'" + value.replace("'", "''") + "'"


def _extract_description(skill_text):
    """Return a one-line description from a template's frontmatter, folding
    YAML `>` / `|` block scalars. Bounded strictly to the frontmatter block
    (never reads the skill body) and stops at the next top-level field —
    otherwise a `trigger-phrases:` list right below `description: >` would
    bleed in and corrupt the command file's YAML head."""
    lines = skill_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    try:
        end = next(i for i, ln in enumerate(lines[1:], 1) if ln.strip() == "---")
    except StopIteration:
        return ""

    fm = lines[1:end]
    for i, line in enumerate(fm):
        m = re.match(r"^description:\s*(>-?|\|-?)?\s*(.*)$", line)
        if not m:
            continue
        marker, inline = m.group(1), m.group(2).strip()
        if not marker:
            # Inline scalar form: `description: text` (possibly quoted).
            return inline.strip("\"'") if inline else ""
        # Block scalar: gather continuation lines (indented) until the
        # next top-level key (line starting in column 0 with a non-space).
        cont = []
        for nl in fm[i + 1:]:
            if not nl.strip():
                continue  # blank lines inside a block fold to a paragraph break
            if not nl[:1].isspace():
                break  # back to a top-level frontmatter field — stop
            cont.append(nl.strip())
        return " ".join(cont)
    return ""


def materialize_template(plugin_root, repo_root, name, *, dry_run=False,
                         today=None):
    """Materialize one template into the consuming repo. Returns a list of
    relative paths written (or that would be written, when dry_run)."""
    template_dir = plugin_root / "templates" / name
    if not template_dir.is_dir():
        raise FileNotFoundError(f"no template at templates/{name}")
    if today is None:
        today = datetime.date.today().isoformat()

    metadata = read_plugin_metadata(plugin_root)
    fv = metadata["factory-version"]
    gv = metadata["generator-version"]

    written = []

    def _write(path, content):
        written.append(str(path.relative_to(repo_root)))
        if dry_run:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    # SKILL.md — inject provenance frontmatter.
    skill_text = (template_dir / "SKILL.md").read_text(encoding="utf-8")
    materialized_skill = inject_skill_frontmatter(
        skill_text, factory_version=fv, generator_version=gv,
        source=f"{name}/SKILL.md", today=today,
    )
    _write(repo_root / ".claude/skills" / name / "SKILL.md", materialized_skill)

    # Description for the command + IDE mirrors.
    description = _extract_description(skill_text) or name

    # scripts/ — inject the provenance header into each Python script.
    for script in sorted((template_dir / "scripts").glob("*.py")) \
            if (template_dir / "scripts").is_dir() else []:
        if script.name.startswith("test_"):
            continue  # tests are dev-time artifacts; not materialized
        original = script.read_text(encoding="utf-8")
        materialized = inject_script_provenance(
            original, factory_version=fv, generator_version=gv,
            source=f"{name}/scripts/{script.name}", today=today,
        )
        _write(repo_root / ".claude/skills" / name / "scripts" / script.name,
               materialized)

    # evals/ — copy verbatim.
    if (template_dir / "evals").is_dir():
        for eval_file in sorted((template_dir / "evals").glob("*")):
            if eval_file.is_file():
                _write(repo_root / ".claude/skills" / name / "evals" / eval_file.name,
                       eval_file.read_text(encoding="utf-8"))

    # Command file — repo-local, unnamespaced.
    command_text = render_command(name, description, fv, gv, today)
    _write(repo_root / ".claude/commands" / f"{name}.md", command_text)

    # Stage into `.rulesync/skills/<name>/` and `.rulesync/commands/<name>.md`
    # so the multi-harness fanout (cursor / codexcli / …) can pick it up.
    # Per-target writes happen in `finalize_targets()` after every
    # template is staged.
    _stage_rulesync_inputs(repo_root, name, materialized_skill, command_text,
                            dry_run=dry_run, written=written)

    return written


def _stage_rulesync_inputs(repo_root, name, materialized_skill, command_text,
                            *, dry_run, written):
    """Stage one materialized template's canonical content into
    `.rulesync/`. Imported lazily so test fixtures can stub the
    sibling module."""
    if dry_run:
        # Report what we'd stage without touching disk.
        written.append(f".rulesync/skills/{name}/SKILL.md")
        written.append(f".rulesync/commands/{name}.md")
        return

    here = pathlib.Path(__file__).resolve().parent
    sys.path.insert(0, str(here))
    try:
        import multi_target_emit as mte  # type: ignore
    finally:
        sys.path[:] = [p for p in sys.path if p != str(here)]

    description = _extract_description(materialized_skill) or name
    body = materialized_skill.split("---\n", 2)[-1] if materialized_skill.count("---\n") >= 2 else materialized_skill
    rulesync_skill_text = render_rulesync_skill(name, description, body)

    paths = mte.stage_into_rulesync(
        repo_root=repo_root, name=name,
        skill_text=rulesync_skill_text,
        command_text=command_text,
    )
    written.extend(paths)


def finalize_targets(repo_root, *, dry_run=False, targets=None, features=None):
    """Run after every template materialization. Reads the configured
    target list from `.config/documents/rulesync.jsonc`, invokes
    `npx rulesync generate` for the staged content, and returns a
    structured result.

    Caller (CLI / `/document:upgrade`) decides how to surface a
    `deferred` or `failed` status. `dry_run=True` skips the actual
    rulesync invocation."""
    here = pathlib.Path(__file__).resolve().parent
    sys.path.insert(0, str(here))
    try:
        import multi_target_emit as mte  # type: ignore
        import target_config as tc  # type: ignore
    finally:
        sys.path[:] = [p for p in sys.path if p != str(here)]

    if targets is None or features is None:
        config_path = tc.config_path_for(repo_root)
        config = tc.load_target_config(config_path)
        if targets is None:
            targets = tc.parsed_targets(config)
        if features is None:
            features = tc.parsed_features(config)

    if dry_run:
        return {
            "status": "dry-run", "reason": "not invoking rulesync",
            "targets": targets, "features": features,
        }

    result = mte.run_rulesync(repo_root, targets, features)
    return {
        "status": result.status,
        "reason": result.reason,
        "targets": list(result.targets),
        "features": features,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
        "fallback_plan": (
            mte.fallback_plan(repo_root, targets)
            if result.status == "deferred" else None
        ),
    }


def list_templates(plugin_root):
    """All templates the plugin offers."""
    return sorted(d.name for d in (plugin_root / "templates").iterdir()
                  if d.is_dir() and (d / "SKILL.md").is_file())


def post_generate(plugin_root, repo_root, name, *, dry_run=False):
    """Run cross-IDE fanout for a Tier-3 skill just produced by
    `document-define`'s generate / regenerate operation.

    The Tier-3 generator writes `.claude/skills/<name>/SKILL.md` and
    `.claude/commands/<name>.md` directly — it does not go through
    `materialize_template()`, so the rulesync staging done there never
    fires. This helper closes that gap:

    1. Reads the canonical `.claude/skills/<name>/SKILL.md`.
    2. Stages a reduced-frontmatter copy (name + description + body)
       into `.rulesync/skills/<name>/SKILL.md`.
    3. Reads the canonical command file (if present); stages a copy
       into `.rulesync/commands/<name>.md`.
    4. Returns a dict with the staged paths and the fanout result
       from `finalize_targets()` — so the calling skill can route
       `ok` / `failed` / `deferred` statuses to the same handlers
       Phase 3 set up for the Tier-2 path.

    `dry_run=True` reports what would be staged without invoking
    rulesync or touching `.rulesync/`.
    """
    repo_root = pathlib.Path(repo_root)
    skill_src = repo_root / ".claude" / "skills" / name / "SKILL.md"
    if not skill_src.is_file():
        raise FileNotFoundError(
            f"no Tier-3 skill at {skill_src} — run /document:define "
            f"{name} first"
        )

    canonical_skill = skill_src.read_text(encoding="utf-8")
    description = _extract_description(canonical_skill) or name
    # The body starts after the second `---\n` boundary; if frontmatter
    # parsing fails (no closing `---`), fall back to the whole file so
    # the staging still includes something useful.
    parts = canonical_skill.split("---\n", 2)
    body = parts[2] if len(parts) >= 3 else canonical_skill

    rulesync_skill_text = render_rulesync_skill(name, description, body)

    cmd_src = repo_root / ".claude" / "commands" / f"{name}.md"
    command_text = (
        cmd_src.read_text(encoding="utf-8") if cmd_src.is_file() else None
    )

    if dry_run:
        staged = [f".rulesync/skills/{name}/SKILL.md"]
        if command_text:
            staged.append(f".rulesync/commands/{name}.md")
        return {"staged": staged, "fanout": None, "dry_run": True}

    here = pathlib.Path(__file__).resolve().parent
    sys.path.insert(0, str(here))
    try:
        import multi_target_emit as mte  # type: ignore
    finally:
        sys.path[:] = [p for p in sys.path if p != str(here)]

    staged = mte.stage_into_rulesync(
        repo_root=repo_root, name=name,
        skill_text=rulesync_skill_text,
        command_text=command_text,
    )

    fanout = finalize_targets(repo_root)
    return {"staged": staged, "fanout": fanout, "dry_run": False}


def materialize_root_config(plugin_root, repo_root, *, dry_run=False):
    """Ensure the consumer repo has a `.config/documents/rulesync.jsonc`.

    If the file already exists, this is a no-op (don't clobber a
    user-edited config). Otherwise the default template under
    `templates/_root/rulesync.jsonc` is copied into place verbatim.

    Returns the list of paths written (repo-relative). Empty list when
    the file already existed.
    """
    target = repo_root / ".config" / "documents" / "rulesync.jsonc"
    if target.is_file():
        return []
    if dry_run:
        return [str(target.relative_to(repo_root))]

    source = plugin_root / "templates" / "_root" / "rulesync.jsonc"
    if not source.is_file():
        raise FileNotFoundError(
            f"missing default config template: {source}"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return [str(target.relative_to(repo_root))]


# --------------------------------------------------------------------------
# git-hooks materialization
# --------------------------------------------------------------------------

# Marker line in pre-commit; presence indicates the document-plugin block
# is already wired in.
PRECOMMIT_MARKER = "# document-plugin: validate staged docs"

PRECOMMIT_INVOCATION = (
    f"{PRECOMMIT_MARKER}\n"
    'python3 "$(git rev-parse --show-toplevel)/.githooks/'
    'document-validate-staged.py" || exit $?\n'
)

PRECOMMIT_NEW_HEADER = """\
#!/bin/bash
# pre-commit hook — materialized by the document plugin.
#
# Document type-integrity check: blocks commits whose staged .md files
# violate their declared type definition (missing required fields or
# sections, unknown type, off-lifecycle status). The Python script is
# self-contained — works with no plugin installed.
#
# Activate this hooks directory:  git config core.hooksPath .githooks
# Bypass for an emergency:        git commit --no-verify

"""


def _inject_script_provenance_explicit(text, *, factory_version,
                                        generator_version, source, today,
                                        tier):
    """Like `inject_script_provenance` but accepts the source path
    verbatim (no `templates/` prefix). Used for scripts materialized
    from `scripts/` rather than `templates/`."""
    lines = text.splitlines()
    header = [
        PROVENANCE_OPEN,
        "# factory: document",
        f"# factory-version: {factory_version}",
        "# generated-by: document-upgrade",
        f"# generator-version: {generator_version}",
        f"# source: {source}",
        f"# materialized: {today}",
        f"# tier: {tier}",
        PROVENANCE_CLOSE,
    ]
    start_idx = next(
        (i for i, ln in enumerate(lines) if ln.strip() == PROVENANCE_OPEN), None
    )
    if start_idx is not None:
        end_idx = next(
            i for i, ln in enumerate(lines[start_idx + 1:], start_idx + 1)
            if ln.strip() == PROVENANCE_CLOSE
        )
        return "\n".join(lines[:start_idx] + header + lines[end_idx + 1:]) + (
            "\n" if text.endswith("\n") else "")
    insert_at = 1 if lines and lines[0].startswith("#!") else 0
    return "\n".join(lines[:insert_at] + header + lines[insert_at:]) + (
        "\n" if text.endswith("\n") else "")


def materialize_githooks(plugin_root, repo_root, *, dry_run=False, today=None):
    """Install the document-validator + pre-commit invocation under
    `<repo>/.githooks/`. Returns list of repo-relative paths written.

    Idempotent: re-running replaces the validator script and the
    invocation line but preserves any other pre-commit content the
    repo's authors added.
    """
    if today is None:
        today = datetime.date.today().isoformat()

    metadata = read_plugin_metadata(plugin_root)
    fv = metadata["factory-version"]
    gv = metadata["generator-version"]

    written = []

    def _write(path, content, *, executable=False):
        written.append(str(path.relative_to(repo_root)))
        if dry_run:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        if executable:
            path.chmod(0o755)

    # 1. document_validator.py — self-sufficient library
    validator_src = plugin_root / "scripts" / "document_validator.py"
    validator_text = _inject_script_provenance_explicit(
        validator_src.read_text(encoding="utf-8"),
        factory_version=fv, generator_version=gv,
        source="scripts/document_validator.py", today=today,
        tier="2-materialized",
    )
    _write(repo_root / ".githooks" / "document_validator.py", validator_text)

    # 2. document-validate-staged.py — pre-commit entry point
    staged_src = plugin_root / "scripts" / "check-document-staged.py"
    staged_text = _inject_script_provenance_explicit(
        staged_src.read_text(encoding="utf-8"),
        factory_version=fv, generator_version=gv,
        source="scripts/check-document-staged.py", today=today,
        tier="2-materialized",
    )
    _write(repo_root / ".githooks" / "document-validate-staged.py",
           staged_text, executable=True)

    # 3. pre-commit — create new, or merge into existing without
    # clobbering hand-written checks.
    precommit_path = repo_root / ".githooks" / "pre-commit"
    if precommit_path.exists():
        existing = precommit_path.read_text(encoding="utf-8")
        if PRECOMMIT_MARKER in existing:
            return written  # already wired, leave alone
        existing_lines = existing.splitlines(keepends=True)
        if existing_lines and existing_lines[0].startswith("#!"):
            merged = (existing_lines[0]
                      + "\n" + PRECOMMIT_INVOCATION + "\n"
                      + "".join(existing_lines[1:]))
        else:
            merged = PRECOMMIT_INVOCATION + "\n" + existing
        _write(precommit_path, merged, executable=True)
    else:
        _write(precommit_path,
               PRECOMMIT_NEW_HEADER + PRECOMMIT_INVOCATION,
               executable=True)

    return written


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="materialize.py",
        description=("Materialize a document-plugin template into the "
                     "consuming repo as a self-sufficient skill."),
    )
    parser.add_argument("--version", action="version",
                        version=f"materialize.py {__version__}")
    parser.add_argument("-C", "--repo", default=".",
                        help="consuming repository (default: current directory)")
    parser.add_argument(
        "--installed-plugin-root",
        default=str(pathlib.Path(__file__).resolve().parents[1]),
        help="path to the installed document plugin (default: this script's plugin)",
    )
    parser.add_argument("--template", help="template name (e.g. document-events)")
    parser.add_argument("--all", action="store_true",
                        help="materialize every template the plugin offers, "
                             "including the .githooks/ pre-commit bundle and "
                             "run cross-IDE fanout via rulesync")
    parser.add_argument("--githooks", action="store_true",
                        help="materialize only the .githooks/ pre-commit bundle "
                             "(document-validate-staged.py + invocation line)")
    parser.add_argument("--post-generate", metavar="NAME", default=None,
                        help="stage an already-generated Tier-3 skill at "
                             "`.claude/skills/NAME/` into `.rulesync/` and "
                             "run cross-IDE fanout. Called by document-define's "
                             "generate / regenerate operations so a new or "
                             "updated type propagates to all configured "
                             "harnesses without a manual /document:upgrade.")
    parser.add_argument("--list", action="store_true",
                        help="list available templates and exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be written without writing")
    parser.add_argument("--no-fanout", action="store_true",
                        help="skip the rulesync invocation; .rulesync/ is "
                             "staged but no per-target outputs are produced "
                             "(useful for tests and for staging across multiple "
                             "templates before a single fanout)")
    parser.add_argument("--targets", default=None,
                        help="comma-separated target list, overriding "
                             ".config/documents/rulesync.jsonc")
    args = parser.parse_args(argv)

    plugin_root = pathlib.Path(args.installed_plugin_root).resolve()
    repo_root = pathlib.Path(args.repo).resolve()

    if args.list:
        for name in list_templates(plugin_root):
            print(name)
        return 0

    names = list_templates(plugin_root) if args.all else (
        [args.template] if args.template else []
    )
    if (not names and not args.githooks and not args.all
            and not args.post_generate):
        parser.error("specify --template <name>, --all, --githooks, "
                     "--post-generate <name>, or --list")

    # --post-generate is a focused mode: stage one Tier-3 skill into
    # `.rulesync/` and run the fanout. No template materialization, no
    # githooks. Reports and returns.
    if args.post_generate:
        try:
            result = post_generate(plugin_root, repo_root,
                                    args.post_generate,
                                    dry_run=args.dry_run)
        except FileNotFoundError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        json.dump(result, sys.stdout, indent=2, sort_keys=True, default=str)
        sys.stdout.write("\n")
        return 0

    summary: dict = {}
    for name in names:
        try:
            summary[name] = materialize_template(
                plugin_root, repo_root, name, dry_run=args.dry_run,
            )
        except FileNotFoundError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    if args.all:
        # Ensure root-level config is present (no-op if user-edited).
        summary["__root_config__"] = materialize_root_config(
            plugin_root, repo_root, dry_run=args.dry_run,
        )

    if args.all or args.githooks:
        summary["__githooks__"] = materialize_githooks(
            plugin_root, repo_root, dry_run=args.dry_run,
        )

    # Cross-IDE fanout — runs after all templates are staged so a
    # single rulesync invocation covers everything.
    fanout: dict | None = None
    if (args.all or names) and not args.no_fanout:
        target_override = (
            [t.strip() for t in args.targets.split(",") if t.strip()]
            if args.targets else None
        )
        fanout = finalize_targets(
            repo_root, dry_run=args.dry_run, targets=target_override,
        )

    payload = {"dry_run": args.dry_run, "materialized": summary}
    if fanout is not None:
        payload["fanout"] = fanout
    json.dump(payload, sys.stdout, indent=2, sort_keys=True, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
