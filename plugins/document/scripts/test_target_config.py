"""Layer-1 tests for target_config.py.

The reader is the one piece of code that sees the consumer's
`.config/documents/rulesync.jsonc` directly, so the test bar is set
high: defaults are returned when the file is absent, valid JSONC is
parsed, malformed content fails loudly, and a foreign rulesync.jsonc
(no `documentTargets: true` marker) is refused instead of silently
consumed.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest

SCRIPT = pathlib.Path(__file__).with_name("target_config.py")


def _load():
    spec = importlib.util.spec_from_file_location("target_config_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tc = _load()


# ---------- parse_jsonc -------------------------------------------------

def test_parse_jsonc_strips_line_comments():
    out = tc.parse_jsonc('{\n  // comment\n  "a": 1 // trailing\n}')
    assert out == {"a": 1}


def test_parse_jsonc_strips_block_comments():
    out = tc.parse_jsonc('/* header */\n{"a": /* mid */ 1}')
    assert out == {"a": 1}


def test_parse_jsonc_tolerates_trailing_commas():
    out = tc.parse_jsonc('{"a": [1, 2,], "b": {"c": 3,},}')
    assert out == {"a": [1, 2], "b": {"c": 3}}


def test_parse_jsonc_preserves_url_inside_strings():
    """// inside a string literal must not be stripped."""
    out = tc.parse_jsonc('{"url": "https://example.com/path"}')
    assert out["url"] == "https://example.com/path"


def test_parse_jsonc_preserves_block_marker_in_string():
    out = tc.parse_jsonc('{"text": "before /* not a */ comment"}')
    assert out["text"] == "before /* not a */ comment"


# ---------- load_target_config ------------------------------------------

def test_missing_path_returns_defaults():
    config = tc.load_target_config(None)
    assert config == tc.DEFAULT_CONFIG
    assert config is not tc.DEFAULT_CONFIG  # caller gets a fresh copy


def test_nonexistent_file_returns_defaults(tmp_path):
    config = tc.load_target_config(tmp_path / "nope.jsonc")
    assert config["targets"] == tc.DEFAULT_CONFIG["targets"]


def test_default_targets_are_cursor_and_codexcli():
    config = tc.load_target_config(None)
    assert sorted(config["targets"].keys()) == ["codexcli", "cursor"]


def test_valid_file_parses(tmp_path):
    p = tmp_path / "rulesync.jsonc"
    p.write_text(
        '{\n'
        '  "documentTargets": true,\n'
        '  "schema-version": 1,\n'
        '  "targets": {\n'
        '    "cursor": ["skills", "commands"]  // comment ok\n'
        '  }\n'
        '}\n',
        encoding="utf-8",
    )
    config = tc.load_target_config(p)
    assert config["targets"] == {"cursor": ["skills", "commands"]}


def test_malformed_jsonc_raises(tmp_path):
    p = tmp_path / "rulesync.jsonc"
    p.write_text('{"documentTargets": true, "targets": broken}\n')
    with pytest.raises(tc.TargetConfigError) as excinfo:
        tc.load_target_config(p)
    assert "invalid JSONC" in str(excinfo.value)


def test_missing_marker_raises(tmp_path):
    """A rulesync.jsonc without `documentTargets: true` must not be
    consumed as the document config — defends against accidentally
    consuming a repo-root rulesync.jsonc."""
    p = tmp_path / "rulesync.jsonc"
    p.write_text(
        '{"targets": {"cursor": ["skills"]}}\n',
        encoding="utf-8",
    )
    with pytest.raises(tc.TargetConfigError) as excinfo:
        tc.load_target_config(p)
    assert "documentTargets" in str(excinfo.value)


def test_marker_must_be_literal_true(tmp_path):
    """`documentTargets: "true"` (string) or `1` (truthy) is rejected.
    Only the literal boolean counts."""
    p = tmp_path / "rulesync.jsonc"
    p.write_text(
        '{"documentTargets": "true", "targets": {"c": ["skills"]}}\n'
    )
    with pytest.raises(tc.TargetConfigError):
        tc.load_target_config(p)


def test_targets_must_be_nonempty(tmp_path):
    p = tmp_path / "rulesync.jsonc"
    p.write_text(
        '{"documentTargets": true, "targets": {}}\n', encoding="utf-8"
    )
    with pytest.raises(tc.TargetConfigError) as excinfo:
        tc.load_target_config(p)
    assert "non-empty" in str(excinfo.value)


def test_targets_features_must_be_string_list(tmp_path):
    p = tmp_path / "rulesync.jsonc"
    p.write_text(
        '{"documentTargets": true, "targets": {"cursor": "skills"}}\n'
    )
    with pytest.raises(tc.TargetConfigError) as excinfo:
        tc.load_target_config(p)
    assert "list of feature strings" in str(excinfo.value)


def test_future_schema_version_warns_not_raises(tmp_path, capsys):
    """Forward compatibility: an unknown future schema version warns
    and proceeds rather than crashes."""
    p = tmp_path / "rulesync.jsonc"
    p.write_text(
        '{"documentTargets": true, "schema-version": 99, '
        '"targets": {"cursor": ["skills"]}}\n'
    )
    config = tc.load_target_config(p)
    captured = capsys.readouterr()
    assert "schema-version is 99" in captured.err
    assert config["targets"] == {"cursor": ["skills"]}


# ---------- parsed_targets / parsed_features -----------------------------

def test_parsed_targets_stable_order():
    config = {"targets": {"cursor": ["skills"], "codexcli": ["skills"]}}
    assert tc.parsed_targets(config) == ["codexcli", "cursor"]


def test_parsed_features_union_stable_order():
    config = {"targets": {"cursor": ["skills", "hooks"],
                          "codexcli": ["skills", "commands"]}}
    assert tc.parsed_features(config) == ["commands", "hooks", "skills"]


# ---------- defaults template -------------------------------------------

def test_shipped_default_template_parses():
    """The default template the materializer ships into a fresh repo
    must parse cleanly via the reader (round-trip safety)."""
    template = (pathlib.Path(__file__).resolve().parents[1]
                / "templates" / "_root" / "rulesync.jsonc")
    config = tc.load_target_config(template)
    assert config["documentTargets"] is True
    assert sorted(config["targets"].keys()) == ["codexcli", "cursor"]


# ---------- CLI ----------------------------------------------------------

def test_cli_version():
    r = subprocess.run([sys.executable, str(SCRIPT), "--version"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "target_config.py" in r.stdout


def test_cli_defaults():
    r = subprocess.run([sys.executable, str(SCRIPT), "--defaults"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "cursor" in data["targets"]
    assert "codexcli" in data["targets"]


def test_cli_reports_missing_config_using_defaults(tmp_path):
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "-C", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["exists"] is False
    assert data["targets"] == ["codexcli", "cursor"]


def test_cli_reports_real_file(tmp_path):
    cfg = tmp_path / ".config/documents"
    cfg.mkdir(parents=True)
    (cfg / "rulesync.jsonc").write_text(
        '{"documentTargets": true, "targets": {"cursor": ["skills"]}}\n'
    )
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "-C", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["exists"] is True
    assert data["targets"] == ["cursor"]


def test_cli_exits_nonzero_on_malformed(tmp_path):
    cfg = tmp_path / ".config/documents"
    cfg.mkdir(parents=True)
    (cfg / "rulesync.jsonc").write_text('{"documentTargets": true,')
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "-C", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert r.returncode != 0
    assert "invalid JSONC" in r.stderr
