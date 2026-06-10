"""Shared fixtures for the `dream-team` plugin test suite.

See tests/README.md for the three-layer layout and how to run each layer.
This file provides helpers used by the Layer 2 (contract & structure) tests.
"""
import pathlib

import pytest

# plugins/dream-team/ — the plugin root, one level up from this tests/ dir.
PLUGIN_ROOT = pathlib.Path(__file__).resolve().parents[1]
# the repo root — three parent steps up from this file
# (…/plugins/dream-team/tests/conftest.py → repo root).
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


def parse_frontmatter(path):
    """Parse a markdown file's YAML frontmatter into a dict of top-level
    scalar fields. Minimal and stdlib-only — scalars are all the contract
    checks need (`name`, `tier`, `version`). Indented lines, list items, and
    block scalars are skipped. Returns {} when there is no frontmatter."""
    lines = pathlib.Path(path).read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if not line[:1].strip() or ":" not in line:
            continue  # blank, indented (list item / block scalar), or non-field
        key, _, value = line.partition(":")
        value = value.strip()
        if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
            value = value[1:-1]
        fields[key.strip()] = value
    return fields


@pytest.fixture(scope="session")
def plugin_root():
    """Absolute path to the dream-team plugin root."""
    return PLUGIN_ROOT


@pytest.fixture(scope="session")
def repo_root():
    """Absolute path to the xp-skills repo root."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def frontmatter():
    """The `parse_frontmatter` helper, injected as a fixture so test modules
    need not import across pytest's importlib boundary."""
    return parse_frontmatter
