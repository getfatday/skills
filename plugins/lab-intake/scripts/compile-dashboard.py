#!/usr/bin/env python3
"""compile-dashboard.py -- portable status dashboard for a lab-intake consumer repo.

Compiles DASHBOARD.md at the repo root from the repository's OWN streams:

  1. OPEN DECISIONS AND COMMITMENTS -- ledger rows (JSONL) not yet resolved
     against committed state: a row closes when the [closes-when: ...] bracket
     in its `hit` text is satisfied at HEAD; a row without a valid bracket
     stays open until the ledger line itself is removed or rewritten.
     Rows carry one optional `assignee` (canonical email) and render in three
     buckets: YOURS (assignee canonicalizes to the current identity), OTHERS'
     (assigned to someone else -- always visible, display name resolved), and
     SHARED (no assignee = everyone sees it; absence of routing fails toward
     visibility). Each row's creator is DERIVED from git blame on its ledger
     line -- never stored; a line with no landing commit yet renders with no
     creator segment at all, never a placeholder.
  2. RECENT ACTIVITY -- journal fragments grouped by day, newest first.

Who-am-I: the header carries an `acting as` line -- `git config user.email`
canonicalized through two optional committed maps, the git-native `.mailmap`
and a root-level `contributors.json` ({"<canonical email>": {"name": ...,
"aka": [...]}}). Display names live only in that map; an unmapped email
renders bare with a hint. Both maps are optional (graceful-missing).

Design laws (the intake discipline applied to status):
  - Status is a projection, never an authored document. This script owns every
    byte of DASHBOARD.md: regenerate it, never edit it.
  - The output is COMMITTED content, so it carries no transient values. Any
    fact that is true only at render time is omitted rather than labelled --
    committing a placeholder would freeze a state that has already moved on.
    A cold reader's checkout must mean what it says.
  - Names appear only where they are RESOLVED from the committed maps at render
    time -- the `acting as` line and an assignee. That is the maps doing their
    job, not authored prose, and it is regenerated every session so it cannot
    drift. Nothing else here names a person.
  - Graceful-missing everywhere. A missing ledger file, journal directory, or
    git binary renders as a visible note inside the affected section, never a
    crash. The script never raises; hook mode always exits 0.
  - Deterministic. No wall clock: the header stamp derives from the HEAD commit
    date. The inputs are the repo's streams plus the rendering identity (git
    config user.email, .mailmap, contributors.json, ledger blame); unchanged
    inputs compile to byte-identical output; the write is atomic and happens
    only when bytes differ.

CLI:
    compile-dashboard.py [repo-root]          render; print one summary line
    compile-dashboard.py [repo-root] --quiet  render silently (hook mode)
    compile-dashboard.py [repo-root] --check  no write; exit 0 fresh / 1 stale

Configuration: .claude/lab-intake.json at the repo root (the init skill writes
it). Keys read here: raw_dir (default research/raw), journal_dir (default
experiments/journal-fragments), and ledger_file (default ledger/ledger.jsonl;
optional -- a repo without a ledger simply shows an empty decisions section).

closes-when predicates (evaluated read-only against HEAD, never the worktree):
    path-exists=<path>        the path is tracked at HEAD
    commit-grep=<text>        some commit message contains the text
    hypothesis-kept=<id>      exactly one hypotheses/<id>-*.md tracked at HEAD
                              whose "## Status" block starts with "kept"
    maintainer-ruling=<slug>  a tracked file under the configured raw dir whose
                              name contains both <slug> and "ruling"
"""
import json
import os
import re
import subprocess
import sys

GIT_TIMEOUT = 10
CAP_DECISIONS = 25
CAP_ACTIVITY_DAYS = 7
DASHBOARD_NAME = "DASHBOARD.md"
CONFIG_RELPATH = os.path.join(".claude", "lab-intake.json")

DEFAULTS = {
    "raw_dir": "research/raw",
    "journal_dir": "experiments/journal-fragments",
    "ledger_file": "ledger/ledger.jsonl",
}

CLOSES_WHEN_RE = re.compile(
    r"\[closes-when:\s*(path-exists|commit-grep|hypothesis-kept|maintainer-ruling)"
    r"=([^\]]+)\]")
STATUS_HEADING_RE = re.compile(r"(?m)^##\s*Status\s*$")
NEXT_HEADING_RE = re.compile(r"(?m)^##\s")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def load_config(root):
    """DEFAULTS overlaid with the consumer's config file, if any. Never raises."""
    cfg = dict(DEFAULTS)
    try:
        with open(os.path.join(root, CONFIG_RELPATH), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for key in DEFAULTS:
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    cfg[key] = value.strip().strip("/")
    except Exception:
        pass
    return cfg


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def git_lines(root, args):
    """stdout lines, or None on ANY failure (no git, not a repo, timeout) --
    callers degrade to the graceful-missing rendering."""
    try:
        proc = subprocess.run(["git", "-C", root] + list(args),
                              capture_output=True, timeout=GIT_TIMEOUT)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", errors="replace").splitlines()


def parse_ledger(text):
    """-> (rows, malformed_count). A row needs date/slug/hit; kind and assignee
    are optional. lineno (1-based) feeds the blame-derived creator."""
    rows, malformed = [], 0
    if text is None:
        return rows, malformed
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            date, slug, hit = rec["date"], rec["slug"], rec["hit"]
        except Exception:
            malformed += 1
            continue
        assignee = rec.get("assignee")
        rows.append({"date": str(date), "slug": str(slug), "hit": str(hit),
                     "kind": str(rec.get("kind", "")).strip(),
                     "assignee": (assignee.strip()
                                  if isinstance(assignee, str) else ""),
                     "lineno": lineno})
    return rows, malformed


def load_identity_maps(root):
    """(alias_to_canonical, email_to_display) from the optional committed
    .mailmap and contributors.json at the repo root. Graceful-missing; emails
    compare case-insensitively. Display names live ONLY in these maps."""
    alias, names = {}, {}
    text = read_text(os.path.join(root, ".mailmap"))
    if text:
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            emails = re.findall(r"<([^<>]+)>", line)
            if not emails:
                continue
            display = line.split("<", 1)[0].strip()
            canon = emails[0].strip().lower()
            if display and canon not in names:
                names[canon] = display
            for extra in emails[1:]:
                alias[extra.strip().lower()] = canon
    text = read_text(os.path.join(root, "contributors.json"))
    if text:
        try:
            data = json.loads(text)
        except Exception:
            data = None
        if isinstance(data, dict):
            for canon, entry in data.items():
                if not isinstance(entry, dict):
                    continue
                canon = str(canon).strip().lower()
                name = entry.get("name")
                if isinstance(name, str) and name.strip():
                    names[canon] = name.strip()
                aka = entry.get("aka")
                if isinstance(aka, list):
                    for extra in aka:
                        if isinstance(extra, str) and extra.strip():
                            alias[extra.strip().lower()] = canon
    return alias, names


def canonical_email(email, alias):
    """Follow alias hops (cycle-bounded) to the canonical, lowercased form."""
    e = (email or "").strip().lower()
    seen = set()
    while e in alias and e not in seen:
        seen.add(e)
        e = alias[e]
    return e


def display_identity(email, names):
    """'Display Name <email>' when mapped, else the bare email."""
    name = names.get(email)
    return "%s <%s>" % (name, email) if name else email


def resolve_current_identity(root, alias, names):
    """(acting-as line, canonical email or None) for the rendering user."""
    lines = git_lines(root, ["config", "user.email"])
    email = lines[0].strip() if lines and lines[0].strip() else ""
    if not email:
        return ("acting as (unknown -- git config user.email is unset; "
                "identity resolves through git, never prose)", None)
    canon = canonical_email(email, alias)
    if canon in names:
        return "acting as %s <%s>" % (names[canon], canon), canon
    return ("acting as %s (unmapped -- add a contributors.json entry to attach "
            "a display name)" % canon, canon)


def blame_creators(root, ledger_rel):
    """lineno -> creator email for lines that have a landing commit; lines not
    yet committed are OMITTED from the map, and None means blame is unavailable
    (untracked ledger, no git). Creators are always derived from the landing
    commit, never stored in the row.

    Uncommitted lines are omitted rather than labelled because DASHBOARD.md is
    committed content: a placeholder like "(uncommitted)" is true only at the
    instant it renders, and committing that byte would freeze a transient state
    into history. An absent creator is honest at every later read."""
    lines = git_lines(root, ["blame", "--line-porcelain", "--", ledger_rel])
    if lines is None:
        return None
    creators, cur_line, cur_sha = {}, None, None
    for ln in lines:
        m = re.match(r"^([0-9a-f]{40}) \d+ (\d+)", ln)
        if m:
            cur_sha, cur_line = m.group(1), int(m.group(2))
        elif ln.startswith("author-mail ") and cur_line is not None:
            if cur_sha != "0" * 40:
                mail = ln[len("author-mail "):].strip().strip("<>").lower()
                creators[cur_line] = mail
    return creators


def extract_status_word(text):
    m = STATUS_HEADING_RE.search(text)
    if not m:
        return None
    rest = text[m.end():]
    nxt = NEXT_HEADING_RE.search(rest)
    block = rest[: nxt.start()] if nxt else rest
    block = HTML_COMMENT_RE.sub(" ", block)
    stripped = block.strip()
    if not stripped:
        return None
    return stripped.split()[0]


def predicate_satisfied(root, pred, arg, cfg, tracked, messages):
    """HEAD-only evaluation; git unavailable means unsatisfied (safe default:
    the row stays visibly open rather than silently closing)."""
    if tracked is None or messages is None:
        return False
    if pred == "path-exists":
        return arg in tracked
    if pred == "commit-grep":
        return any(arg in line for line in messages)
    if pred == "maintainer-ruling":
        needle = arg.lower()
        prefix = cfg["raw_dir"].strip("/") + "/"
        for path in tracked:
            if not path.startswith(prefix):
                continue
            name = path.rsplit("/", 1)[-1].lower()
            if needle in name and "ruling" in name:
                return True
        return False
    if pred == "hypothesis-kept":
        pattern = re.compile(r"^hypotheses/%s-.*\.md$" % re.escape(arg))
        matches = [p for p in tracked if pattern.match(p)]
        if len(matches) != 1:
            return False
        lines = git_lines(root, ["show", "HEAD:" + matches[0]])
        if lines is None:
            return False
        word = extract_status_word("\n".join(lines))
        return word is not None and word.lower() == "kept"
    return False


def parse_fragment(name, text):
    """id/date from frontmatter (filename prefix as id fallback); slug from name."""
    stem = name[:-3] if name.endswith(".md") else name
    prefix, _sep, slug = stem.partition("-")
    frag_id = int(prefix) if prefix.isdigit() else None
    date = ""
    if text:
        fm = re.match(r"\s*---\s*\n(.*?)\n---", text, re.DOTALL)
        if fm:
            im = re.search(r"(?m)^id:\s*(\d+)\s*$", fm.group(1))
            dm = re.search(r"(?m)^date:\s*(\S+)", fm.group(1))
            if im:
                frag_id = int(im.group(1))
            if dm:
                date = dm.group(1)
    return frag_id, slug or stem, date


def compile_text(root):
    cfg = load_config(root)
    tracked_list = git_lines(root, ["ls-tree", "-r", "--name-only", "HEAD"])
    tracked = set(tracked_list) if tracked_list is not None else None
    messages = git_lines(root, ["log", "--format=%B"])
    stamp_lines = git_lines(root, ["log", "-1", "--format=%cI"])
    stamp = stamp_lines[0].strip() if stamp_lines else "unknown"

    out = []
    out.append("<!-- GENERATED by the lab-intake plugin "
               "(scripts/compile-dashboard.py) -- a compiled projection; "
               "edits are overwritten. stamp: %s -->" % stamp)
    out.append("")
    out.append("# DASHBOARD")
    out.append("")
    out.append("Compiled from this repository's own streams -- status is a "
               "projection, never an authored document.")
    out.append("")
    alias, names = load_identity_maps(root)
    who_line, me = resolve_current_identity(root, alias, names)
    out.append(who_line)
    out.append("")

    # 1. open decisions and commitments
    ledger_rel = cfg["ledger_file"]
    ledger_text = read_text(os.path.join(root, ledger_rel))
    rows, malformed = parse_ledger(ledger_text)
    open_rows = []
    for row in rows:
        m = CLOSES_WHEN_RE.search(row["hit"])
        if m and m.group(2).strip():
            if predicate_satisfied(root, m.group(1), m.group(2).strip(), cfg,
                                   tracked, messages):
                continue
            row["waits"] = "%s=%s" % (m.group(1), m.group(2).strip())
        else:
            row["waits"] = "no closes-when bracket (open until the row is removed)"
        open_rows.append(row)
    open_rows.sort(key=lambda r: r["date"])  # stable: file order within a date
    out.append("## 1. OPEN DECISIONS AND COMMITMENTS (%d)" % len(open_rows))
    out.append("")
    if ledger_text is None:
        out.append("source missing: %s (no ledger -- nothing to resolve)" % ledger_rel)
    if (tracked is None or messages is None) and rows:
        out.append("note: git unavailable -- bracketed rows render as open "
                   "(safe default)")
    if malformed:
        out.append("note: %d malformed ledger line(s) skipped" % malformed)
    creators = blame_creators(root, ledger_rel) if open_rows else None

    def render_row(row, show_assignee):
        kind = (" %s" % row["kind"]) if row["kind"] else ""
        hit = " ".join(CLOSES_WHEN_RE.sub(" ", row["hit"]).split())
        if len(hit) > 160:
            hit = hit[:159] + "..."
        extra = ""
        if show_assignee and row["canon_assignee"]:
            extra = (" -- assignee: %s"
                     % display_identity(row["canon_assignee"], names))
        # No creator resolved (line not yet committed, or blame unavailable) ->
        # omit the segment. Never emit a render-time-only value: this file is
        # committed, and a frozen placeholder would outlive the state it named.
        creator = creators.get(row["lineno"]) if creators else None
        cred = (" -- creator: %s" % creator) if creator else ""
        return ("- [%s]%s %s: %s%s%s -- waits on: %s"
                % (row["date"], kind, row["slug"], hit, extra, cred,
                   row["waits"]))

    yours, others, shared = [], [], []
    for row in open_rows:
        canon = (canonical_email(row["assignee"], alias)
                 if row["assignee"] else "")
        row["canon_assignee"] = canon
        if not canon:
            shared.append(row)     # unassigned = everyone sees it, never hidden
        elif me is not None and canon == me:
            yours.append(row)
        else:
            others.append(row)

    def render_bucket(heading, bucket, show_assignee):
        out.append("")
        out.append(heading % len(bucket))
        for row in bucket[:CAP_DECISIONS]:
            out.append(render_row(row, show_assignee))
        if len(bucket) > CAP_DECISIONS:
            out.append("(+%d more)" % (len(bucket) - CAP_DECISIONS))
        if not bucket:
            out.append("(none)")

    if open_rows:
        render_bucket("### YOURS (%d) -- assigned to the current identity",
                      yours, False)
        render_bucket("### OTHERS' (%d) -- assigned, always visible to everyone",
                      others, True)
        render_bucket("### SHARED (%d) -- unassigned: visible to every identity",
                      shared, False)
    if not open_rows and ledger_text is not None:
        out.append("(none -- every ledger row resolves against committed state)")

    # 2. recent activity
    out.append("")
    frag_rel = cfg["journal_dir"]
    frag_dir = os.path.join(root, frag_rel)
    try:
        names = sorted(n for n in os.listdir(frag_dir) if n.endswith(".md"))
    except OSError:
        names = None
    frags = []
    for name in names or []:
        frag_id, slug, date = parse_fragment(
            name, read_text(os.path.join(frag_dir, name)))
        frags.append({"id": frag_id, "slug": slug, "date": date, "name": name})
    days = {}
    for f in frags:
        days.setdefault(f["date"] or "undated", []).append(f)
    day_keys = sorted(days, reverse=True)[:CAP_ACTIVITY_DAYS]
    out.append("## 2. RECENT ACTIVITY (last %d day(s) with journal fragments)"
               % len(day_keys))
    out.append("")
    if names is None:
        out.append("source missing: %s/" % frag_rel)
    for day in day_keys:
        entries = sorted(days[day],
                         key=lambda f: (-(f["id"] if f["id"] is not None else -1),
                                        f["name"]))
        out.append("%s:" % day)
        for f in entries:
            fid = ("fragment %d" % f["id"]) if f["id"] is not None else f["name"]
            out.append("- %s (%s)" % (f["slug"], fid))
    if not day_keys and names is not None:
        out.append("(none yet -- journal fragments will appear here)")

    out.append("")
    return "\n".join(out) + "\n"


def main(argv):
    args = list(argv[1:])
    flags = {a for a in args if a.startswith("--")}
    positional = [a for a in args if not a.startswith("--")]
    if positional:
        root = os.path.abspath(positional[0])
    else:
        env_root = os.environ.get("CLAUDE_PROJECT_DIR")
        root = env_root if env_root and os.path.isdir(env_root) else os.getcwd()
    quiet = "--quiet" in flags
    try:
        text = compile_text(root)
        target = os.path.join(root, DASHBOARD_NAME)
        current = read_text(target)
        if "--check" in flags:
            return 0 if current == text else 1
        if current != text:
            tmp = target + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp, target)
        if not quiet:
            sys.stdout.write("%s: %d line(s) compiled%s\n"
                             % (DASHBOARD_NAME, text.count("\n"),
                                " (unchanged)" if current == text else ""))
    except Exception:
        # fail open: a status surface must never break a session or a stop
        if not quiet:
            sys.stdout.write("dashboard compile skipped (unexpected error; "
                             "failing open)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
