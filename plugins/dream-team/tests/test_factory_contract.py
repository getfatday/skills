"""Layer 2 — factory-contract compliance.

Mechanically enforces the rules in `plugins/dream-team/FACTORY.md`: tier
declarations, the provenance stamp, the self-sufficiency rule, and config
schema-version coherence. Deterministic; runs on every commit via `make test`.

What this CANNOT check (stays human-reviewed): whether a tier classification
is *correct*, whether a skill's prose secretly assumes the plugin, whether a
migration step is idempotent, whether a persona's voice is faithful to the
expert. See FACTORY.md "What CI enforces — and what it cannot".
"""
import pathlib

import pytest

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[1]

VALID_TIERS = {"1-plugin", "2-plugin", "2-materialized", "3"}

SKILL_FILES = sorted(PLUGIN_ROOT.glob("skills/*/SKILL.md"))
# Materializable templates live under three buckets:
#   templates/team-assemble/SKILL.md     — the workflow engine
#   templates/orchestrator/orchestrator.md — the team-lead agent
#   templates/team-commands/<verb>/<verb>.md — the 4 entry commands
# The other template subtrees (team-members/, teams/, team-member-plugin) are
# factory library content — they do NOT carry a tier:/materialized: stamp on
# their bundled file; the stamp is added when the materializer renders them
# into a consumer.
TEMPLATE_SKILL_FILES = (
    sorted(p for p in PLUGIN_ROOT.glob("templates/team-assemble/SKILL.md"))
    + sorted(p for p in PLUGIN_ROOT.glob("templates/orchestrator/orchestrator.md"))
    + sorted(PLUGIN_ROOT.glob("templates/team-commands/*/*.md"))
)

PROVENANCE_FIELDS = (
    "factory:", "factory-version:", "generated-by:", "generator-version:",
    "source:", "materialized:", "tier:",
)


def _skill_name(skill_md):
    return skill_md.parent.name


def test_factory_contract_document_exists():
    assert (PLUGIN_ROOT / "FACTORY.md").is_file(), "plugins/dream-team/FACTORY.md missing"


def test_plugin_claude_md_exists():
    assert (PLUGIN_ROOT / "CLAUDE.md").is_file(), "plugins/dream-team/CLAUDE.md missing"


def test_skills_present():
    """Anti-vacuous guard: the rest of this module parametrizes over skills,
    so an empty glob would make every parametrized test silently pass."""
    assert SKILL_FILES, "no skills found under plugins/dream-team/skills/"


@pytest.mark.parametrize("skill_md", SKILL_FILES, ids=_skill_name)
def test_skill_declares_valid_tier(skill_md, frontmatter):
    """Every plugin skill must declare a `tier:` from the FACTORY.md enum.

    Plugin-resident skills are 1-plugin. Transitional skills (assemble, consult)
    that will move into templates/ in Phase 2c are also 1-plugin until they
    are deleted.
    """
    fields = frontmatter(skill_md)
    tier = fields.get("tier")
    assert tier in VALID_TIERS, (
        f"{skill_md.relative_to(PLUGIN_ROOT)}: tier={tier!r} not in {sorted(VALID_TIERS)}"
    )


def test_materialized_templates_present():
    """The operational templates that Phase 2e materializes into consumer
    repos. Phase 2c populated them."""
    assert TEMPLATE_SKILL_FILES, "no materializable templates found"


@pytest.mark.parametrize(
    "template_md",
    TEMPLATE_SKILL_FILES,
    ids=lambda p: str(p.relative_to(PLUGIN_ROOT)),
)
def test_template_carries_tier_and_materialized(template_md, frontmatter):
    """Every materializable template carries tier: and materialized: in its
    own frontmatter — these survive to the consumer's frontmatter unchanged.
    The remaining provenance fields (factory, factory-version, generated-by,
    generator-version, source) are stamped by the materializer at emit time;
    they are asserted on the generator skill, not on templates."""
    fields = frontmatter(template_md)
    assert fields.get("tier") == "2-materialized", (
        f"{template_md.relative_to(PLUGIN_ROOT)}: tier={fields.get('tier')!r}, "
        "expected '2-materialized'"
    )
    materialized = fields.get("materialized")
    assert materialized, (
        f"{template_md.relative_to(PLUGIN_ROOT)}: missing or empty materialized: <date> stamp "
        f"(got {materialized!r})"
    )


def test_generator_emits_full_provenance_stamp():
    """`team-member-recruit` must emit every provenance field *together* onto
    the per-member artifacts it generates (FACTORY.md provenance standard).
    Checked as one contiguous fenced block, so a partial or split stamp is
    caught — not only the wholesale deletion of a field name."""
    import re
    spec_path = PLUGIN_ROOT / "skills/team-member-recruit/SKILL.md"
    spec = spec_path.read_text(encoding="utf-8")
    fenced_blocks = re.findall(r"(?ms)^[ \t]*```[a-z]*\n(.*?)^[ \t]*```", spec)
    assert fenced_blocks, "team-member-recruit/SKILL.md has no fenced example blocks"
    assert any(
        all(field in block for field in PROVENANCE_FIELDS)
        for block in fenced_blocks
    ), (
        "no fenced block in team-member-recruit/SKILL.md carries the full "
        f"provenance stamp ({', '.join(PROVENANCE_FIELDS)})"
    )


@pytest.mark.parametrize(
    "template_md",
    TEMPLATE_SKILL_FILES,
    ids=lambda p: str(p.relative_to(PLUGIN_ROOT)),
)
def test_template_is_self_sufficient(template_md):
    """A materializable template must not reference ${CLAUDE_PLUGIN_ROOT} or
    plugin-relative paths like plugins/. After materialization, the artifact
    must work with the plugin uninstalled.

    Patterns under templates/team-assemble/patterns/ are exempt from this
    iteration — they are pure pattern definitions read by the materialized
    team-assemble skill via repo-relative path."""
    body = template_md.read_text(encoding="utf-8")
    assert "${CLAUDE_PLUGIN_ROOT}" not in body, (
        f"{template_md.relative_to(PLUGIN_ROOT)}: references ${{CLAUDE_PLUGIN_ROOT}} — "
        "self-sufficiency rule violated"
    )
    # Block ANY `plugins/` path (own plugin or sibling); the materialized
    # artifact lives in a consumer repo that has no plugins/ tree.
    for line_no, line in enumerate(body.splitlines(), start=1):
        if "plugins/" in line:
            assert False, (
                f"{template_md.relative_to(PLUGIN_ROOT)}:{line_no} references a plugins/ path — "
                f"self-sufficiency rule violated: {line.strip()!r}"
            )


def test_materializer_script_present():
    """The materializer script turns templates into materialized artifacts."""
    materialize = PLUGIN_ROOT / "scripts" / "materialize.py"
    assert materialize.is_file(), "scripts/materialize.py missing"


def test_ci_factory_contract_check_present():
    """A CI-runnable wrapper around the contract checks."""
    checker = PLUGIN_ROOT / "scripts" / "check-factory-contract.py"
    assert checker.is_file(), "scripts/check-factory-contract.py missing"


def test_pretooluse_hook_present():
    """PreToolUse hook blocks direct edits to materialized files."""
    hooks_json = PLUGIN_ROOT / "hooks" / "hooks.json"
    edit_check = PLUGIN_ROOT / "scripts" / "check-generated-edit.py"
    assert hooks_json.is_file(), "hooks/hooks.json missing"
    assert edit_check.is_file(), "scripts/check-generated-edit.py missing"

    # hooks.json must register the PreToolUse hook on Edit|Write and point
    # at the materialized integrity checker.
    import json
    data = json.loads(hooks_json.read_text(encoding="utf-8"))
    pretool = data.get("hooks", {}).get("PreToolUse", [])
    assert pretool, "hooks.json missing PreToolUse entry"
    entry = pretool[0]
    assert "Edit" in entry["matcher"]
    assert "Write" in entry["matcher"]
    cmd = entry["hooks"][0]["command"]
    assert "check-generated-edit.py" in cmd
    assert "${CLAUDE_PLUGIN_ROOT}" in cmd


def test_precommit_hook_present():
    """Materialized pre-commit hook script — same validator library, run
    at commit time so the plugin can be uninstalled and integrity holds."""
    validator = PLUGIN_ROOT / "scripts" / "team_member_validator.py"
    staged_check = PLUGIN_ROOT / "scripts" / "check-blueprint-staged.py"
    assert validator.is_file(), "scripts/team_member_validator.py missing"
    assert staged_check.is_file(), "scripts/check-blueprint-staged.py missing"
