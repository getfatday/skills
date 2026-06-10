#!/usr/bin/env python3
"""check-factory-contract.py — CI-runnable enforcement of FACTORY.md.

A thin wrapper around the Layer 2 contract tests. Runs the same assertions
pytest does, but produces non-pytest output for use in workflow steps that
prefer a single-script invocation over `uv run pytest plugins/dream-team`.

Returns:
  0 — contract clean
  1 — one or more violations (printed to stderr)
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent.parent

VALID_TIERS = {"1-plugin", "2-plugin", "2-materialized", "3"}
PROVENANCE_FIELDS = (
    "factory:", "factory-version:", "generated-by:", "generator-version:",
    "source:", "materialized:", "tier:",
)


def _parse_frontmatter(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if not line[:1].strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
            value = value[1:-1]
        fields[key.strip()] = value
    return fields


def _err(violations, message):
    violations.append(message)


def check_factory_contract():
    violations = []

    # FACTORY.md + CLAUDE.md exist.
    if not (PLUGIN_ROOT / "FACTORY.md").is_file():
        _err(violations, "FACTORY.md missing at plugin root")
    if not (PLUGIN_ROOT / "CLAUDE.md").is_file():
        _err(violations, "CLAUDE.md missing at plugin root")

    # Every plugin skill declares a valid tier.
    skills = sorted(PLUGIN_ROOT.glob("skills/*/SKILL.md"))
    if not skills:
        _err(violations, "no plugin skills found under skills/")
    for skill in skills:
        fields = _parse_frontmatter(skill)
        tier = fields.get("tier")
        if tier not in VALID_TIERS:
            _err(violations, f"{skill.relative_to(PLUGIN_ROOT)}: invalid tier={tier!r}")

    # Materializable templates carry tier: 2-materialized + materialized:.
    templates = (
        list(PLUGIN_ROOT.glob("templates/team-assemble/SKILL.md"))
        + list(PLUGIN_ROOT.glob("templates/orchestrator/orchestrator.md"))
        + list(PLUGIN_ROOT.glob("templates/team-commands/*/*.md"))
    )
    for template in templates:
        fields = _parse_frontmatter(template)
        if fields.get("tier") != "2-materialized":
            _err(violations, f"{template.relative_to(PLUGIN_ROOT)}: tier must be '2-materialized'")
        if not fields.get("materialized"):
            _err(violations, f"{template.relative_to(PLUGIN_ROOT)}: missing materialized: date stamp")

        # Self-sufficiency: no plugin paths, no ${CLAUDE_PLUGIN_ROOT}.
        body = template.read_text(encoding="utf-8")
        for line_no, line in enumerate(body.splitlines(), 1):
            if "${CLAUDE_PLUGIN_ROOT}" in line:
                _err(violations,
                     f"{template.relative_to(PLUGIN_ROOT)}:{line_no}: references ${{CLAUDE_PLUGIN_ROOT}}")
            if "plugins/" in line:
                _err(violations,
                     f"{template.relative_to(PLUGIN_ROOT)}:{line_no}: references a plugins/ path")

    # plugin.json declares dreamTeamSchemaVersion.
    plugin_json = json.loads(
        (PLUGIN_ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
    )
    if "dreamTeamSchemaVersion" not in plugin_json:
        _err(violations, ".claude-plugin/plugin.json missing dreamTeamSchemaVersion")

    # team-member-recruit emits the full provenance stamp via a fenced example.
    spec = PLUGIN_ROOT / "skills/team-member-recruit/SKILL.md"
    if spec.is_file():
        spec_text = spec.read_text(encoding="utf-8")
        fenced = re.findall(r"(?ms)^[ \t]*```[a-z]*\n(.*?)^[ \t]*```", spec_text)
        if not any(
            all(field in block for field in PROVENANCE_FIELDS) for block in fenced
        ):
            _err(violations,
                 "skills/team-member-recruit/SKILL.md: no fenced example block carries the full provenance stamp "
                 f"({', '.join(PROVENANCE_FIELDS)})")

    return violations


def main():
    violations = check_factory_contract()
    if violations:
        print(f"FACTORY contract: {len(violations)} violation(s)", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1
    print("FACTORY contract: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
