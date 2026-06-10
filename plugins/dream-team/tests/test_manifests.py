"""Layer 2 — manifest validity and consistency.

Checks the plugin manifest, the cursor-plugin manifest, the marketplace entry,
and basic plugin structure. Deterministic; runs on every commit. Mirrors the
logic of the `plugin-validation` CI workflow so a break is caught locally by
`make test` before it reaches CI.
"""
import json
import pathlib

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

PLUGIN_JSON = PLUGIN_ROOT / ".claude-plugin/plugin.json"
CURSOR_PLUGIN_JSON = PLUGIN_ROOT / ".cursor-plugin/plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin/marketplace.json"
FACTORY_MARKETPLACE_JSON = PLUGIN_ROOT / "marketplace.json"

SKILL_FILES = sorted(PLUGIN_ROOT.glob("skills/*/SKILL.md"))


def _load(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def test_skills_present():
    """Anti-vacuous guard for the parametrize over SKILL_FILES below — an
    empty glob would make the test collect zero instances and silently pass."""
    assert SKILL_FILES, "no skills found under plugins/dream-team/skills/"


def test_plugin_json_valid_and_complete():
    """plugin.json is valid JSON with every field plugin-validation requires."""
    manifest = _load(PLUGIN_JSON)
    for field in ("name", "description", "version", "author"):
        assert manifest.get(field), f"plugin.json missing required field {field!r}"
    assert manifest["name"] == "dream-team"


def test_plugin_json_declares_dream_team_schema_version():
    """The factory needs a declared config-schema version (FACTORY.md)."""
    assert "dreamTeamSchemaVersion" in _load(PLUGIN_JSON), (
        "plugin.json must declare dreamTeamSchemaVersion"
    )


def test_cursor_plugin_json_matches_main_manifest():
    """The cross-IDE mirror manifest must agree with .claude-plugin/plugin.json
    on name and version (rulesync regenerates it; drift means a missed run)."""
    main = _load(PLUGIN_JSON)
    mirror = _load(CURSOR_PLUGIN_JSON)
    assert mirror["name"] == main["name"]
    assert mirror["version"] == main["version"], (
        f"version drift: plugin.json={main['version']} cursor-plugin.json={mirror['version']} "
        "— re-run scripts/rulesync.sh dream-team"
    )


def test_marketplace_entry_present():
    """The repo-root marketplace must list this plugin."""
    market = _load(MARKETPLACE_JSON)
    names = {p["name"] for p in market["plugins"]}
    assert "dream-team" in names, "dream-team missing from .claude-plugin/marketplace.json"


def test_no_misplaced_component_directories():
    """skills/agents/hooks/commands must live at the plugin root, never under
    .claude-plugin/ (a plugin-validation rule)."""
    for forbidden in ("skills", "agents", "hooks", "commands"):
        assert not (PLUGIN_ROOT / ".claude-plugin" / forbidden).exists(), (
            f".claude-plugin/{forbidden}/ is misplaced — move it to the plugin root"
        )


def test_factory_marketplace_valid():
    """The factory's own marketplace.json (the team-member + team catalog) is
    valid JSON with the expected shape."""
    catalog = _load(FACTORY_MARKETPLACE_JSON)
    assert "members" in catalog, "factory marketplace.json missing 'members' array"
    assert "teams" in catalog, "factory marketplace.json missing 'teams' array"
    assert isinstance(catalog["members"], list)
    assert isinstance(catalog["teams"], list)
    assert len(catalog["members"]) > 0, "no team-members in factory catalog"
    for member in catalog["members"]:
        for field in ("name", "expert", "domains"):
            assert field in member, f"member entry missing {field!r}: {member}"
        assert member["name"].startswith("team-member-"), (
            f"member name must use 'team-member-' prefix: {member['name']!r}"
        )
    for team in catalog["teams"]:
        for field in ("name", "domains", "members"):
            assert field in team, f"team entry missing {field!r}: {team}"
        assert team["name"].startswith("team-"), (
            f"team name must use 'team-' prefix: {team['name']!r}"
        )


def test_factory_marketplace_members_have_blueprints():
    """Every member in the factory catalog must have a corresponding
    TEAM-MEMBER.md blueprint under templates/team-members/."""
    catalog = _load(FACTORY_MARKETPLACE_JSON)
    for member in catalog["members"]:
        slug = member["name"].removeprefix("team-member-")
        blueprint = PLUGIN_ROOT / "templates" / "team-members" / slug / "TEAM-MEMBER.md"
        assert blueprint.is_file(), (
            f"factory catalog lists {member['name']!r} but blueprint missing: "
            f"{blueprint.relative_to(PLUGIN_ROOT)}"
        )


def test_factory_marketplace_teams_have_blueprints():
    """Every team in the factory catalog must have a corresponding TEAM.md
    blueprint under templates/teams/."""
    catalog = _load(FACTORY_MARKETPLACE_JSON)
    for team in catalog["teams"]:
        slug = team["name"].removeprefix("team-")
        blueprint = PLUGIN_ROOT / "templates" / "teams" / slug / "TEAM.md"
        assert blueprint.is_file(), (
            f"factory catalog lists {team['name']!r} but blueprint missing: "
            f"{blueprint.relative_to(PLUGIN_ROOT)}"
        )


def test_no_orphan_team_member_blueprints():
    """Reverse of test_factory_marketplace_members_have_blueprints — every
    blueprint on disk under templates/team-members/ must be cataloged."""
    catalog = _load(FACTORY_MARKETPLACE_JSON)
    cataloged_slugs = {
        m["name"].removeprefix("team-member-") for m in catalog["members"]
    }
    disk_slugs = {
        p.parent.name
        for p in PLUGIN_ROOT.glob("templates/team-members/*/TEAM-MEMBER.md")
    }
    orphans = disk_slugs - cataloged_slugs
    assert not orphans, (
        f"team-member blueprints on disk but missing from marketplace.json: "
        f"{sorted(orphans)}"
    )


def test_no_orphan_team_blueprints():
    """Reverse of test_factory_marketplace_teams_have_blueprints — every team
    blueprint on disk under templates/teams/ must be cataloged."""
    catalog = _load(FACTORY_MARKETPLACE_JSON)
    cataloged_slugs = {t["name"].removeprefix("team-") for t in catalog["teams"]}
    disk_slugs = {
        p.parent.name for p in PLUGIN_ROOT.glob("templates/teams/*/TEAM.md")
    }
    orphans = disk_slugs - cataloged_slugs
    assert not orphans, (
        f"team blueprints on disk but missing from marketplace.json: "
        f"{sorted(orphans)}"
    )


import pytest


@pytest.mark.parametrize("skill_md", SKILL_FILES, ids=lambda p: p.parent.name)
def test_skill_name_matches_directory_name(skill_md, frontmatter):
    """A skill's frontmatter `name:` must match its directory name."""
    fields = frontmatter(skill_md)
    name = fields.get("name")
    dir_name = skill_md.parent.name
    assert name == dir_name, (
        f"{skill_md.relative_to(PLUGIN_ROOT)}: frontmatter name={name!r} "
        f"does not match directory {dir_name!r}"
    )
