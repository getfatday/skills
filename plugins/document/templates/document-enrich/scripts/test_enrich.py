"""Layer 1 — unit tests for enrich.py (the relationship enricher).

Run via `make test` (pytest over plugins/document). Covers the deterministic
core: tokenization, fuzzy scoring, type-def / sidecar parsing, field rewrite,
and proposal application.
"""
import importlib.util
import pathlib
import sys

SCRIPT = pathlib.Path(__file__).with_name("enrich.py")


def _load():
    spec = importlib.util.spec_from_file_location("enrich_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # Register before exec: enrich.py uses @dataclass, which resolves the
    # owning module via sys.modules during class processing.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


enrich = _load()
MatchConfig = enrich.MatchConfig


# --------------------------------------------------------------------------
# string helpers
# --------------------------------------------------------------------------

def test_tokenize_lowercases_and_splits_on_non_alpha():
    assert enrich.tokenize("EGDS Asset-Cache 2024") == {"egds", "asset", "cache"}


def test_tokenize_empty_and_none():
    assert enrich.tokenize("") == set()
    assert enrich.tokenize(None) == set()


def test_slug_simplify_strips_non_alphanumeric():
    assert enrich.slug_simplify("EGDS Asset-Cache!") == "egdsassetcache"


def test_is_legacy_wikilink():
    assert enrich.is_legacy_wikilink("[[Bare Name]]") is True
    assert enrich.is_legacy_wikilink("[[Path/To/Doc|Display]]") is False
    assert enrich.is_legacy_wikilink("plain text") is False
    assert enrich.is_legacy_wikilink("") is False


def test_extract_legacy_name():
    assert enrich.extract_legacy_name("[[Bare Name]]") == "Bare Name"
    assert enrich.extract_legacy_name("[[Path/Doc|D]]") is None


# --------------------------------------------------------------------------
# fuzzy matching — the scoring core
# --------------------------------------------------------------------------

def test_fuzzy_exact_slug_match_is_high_confidence():
    result = enrich.fuzzy_match_target(["EGDS Asset Cache"], ["Egds Asset Cache"],
                                       MatchConfig())
    assert result is not None
    target, reason, confidence = result
    assert target == "Egds Asset Cache"
    assert confidence == "high"
    assert "slug_exact" in reason


def test_fuzzy_token_overlap_match():
    result = enrich.fuzzy_match_target(["alpha beta gamma"], ["alpha beta delta"],
                                       MatchConfig())
    assert result is not None
    target, reason, confidence = result
    assert target == "alpha beta delta"
    assert "token_overlap" in reason


def test_fuzzy_below_threshold_returns_none():
    # One shared token, no slug overlap -> score 15, under the default 30.
    assert enrich.fuzzy_match_target(["alpha beta"], ["alpha gamma"],
                                     MatchConfig()) is None


def test_fuzzy_no_candidates_returns_none():
    assert enrich.fuzzy_match_target(["anything"], [], MatchConfig()) is None


def test_fuzzy_score_threshold_is_honored():
    # This pair scores 40 (two shared tokens): matched at the default
    # threshold of 30, suppressed when the threshold is raised above 40.
    hints, targets = ["alpha beta gamma"], ["alpha beta delta"]
    assert enrich.fuzzy_match_target(hints, targets, MatchConfig()) is not None
    assert enrich.fuzzy_match_target(hints, targets,
                                     MatchConfig(score_threshold=50)) is None


def test_fuzzy_extra_weight_promotes_a_token():
    cfg = MatchConfig(extra_weight={"token:cache": 50})
    result = enrich.fuzzy_match_target(["alpha"], ["cache store"], cfg)
    assert result is not None
    assert "pref_cache" in result[1]


def test_match_config_defaults():
    cfg = MatchConfig()
    assert cfg.stopwords == set()
    assert cfg.score_threshold == 30
    assert cfg.extra_weight == {}
    assert cfg.skip_fields == set()


# --------------------------------------------------------------------------
# parsing — frontmatter, type definitions, sidecar
# --------------------------------------------------------------------------

def test_read_frontmatter(tmp_path):
    doc = tmp_path / "d.md"
    doc.write_text('---\ntype: session\nproject: "[[P/index|P]]"\n---\n\nbody\n',
                   encoding="utf-8")
    fm = enrich.read_frontmatter(doc)
    assert fm["type"] == "session"
    assert fm["project"] == "[[P/index|P]]"  # surrounding quotes stripped


def test_parse_type_def(tmp_path):
    td = tmp_path / "session.md"
    td.write_text(
        "# Session\n\n"
        "## Identity\n- name: session\n- display: Session\n\n"
        "## Fields\n### Required\n- `type: string` — always\n"
        "- `project: link` — the project\n\n"
        "## Relationships\n- links-to: project via project — one — the project\n",
        encoding="utf-8",
    )
    parsed = enrich.parse_type_def(td)
    assert parsed is not None
    assert parsed.name == "session"
    assert parsed.fields.get("project") == "link"
    assert len(parsed.relationships) == 1
    rel = parsed.relationships[0]
    assert rel.field_name == "project"
    assert rel.target_type == "project"
    assert rel.cardinality == "one"


def test_parse_sidecar_enrichment_block(tmp_path):
    sidecar = tmp_path / "session.skill.md"
    sidecar.write_text(
        "# Session — Custom Logic\n\n"
        "## Enrichment\n"
        "- stopwords: [session, the, of]\n"
        "- score_threshold: 45\n"
        "- skip_fields: [parent-session]\n",
        encoding="utf-8",
    )
    cfg = enrich.parse_sidecar(sidecar)
    assert cfg["stopwords"] == ["session", "the", "of"]
    assert cfg["score_threshold"] == 45  # coerced to int
    assert cfg["skip_fields"] == ["parent-session"]


def test_parse_sidecar_absent_file_is_empty():
    assert enrich.parse_sidecar(pathlib.Path("/no/such/file.skill.md")) == {}


# --------------------------------------------------------------------------
# field rewrite + apply
# --------------------------------------------------------------------------

def test_rewrite_field_sets_value_and_inferred_marker(tmp_path):
    doc = tmp_path / "a.md"
    doc.write_text("---\ntype: session\nproject:\n---\n\nbody\n", encoding="utf-8")
    enrich.rewrite_field(doc, "project", '"[[Projects/X/index|X]]"')
    fm = enrich.read_frontmatter(doc)
    assert fm["project"] == "[[Projects/X/index|X]]"
    assert fm["inferred"] == "true"
    assert doc.read_text(encoding="utf-8").rstrip().endswith("body")


def test_apply_mapping_applies_confirmed_skips_unconfirmed(tmp_path):
    (tmp_path / "a.md").write_text("---\ntype: session\nproject:\n---\n",
                                   encoding="utf-8")
    (tmp_path / "b.md").write_text("---\ntype: session\nproject:\n---\n",
                                   encoding="utf-8")
    mapping = tmp_path / "proposals.yaml"
    mapping.write_text(
        "proposals:\n"
        "  - instance_file: a.md\n"
        "    field: project\n"
        '    proposed_value: "[[Projects/X/index|X]]"\n'
        "    proposed_create: null\n"
        "    confirmed: true\n"
        "  - instance_file: b.md\n"
        "    field: project\n"
        '    proposed_value: "[[Projects/Y/index|Y]]"\n'
        "    proposed_create: null\n"
        "    confirmed: false\n",
        encoding="utf-8",
    )
    result = enrich.apply_mapping(tmp_path, mapping)
    assert result["applied"] == 1
    assert result["skipped"] == 1
    assert enrich.read_frontmatter(tmp_path / "a.md")["project"] == "[[Projects/X/index|X]]"
    assert not enrich.read_frontmatter(tmp_path / "b.md").get("project")


def test_apply_mapping_dry_run_writes_nothing(tmp_path):
    (tmp_path / "a.md").write_text("---\ntype: session\nproject:\n---\n",
                                   encoding="utf-8")
    before = (tmp_path / "a.md").read_text(encoding="utf-8")
    mapping = tmp_path / "proposals.yaml"
    mapping.write_text(
        "proposals:\n"
        "  - instance_file: a.md\n"
        "    field: project\n"
        '    proposed_value: "[[Projects/X/index|X]]"\n'
        "    proposed_create: null\n"
        "    confirmed: true\n",
        encoding="utf-8",
    )
    result = enrich.apply_mapping(tmp_path, mapping, dry_run=True)
    assert result["applied"] == 1
    assert (tmp_path / "a.md").read_text(encoding="utf-8") == before


# --------------------------------------------------------------------------
# proposal generation — propose_for_instance (the enrichment core)
# --------------------------------------------------------------------------

def _session_type_def(tmp_path):
    """A `session` type whose one relationship is `project: link -> project`."""
    return enrich.TypeDef(
        name="session",
        display="Session",
        fields={"type": "string", "project": "link"},
        relationships=[enrich.Relationship("project", "project", "one")],
        raw_path=tmp_path / "session.md",
    )


def test_propose_for_instance_fuzzy_matches_a_target(tmp_path):
    """A missing relationship field with a fuzzy-matchable target yields a
    proposal carrying a proposed_value (Case A, match branch)."""
    instance = tmp_path / "alpha-project-notes.md"
    instance.write_text("---\ntype: session\n---\n\nnotes\n", encoding="utf-8")
    proposals = list(enrich.propose_for_instance(
        tmp_path, instance, _session_type_def(tmp_path),
        {"project": ["Alpha Project"]}, MatchConfig(),
    ))
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.field == "project"
    assert proposal.proposed_value is not None
    assert proposal.proposed_create is None
    assert proposal.reason.startswith("fuzzy_match")


def test_propose_for_instance_proposes_creation_when_no_match(tmp_path):
    """A missing relationship field with no matchable target yields a
    proposal to create a new target (Case A, no-match branch)."""
    instance = tmp_path / "zeta-unrelated.md"
    instance.write_text("---\ntype: session\n---\n\nnotes\n", encoding="utf-8")
    proposals = list(enrich.propose_for_instance(
        tmp_path, instance, _session_type_def(tmp_path),
        {"project": ["Alpha Project"]}, MatchConfig(),
    ))
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.proposed_value is None
    assert proposal.proposed_create == "project:Zeta Unrelated"
    assert proposal.confidence == "none"


def test_propose_for_instance_skips_resolved_field(tmp_path):
    """A relationship field already holding a normalized wikilink is Case C —
    nothing is proposed."""
    instance = tmp_path / "alpha-project-notes.md"
    instance.write_text(
        '---\ntype: session\nproject: "[[Projects/Alpha/index|Alpha]]"\n---\n',
        encoding="utf-8",
    )
    proposals = list(enrich.propose_for_instance(
        tmp_path, instance, _session_type_def(tmp_path),
        {"project": ["Alpha Project"]}, MatchConfig(),
    ))
    assert proposals == []
