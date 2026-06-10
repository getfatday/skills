#!/usr/bin/env python3
"""materialize.py — install dream-team operational templates as
self-sufficient repo-local skills, commands, agents, and blueprints.

Tier-1 plugin-only helper for `/dream-team:recruit` (first-run bootstrap)
and `/dream-team:update`. Reads templates under `plugins/dream-team/templates/`
and renders provenance-stamped artifacts into a consuming repo's:

  .config/team/root.md                       # roster manifest (first-run)
  .config/team/team-members/<slug>.md        # blueprint (per member)
  .config/team/teams/<slug>.md               # blueprint (per team)
  .claude/skills/<slug>/SKILL.md             # materialized persona (Tier 3)
  .claude/skills/team-<slug>/SKILL.md        # materialized team (Tier 3)
  .claude/skills/team-assemble/SKILL.md      # workflow engine (Tier 2-materialized)
  .claude/skills/team-assemble/patterns/*    # the 12 conversation patterns
  .claude/agents/orchestrator.md             # team lead (Tier 2-materialized)
  .claude/commands/{consult,coach,plan,review}.md  # entry verbs (Tier 2-materialized)

Zero third-party dependencies. Python 3 stdlib only.

    python3 materialize.py [-C <repo>] --bootstrap
    python3 materialize.py [-C <repo>] --member <slug>
    python3 materialize.py [-C <repo>] --team <slug>
    python3 materialize.py [-C <repo>] --all [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import re
import sys

# Local import — target-specific frontmatter transforms for cursor/copilot.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import target_emit  # noqa: E402

__version__ = "0.1.0"


# --------------------------------------------------------------------------
# Plugin metadata
# --------------------------------------------------------------------------

def read_plugin_metadata(plugin_root):
    """Return (factory-version, generator-version) for stamping artifacts."""
    plugin_json = json.loads(
        (plugin_root / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
    )
    spec_path = plugin_root / "skills/team-member-recruit/SKILL.md"
    if spec_path.is_file():
        spec = spec_path.read_text(encoding="utf-8")
        gv_match = re.search(r'generator-version:\s*"([^"]+)"', spec)
        generator_version = gv_match.group(1) if gv_match else "0.1"
    else:
        generator_version = "0.1"
    return {
        "factory-version": plugin_json.get("version", ""),
        "generator-version": generator_version,
    }


# --------------------------------------------------------------------------
# Provenance injection
# --------------------------------------------------------------------------

PROVENANCE_FRONTMATTER_FIELDS = (
    "factory", "factory-version", "generated-by", "generator-version",
    "source", "materialized", "tier",
)


def _yaml_quote(value):
    """Single-quoted YAML string — safe for any content."""
    return "'" + str(value).replace("'", "''") + "'"


def inject_provenance_frontmatter(
    text, *, factory_version, generator_version, source, today,
    generated_by="team-member-recruit", blueprint_path=None,
    blueprint_hash=None, default_tier=None,
):
    """Add or update provenance fields in a markdown file's YAML frontmatter.

    Existing fields (name, description, tier already on the template) are
    preserved. Provenance fields are added or updated. Optional blueprint
    fields are added for Tier 3 (per-member, per-team) artifacts. If the
    template doesn't already declare `tier:` and `default_tier` is given,
    the default tier is injected.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("template has no leading frontmatter block")
    try:
        end = next(i for i, ln in enumerate(lines[1:], 1) if ln.strip() == "---")
    except StopIteration as exc:
        raise ValueError("frontmatter block is not closed") from exc

    fm = lines[1:end]
    body = lines[end + 1:]

    stamped = {
        "factory": "'dream-team'",
        "factory-version": _yaml_quote(factory_version),
        "generated-by": _yaml_quote(generated_by),
        "generator-version": _yaml_quote(generator_version),
        "source": _yaml_quote(source),
        "materialized": _yaml_quote(today),
    }
    if blueprint_path is not None:
        stamped["blueprint"] = _yaml_quote(blueprint_path)
    if blueprint_hash is not None:
        stamped["blueprint-hash"] = _yaml_quote(blueprint_hash)

    seen = set()
    new_fm = []
    for line in fm:
        m = re.match(r"^([a-zA-Z][a-zA-Z0-9_-]*)\s*:", line)
        if m and m.group(1) in stamped:
            new_fm.append(f"{m.group(1)}: {stamped[m.group(1)]}")
            seen.add(m.group(1))
        else:
            new_fm.append(line)

    # Order: append in canonical order at end (preserves existing field positions
    # where they already appeared, otherwise emits at the tail).
    ordered = list(PROVENANCE_FRONTMATTER_FIELDS)
    if blueprint_path is not None:
        ordered.append("blueprint")
    if blueprint_hash is not None:
        ordered.append("blueprint-hash")
    for field in ordered:
        if field == "tier":
            # Tier is template-owned, but for templates that don't declare it
            # (persona/team skills under templates/team-members/, templates/teams/)
            # the materializer injects default_tier.
            if "tier" not in seen and default_tier is not None:
                new_fm.append(f"tier: {default_tier}")
            continue
        if field not in seen and field in stamped:
            new_fm.append(f"{field}: {stamped[field]}")

    trailing_nl = "\n" if text.endswith("\n") else ""
    return "\n".join(["---", *new_fm, "---", *body]) + trailing_nl


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# `<extends>` path rewriting
# --------------------------------------------------------------------------

# Template paths reference: `team-engineering/skills/engineering/SKILL.md`
# Materialized paths reference: `team-engineering/SKILL.md`
EXTENDS_REWRITES = [
    (
        re.compile(r"team-([\w-]+)/skills/\1/SKILL\.md"),
        r"team-\1/SKILL.md",
    ),
]


def rewrite_extends(text):
    """Rewrite `<extends>` paths from plugin-tree layout to materialized
    `.claude/skills/team-<domain>/SKILL.md` layout."""
    for pattern, repl in EXTENDS_REWRITES:
        text = pattern.sub(repl, text)
    return text


# --------------------------------------------------------------------------
# Materialization
# --------------------------------------------------------------------------

def materialize_team_assemble(plugin_root, repo_root, *, dry_run, today, fv, gv,
                               targets=("claude",)):
    """Materialize the team-assemble workflow engine (SKILL.md + patterns/)
    into each requested target tree (claude → .claude/, cursor → .cursor/,
    copilot → .github/)."""
    template_dir = plugin_root / "templates/team-assemble"
    if not template_dir.is_dir():
        raise FileNotFoundError("templates/team-assemble/ missing")

    written = []
    skill_md = (template_dir / "SKILL.md").read_text(encoding="utf-8")
    stamped = inject_provenance_frontmatter(
        skill_md, factory_version=fv, generator_version=gv,
        source="templates/team-assemble/SKILL.md", today=today,
        generated_by="team-update",
    )
    _emit_skill(repo_root, "team-assemble", stamped,
                dry_run=dry_run, written=written, targets=targets)

    patterns_dir = template_dir / "patterns"
    if patterns_dir.is_dir():
        for pattern_md in sorted(patterns_dir.glob("*.md")):
            content = pattern_md.read_text(encoding="utf-8")
            _emit_reference(repo_root, "team-assemble",
                            f"patterns/{pattern_md.name}", content,
                            dry_run=dry_run, written=written, targets=targets)

    return written


def materialize_orchestrator(plugin_root, repo_root, *, dry_run, today, fv, gv,
                              targets=("claude",)):
    """Materialize the orchestrator agent. Claude only — cursor and copilot
    don't have an agents concept, so those targets are a no-op."""
    template = plugin_root / "templates/orchestrator/orchestrator.md"
    if not template.is_file():
        raise FileNotFoundError("templates/orchestrator/orchestrator.md missing")

    text = template.read_text(encoding="utf-8")
    stamped = inject_provenance_frontmatter(
        text, factory_version=fv, generator_version=gv,
        source="templates/orchestrator/orchestrator.md", today=today,
        generated_by="team-update",
    )
    written = []
    _emit_agent(repo_root, "orchestrator", stamped,
                dry_run=dry_run, written=written, targets=targets)
    return written


def materialize_githooks(plugin_root, repo_root, *, dry_run, today, fv, gv,
                          targets=None):
    """Materialize the pre-commit blueprint-integrity hook into
    `.githooks/` of the consumer repo. The hook keeps working when the
    plugin is uninstalled because it ships with its validator library
    colocated.

    `targets` is accepted for API uniformity with the other materialize_*
    functions but is unused — githooks are tooling, not IDE artifacts."""
    del targets  # unused — keep the kwarg for fanout-loop parity
    scripts_dir = plugin_root / "scripts"
    validator = scripts_dir / "team_member_validator.py"
    checker = scripts_dir / "check-blueprint-staged.py"
    if not validator.is_file() or not checker.is_file():
        raise FileNotFoundError(
            "scripts/team_member_validator.py or "
            "scripts/check-blueprint-staged.py missing"
        )

    pre_commit_dst = repo_root / ".githooks/pre-commit"
    # Pre-flight: don't silently clobber a consumer's existing pre-commit
    # (linter chain, secrets scanner, etc.). Only safe to overwrite when the
    # existing file is one we wrote ourselves (`factory: dream-team` in the
    # banner) or doesn't exist.
    if pre_commit_dst.is_file():
        try:
            head = pre_commit_dst.read_text(encoding="utf-8")[:512]
        except OSError:
            head = ""
        if "factory: dream-team" not in head:
            raise FileExistsError(
                f"{pre_commit_dst.relative_to(repo_root)} already exists and "
                "wasn't authored by the dream-team factory. Refusing to "
                "overwrite. Move it aside or chain the dream-team check by "
                "appending: "
                'python3 "$(dirname "$0")/lib/check-blueprint-staged.py"'
            )

    written = []
    # Validator library (Python module).
    _write(
        repo_root / ".githooks/lib/team_member_validator.py",
        validator.read_text(encoding="utf-8"),
        dry_run, repo_root, written,
    )
    # Pre-commit checker (Python).
    _write(
        repo_root / ".githooks/lib/check-blueprint-staged.py",
        checker.read_text(encoding="utf-8"),
        dry_run, repo_root, written,
    )
    # Pre-commit entry — single line that invokes the python script.
    # python3 may be missing on some contributor machines (Windows GitHub
    # Desktop, slimmed CI images). Fail open with a noisy warning rather
    # than fail closed with "command not found" exit 127 — drift will be
    # caught at the next `/dream-team:update` regardless.
    entry = (
        "#!/usr/bin/env bash\n"
        f"# materialized: {today} | factory: dream-team | "
        f"factory-version: {fv}\n"
        "# Blocks commits that hand-edit materialized dream-team artifacts.\n"
        "# Bypass with `git commit --no-verify` (you take ownership of the "
        "drift).\n"
        "set -e\n"
        'if ! command -v python3 >/dev/null 2>&1; then\n'
        '  echo "dream-team pre-commit: python3 not found on PATH — '
        'skipping blueprint-integrity check. Install python3 or '
        'run /dream-team:update from a python3-capable shell." >&2\n'
        '  exit 0\n'
        'fi\n'
        'exec python3 "$(dirname "$0")/lib/check-blueprint-staged.py"\n'
    )
    _write(pre_commit_dst, entry, dry_run, repo_root, written)
    # The entry needs to be executable, but `_write` doesn't chmod. We
    # post-process here when not in dry-run.
    if not dry_run:
        pre_commit_dst.chmod(0o755)

    return written


def materialize_entry_commands(plugin_root, repo_root, *, dry_run, today, fv, gv,
                                targets=("claude",)):
    """Materialize the 4 entry commands (consult, coach, plan, review) into
    each requested target tree."""
    commands_dir = plugin_root / "templates/team-commands"
    if not commands_dir.is_dir():
        raise FileNotFoundError("templates/team-commands/ missing")

    written = []
    for verb_dir in sorted(commands_dir.iterdir()):
        if not verb_dir.is_dir():
            continue
        verb = verb_dir.name
        cmd_md = verb_dir / f"{verb}.md"
        if not cmd_md.is_file():
            continue
        text = cmd_md.read_text(encoding="utf-8")
        stamped = inject_provenance_frontmatter(
            text, factory_version=fv, generator_version=gv,
            source=f"templates/team-commands/{verb}/{verb}.md", today=today,
            generated_by="team-update",
        )
        _emit_command(repo_root, verb, stamped,
                      dry_run=dry_run, written=written, targets=targets)
    return written


def materialize_team_member(plugin_root, repo_root, slug, *,
                             dry_run, today, fv, gv, keep_blueprint=False,
                             targets=("claude",)):
    """Materialize one team-member: copy blueprint → .config/team/team-members/<slug>.md,
    render persona skill → .claude/skills/<slug>/SKILL.md + references/.

    When `keep_blueprint=True` and the consumer already has a blueprint at
    `.config/team/team-members/<slug>.md`, that on-disk blueprint is treated as
    the source of truth: it is NOT overwritten from the template, and its hash
    seeds the persona-skill provenance stamp. This is the mode `team-member-update`
    uses after merging new research into the blueprint.
    """
    template_dir = plugin_root / "templates/team-members" / slug
    blueprint_src = template_dir / "TEAM-MEMBER.md"
    blueprint_dst = repo_root / ".config/team/team-members" / f"{slug}.md"

    if keep_blueprint and blueprint_dst.is_file():
        blueprint_text = blueprint_dst.read_text(encoding="utf-8")
    else:
        if not blueprint_src.is_file():
            raise FileNotFoundError(
                f"templates/team-members/{slug}/TEAM-MEMBER.md missing"
            )
        blueprint_text = blueprint_src.read_text(encoding="utf-8")

    written = []
    # 1. Blueprint placement: write from template unless preserving an on-disk
    #    blueprint (the user's edited source of truth).
    if not (keep_blueprint and blueprint_dst.is_file()):
        _write(blueprint_dst, blueprint_text, dry_run, repo_root, written)
    blueprint_hash = hashlib.sha256(blueprint_text.encode("utf-8")).hexdigest()
    blueprint_relpath = str(blueprint_dst.relative_to(repo_root))

    # 2. Persona skill — generated from blueprint + extended-knowledge body.
    extended_skill = template_dir / "skills" / slug / "SKILL.md"
    if extended_skill.is_file():
        extended_text = extended_skill.read_text(encoding="utf-8")
        extended_text = rewrite_extends(extended_text)
        stamped = inject_provenance_frontmatter(
            extended_text, factory_version=fv, generator_version=gv,
            source=f"templates/team-members/{slug}/skills/{slug}/SKILL.md",
            today=today, generated_by="team-member-recruit",
            blueprint_path=blueprint_relpath, blueprint_hash=blueprint_hash,
            default_tier="3",
        )
        _emit_skill(repo_root, slug, stamped,
                    dry_run=dry_run, written=written, targets=targets)

    # 3. references/ — copy alongside the persona skill.
    refs_src = template_dir / "skills" / slug / "references"
    if refs_src.is_dir():
        for ref in sorted(refs_src.glob("*.md")):
            _emit_reference(repo_root, slug, f"references/{ref.name}",
                            ref.read_text(encoding="utf-8"),
                            dry_run=dry_run, written=written, targets=targets)

    return written


def materialize_team(plugin_root, repo_root, slug, *, dry_run, today, fv, gv,
                     keep_blueprint=False, targets=("claude",)):
    """Materialize one team: blueprint → .config/team/teams/<slug>.md,
    team skill → .claude/skills/team-<slug>/SKILL.md.

    `keep_blueprint=True` preserves an on-disk team blueprint, mirroring the
    same flag on `materialize_team_member`.
    """
    template_dir = plugin_root / "templates/teams" / slug
    blueprint_src = template_dir / "TEAM.md"
    blueprint_dst = repo_root / ".config/team/teams" / f"{slug}.md"

    if keep_blueprint and blueprint_dst.is_file():
        blueprint_text = blueprint_dst.read_text(encoding="utf-8")
    else:
        if not blueprint_src.is_file():
            raise FileNotFoundError(f"templates/teams/{slug}/TEAM.md missing")
        blueprint_text = blueprint_src.read_text(encoding="utf-8")

    written = []
    if not (keep_blueprint and blueprint_dst.is_file()):
        _write(blueprint_dst, blueprint_text, dry_run, repo_root, written)

    team_skill = template_dir / "skills" / slug / "SKILL.md"
    if team_skill.is_file():
        text = team_skill.read_text(encoding="utf-8")
        # Team skills materialize at .claude/skills/team-<slug>/, so the skill
        # `name:` field needs `team-` prefix if it doesn't already have one.
        text = _ensure_team_prefix(text, slug)
        stamped = inject_provenance_frontmatter(
            text, factory_version=fv, generator_version=gv,
            source=f"templates/teams/{slug}/skills/{slug}/SKILL.md",
            today=today, generated_by="team-member-recruit",
            default_tier="3",
        )
        _emit_skill(repo_root, f"team-{slug}", stamped,
                    dry_run=dry_run, written=written, targets=targets)

        refs_src = template_dir / "skills" / slug / "references"
        if refs_src.is_dir():
            for ref in sorted(refs_src.glob("*.md")):
                _emit_reference(repo_root, f"team-{slug}",
                                f"references/{ref.name}",
                                ref.read_text(encoding="utf-8"),
                                dry_run=dry_run, written=written,
                                targets=targets)

    return written


def _ensure_team_prefix(text, slug):
    """Ensure the SKILL.md frontmatter `name:` is `team-<slug>` (matches the
    materialized directory name)."""
    pattern = re.compile(rf"^(name:\s*)['\"]?{re.escape(slug)}['\"]?\s*$",
                         re.MULTILINE)
    return pattern.sub(rf"\1team-{slug}", text, count=1)


def _write(path, content, dry_run, repo_root, written):
    written.append(str(path.relative_to(repo_root)))
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# --------------------------------------------------------------------------
# Multi-target fanout — Claude (canonical) + Cursor + Copilot mirrors
# --------------------------------------------------------------------------

def _emit_skill(repo_root, slug, stamped, *, dry_run, written, targets):
    """Emit the materialized skill into every requested IDE harness."""
    for target in targets:
        rel_path, content = target_emit.emit_skill(target, stamped, slug)
        _write(repo_root / rel_path, content, dry_run, repo_root, written)


def _emit_command(repo_root, verb, stamped, *, dry_run, written, targets):
    """Emit the materialized entry command into every requested IDE harness."""
    for target in targets:
        rel_path, content = target_emit.emit_command(target, stamped, verb)
        _write(repo_root / rel_path, content, dry_run, repo_root, written)


def _emit_agent(repo_root, agent_name, stamped, *, dry_run, written, targets):
    """Emit an agent — Claude only; cursor/copilot returns None and is skipped."""
    for target in targets:
        result = target_emit.emit_agent(target, stamped, agent_name)
        if result is None:
            continue
        rel_path, content = result
        _write(repo_root / rel_path, content, dry_run, repo_root, written)


def _emit_reference(repo_root, slug, ref_subpath, content, *, dry_run,
                    written, targets):
    """Emit a reference file (under references/, patterns/) — byte-identical
    across every requested target."""
    for target in targets:
        rel_path, body = target_emit.emit_reference(target, content, slug,
                                                    ref_subpath)
        _write(repo_root / rel_path, body, dry_run, repo_root, written)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("-C", "--repo", type=pathlib.Path,
                        default=pathlib.Path.cwd(),
                        help="consumer repo root (default: cwd)")
    parser.add_argument("--plugin-root", type=pathlib.Path,
                        help="dream-team plugin root (default: derived from script location)")
    parser.add_argument("--bootstrap", action="store_true",
                        help="materialize team-assemble + orchestrator + 4 commands")
    parser.add_argument("--member", action="append", default=[],
                        help="materialize a single team-member by slug (repeatable)")
    parser.add_argument("--team", action="append", default=[],
                        help="materialize a single team by slug (repeatable)")
    parser.add_argument("--all", action="store_true",
                        help="materialize bootstrap + every member + every team in the catalog")
    parser.add_argument("--githooks", action="store_true",
                        help="materialize the pre-commit blueprint-integrity hook "
                             "into <repo>/.githooks/. Run `git config core.hooksPath "
                             ".githooks` after this to activate.")
    parser.add_argument("--keep-blueprint", action="store_true",
                        help="preserve on-disk blueprints in .config/team/ — re-stamp only the "
                             "generated skill artifacts. Used by team-member-update after merging "
                             "new research into a blueprint.")
    parser.add_argument("--targets", default="claude,cursor,copilot",
                        help="comma-separated list of IDE harnesses to emit "
                             "into. Default emits all three. Valid: " +
                             ",".join(target_emit.ALL_TARGETS))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args()

    plugin_root = args.plugin_root or pathlib.Path(__file__).resolve().parent.parent
    repo_root = args.repo.resolve()
    today = datetime.date.today().isoformat()
    meta = read_plugin_metadata(plugin_root)
    fv = meta["factory-version"]
    gv = meta["generator-version"]

    targets = tuple(t.strip() for t in args.targets.split(",") if t.strip())
    unknown = [t for t in targets if t not in target_emit.ALL_TARGETS]
    if unknown:
        parser.error(f"unknown target(s): {unknown}. Valid: "
                     f"{list(target_emit.ALL_TARGETS)}")

    actions = []

    if args.bootstrap or args.all:
        actions.append(("team-assemble", materialize_team_assemble))
        actions.append(("orchestrator", materialize_orchestrator))
        actions.append(("entry-commands", materialize_entry_commands))

    if args.githooks or args.all:
        actions.append(("githooks", materialize_githooks))

    written_all = []
    for name, fn in actions:
        written_all.extend(
            fn(plugin_root, repo_root, dry_run=args.dry_run, today=today,
               fv=fv, gv=gv, targets=targets)
        )

    member_slugs = list(args.member)
    team_slugs = list(args.team)
    if args.all:
        catalog = json.loads(
            (plugin_root / "marketplace.json").read_text(encoding="utf-8")
        )
        member_slugs.extend(
            m["name"].removeprefix("team-member-") for m in catalog["members"]
        )
        team_slugs.extend(
            t["name"].removeprefix("team-") for t in catalog["teams"]
        )

    for slug in member_slugs:
        written_all.extend(materialize_team_member(
            plugin_root, repo_root, slug,
            dry_run=args.dry_run, today=today, fv=fv, gv=gv,
            keep_blueprint=args.keep_blueprint, targets=targets,
        ))
    for slug in team_slugs:
        written_all.extend(materialize_team(
            plugin_root, repo_root, slug,
            dry_run=args.dry_run, today=today, fv=fv, gv=gv,
            keep_blueprint=args.keep_blueprint, targets=targets,
        ))

    prefix = "would write" if args.dry_run else "wrote"
    for path in written_all:
        print(f"{prefix}: {path}")
    if not written_all and not actions and not member_slugs and not team_slugs:
        parser.error(
            "nothing to do: pass --bootstrap, --member, --team, --githooks, "
            "or --all"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
