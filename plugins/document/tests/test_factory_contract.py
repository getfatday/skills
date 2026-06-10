"""Layer 2 — factory-contract compliance.

Mechanically enforces the rules in `plugins/document/FACTORY.md`: tier
declarations, the provenance stamp, the self-sufficiency rule, and config
schema-version coherence. Deterministic; runs on every commit via `make test`.

What this CANNOT check (stays human-reviewed): whether a tier classification
is *correct*, whether a skill's prose secretly assumes the plugin, whether a
migration step is idempotent. See FACTORY.md "What CI enforces — and what it
cannot".
"""
import json
import pathlib
import re

import pytest

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[1]

VALID_TIERS = {"1-plugin", "2-plugin", "2-materialized", "3"}

SKILL_FILES = sorted(PLUGIN_ROOT.glob("skills/*/SKILL.md"))
TEMPLATE_FILES = sorted(PLUGIN_ROOT.glob("templates/*/SKILL.md"))

PROVENANCE_FIELDS = (
    "factory:", "factory-version:", "generated-by:", "generator-version:",
    "source:", "materialized:", "tier:",
    # Tier-3 stamp adds these; the generator's emitted Tier-3 frontmatter
    # template must include them.
    "type-definition:", "type-definition-hash:",
)


def _skill_name(skill_md):
    return skill_md.parent.name


def test_skills_present():
    """Anti-vacuous guard: the rest of this module parametrizes over skills,
    so an empty glob would make every parametrized test silently pass."""
    assert SKILL_FILES, "no skills found under plugins/document/skills/"


def test_factory_contract_document_exists():
    assert (PLUGIN_ROOT / "FACTORY.md").is_file(), "plugins/document/FACTORY.md missing"


@pytest.mark.parametrize("skill_md", SKILL_FILES, ids=_skill_name)
def test_skill_declares_valid_tier(skill_md, frontmatter):
    """Every plugin skill must declare a `tier:` from the FACTORY.md enum."""
    fields = frontmatter(skill_md)
    assert "tier" in fields, f"{_skill_name(skill_md)}: SKILL.md has no `tier:` field"
    assert fields["tier"] in VALID_TIERS, (
        f"{_skill_name(skill_md)}: tier '{fields['tier']}' not in {sorted(VALID_TIERS)}"
    )


def test_templates_present():
    """The plugin ships materialization templates under templates/. An empty
    glob would make the parametrized template tests vacuously pass."""
    assert TEMPLATE_FILES, "no templates found under plugins/document/templates/"


@pytest.mark.parametrize("template_md", TEMPLATE_FILES, ids=_skill_name)
def test_template_declares_materialized_tier(template_md, frontmatter):
    """Every template represents a materialized artifact and must declare
    `tier: 2-materialized` so `/document:upgrade` knows to materialize it."""
    fields = frontmatter(template_md)
    assert fields.get("tier") == "2-materialized", (
        f"{_skill_name(template_md)}: template tier is "
        f"{fields.get('tier')!r}; expected 2-materialized"
    )


@pytest.mark.parametrize("template_md", TEMPLATE_FILES, ids=_skill_name)
def test_template_is_self_sufficient(template_md):
    """A template must not reference ${CLAUDE_PLUGIN_ROOT} — its output is
    materialized into a consuming repo that has no plugin installed
    (FACTORY.md self-sufficiency rule). The same check covers any colocated
    scripts in the template's `scripts/` directory."""
    template_dir = template_md.parent
    leakers = []
    for path in [template_md, *template_dir.glob("scripts/*")]:
        if path.is_file() and "${CLAUDE_PLUGIN_ROOT}" in path.read_text(encoding="utf-8"):
            leakers.append(path.relative_to(template_dir))
    assert not leakers, (
        f"{_skill_name(template_md)} template references ${{CLAUDE_PLUGIN_ROOT}} "
        f"in: {leakers}. Use a repo-relative path rooted at "
        "$(git rev-parse --show-toplevel) instead."
    )


def test_generator_emits_full_provenance_stamp():
    """`document-define` must emit every provenance field *together* onto the
    per-type artifacts it generates (FACTORY.md provenance standard). Checked
    as one contiguous fenced block, so a partial or split stamp is caught —
    not only the wholesale deletion of a field name."""
    spec = (PLUGIN_ROOT / "skills/document-define/SKILL.md").read_text(encoding="utf-8")
    # The fences sit inside numbered-list items and are indented; allow that.
    fenced_blocks = re.findall(r"(?ms)^[ \t]*```[a-z]*\n(.*?)^[ \t]*```", spec)
    assert fenced_blocks, "document-define/SKILL.md has no fenced example blocks"
    assert any(
        all(field in block for field in PROVENANCE_FIELDS)
        for block in fenced_blocks
    ), (
        "no fenced block in document-define/SKILL.md carries the full "
        f"provenance stamp ({', '.join(PROVENANCE_FIELDS)})"
    )


def test_generator_version_is_consistent_across_templates():
    """document-define declares the canonical `generator-version` in fenced
    template blocks (step 5 + step 7). Every mention must agree — the
    upgrade-scan script picks the first match, so disagreement would
    silently mislead `/document:upgrade`'s drift detection."""
    spec = (PLUGIN_ROOT / "skills/document-define/SKILL.md").read_text(encoding="utf-8")
    versions = re.findall(r'generator-version:\s*"([^"]+)"', spec)
    assert versions, "no generator-version found in document-define spec"
    assert len(set(versions)) == 1, (
        f"generator-version values disagree in document-define/SKILL.md: "
        f"{sorted(set(versions))} — all template emissions must use the same value"
    )


def test_schema_version_is_coherent():
    """`documentSchemaVersion` in plugin.json must agree with
    schema-migrations.md, and the count of migration steps must equal
    (version - 1) — one `## N → N+1` heading per version increment."""
    plugin_json = json.loads(
        (PLUGIN_ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
    )
    version = plugin_json.get("documentSchemaVersion")
    assert isinstance(version, int) and version >= 1, (
        f"plugin.json documentSchemaVersion must be an int >= 1, got {version!r}"
    )

    migrations = PLUGIN_ROOT / "skills/document-define/references/schema-migrations.md"
    assert migrations.is_file(), "schema-migrations.md missing"
    text = migrations.read_text(encoding="utf-8")

    # Strip fenced code blocks first, so a `## N -> N+1` shown as a template
    # example is not miscounted as a real migration step.
    prose = re.sub(r"(?ms)^```.*?^```\s*$", "", text)
    steps = re.findall(r"(?m)^##\s+\d+\s*(?:->|→)\s*\d+\s*$", prose)
    assert len(steps) == version - 1, (
        f"documentSchemaVersion is {version} but schema-migrations.md has "
        f"{len(steps)} migration step(s); expected {version - 1}"
    )
