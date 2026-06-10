"""Tests for derive-events.py — Layer 1 of the document plugin test suite.

Part of `make test` (pytest's testpaths include `plugins/document`).
Integration tests build throwaway git repositories in tmp_path and invoke the
script as a subprocess; unit tests load the module via importlib because the
script filename contains a hyphen.
"""
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "derive-events.py")

GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test Author",
    "GIT_AUTHOR_EMAIL": "author@example.com",
    "GIT_COMMITTER_NAME": "Test Author",
    "GIT_COMMITTER_EMAIL": "author@example.com",
}


def _load_module():
    spec = importlib.util.spec_from_file_location("derive_events", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


de = _load_module()


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

class Repo:
    """A throwaway git repository with fixed, deterministic commit metadata."""

    def __init__(self, path):
        self.path = str(path)
        self._day = 0

    def git(self, *args, date=None):
        env = dict(os.environ)
        env.update(GIT_ENV)
        if date:
            env["GIT_AUTHOR_DATE"] = date
            env["GIT_COMMITTER_DATE"] = date
        return subprocess.run(
            ["git", "-C", self.path, *args],
            capture_output=True, text=True, check=True, env=env,
        )

    def init(self):
        os.makedirs(self.path, exist_ok=True)
        self.git("init", "-q", "-b", "main")
        return self

    def write(self, relpath, content):
        full = os.path.join(self.path, relpath)
        os.makedirs(os.path.dirname(full) or self.path, exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(content)

    def write_bytes(self, relpath, data):
        full = os.path.join(self.path, relpath)
        os.makedirs(os.path.dirname(full) or self.path, exist_ok=True)
        with open(full, "wb") as handle:
            handle.write(data)

    def rm(self, relpath):
        self.git("rm", "-q", relpath)

    def mv(self, src, dst):
        full = os.path.join(self.path, dst)
        os.makedirs(os.path.dirname(full) or self.path, exist_ok=True)
        self.git("mv", src, dst)

    def commit(self, message):
        self._day += 1
        date = f"2026-03-{self._day:02d}T12:00:00+00:00"
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message, date=date)
        return self


def doc(doc_type="prd", fields=None, sections=None):
    """Render a typed document with frontmatter and optional H2 sections."""
    lines = ["---", f"type: {doc_type}"]
    for key, value in (fields or {}).items():
        lines.append(f"{key}: {value}")
    lines += ["---", ""]
    for name, body in (sections or {}).items():
        lines += [f"## {name}", "", body, ""]
    return "\n".join(lines) + "\n"


def run(repo_path, *args):
    return subprocess.run(
        [sys.executable, SCRIPT, "-C", str(repo_path), *args],
        capture_output=True, text=True,
    )


def events(repo_path, *args):
    result = run(repo_path, "derive", *args)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


# --------------------------------------------------------------------------
# op classification
# --------------------------------------------------------------------------

def test_created(tmp_path):
    repo = Repo(tmp_path / "r").init()
    repo.write("Products/checkout.md", doc("prd", {"status": "draft"}))
    repo.commit("add checkout prd")
    evs = events(tmp_path / "r")
    assert len(evs) == 1
    event = evs[0]
    assert event["op"] == "created"
    assert event["document"] == "Products/checkout.md"
    assert event["type"] == "prd"
    assert event["changes"] == []
    assert event["seq"] == 0
    assert event["id"] == f'{event["commit"]}:Products/checkout.md:0'
    assert event["actor"] == "Test Author <author@example.com>"


def test_field_update(tmp_path):
    repo = Repo(tmp_path / "r").init()
    repo.write("a.md", doc("prd", {"status": "draft", "owner": "alice"}))
    repo.commit("c1")
    repo.write("a.md", doc("prd", {"status": "draft", "owner": "bob"}))
    repo.commit("c2")
    evs = events(tmp_path / "r")
    assert [e["op"] for e in evs] == ["created", "updated"]
    assert {"field": "owner", "from": "alice", "to": "bob"} in evs[1]["changes"]


def test_status_changed(tmp_path):
    repo = Repo(tmp_path / "r").init()
    repo.write("a.md", doc("prd", {"status": "draft"}))
    repo.commit("c1")
    repo.write("a.md", doc("prd", {"status": "review"}))
    repo.commit("c2")
    evs = events(tmp_path / "r")
    assert evs[1]["op"] == "status-changed"
    assert {"field": "status", "from": "draft", "to": "review"} in evs[1]["changes"]


def test_status_change_takes_precedence_over_other_fields(tmp_path):
    repo = Repo(tmp_path / "r").init()
    repo.write("a.md", doc("prd", {"status": "draft", "owner": "alice"}))
    repo.commit("c1")
    repo.write("a.md", doc("prd", {"status": "review", "owner": "bob"}))
    repo.commit("c2")
    evs = events(tmp_path / "r")
    assert evs[1]["op"] == "status-changed"
    fields = {d["field"] for d in evs[1]["changes"] if "field" in d}
    assert fields == {"status", "owner"}


def test_section_modified(tmp_path):
    repo = Repo(tmp_path / "r").init()
    repo.write("a.md", doc("prd", {"status": "draft"}, {"Overview": "first"}))
    repo.commit("c1")
    repo.write("a.md", doc("prd", {"status": "draft"}, {"Overview": "second"}))
    repo.commit("c2")
    evs = events(tmp_path / "r")
    assert evs[1]["op"] == "updated"
    assert {"section": "Overview", "change": "modified"} in evs[1]["changes"]


def test_deleted(tmp_path):
    repo = Repo(tmp_path / "r").init()
    repo.write("a.md", doc("prd"))
    repo.commit("c1")
    repo.rm("a.md")
    repo.commit("c2")
    evs = events(tmp_path / "r")
    assert [e["op"] for e in evs] == ["created", "deleted"]
    assert evs[1]["changes"] == []


def test_renamed(tmp_path):
    repo = Repo(tmp_path / "r").init()
    repo.write("old.md", doc("prd", {"status": "draft"}))
    repo.commit("c1")
    repo.mv("old.md", "moved/new.md")
    repo.commit("c2")
    evs = events(tmp_path / "r")
    assert evs[1]["op"] == "renamed"
    assert evs[1]["document"] == "moved/new.md"
    assert evs[1]["from-path"] == "old.md"


# --------------------------------------------------------------------------
# document detection and scope
# --------------------------------------------------------------------------

def test_non_document_ignored(tmp_path):
    repo = Repo(tmp_path / "r").init()
    repo.write("notes.md", "# Just notes\n\nNo frontmatter here.\n")
    repo.write("doc.md", doc("prd"))
    repo.commit("c1")
    evs = events(tmp_path / "r")
    assert [e["document"] for e in evs] == ["doc.md"]


def test_excluded_paths(tmp_path):
    repo = Repo(tmp_path / "r").init()
    repo.write(".config/documents/types/prd.md", doc("prd"))
    repo.write(".claude/skills/prd/templates/prd.md", doc("prd"))
    repo.write("real.md", doc("prd"))
    repo.commit("c1")
    evs = events(tmp_path / "r")
    assert [e["document"] for e in evs] == ["real.md"]


# --------------------------------------------------------------------------
# seq, ids, determinism
# --------------------------------------------------------------------------

def test_seq_ordering_is_path_sorted(tmp_path):
    repo = Repo(tmp_path / "r").init()
    repo.write("b.md", doc("prd"))
    repo.write("a.md", doc("prd"))
    repo.write("c.md", doc("prd"))
    repo.commit("c1")
    evs = events(tmp_path / "r")
    assert [e["document"] for e in evs] == ["a.md", "b.md", "c.md"]
    assert [e["seq"] for e in evs] == [0, 1, 2]
    for event in evs:
        assert event["id"].endswith(f':{event["seq"]}')


def test_determinism_same_repo(tmp_path):
    repo = Repo(tmp_path / "r").init()
    repo.write("a.md", doc("prd", {"status": "draft"}))
    repo.commit("c1")
    repo.write("a.md", doc("prd", {"status": "review"}))
    repo.commit("c2")
    first = run(tmp_path / "r", "derive").stdout
    second = run(tmp_path / "r", "derive").stdout
    assert first == second


def test_determinism_across_clones(tmp_path):
    repo = Repo(tmp_path / "r").init()
    repo.write("a.md", doc("prd", {"status": "draft"}, {"Overview": "x"}))
    repo.commit("c1")
    repo.write("Products/b.md", doc("brand", {"status": "active"}))
    repo.write("a.md", doc("prd", {"status": "review"}, {"Overview": "y"}))
    repo.commit("c2")
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "-q", str(tmp_path / "r"), str(clone)],
        check=True, capture_output=True,
    )
    original = run(tmp_path / "r", "derive").stdout
    cloned = run(clone, "derive").stdout
    assert original == cloned
    assert json.loads(original), "expected a non-empty event log"


# --------------------------------------------------------------------------
# git edge cases
# --------------------------------------------------------------------------

def test_merge_commit_first_parent(tmp_path):
    repo = Repo(tmp_path / "r").init()
    repo.write("a.md", doc("prd", {"status": "draft"}))
    repo.commit("base")
    repo.git("checkout", "-q", "-b", "feature")
    repo.write("a.md", doc("prd", {"status": "review"}))
    repo.commit("feature change")
    repo.git("checkout", "-q", "main")
    repo.git("merge", "-q", "--no-ff", "feature", "-m", "merge feature")
    evs = events(tmp_path / "r")
    # The deriver must not crash on a merge; --first-parent shows the merge's
    # net change once, against base.
    assert [e["op"] for e in evs] == ["created", "status-changed"]
    assert all("id" in e for e in evs)


def test_initial_commit(tmp_path):
    repo = Repo(tmp_path / "r").init()
    repo.write("first.md", doc("prd"))
    repo.commit("the very first commit")
    evs = events(tmp_path / "r")
    assert len(evs) == 1 and evs[0]["op"] == "created"


def test_empty_repo(tmp_path):
    Repo(tmp_path / "r").init()
    result = run(tmp_path / "r", "derive")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == []


def test_malformed_frontmatter_is_ignored(tmp_path):
    repo = Repo(tmp_path / "r").init()
    repo.write("bad.md", "---\ntype: prd\nstatus: draft\n\n# Body, no closing fence\n")
    repo.commit("c1")
    # Unclosed frontmatter -> not a recognizable document -> no events, no crash.
    assert events(tmp_path / "r") == []


def test_non_utf8_does_not_crash(tmp_path):
    repo = Repo(tmp_path / "r").init()
    repo.write("a.md", doc("prd"))
    repo.commit("c1")
    repo.write_bytes("a.md", b"---\ntype: prd\n---\n\n## Body\n\n\xff\xfe raw bytes\n")
    repo.commit("c2")
    result = run(tmp_path / "r", "derive")
    assert result.returncode == 0, result.stderr
    assert [e["op"] for e in json.loads(result.stdout)] == ["created", "updated"]


def test_not_a_git_repo(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    result = run(plain, "derive")
    assert result.returncode == 1
    assert "not a git repository" in result.stderr


# --------------------------------------------------------------------------
# the log subcommand
# --------------------------------------------------------------------------

def test_log_filters(tmp_path):
    repo = Repo(tmp_path / "r").init()
    repo.write("p.md", doc("prd", {"status": "draft"}))
    repo.write("b.md", doc("brand", {"status": "active"}))
    repo.commit("c1")
    repo.write("p.md", doc("prd", {"status": "review"}))
    repo.commit("c2")

    by_type = json.loads(run(tmp_path / "r", "log", "--type", "prd").stdout)
    assert len(by_type) == 2 and all(e["type"] == "prd" for e in by_type)

    by_op = json.loads(run(tmp_path / "r", "log", "--op", "status-changed").stdout)
    assert len(by_op) == 1 and by_op[0]["op"] == "status-changed"

    by_doc = json.loads(run(tmp_path / "r", "log", "--document", "b.md").stdout)
    assert by_doc and all("b.md" in e["document"] for e in by_doc)


def test_version():
    result = subprocess.run(
        [sys.executable, SCRIPT, "--version"], capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "derive-events.py" in result.stdout


def test_log_since_filter(tmp_path):
    repo = Repo(tmp_path / "r").init()
    repo.write("a.md", doc("prd", {"status": "draft"}))
    repo.commit("c1")  # dated 2026-03-01
    repo.write("a.md", doc("prd", {"status": "review"}))
    repo.commit("c2")  # dated 2026-03-02
    evs = json.loads(run(tmp_path / "r", "log", "--since", "2026-03-02").stdout)
    assert len(evs) == 1
    assert evs[0]["op"] == "status-changed"


# --------------------------------------------------------------------------
# review-gate hardening: code fences, shallow clones, BOM, CRLF
# --------------------------------------------------------------------------

def test_section_heading_in_code_fence_ignored(tmp_path):
    repo = Repo(tmp_path / "r").init()
    repo.write("a.md", doc("prd", {"status": "draft"},
                            {"Overview": "real\n\n```\n## not a heading\n```\n"}))
    repo.commit("c1")
    repo.write("a.md", doc("prd", {"status": "draft"},
                            {"Overview": "real\n\n```\n## edited, still not a heading\n```\n"}))
    repo.commit("c2")
    evs = events(tmp_path / "r")
    sections = {d.get("section") for d in evs[1]["changes"]}
    assert sections == {"Overview"}, f"fenced `## ` leaked into sections: {sections}"


def test_shallow_clone_does_not_abort(tmp_path):
    repo = Repo(tmp_path / "r").init()
    repo.write("a.md", doc("prd", {"status": "draft"}))
    repo.commit("c1")
    repo.write("a.md", doc("prd", {"status": "review"}))
    repo.commit("c2")
    repo.write("a.md", doc("prd", {"status": "approved"}))
    repo.commit("c3")
    shallow = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "1",
         "file://" + str(tmp_path / "r"), str(shallow)],
        check=True, capture_output=True,
    )
    result = run(shallow, "derive")
    assert result.returncode == 0, result.stderr
    evs = json.loads(result.stdout)
    # The boundary commit's parent is unreachable; it must still derive (as a
    # creation) instead of aborting the whole run.
    assert len(evs) == 1
    assert evs[0]["op"] == "created"


def test_bom_prefixed_document(tmp_path):
    repo = Repo(tmp_path / "r").init()
    repo.write_bytes("a.md",
                     b"\xef\xbb\xbf" + doc("prd", {"status": "draft"}).encode("utf-8"))
    repo.commit("c1")
    evs = events(tmp_path / "r")
    assert len(evs) == 1
    assert evs[0]["type"] == "prd"
    assert evs[0]["op"] == "created"


def test_crlf_line_endings(tmp_path):
    repo = Repo(tmp_path / "r").init()
    content = ("---\r\ntype: prd\r\nstatus: draft\r\n---\r\n\r\n"
               "## Overview\r\n\r\nbody\r\n")
    repo.write_bytes("a.md", content.encode("utf-8"))
    repo.commit("c1")
    evs = events(tmp_path / "r")
    assert len(evs) == 1
    assert evs[0]["type"] == "prd"
    assert evs[0]["op"] == "created"


# --------------------------------------------------------------------------
# parser units
# --------------------------------------------------------------------------

def test_parse_frontmatter_scalars():
    assert de.parse_frontmatter("---\ntype: prd\nstatus: draft\n---\n\nbody\n") == {
        "type": "prd", "status": "draft",
    }


def test_parse_frontmatter_inline_list():
    assert de.parse_frontmatter("---\ntype: prd\ntags: [a, b, c]\n---\n")["tags"] == [
        "a", "b", "c",
    ]


def test_parse_frontmatter_block_list():
    text = "---\ntype: prd\ndepends-on:\n  - one\n  - two\n---\n"
    assert de.parse_frontmatter(text)["depends-on"] == ["one", "two"]


def test_parse_frontmatter_quoted_value_with_colon():
    fm = de.parse_frontmatter('---\ntype: prd\ntitle: "Hello: World"\n---\n')
    assert fm["title"] == "Hello: World"


def test_parse_frontmatter_absent_or_malformed():
    assert de.parse_frontmatter(None) == {}
    assert de.parse_frontmatter("no frontmatter here\n") == {}
    assert de.parse_frontmatter("---\ntype: prd\n") == {}  # unclosed fence


def test_diff_fields():
    assert de.diff_fields({"a": "1", "b": "2"}, {"a": "9", "c": "3"}) == [
        {"field": "a", "from": "1", "to": "9"},
        {"field": "b", "from": "2", "to": None},
        {"field": "c", "from": None, "to": "3"},
    ]


def test_parse_sections():
    text = "---\ntype: prd\n---\n\n## One\n\nbody one\n\n## Two\n\nbody two\n"
    assert de.parse_sections(text) == {"One": "body one", "Two": "body two"}
