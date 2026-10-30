"""End-to-end tests for dehydrate.py on throwaway repos. Stdlib only: python3 -m unittest discover tests

Every test builds its own fixture under a temp dir: a bare origin, a clone with linked worktrees in
known states, a fake ~/.claude (transcripts, jobs), a fake `claude` binary that logs its calls, and a
fixed --now 30 days in the future so "stale" never depends on the wall clock.
"""
import gzip
import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "dehydrate.py")
NOW = time.time() + 30 * 86400
ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x", GIT_COMMITTER_NAME="t",
           GIT_COMMITTER_EMAIL="t@x", GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
for k in [k for k in ENV if k.startswith(("DEHYDRATE_", "FAKE_"))] + ["CLAUDE_CODE_SESSION_ID", "CLAUDE_JOB_DIR",
                                                                       "CLAUDE_CONFIG_DIR"]:
    ENV.pop(k, None)  # a sandbox shell (make_fixture's exports) must not leak into the tests
FAKE_CLAUDE = os.path.join(HERE, "fake_claude.sh")
FAKE_GH = os.path.join(HERE, "fake_gh.sh")  # exits 1 without $FAKE_GH_JSON: no test reaches the real gh
SLOW_FETCH_S = 180  # fetch budget for the merge rule in tests (a fail-closed case sets its own 1 s)


def sh(cwd, *a, check=True):
    r = subprocess.run(list(a), cwd=cwd, capture_output=True, text=True, env=ENV)
    if check and r.returncode:
        raise AssertionError(f"{a} failed in {cwd}: {r.stderr}")
    return r.stdout.strip()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(text)


def touch_future(path, days=29):
    t = time.time() + days * 86400
    os.utime(path, (t, t))


def sha256_file(p):
    import hashlib
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def status_set(path):
    """Porcelain status as {path: XY code}: staged and unstaged state both have to round-trip."""
    out = subprocess.run(["git", "status", "--porcelain=v1", "-uall"], cwd=path, capture_output=True,
                         text=True, env=ENV).stdout
    return {line[3:]: line[:2] for line in out.splitlines()}


class Fixture:
    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="dehydrate-test-")
        r = self.root
        self.src = os.path.join(r, "src")
        self.home = os.path.join(r, "claude")
        self.state = os.path.join(r, "state")
        self.repo = os.path.join(self.src, "app")
        self.bare = os.path.join(r, "origin.git")
        os.makedirs(self.src)
        sh(r, "git", "init", "-q", "--bare", "-b", "main", self.bare)
        sh(self.src, "git", "clone", "-q", self.bare, self.repo)
        write(os.path.join(self.repo, ".gitignore"), "node_modules/\n*.log\nsecrets.local\nnotes-local/\n")
        write(os.path.join(self.repo, "a.txt"), "a1\n")
        write(os.path.join(self.repo, "gone.txt"), "will be deleted\n")
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "init")
        sh(self.repo, "git", "push", "-q", "origin", "HEAD:main")
        self.main_sha = sh(self.repo, "git", "rev-parse", "HEAD")
        wt = os.path.join(self.repo, ".claude", "worktrees")
        self.wt = {}
        for name in ("dirty", "clean", "recent", "locked", "nested", "unpushed", "busy", "ignored-big"):
            p = os.path.join(wt, name)
            sh(self.repo, "git", "worktree", "add", "-q", "-b", f"wt-{name}", p)
            self.wt[name] = os.path.realpath(p)
        d = self.wt["dirty"]
        write(os.path.join(d, "a.txt"), "a2 modified\n")
        write(os.path.join(d, "staged.txt"), "staged\n")
        sh(d, "git", "add", "staged.txt")
        write(os.path.join(d, "new", "untracked.txt"), "untracked\n")
        os.unlink(os.path.join(d, "gone.txt"))
        write(os.path.join(d, "secrets.local"), "real ignored content\n")
        write(os.path.join(d, "notes-local", "n.md"), "ignored dir content\n")
        write(os.path.join(d, "node_modules", "x", "index.js"), "regenerable\n")
        write(os.path.join(d, "build.log"), "regenerable log\n")
        touch_future(self.wt["recent"])
        sh(self.repo, "git", "worktree", "lock", "--reason", "held by test", self.wt["locked"])
        n = self.wt["nested"]
        os.makedirs(os.path.join(n, "inner"))
        sh(os.path.join(n, "inner"), "git", "init", "-q")
        write(os.path.join(n, "inner", "f.txt"), "x")
        u = self.wt["unpushed"]
        write(os.path.join(u, "b.txt"), "b\n")
        sh(u, "git", "add", "-A")
        sh(u, "git", "commit", "-qm", "local only")
        self.unpushed_sha = sh(u, "git", "rev-parse", "HEAD")
        ib = self.wt["ignored-big"]
        write(os.path.join(ib, "secrets.local"), "x" * (2 * 2 ** 20))
        # excluded tree (another system's)
        self.hermes = os.path.join(self.repo, ".worktrees", "t_abc")
        sh(self.repo, "git", "worktree", "add", "-q", "-b", "hermes-x", self.hermes)
        self.hermes = os.path.realpath(self.hermes)
        # unregistered leftover dir
        self.orphan = os.path.join(wt, "leftover")
        write(os.path.join(self.orphan, "keep.md"), "orphan content\n")
        write(os.path.join(self.orphan, "node_modules", "z.js"), "regen\n")
        self.orphan = os.path.realpath(self.orphan)
        # fake ~/.claude: transcripts + jobs + agents
        self.sessions = {
            "dirty": ("aaaaaaaa-0000-0000-0000-000000000001", "b0000001", "done", self.wt["dirty"], "Fix the widget"),
            "busy": ("aaaaaaaa-0000-0000-0000-000000000002", "b0000002", "working", self.wt["busy"], "Busy work"),
            "main": ("aaaaaaaa-0000-0000-0000-000000000003", "b0000003", "blocked", self.repo, "Old question"),
            "fresh": ("aaaaaaaa-0000-0000-0000-000000000004", "b0000004", "idle", self.repo, "Fresh one"),
            "refuse": ("aaaaaaaa-0000-0000-0000-000000000005", "b0000005", "done", self.repo, "Refuses rm"),
        }
        agents = []
        for key, (sid, bid, state, cwd, title) in self.sessions.items():
            pd = os.path.join(self.home, "projects", cwd.replace("/", "-").replace(".", "-"))
            os.makedirs(pd, exist_ok=True)
            tp = os.path.join(pd, f"{sid}.jsonl")
            lines = [{"type": "user", "cwd": cwd, "sessionId": sid, "gitBranch": "x", "origin": {"kind": "human"},
                      "message": {"role": "user", "content": f"<system-reminder>noise</system-reminder>Please {title.lower()}"}},
                     {"type": "custom-title", "customTitle": title, "sessionId": sid},
                     {"type": "assistant", "message": {"content": [{"type": "text", "text": f"Done with {title}."}]}}]
            write(tp, "\n".join(json.dumps(x) for x in lines) + "\n")
            jd = os.path.join(self.home, "jobs", bid)
            write(os.path.join(jd, "state.json"), json.dumps({"state": state}))
            write(os.path.join(jd, "tmp", "scratch.py"), "print(1)\n")
            if key == "fresh":
                for p in (tp, os.path.join(jd, "state.json")):
                    touch_future(p)
            agents.append({"id": bid, "sessionId": sid, "name": title, "cwd": cwd, "kind": "background",
                           "state": state, "startedAt": int((time.time() - 40 * 86400) * 1000)})
        agents.append({"id": None, "sessionId": None, "name": "cwd-3c", "cwd": "/tmp", "kind": "interactive",
                       "state": "idle", "startedAt": int(time.time() * 1000)})
        os.makedirs(self.state, exist_ok=True)
        json.dump({"ignored_cap_mb": 1, "disk_floor_gb": 0}, open(os.path.join(self.state, "config.json"), "w"))
        self.agents = os.path.join(r, "agents.json")
        json.dump(agents, open(self.agents, "w"))
        self.calls = os.path.join(r, "claude-calls.log")
        self.claude = os.path.join(r, "fake-claude")
        write(self.claude, f"""#!/bin/sh
echo "$@" >> {self.calls}
case "$*" in "rm b0000005") echo "refusing: unpushed commits" >&2; exit 1;; esac
exit 0
""")
        os.chmod(self.claude, 0o755)

    def run(self, *a, check=True):
        cmd = [sys.executable, SCRIPT, *a]
        if a[0] in ("plan", "apply", "refresh"):
            cmd += ["--roots", self.src, "--agents-json", self.agents, "--now", str(NOW)]
        if a[0] == "refresh":
            cmd += ["--gh-bin", FAKE_GH]
        if a[0] not in ("list", "show", "nudge"):
            cmd += ["--claude-home", self.home, "--claude-bin", self.claude]
        if a[0] == "nudge":
            cmd += ["--claude-home", self.home]
        cmd += ["--state-dir", self.state]
        r = subprocess.run(cmd, capture_output=True, text=True, env=ENV, cwd=self.root)
        if check and r.returncode not in (0,):
            raise AssertionError(f"{a} rc={r.returncode}\n{r.stdout}\n{r.stderr}")
        return r

    def plan(self, *extra):
        return json.loads(self.run("plan", "--json", *extra).stdout)

    def manifest(self):
        p = os.path.join(self.state, "manifest.jsonl")
        rows = []
        for x in (open(p) if os.path.exists(p) else []):
            try:
                rows.append(json.loads(x))
            except ValueError:
                pass  # torn lines are planted on purpose in some tests
        return [r for r in rows if isinstance(r, dict) and r.get("event") == "dehydrated"]

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


class DehydrateTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()

    def tearDown(self):
        self.f.cleanup()

    def actions(self, plan):
        return {w["path"]: (w["action"], w["reason"]) for w in plan["worktrees"]}

    def test_plan_classifies_every_worktree(self):
        f = self.f
        a = self.f and self.actions(f.plan())
        self.assertEqual(a[f.wt["dirty"]][0], "dehydrate")
        self.assertEqual(a[f.wt["clean"]][0], "dehydrate")
        self.assertEqual(a[f.wt["unpushed"]][0], "dehydrate")
        self.assertEqual(a[f.wt["recent"]][0], "keep")
        self.assertEqual(a[f.wt["busy"]][0], "keep")          # bound to a working session
        self.assertEqual(a[f.wt["locked"]][0], "hold")
        self.assertEqual(a[f.wt["nested"]][0], "hold")
        self.assertEqual(a[f.hermes][0], "skip")
        self.assertIn("ignored-big", " ".join(a))

    def test_plan_is_read_only_and_deterministic(self):
        f = self.f
        before = status_set(f.wt["dirty"]), sh(f.repo, "git", "for-each-ref")
        p1, p2 = f.plan(), f.plan()
        for p in (p1, p2):
            p.pop("host", None)
        self.assertEqual(json.dumps(p1, sort_keys=True), json.dumps(p2, sort_keys=True))
        self.assertEqual(before, (status_set(f.wt["dirty"]), sh(f.repo, "git", "for-each-ref")))
        self.assertFalse(os.path.exists(os.path.join(f.state, "manifest.jsonl")))
        self.assertFalse(os.path.exists(f.calls))

    def test_sessions_selection(self):
        s = {x["bg_id"]: x for x in self.f.plan()["sessions"]}
        self.assertEqual(s["b0000001"]["action"], "close")
        self.assertEqual(s["b0000002"]["action"], "keep")   # working
        self.assertEqual(s["b0000003"]["action"], "close")  # blocked and stale
        self.assertEqual(s["b0000004"]["action"], "keep")   # fresh transcript
        self.assertEqual(s[None]["action"] if None in s else "keep", "keep")

    def test_days_flag(self):
        p = self.f.plan("--days", "60")
        self.assertEqual(p["totals"]["worktrees_dehydrate"], 0)
        self.assertEqual(p["totals"]["sessions_close"], 0)

    def test_apply_requires_yes(self):
        r = self.f.run("apply", check=False)
        self.assertEqual(r.returncode, 2)
        self.assertTrue(os.path.isdir(self.f.wt["dirty"]))

    def test_apply_then_rehydrate_round_trip(self):
        f = self.f
        want = status_set(f.wt["dirty"])
        want_a = open(os.path.join(f.wt["dirty"], "a.txt")).read()
        branch_before = sh(f.repo, "git", "rev-parse", "wt-dirty")
        r = f.run("apply", "--yes", check=False)
        self.assertEqual(r.returncode, 1, r.stdout)  # b0000005's refused rm is "not done"
        self.assertIn("claude rm b0000005", r.stdout)
        # removed, captured, nothing moved
        for k in ("dirty", "clean", "unpushed"):
            self.assertFalse(os.path.exists(f.wt[k]), k)
        for k in ("recent", "busy", "locked", "nested", "ignored-big"):
            self.assertTrue(os.path.isdir(f.wt[k]), k)
        self.assertTrue(os.path.isdir(f.hermes))
        self.assertFalse(os.path.exists(f.orphan))
        self.assertEqual(sh(f.repo, "git", "rev-parse", "main"), f.main_sha)
        self.assertEqual(sh(f.bare, "git", "rev-parse", "main"), f.main_sha)
        self.assertEqual(sh(f.repo, "git", "rev-parse", "wt-dirty"), branch_before)
        self.assertEqual(sh(f.repo, "git", "rev-parse", "wt-unpushed"), f.unpushed_sha)
        self.assertEqual(sh(f.bare, "git", "for-each-ref", "refs/dehydrated"), "")  # nothing pushed
        m = {r["worktree"]["path"]: r for r in f.manifest() if r["kind"] in ("worktree", "orphan")}
        rec = m[f.wt["dirty"]]
        state = {r["id"]: r for r in json.loads(f.run("list", "--json").stdout)}
        self.assertTrue(state[rec["id"]]["removed"])
        self.assertEqual(rec["sessions"][0]["title"], "Fix the widget")
        self.assertIn("fix the widget", rec["description"].lower())
        self.assertNotIn("system-reminder", rec["description"])
        sh(f.repo, "git", "bundle", "verify", rec["snapshot"]["bundle"])
        self.assertEqual(rec["ignored"]["count"], 3)  # secrets.local, notes-local/n.md, build.log; not node_modules
        # sessions: stop for blocked, rm for all closed; busy/fresh untouched; refusal recorded
        calls = open(f.calls).read().splitlines()
        self.assertIn("stop b0000003", calls)
        self.assertIn("rm b0000001", calls)
        self.assertIn("rm b0000003", calls)
        self.assertFalse(any("b0000002" in c or "b0000004" in c for c in calls))
        srec = [r for r in f.manifest() if r["kind"] == "session"]
        refused = [r for r in srec if r["sessions"][0]["bg_id"] == "b0000005"][0]
        self.assertFalse(state[refused["id"]]["removed"])
        self.assertTrue(os.path.isfile(refused["sessions"][0]["transcript_copy"]))
        self.assertTrue(os.path.isfile(os.path.join(f.state, "index.md")))
        # second plan: nothing left to do (idempotent)
        self.assertEqual(f.plan()["totals"]["worktrees_dehydrate"], 0)
        # rehydrate by session id prefix; delete the local ref first so the bundle path is exercised
        sh(f.repo, "git", "update-ref", "-d", rec["snapshot"]["ref"])
        tp = [p for p in [os.path.join(dp, fn) for dp, _, fns in os.walk(os.path.join(f.home, "projects")) for fn in fns]
              if "000000000001" in p][0]
        os.unlink(tp)
        out = json.loads(f.run("rehydrate", rec["id"], "--json").stdout)
        d = f.wt["dirty"]
        self.assertTrue(os.path.isdir(d))
        self.assertEqual(sh(d, "git", "branch", "--show-current"), "wt-dirty")
        self.assertEqual(status_set(d), want)
        self.assertEqual(open(os.path.join(d, "a.txt")).read(), want_a)
        self.assertFalse(os.path.exists(os.path.join(d, "gone.txt")))
        self.assertEqual(open(os.path.join(d, "secrets.local")).read(), "real ignored content\n")
        self.assertTrue(os.path.isfile(os.path.join(d, "notes-local", "n.md")))
        self.assertFalse(os.path.exists(os.path.join(d, "node_modules")))
        self.assertTrue(os.path.isfile(tp), "transcript restored")
        self.assertEqual(out["resume"][0]["session_id"], "aaaaaaaa-0000-0000-0000-000000000001")
        self.assertIn("claude --resume aaaaaaaa-0000-0000-0000-000000000001", out["resume"][0]["command"])
        self.assertEqual(out["notes"].count("WARNING: restored tree differs from the snapshot tree"), 0)
        # list finds it by words from the description and shows it rehydrated
        lst = json.loads(f.run("list", "widget", "--json").stdout)
        self.assertTrue(any(r["id"] == rec["id"] and r["rehydrations"] for r in lst))
        # a rerun while it is still restored there changes nothing (review: no silent extra rehydration)
        n = len([x for x in open(os.path.join(f.state, "manifest.jsonl")) if '"rehydrated"' in x])
        r = f.run("rehydrate", rec["id"])
        self.assertIn(f"already restored at {d}, nothing changed", r.stdout)
        self.assertEqual(len([x for x in open(os.path.join(f.state, "manifest.jsonl")) if '"rehydrated"' in x]), n)
        # rehydrating onto a path that holds something else refuses
        other = os.path.join(f.root, "taken")
        os.makedirs(other)
        r = f.run("rehydrate", rec["id"], "--path", other, check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("already exists", r.stdout + r.stderr)

    def test_rehydrate_unpushed_after_branch_deleted(self):
        f = self.f
        f.run("apply", "--yes", "--only", "unpushed")
        rec = [r for r in f.manifest() if r["kind"] == "worktree"][0]
        sh(f.repo, "git", "branch", "-D", "wt-unpushed")
        sh(f.repo, "git", "update-ref", "-d", rec["snapshot"]["ref"])
        sh(f.repo, "git", "gc", "-q", "--prune=now")
        f.run("rehydrate", "wt-unpushed")
        self.assertEqual(sh(f.wt["unpushed"], "git", "rev-parse", "HEAD"), f.unpushed_sha)
        self.assertEqual(open(os.path.join(f.wt["unpushed"], "b.txt")).read(), "b\n")

    def test_only_limits_scope(self):
        f = self.f
        f.run("apply", "--yes", "--only", "clean")
        self.assertFalse(os.path.exists(f.wt["clean"]))
        self.assertTrue(os.path.isdir(f.wt["dirty"]))
        self.assertTrue(os.path.exists(f.orphan))

    def test_mains_snapshot_never_touches_checkout(self):
        f = self.f
        write(os.path.join(f.repo, ".gitignore"), open(os.path.join(f.repo, ".gitignore")).read() + ".claude/worktrees/\n")
        write(os.path.join(f.repo, "a.txt"), "main dirty\n")
        write(os.path.join(f.repo, "loose.txt"), "loose\n")
        before = status_set(f.repo)
        f.run("apply", "--yes", "--mains", "--no-worktrees", "--no-sessions")
        self.assertEqual(status_set(f.repo), before)
        self.assertEqual(sh(f.repo, "git", "rev-parse", "HEAD"), f.main_sha)
        rec = [r for r in f.manifest() if r["kind"] == "main-snapshot"][0]
        self.assertEqual(sh(f.repo, "git", "show", f"{rec['snapshot']['commit']}:loose.txt"), "loose")
        # unchanged checkout -> no second snapshot
        f.run("apply", "--yes", "--mains", "--no-worktrees", "--no-sessions")
        self.assertEqual(len([r for r in f.manifest() if r["kind"] == "main-snapshot"]), 1)
        r = f.run("rehydrate", rec["id"], check=False)
        self.assertNotEqual(r.returncode, 0)  # never restored over the checkout
        side = os.path.join(f.root, "side")
        f.run("rehydrate", rec["id"], "--path", side)
        self.assertEqual(open(os.path.join(side, "loose.txt")).read(), "loose\n")

    def test_changed_during_capture_holds(self):
        """If the tree changes between capture and verify, the worktree is kept."""
        f = self.f
        sys.path.insert(0, os.path.dirname(SCRIPT))
        import dehydrate as d
        orig = d.snapshot_tree
        calls = {"n": 0}

        def flaky(path, skip=()):
            calls["n"] += 1
            if calls["n"] == 2:
                write(os.path.join(path, "late.txt"), "late\n")
            return orig(path, skip)
        d.snapshot_tree = flaky
        try:
            with self.assertRaises(RuntimeError):
                d.make_snapshot(f.wt["clean"], "t1", "m", tempfile.mkdtemp())
        finally:
            d.snapshot_tree = orig

    def test_redteam_regressions(self):
        """One fixture, the data-loss repros from the red-team pass."""
        f = self.f
        c = f.wt["clean"]
        # exact bytes and modes: CRLF under autocrlf, a 0600 untracked file, an untracked symlink
        sh(c, "git", "config", "core.autocrlf", "input")
        open(os.path.join(c, "win.txt"), "wb").write(b"a\r\nb\r\n")
        write(os.path.join(c, "secret.key"), "k\n")
        os.chmod(os.path.join(c, "secret.key"), 0o600)
        os.symlink("a.txt", os.path.join(c, "link-to-a"))
        # partial staging
        write(os.path.join(c, "a.txt"), "staged\n")
        sh(c, "git", "add", "a.txt")
        write(os.path.join(c, "a.txt"), "worktree\n")
        want = status_set(c)
        # a registered worktree inside a stale one must hold the outer one
        inner = os.path.join(f.wt["unpushed"], "inner-wt")
        sh(f.repo, "git", "worktree", "add", "-q", "-b", "wt-inner", inner)
        # a nested repo under a gitignored path must hold the worktree
        lib = os.path.join(f.wt["dirty"], "notes-local", "lib")
        os.makedirs(lib)
        sh(lib, "git", "init", "-q")
        # a torn last manifest line must not swallow the next record
        os.makedirs(f.state, exist_ok=True)
        open(os.path.join(f.state, "manifest.jsonl"), "w").write('{"event": "dehydrated", "id": "half')
        a = self.actions(f.plan())
        self.assertEqual(a[f.wt["unpushed"]][0], "hold", a[f.wt["unpushed"]])
        self.assertEqual(a[f.wt["dirty"]][0], "hold", a[f.wt["dirty"]])
        f.run("apply", "--yes", "--only", "clean")
        rec = [r for r in f.manifest() if isinstance(r, dict) and r.get("kind") == "worktree"]
        self.assertEqual(len(rec), 1)
        self.assertTrue(json.loads(f.run("list", "clean", "--json").stdout)[0]["removed"])
        f.run("rehydrate", "wt-clean")
        self.assertEqual(open(os.path.join(c, "win.txt"), "rb").read(), b"a\r\nb\r\n")
        self.assertEqual(os.stat(os.path.join(c, "secret.key")).st_mode & 0o777, 0o600)
        self.assertEqual(os.readlink(os.path.join(c, "link-to-a")), "a.txt")
        self.assertEqual(open(os.path.join(c, "a.txt")).read(), "worktree\n")
        self.assertEqual(sh(c, "git", "show", ":a.txt"), "staged")
        self.assertEqual(status_set(c), want)
        # dehydrating the same path again with the same --now gets a fresh id and keeps the first archive
        first = rec[0]
        f.run("apply", "--yes", "--only", "clean")
        recs = [r for r in f.manifest() if isinstance(r, dict) and r.get("kind") == "worktree"]
        self.assertEqual(len({r["id"] for r in recs}), 2)
        self.assertEqual(sha256_file(first["snapshot"]["bundle"]), first["snapshot"]["bundle_sha256"])
        # a junk manifest line does not break list
        with open(os.path.join(f.state, "manifest.jsonl"), "a") as fh:
            fh.write("123\nnull\n{}\n")
        f.run("list")

    def test_unborn_and_conflicted_are_held(self):
        f = self.f
        orph = os.path.join(f.repo, ".claude", "worktrees", "orph")
        sh(f.repo, "git", "worktree", "add", "-q", "--orphan", "-b", "orph", orph)
        write(os.path.join(orph, "draft.txt"), "d\n")
        sh(orph, "git", "add", "draft.txt")
        c = f.wt["clean"]
        sh(c, "git", "checkout", "-q", "-b", "side")
        write(os.path.join(c, "a.txt"), "side\n")
        sh(c, "git", "commit", "-qam", "side")
        sh(c, "git", "checkout", "-q", "wt-clean")
        write(os.path.join(c, "a.txt"), "mine\n")
        sh(c, "git", "commit", "-qam", "mine")
        sh(c, "git", "merge", "-q", "side", check=False)
        a = self.actions(f.plan())
        self.assertEqual(a[os.path.realpath(orph)][0], "hold", a[os.path.realpath(orph)])
        self.assertEqual(a[c][0], "hold", a[c])

    def test_rehydrate_refuses_missing_raw_index(self):
        f = self.f
        f.run("apply", "--yes", "--only", "dirty")
        rec = [r for r in f.manifest() if r["kind"] == "worktree"][0]
        os.unlink(rec["raw"]["files"])
        r = f.run("rehydrate", rec["id"], check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("nothing was changed", r.stderr + r.stdout)
        self.assertFalse(os.path.exists(f.wt["dirty"]))

    def test_disk_floor_pauses_before_touching_anything(self):
        f = self.f
        json.dump({"disk_floor_gb": 10 ** 6}, open(os.path.join(f.state, "config.json"), "w"))
        r = f.run("apply", "--yes", check=False)
        self.assertEqual(r.returncode, 3)
        self.assertIn("PAUSED", r.stdout)
        self.assertTrue(all(os.path.isdir(p) for p in f.wt.values()))
        self.assertFalse(os.path.exists(f.calls))

    def test_nudge_and_refresh(self):
        f = self.f
        r = f.run("nudge")
        self.assertEqual(r.stdout, "")  # no cached plan yet
        f.run("refresh")
        self.assertTrue(os.path.isfile(os.path.join(f.state, "last-plan.json")))
        r1, r2 = f.run("nudge").stdout, f.run("nudge").stdout
        self.assertTrue(r1.startswith("DEHYDRATE:"))
        self.assertEqual(r2, "")  # cooldown

    # ---- --pressure: free disk target, idle window ignored, one worktree at a time

    def pressure_run(self, *a, fake="", check=False):
        env = dict(ENV, DEHYDRATE_FAKE_FREE_GB=fake) if fake else ENV
        f = self.f
        cmd = [sys.executable, SCRIPT, *a, "--roots", f.src, "--agents-json", f.agents, "--now", str(NOW),
               "--claude-home", f.home, "--claude-bin", f.claude, "--state-dir", f.state]
        return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=f.root)

    def test_pressure_plan_ignores_window_keeps_holds(self):
        f = self.f
        r = self.pressure_run("plan", "--json", "--pressure", "--target-gb", "10", "--days", "60")
        self.assertEqual(r.returncode, 0, r.stderr)
        p = json.loads(r.stdout)
        a = self.actions(p)
        self.assertEqual(a[f.wt["recent"]][0], "dehydrate")   # touched a day ago: the window is ignored
        self.assertEqual(a[f.wt["busy"]][0], "keep")          # bound to a working session: still kept
        self.assertEqual(a[f.wt["locked"]][0], "hold")
        self.assertEqual(a[f.wt["nested"]][0], "hold")
        self.assertEqual(a[f.hermes][0], "skip")
        order = p["pressure"]["order"]
        self.assertEqual(order[-1], f.wt["recent"])          # least recently active first
        self.assertEqual(set(order), {w for w, (act, _) in a.items() if act == "dehydrate"})
        s = {x["bg_id"]: x for x in p["sessions"]}
        # done for 30 days (> 24 h) under a 60-day window: no longer protects its worktree under pressure
        self.assertEqual(s["b0000001"]["action"], "close")
        self.assertIn("pressure", s["b0000001"]["reason"])
        self.assertEqual(s["b0000002"]["action"], "keep")    # working
        self.assertEqual(s["b0000003"]["action"], "keep")    # blocked, but frees no disk on its own
        self.assertEqual(p["orphans"], [])
        normal = f.plan("--days", "60")
        self.assertEqual(normal["totals"]["worktrees_dehydrate"], 0)
        self.assertEqual({x["bg_id"]: x["action"] for x in normal["sessions"]}["b0000001"], "keep")

    def test_pressure_apply_stops_at_target(self):
        f = self.f
        p = json.loads(self.pressure_run("plan", "--json", "--pressure", "--target-gb", "10").stdout)
        first = p["pressure"]["order"][0]
        r = self.pressure_run("apply", "--yes", "--json", "--pressure", "--target-gb", "10", fake="1,50")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        res = json.loads(r.stdout)
        self.assertEqual([w["path"] for w in res["worktrees"]], [first])
        self.assertTrue(res["worktrees"][0]["removed"])
        self.assertTrue(res["pressure"]["reached"])
        self.assertFalse(os.path.exists(first))
        for name, path in f.wt.items():
            if path != first:
                self.assertTrue(os.path.isdir(path), name)
        self.assertTrue(os.path.isdir(f.orphan))             # leftovers are not pressure candidates
        closed = {x["bg_id"] for x in res["sessions"] if x.get("ok")}
        bound = {x["bg_id"] for x in p["sessions"] if x.get("worktree") == first and x["action"] == "close"}
        self.assertEqual(closed, bound)
        self.assertTrue(os.path.isfile(os.path.join(f.state, "index.md")))

    def test_pressure_already_at_target_does_nothing(self):
        f = self.f
        r = self.pressure_run("apply", "--yes", "--json", "--pressure", "--target-gb", "10", fake="100")
        self.assertEqual(r.returncode, 0, r.stderr)
        res = json.loads(r.stdout)
        self.assertEqual(res["worktrees"], [])
        self.assertEqual(res["sessions"], [])
        self.assertTrue(res["pressure"]["reached"])
        self.assertTrue(all(os.path.isdir(p) for p in f.wt.values()))
        self.assertFalse(os.path.exists(f.calls))

    def test_pressure_floor_is_per_item(self):
        """0.2.2: under --pressure the fixed disk_floor_gb gives way to capture estimate + 200 MB per item."""
        f = self.f
        cp = os.path.join(f.state, "config.json")
        c = json.load(open(cp))
        c["disk_floor_gb"] = 2
        json.dump(c, open(cp, "w"))
        # 0.2002 GiB (about 205 MiB) free: under the 2 GB floor, but room for a small item plus the margin
        r = self.pressure_run("apply", "--yes", "--json", "--pressure", "--target-gb", "10", fake="0.2002")
        res = json.loads(r.stdout)
        self.assertIsNone(res["paused"], res["paused"])
        self.assertTrue(any(w.get("removed") for w in res["worktrees"]), res["worktrees"])
        # normal apply keeps the fixed floor (real free disk is far above 0 here, so prove it with a huge floor)
        c["disk_floor_gb"] = 10 ** 6
        json.dump(c, open(cp, "w"))
        r = f.run("apply", "--yes", "--json", "--no-sessions", check=False)
        self.assertEqual(r.returncode, 3)
        self.assertIn("under floor", json.loads(r.stdout)["paused"])

    def test_pressure_pauses_before_an_item_too_big_to_capture(self):
        f = self.f
        p = json.loads(self.pressure_run("plan", "--json", "--pressure", "--target-gb", "10").stdout)
        first = p["pressure"]["order"][0]
        st = os.stat(first)
        with open(os.path.join(first, "big-untracked.bin"), "wb") as fh:
            fh.write(os.urandom(10 * 2 ** 20))                     # 10 MiB to capture, twice (overlay + bundle)
        os.utime(os.path.join(first, "big-untracked.bin"), (0, 0))  # keep its place in the order (oldest first)
        os.utime(first, (st.st_atime, st.st_mtime))
        r = self.pressure_run("apply", "--yes", "--json", "--pressure", "--target-gb", "10", fake="0.2002")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        res = json.loads(r.stdout)
        self.assertEqual(res["worktrees"], [])                       # paused before touching anything
        self.assertIn("needs: about 20 MB", res["paused"])
        self.assertIn("200 MB margin", res["paused"])
        self.assertTrue(os.path.isdir(first))

    def test_pressure_flags_go_together(self):
        self.assertEqual(self.pressure_run("plan", "--pressure").returncode, 2)
        self.assertEqual(self.pressure_run("plan", "--target-gb", "5").returncode, 2)

    def test_apply_survives_a_crashing_item_and_a_remove_timeout(self):
        """A crash in one item is a "not done" line; prune and the index still run (in-process, patched)."""
        import importlib.util
        import io
        from contextlib import redirect_stdout
        from unittest import mock
        f = self.f
        spec = importlib.util.spec_from_file_location("dehydrate_under_test", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        real_rid, real_git = mod.unique_rid, mod.git
        crashed, timed_out = [], []

        def flaky_rid(sd, rid):
            if not crashed:
                crashed.append(rid)
                raise OSError("disk hiccup")
            return real_rid(sd, rid)

        def slow_git(cwd, *a, **k):
            if a[:2] == ("worktree", "remove") and not timed_out:
                timed_out.append(a[-1])
                raise subprocess.TimeoutExpired(["git"], 3600)
            return real_git(cwd, *a, **k)

        argv = ["apply", "--yes", "--json", "--no-sessions", "--roots", f.src, "--agents-json", f.agents,
                "--now", str(NOW), "--claude-home", f.home, "--claude-bin", f.claude, "--state-dir", f.state]
        buf = io.StringIO()
        with mock.patch.dict(os.environ, ENV, clear=True), mock.patch.object(mod, "unique_rid", flaky_rid), \
                mock.patch.object(mod, "git", slow_git), redirect_stdout(buf):
            rc = mod.main(argv)
        res = json.loads(buf.getvalue())
        self.assertEqual(rc, 1)
        bad = [w for w in res["worktrees"] if not w.get("ok")]
        good = [w for w in res["worktrees"] if w.get("ok")]
        self.assertEqual(len(bad), 2, bad)
        self.assertTrue(any("disk hiccup" in w["error"] for w in bad))
        self.assertTrue(any("timed out" in w["error"] for w in bad))
        self.assertGreaterEqual(len(good), 2)                # the loop went on after both failures
        self.assertTrue(res["pruned"] and all(x["ok"] for x in res["pruned"]))
        self.assertTrue(os.path.isfile(os.path.join(f.state, "index.md")))
        self.assertTrue(os.path.isdir(timed_out[0]))         # captured, not removed, rerun-able


# ---- 0.2.0: the merge rule, auto-dehydrate on close, list --picker, rehydrate --launch (DESIGN 8.1)

def load_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("dehydrate_mini", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Mini:
    """A small fixture: a bare origin, a clone on main, worktrees made per test, a fake ~/.claude, and the fake
    claude and gh bins driven by env. Cheaper than Fixture, so each auto test builds only what it checks."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="dehydrate-mini-")
        r = self.root
        self.src, self.home, self.state = (os.path.join(r, x) for x in ("src", "claude", "state"))
        self.repo, self.bare = os.path.join(self.src, "app"), os.path.join(r, "origin.git")
        os.makedirs(self.src)
        os.makedirs(self.state)
        sh(r, "git", "init", "-q", "--bare", "-b", "main", self.bare)
        sh(self.src, "git", "clone", "-q", self.bare, self.repo)
        write(os.path.join(self.repo, "a.txt"), "a\n")
        write(os.path.join(self.repo, "b.txt"), "line1\nline2\nline3\n")
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "init")
        sh(self.repo, "git", "push", "-q", "origin", "HEAD:main")
        self.agents = os.path.join(r, "agents.json")
        self.rows = []
        json.dump([], open(self.agents, "w"))
        self.config({})
        self.log = os.path.join(r, "claude-calls.log")
        self.env = dict(ENV, FAKE_CLAUDE_LOG=self.log)

    def config(self, extra):
        # a local bare-remote fetch can pass the 30 s default on a loaded host; the rule would fail closed
        json.dump(dict({"disk_floor_gb": 0, "auto_fetch_timeout_s": SLOW_FETCH_S}, **extra),
                  open(os.path.join(self.state, "config.json"), "w"))

    def wt(self, name, commits=(), path=None):
        p = path or os.path.join(self.repo, ".claude", "worktrees", name)
        sh(self.repo, "git", "worktree", "add", "-q", "-b", f"wt-{name}", p, "main")
        for i, (fn, text) in enumerate(commits):
            write(os.path.join(p, fn), text)
            sh(p, "git", "add", "-A")
            sh(p, "git", "commit", "-qm", f"{name} {i}")
        return os.path.realpath(p)

    def main_commit(self, fn, text):
        write(os.path.join(self.repo, fn), text)
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", f"main {fn}")
        sh(self.repo, "git", "push", "-q", "origin", "main")

    def merge(self, name, how="no-ff"):
        b = f"wt-{name}"
        if how == "no-ff":
            sh(self.repo, "git", "merge", "-q", "--no-ff", "-m", f"merge {name}", b)
        elif how == "ff":
            sh(self.repo, "git", "merge", "-q", "--ff-only", b)
        elif how == "squash":
            sh(self.repo, "git", "merge", "-q", "--squash", b)
            sh(self.repo, "git", "commit", "-qm", f"squash {name}")
        elif how == "rebase":
            for c in sh(self.repo, "git", "rev-list", "--reverse", f"main..{b}").split():
                sh(self.repo, "git", "cherry-pick", c)
        sh(self.repo, "git", "push", "-q", "origin", "main")

    def session(self, sid, bid, cwd, name, state="done", kind="background", pid=None, ended=None, listed=True):
        ended = ended or time.time() - 3600
        pd = os.path.join(self.home, "projects", cwd.replace("/", "-").replace(".", "-"))
        tp = os.path.join(pd, f"{sid}.jsonl")
        write(tp, json.dumps({"type": "user", "cwd": cwd, "sessionId": sid, "origin": {"kind": "human"},
                              "message": {"role": "user", "content": f"please {name}"}}) + "\n")
        os.utime(tp, (ended, ended))
        if bid:
            sp = os.path.join(self.home, "jobs", bid, "state.json")
            write(sp, json.dumps({"state": state, "sessionId": sid}))
            os.utime(sp, (ended, ended))
        if listed:
            row = {"id": bid, "sessionId": sid, "name": name, "cwd": cwd, "kind": kind, "startedAt": int((ended - 60) * 1000)}
            row.update({"state": state} if kind == "background" else {"status": "idle"})
            if pid:
                row["pid"] = pid
            self.rows.append(row)
            json.dump(self.rows, open(self.agents, "w"))
        return tp

    def run(self, *a, env=None, check=True):
        cmd = [sys.executable, SCRIPT, *a]
        if a[0] in ("auto", "refresh", "plan", "apply"):
            cmd += ["--roots", self.src, "--agents-json", self.agents]
        if a[0] in ("auto", "refresh"):
            cmd += ["--gh-bin", FAKE_GH]
        if a[0] != "show":
            cmd += ["--claude-home", self.home, "--claude-bin", FAKE_CLAUDE]
        cmd += ["--state-dir", self.state]
        r = subprocess.run(cmd, capture_output=True, text=True, env=dict(self.env, **(env or {})), cwd=self.root,
                           timeout=600)
        if check and r.returncode != 0:
            raise AssertionError(f"{a} rc={r.returncode}\n{r.stdout}\n{r.stderr}")
        return r

    def records(self):
        p = os.path.join(self.state, "manifest.jsonl")
        return [json.loads(x) for x in open(p)] if os.path.exists(p) else []

    def auto_log(self):
        p = os.path.join(self.state, "auto.log")
        return [json.loads(x) for x in open(p)] if os.path.exists(p) else []

    def calls(self):
        return open(self.log).read().splitlines() if os.path.exists(self.log) else []

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


class AutoAndPickerTests(unittest.TestCase):
    def setUp(self):
        self.m = Mini()

    def tearDown(self):
        self.m.cleanup()

    def rule(self, path, env=None, **cfg):
        from unittest import mock
        d = load_module()
        with mock.patch.dict(os.environ, dict(ENV, **(env or {})), clear=True):
            return d.merge_rule(path, dict(d.DEFAULTS, **dict({"auto_fetch_timeout_s": SLOW_FETCH_S}, **cfg)), FAKE_GH)

    def test_merge_rule_scenarios(self):
        m = self.m
        ff = m.wt("ff", [("ff.txt", "ff\n")])
        m.merge("ff", "ff")
        squash = m.wt("squash", [("s1.txt", "1\n"), ("s2.txt", "2\n")])
        m.merge("squash", "squash")
        rebase = m.wt("rebase", [("r.txt", "r\n")])
        m.main_commit("other.txt", "o\n")
        m.merge("rebase", "rebase")
        dirty = m.wt("dirty", [("d.txt", "d\n")])
        m.merge("dirty", "no-ff")
        write(os.path.join(dirty, "scratch.txt"), "uncommitted\n")
        write(os.path.join(dirty, "a.txt"), "edited\n")
        opn = m.wt("open", [("o.txt", "open\n")])
        sqp = m.wt("squashplus", [("sp.txt", "1\n")])
        m.merge("squashplus", "squash")
        write(os.path.join(sqp, "sp.txt"), "2\n")
        sh(sqp, "git", "commit", "-qam", "after the squash")
        fresh = m.wt("fresh")
        det = os.path.join(m.repo, ".claude", "worktrees", "det")
        sh(m.repo, "git", "worktree", "add", "-q", "--detach", det, "main")
        want = {ff: "ancestor", squash: "merge-tree", rebase: "merge-tree", dirty: "ancestor"}
        for path, by in want.items():
            got = self.rule(path)
            self.assertTrue(got["merged"], (path, got))
            self.assertEqual(got["by"], by, path)
            self.assertEqual(got["default_branch"], "main")
        for path, why in ((opn, "commits not in"), (sqp, "commits not in"), (fresh, "no commits of its own"),
                          (m.repo, "main checkout"), (det, "detached")):
            got = self.rule(path)
            self.assertFalse(got["merged"], (path, got))
            self.assertIn(why, got["reason"], path)
        self.assertFalse(self.rule(dirty, auto_require_clean=True)["merged"])
        self.assertTrue(self.rule(ff, auto_require_clean=True)["merged"])
        # the default branch itself, checked out in a linked worktree
        sh(m.repo, "git", "checkout", "-q", "--detach")
        dflt = os.path.join(m.root, "on-main")
        sh(m.repo, "git", "worktree", "add", "-q", dflt, "main")
        self.assertIn("default branch", self.rule(dflt)["reason"])

    def test_merge_rule_gh_recovers_conflicting_squash(self):
        m = self.m
        g = m.wt("gh", [("b.txt", "line1\nCHANGED\nline3\n")])
        m.merge("gh", "squash")
        m.main_commit("b.txt", "line1\nAGAIN\nline3\n")  # the default branch edits the squashed lines later
        head = sh(g, "git", "rev-parse", "HEAD")
        self.assertFalse(self.rule(g, auto_use_gh=False)["merged"])
        self.assertFalse(self.rule(g)["merged"])  # fake gh exits 1: not merged
        pr = {"number": 620, "headRefOid": head, "baseRefName": "main", "mergedAt": "2026-10-29T10:00:00Z"}
        got = self.rule(g, env={"FAKE_GH_JSON": json.dumps([pr])})
        self.assertEqual((got["merged"], got["by"], got["pr"]), (True, "gh-pr", 620))
        for bad in (dict(pr, headRefOid="0" * 40), dict(pr, baseRefName="develop")):
            self.assertFalse(self.rule(g, env={"FAKE_GH_JSON": json.dumps([bad])})["merged"], bad)

    def test_merge_rule_fails_closed(self):
        m = self.m
        w = m.wt("hang", [("h.txt", "h\n")])
        m.merge("hang", "ff")
        self.assertTrue(self.rule(w)["merged"])
        hang = os.path.join(m.root, "hang-upload-pack")
        write(hang, "#!/bin/sh\nexec sleep 30 2>/dev/null\n")  # holds none of our pipes
        os.chmod(hang, 0o755)
        sh(m.repo, "git", "remote", "set-head", "origin", "main")
        sh(m.repo, "git", "config", "remote.origin.uploadpack", hang)
        t0 = time.time()
        got = self.rule(w, auto_fetch_timeout_s=1)
        self.assertFalse(got["merged"])
        self.assertIn("timed out", got["reason"])
        self.assertLess(time.time() - t0, 20)  # bounded by the timeout, not the 30 s hang (slow host: wide margin)
        sh(m.repo, "git", "config", "--unset", "remote.origin.uploadpack")
        sh(m.repo, "git", "remote", "remove", "origin")
        got = self.rule(w)
        self.assertFalse(got["merged"])
        self.assertIn("no origin", got["reason"])

    def test_auto_sweep_dehydrates_only_merged(self):
        m = self.m
        wts = {k: m.wt(k, [(f"{k}.txt", k + "\n")]) for k in ("merged", "open", "merged2", "merged3", "merged4")}
        hermes = m.wt("t_x", [("t.txt", "t\n")], path=os.path.join(m.repo, ".worktrees", "t_x"))
        for k in ("merged", "merged2", "merged3", "merged4", "t_x"):
            m.merge(k)
        S = {"A": "aaaaaaaa-0000-0000-0000-00000000000a", "B": "bbbbbbbb-0000-0000-0000-00000000000b",
             "C": "cccccccc-0000-0000-0000-00000000000c", "D": "dddddddd-0000-0000-0000-00000000000d",
             "E": "eeeeeeee-0000-0000-0000-00000000000e", "F": "ffffffff-0000-0000-0000-00000000000f",
             "G": "99999999-0000-0000-0000-000000000009"}
        m.session(S["A"], "aaaaaaaa", wts["merged"], "merged work")
        m.session(S["B"], "bbbbbbbb", wts["open"], "open work")
        m.session(S["C"], "cccccccc", wts["merged2"], "waiting on owner", state="blocked")
        m.session(S["D"], "dddddddd", wts["merged3"], "still has a pid", pid=os.getpid())
        m.session(S["E"], None, os.path.join(wts["merged4"]), "cwd-3c", kind="interactive", pid=os.getpid())
        m.session(S["F"], "ffffffff", wts["merged4"], "next to an open terminal")
        m.session(S["G"], "99999999", hermes, "hermes task")
        out = json.loads(m.run("auto", "--json").stdout)
        dec = {d["session_id"]: d for d in out["decisions"]}
        self.assertEqual(dec[S["A"]]["decision"], "dehydrated", dec[S["A"]])
        self.assertEqual([k for k, s in S.items() if dec.get(s, {}).get("decision") == "dehydrated"], ["A"])
        self.assertIn("not merged", dec[S["B"]]["reason"])
        self.assertIn("blocked", dec[S["C"]]["reason"])
        self.assertIn("pid", dec[S["D"]]["reason"])
        self.assertIn("interactive session cwd-3c is open", dec[S["F"]]["reason"])
        self.assertIn("excluded", dec[S["G"]]["reason"])
        self.assertNotIn(S["E"], dec)  # an interactive session is never a sweep candidate
        self.assertFalse(os.path.exists(wts["merged"]))
        for k in ("open", "merged2", "merged3", "merged4"):
            self.assertTrue(os.path.isdir(wts[k]), k)
        self.assertTrue(os.path.isdir(hermes))
        recs = [r for r in m.records() if r.get("event") == "dehydrated"]
        self.assertEqual(sorted(r["kind"] for r in recs), ["session", "worktree"])
        for r in recs:
            self.assertEqual(r["auto"], {"trigger": "sweep", "merged_by": "ancestor", "pr": None,
                                         "default_branch": "main"})
        wrec = [r for r in recs if r["kind"] == "worktree"][0]
        self.assertEqual(wrec["worktree"]["branch"], "wt-merged")
        self.assertEqual(wrec["sessions"][0]["name"], "merged work")
        self.assertIn("rm aaaaaaaa", m.calls())
        self.assertFalse(any(x.startswith("rm ") and "aaaaaaaa" not in x for x in m.calls()), m.calls())
        logged = {d["session_id"]: d for d in m.auto_log()}
        self.assertEqual(logged[S["A"]]["decision"], "dehydrated")
        self.assertEqual(logged[S["B"]]["decision"], "refused")
        self.assertTrue(all(k in logged[S["B"]] for k in ("at", "session_id", "bg_id", "name", "decision", "reason")))
        # the next sweep does not log the same refusals again (A's row goes, as `claude rm` drops it)
        json.dump([x for x in m.rows if x["sessionId"] != S["A"]], open(m.agents, "w"))
        n = len(m.auto_log())
        m.run("auto", "--json")
        self.assertEqual(len(m.auto_log()), n)

    def test_auto_grace_and_rate_limit(self):
        m = self.m
        w = m.wt("g", [("g.txt", "g\n")])
        m.merge("g")
        t = time.time() - 3600
        sid = "abababab-0000-0000-0000-000000000001"
        m.session(sid, "abababab", w, "graceful", ended=t)
        r = json.loads(m.run("auto", "--json", "--now", str(t + 300)).stdout)
        self.assertEqual(r["decisions"][0]["decision"], "refused")
        self.assertIn("ended 5m ago", r["decisions"][0]["reason"])
        self.assertTrue(os.path.isdir(w))
        # SessionStart refresh sweeps at most once per auto_sweep_minutes
        m.run("refresh", "--now", str(t + 300))
        self.assertTrue(os.path.isfile(os.path.join(m.state, "last-auto")))
        n = len(m.auto_log())
        m.run("refresh", "--now", str(t + 900))
        self.assertTrue(os.path.isdir(w))
        self.assertEqual(len(m.auto_log()), n)
        old = time.time() - 3600
        os.utime(os.path.join(m.state, "last-auto"), (old, old))
        m.run("refresh", "--now", str(t + 900))
        self.assertFalse(os.path.exists(w))
        self.assertEqual(m.auto_log()[-1]["decision"], "dehydrated")

    def test_auto_off_switch(self):
        m = self.m
        w = m.wt("off", [("o.txt", "o\n")])
        m.merge("off")
        m.session("acacacac-0000-0000-0000-000000000001", "acacacac", w, "switched off")
        m.config({"auto_on_close": False})
        self.assertIn("auto_on_close is off", m.run("auto").stdout)
        m.run("refresh")
        self.assertTrue(os.path.isdir(w))
        self.assertEqual(m.records(), [])
        for f in ("auto.log", "last-auto"):
            self.assertFalse(os.path.exists(os.path.join(m.state, f)), f)
        self.assertEqual(m.calls(), [])

    def test_auto_session_mode(self):
        m = self.m
        merged, opn = m.wt("im", [("i.txt", "i\n")]), m.wt("io", [("j.txt", "j\n")])
        m.merge("im")
        p = subprocess.Popen(["true"])
        p.wait()  # a pid that has exited: the session's process is gone
        sids = {"im": "12121212-0000-0000-0000-000000000001", "io": "12121212-0000-0000-0000-000000000002"}
        for k, w in (("im", merged), ("io", opn)):
            m.session(sids[k], None, w, "", kind="interactive", ended=time.time(), listed=False)
            write(os.path.join(m.home, "sessions", f"{p.pid}{k}.json"),
                  json.dumps({"pid": p.pid, "sessionId": sids[k], "cwd": w, "name": f"terminal {k}", "kind": "interactive"}))
        env = {"DEHYDRATE_AUTO_WAIT_S": "2"}
        r = json.loads(m.run("auto", "--session", sids["im"], "--json", env=env).stdout)
        self.assertEqual([d["decision"] for d in r["decisions"]], ["dehydrated"], r)
        self.assertFalse(os.path.exists(merged))
        rec = [x for x in m.records() if x.get("event") == "dehydrated"][0]
        self.assertEqual(rec["kind"], "worktree")
        self.assertEqual(rec["auto"]["trigger"], "session.end")
        self.assertEqual(rec["sessions"][0]["session_id"], sids["im"])
        self.assertEqual(rec["sessions"][0]["name"], "terminal im")  # the name it had, for the picker
        r = json.loads(m.run("auto", "--session", sids["io"], "--json", env=env).stdout)
        self.assertEqual(r["decisions"][0]["decision"], "refused")
        self.assertIn("not merged", r["decisions"][0]["reason"])
        self.assertTrue(os.path.isdir(opn))

    def test_auto_session_mode_background_and_dry_run(self):
        """The kick runs with the ending session's env; a background target is still the target."""
        m = self.m
        w = m.wt("bgk", [("k.txt", "k\n")])
        m.merge("bgk")
        sid = "34343434-0000-0000-0000-000000000001"
        m.session(sid, "34343434", w, "kicked", ended=time.time())  # just ended: no grace in --session mode
        env = {"DEHYDRATE_AUTO_WAIT_S": "1", "CLAUDE_CODE_SESSION_ID": sid,
               "CLAUDE_JOB_DIR": os.path.join(m.home, "jobs", "34343434")}
        r = json.loads(m.run("auto", "--session", sid, "--dry-run", "--json", env=env).stdout)
        self.assertEqual((r["decisions"][0]["decision"], r["decisions"][0]["dry_run"]), ("dehydrate", True))
        self.assertTrue(os.path.isdir(w))
        self.assertEqual((m.records(), m.auto_log()), ([], []))
        r = json.loads(m.run("auto", "--session", sid, "--json", env=env).stdout)
        self.assertEqual(r["decisions"][0]["decision"], "dehydrated", r)
        self.assertFalse(os.path.exists(w))
        self.assertIn("rm 34343434", m.calls())

    # ---- list --picker

    def put(self, *recs):
        with open(os.path.join(self.m.state, "manifest.jsonl"), "a") as f:
            for r in recs:
                f.write(json.dumps(dict({"event": "dehydrated", "schema": 1}, **r)) + "\n")

    def iso(self, ts):
        import datetime as dt
        return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat(timespec="seconds")

    def picker(self, *words, env=None, extra=()):
        return json.loads(self.m.run("list", "--picker", *words, *extra, env=env).stdout)

    def test_list_picker_shape_and_groups(self):
        import datetime as dt
        now = dt.datetime(2026, 10, 15, 12, 0).timestamp()  # local noon: -1h stays on the same date
        H, D = 3600, 86400
        self.put({"id": "r1", "kind": "worktree", "at": self.iso(now - H), "description": "alpha work",
                  "repo": {"path": "/x/src/vault", "origin": "git@github.com:getfatday/vault.git"},
                  "worktree": {"path": "/x/src/vault/.claude/worktrees/alpha", "branch": "wt-alpha"}, "removed": True,
                  "auto": {"trigger": "sweep"},
                  "sessions": [{"session_id": "aaaa1111-0", "bg_id": "aaaa1111", "name": "alpha sprites",
                                "first_prompt": "make the sprites"},
                               {"session_id": "bbbb2222-0", "bg_id": "bbbb2222", "name": "beta second"}]},
                 {"id": "r2", "kind": "session", "at": self.iso(now - 3 * D), "repo": {"path": "/x/src/product-portfolio"},
                  "sessions": [{"session_id": "cccc3333-0", "bg_id": "cccc3333", "title": "capacity plan"}]},
                 {"id": "r3", "kind": "worktree", "at": self.iso(now - 20 * D),
                  "repo": {"path": None, "origin": "git@github.com:getfatday/dotfiles.git"},
                  "worktree": {"path": "/x/dotfiles/.claude/worktrees/wt-gamma", "branch": "wt-gamma"}, "sessions": []},
                 {"id": "r4", "kind": "orphan", "at": self.iso(now - 90 * D), "repo": {"path": "/x/src/vault"},
                  "worktree": {"path": "/x/src/vault/.claude/worktrees/left", "branch": None}})
        out = self.picker(extra=("--now", str(now), "--agents-json", self.m.agents))
        self.assertEqual(out["agents"], "live")
        rows = out["rows"]
        self.assertEqual([(r["id"], r["bg_id"], r["group"]) for r in rows],
                         [("r1", "aaaa1111", "today"), ("r1", "bbbb2222", "today"), ("r2", "cccc3333", "week"),
                          ("r3", None, "month"), ("r4", None, "older")])
        self.assertEqual(set(rows[0]), {"id", "kind", "name", "bg_id", "session_id", "group", "dehydrated_at",
                                        "dehydrated_ts", "description", "first_prompt", "branch", "repo", "repo_path",
                                        "cwd", "removed", "restored", "auto", "rehydrations", "running", "search"})
        self.assertEqual(out["total"], 5)
        by = {(r["id"], r["bg_id"]): r for r in rows}
        self.assertEqual(by[("r1", "bbbb2222")]["name"], "beta second")
        self.assertEqual(by[("r2", "cccc3333")]["name"], "capacity plan")  # title is the fallback
        self.assertEqual(by[("r3", None)]["name"], "wt-gamma")            # then the worktree basename
        self.assertEqual(by[("r3", None)]["repo"], "dotfiles")             # repo from the origin URL
        self.assertTrue(by[("r1", "aaaa1111")]["auto"] and by[("r1", "aaaa1111")]["removed"])
        self.assertIsNone(by[("r1", "aaaa1111")]["running"])
        hits = self.picker("dotfiles", extra=("--now", str(now), "--agents-json", self.m.agents))["rows"]
        self.assertEqual([r["id"] for r in hits], ["r3"])
        hits = self.picker("product-portfolio", extra=("--now", str(now), "--agents-json", self.m.agents))["rows"]
        self.assertEqual([r["id"] for r in hits], ["r2"])
        # list <words> searches the same haystack
        self.assertEqual([r["id"] for r in json.loads(self.m.run("list", "dotfiles", "--json").stdout)], ["r3"])

    def test_list_picker_agents_cache(self):
        m = self.m
        self.put({"id": "r1", "kind": "session", "at": self.iso(time.time()), "repo": {"path": m.repo},
                  "sessions": [{"session_id": "aaaa1111-0", "bg_id": "aaaa1111", "name": "alpha", "cwd": m.repo}]})
        slow = {"FAKE_AGENTS_SLEEP": "5"}
        out = self.picker(env=slow, extra=("--agents-timeout", "1"))
        self.assertEqual(out["agents"], "unavailable")
        self.assertIsNone(out["rows"][0]["running"])
        live = os.path.join(m.root, "live.json")
        json.dump([{"id": "aaaa1111", "sessionId": "aaaa1111-0", "pid": 4242, "name": "alpha", "cwd": m.repo}],
                  open(live, "w"))
        out = self.picker(env={"FAKE_AGENTS_JSON": live})
        self.assertEqual(out["agents"], "live")
        self.assertEqual(out["rows"][0]["running"], {"bg_id": "aaaa1111", "session_id": "aaaa1111-0", "state": None,
                                                     "live": True})
        out = self.picker(env=slow, extra=("--agents-timeout", "1"))
        self.assertEqual(out["agents"], "cached")
        self.assertEqual(out["rows"][0]["running"]["bg_id"], "aaaa1111")

    # ---- rehydrate --launch

    def session_record(self, rid, sid, bid, name):
        m = self.m
        m.session(sid, bid, m.repo, name, listed=False)
        self.put({"id": rid, "kind": "session", "at": self.iso(time.time()), "repo": {"path": m.repo},
                  "worktree": None, "linked_worktree_id": None, "removed": True,
                  "sessions": [{"session_id": sid, "bg_id": bid, "name": name, "cwd": m.repo}]})

    def test_launch_records_copy_and_dedupes(self):
        m = self.m
        sid, copy = "cdcdcdcd-0000-0000-0000-000000000001", "1be4ed48-0000-0000-0000-000000000009"
        self.session_record("r1", sid, "cdcdcdcd", "Sess one")
        write(os.path.join(m.home, "jobs", "1be4ed48", "state.json"), json.dumps({"sessionId": copy}))
        env = {"FAKE_AGENTS_JSON": m.agents, "FAKE_BG_ID": "1be4ed48"}
        out = json.loads(m.run("rehydrate", "r1", "--launch", "--json", env=env).stdout)
        l = out["launched"][0]
        self.assertEqual((l["bg_id"], l["session_id"], l["reused"], l["note"]), ("1be4ed48", copy, False, None))
        self.assertIn(f"--bg --resume {sid} -n Sess one", m.calls())
        ev = [r for r in m.records() if r.get("event") == "rehydrated"][-1]
        self.assertEqual(ev["launched"][0]["bg_id"], "1be4ed48")
        self.assertEqual(ev["launched"][0]["from_session_id"], sid)
        # the copy is live now: a second --launch reuses it and starts nothing
        json.dump([{"id": "1be4ed48", "sessionId": copy, "pid": 4242, "name": "Sess one", "cwd": m.repo,
                    "kind": "background", "state": "working"}], open(m.agents, "w"))
        out = json.loads(m.run("rehydrate", "r1", "--launch", "--json", env=env).stdout)
        self.assertEqual((out["launched"][0]["bg_id"], out["launched"][0]["reused"]), ("1be4ed48", True))
        self.assertEqual(sum("--bg" in c for c in m.calls()), 1)
        row = self.picker(env=env)["rows"][0]
        self.assertEqual(row["running"], {"bg_id": "1be4ed48", "session_id": copy, "state": "working", "live": True})
        self.assertIn("1be4ed48", row["search"])
        # same name in the same cwd also counts as running
        self.session_record("r2", "efefefef-0000-0000-0000-000000000001", "efefefef", "Named two")
        rows = json.load(open(m.agents)) + [{"id": "77777777", "sessionId": "77777777-0", "pid": 4343,
                                             "name": "Named two", "cwd": m.repo, "kind": "interactive"}]
        json.dump(rows, open(m.agents, "w"))
        out = json.loads(m.run("rehydrate", "r2", "--launch", "--json", env=env).stdout)
        self.assertEqual((out["launched"][0]["bg_id"], out["launched"][0]["reused"]), ("77777777", True))
        self.assertEqual(sum("--bg" in c for c in m.calls()), 1)

    def test_launch_fails_closed_when_agents_unreadable(self):
        m = self.m
        sid = "fafafafa-0000-0000-0000-000000000001"
        self.session_record("r1", sid, "fafafafa", "Sess three")
        r = m.run("rehydrate", "r1", "--launch", env={"FAKE_AGENTS_FAIL": "1"})
        self.assertIn("could not check claude agents; not launched", r.stdout)
        self.assertIn(f"claude --bg --resume {sid}", r.stdout)
        self.assertFalse(any("--bg" in c for c in m.calls()))
        out = json.loads(m.run("rehydrate", "r1", "--launch", "--json", env={"FAKE_AGENTS_FAIL": "1"}).stdout)
        self.assertIsNone(out["launched"][0]["bg_id"])
        # an error with --json comes back as JSON (the picker reads it)
        r = m.run("rehydrate", "nope", "--json", check=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no manifest record", json.loads(r.stdout)["error"])


class ReviewFixTests(unittest.TestCase):
    """The 0.2.0 review findings: merge evidence, picker folding and restored state, repeat and in-place rehydrate,
    launch records, auto after a rehydrate, the lock queue, config checks, one clock. One Mini fixture each."""

    def setUp(self):
        self.m = Mini()

    def tearDown(self):
        self.m.cleanup()

    rule = AutoAndPickerTests.rule
    put = AutoAndPickerTests.put
    iso = AutoAndPickerTests.iso

    def merged_session(self, name, sid, bid, how="ff", interactive=False):
        """A worktree merged into main with an ended session bound to it, auto-dehydrated -> (path, worktree id)."""
        m = self.m
        w = m.wt(name, [(f"{name}.txt", name + "\n")])
        m.merge(name, how)
        m.session(sid, bid, w, f"merged {name}", ended=time.time() - 3600)
        out = json.loads(m.run("auto", "--json").stdout)
        self.assertEqual([d["decision"] for d in out["decisions"] if d["session_id"] == sid], ["dehydrated"], out)
        rid = [r["id"] for r in m.records() if r.get("event") == "dehydrated" and r["kind"] == "worktree"
               and r["worktree"]["path"] == w][0]
        return w, rid

    def events(self, rid):
        return [r for r in self.m.records() if r.get("event") == "rehydrated" and r["id"] == rid]

    def test_merge_rule_needs_evidence_of_a_merge(self):
        m = self.m
        rev = m.wt("rev", [("r.txt", "real work\n")])
        sh(rev, "git", "revert", "--no-edit", "HEAD")
        undo = m.wt("undo", [("u.txt", "draft\n")])
        os.unlink(os.path.join(undo, "u.txt"))
        sh(undo, "git", "add", "-A")
        sh(undo, "git", "commit", "-qm", "park")
        sqe = m.wt("sqe", [("e.txt", "e\n")])
        m.merge("sqe", "squash")
        sh(sqe, "git", "commit", "-q", "--allow-empty", "-m", "notes in a message only")
        ra = m.wt("ra", [("lost.txt", "only in the reflog\n")])
        sh(ra, "git", "reset", "-q", "--hard", "origin/main")
        for path, why in ((rev, "change nothing in total"), (undo, "change nothing in total"),
                          (sqe, "a commit with no changes"), (ra, "no commits of its own")):
            got = self.rule(path)
            self.assertFalse(got["merged"], (path, got))
            self.assertIn(why, got["reason"], path)
        # the gh check names origin's repo (-R), the remote the git checks fetched
        d = load_module()
        sh(m.repo, "git", "remote", "set-url", "origin", "git@github.com:getfatday/app.git")
        log = os.path.join(m.root, "gh.log")
        with mock_env(FAKE_GH_LOG=log):
            d.gh_merged_pr(rev, "wt-rev", "main", "0" * 40, FAKE_GH)
        self.assertIn("pr list -R github.com/getfatday/app --head wt-rev", open(log).read())
        self.assertEqual(d.gh_repo_arg("https://github.expedia.biz/eg/x.git"), "github.expedia.biz/eg/x")

    def test_picker_folds_linked_worktree_restored_and_capped(self):
        m = self.m
        now = time.time()
        live_dir = os.path.join(m.root, "restored-here")
        os.makedirs(live_dir)
        long_prompt = "q" * 1500
        self.put(
            {"id": "w1", "kind": "worktree", "at": self.iso(now - 60), "repo": {"path": m.repo},
             "worktree": {"path": live_dir, "branch": "wt-a"}, "removed": True,
             "sessions": [{"session_id": "s1-0", "bg_id": "s1s1s1s1", "name": "alpha"},
                          {"session_id": "s9-0", "name": "terminal only", "first_prompt": long_prompt}]},
            {"id": "s1", "kind": "session", "at": self.iso(now - 60), "repo": {"path": m.repo},
             "worktree": {"path": live_dir, "branch": "wt-a"}, "linked_worktree_id": "w1", "removed": True,
             "sessions": [{"session_id": "s1-0", "bg_id": "s1s1s1s1", "name": "alpha"}]},
            {"id": "w2", "kind": "worktree", "at": self.iso(now - 120), "repo": {"path": m.repo},
             "worktree": {"path": "/x/gone", "branch": "wt-b"}, "removed": True,
             "sessions": [{"session_id": "s2-0", "bg_id": "s2s2s2s2", "name": "beta"}]},
            {"id": "s2", "kind": "session", "at": self.iso(now - 120), "repo": {"path": m.repo},
             "worktree": {"path": "/x/gone", "branch": "wt-b"}, "linked_worktree_id": "w2", "removed": False,
             "sessions": [{"session_id": "s2-0", "bg_id": "s2s2s2s2", "name": "beta"}]})
        with open(os.path.join(m.state, "manifest.jsonl"), "a") as f:
            f.write(json.dumps({"event": "rehydrated", "id": "w1", "at": self.iso(now), "path": live_dir}) + "\n")
        out = self.picker_rows()
        got = [(r["id"], r["bg_id"]) for r in out["rows"]]
        # w1's alpha row folds into s1; its terminal-only session has no session record and stays; w2 stays
        # beside s2 because `claude rm` refused s2 (removed false)
        self.assertEqual(sorted(got), sorted([("s1", "s1s1s1s1"), ("w1", "s9-0"[:8]), ("w2", "s2s2s2s2"),
                                              ("s2", "s2s2s2s2")]))
        by = {(r["id"], r["bg_id"]): r for r in out["rows"]}
        self.assertTrue(by[("s1", "s1s1s1s1")]["restored"])
        self.assertTrue(by[("w1", "s9-0")]["restored"])
        self.assertFalse(by[("w2", "s2s2s2s2")]["restored"])
        self.assertEqual(out["total"], 4)
        self.assertNotIn("qqqq", by[("s1", "s1s1s1s1")]["search"])  # another session's prompt is not copied in
        self.assertLessEqual(len(by[("w1", "s9-0")]["search"]), 2048)
        self.assertEqual(self.picker_rows(extra=("--limit", "1"))["total"], 4)
        # text list: names and short ids; exact agents name is a key; empty store text
        txt = m.run("list").stdout
        self.assertIn("alpha (s1s1s1s1)", txt)
        self.assertEqual(json.loads(m.run("show", "beta").stdout)["id"], "s2")  # the session record wins
        os.unlink(os.path.join(m.state, "manifest.jsonl"))
        self.assertEqual(m.run("list").stdout.strip(), "Nothing has been dehydrated yet. /dehydrate closes idle sessions.")
        self.assertEqual(m.run("list", "zzz").stdout.strip(), "Nothing has been dehydrated yet. /dehydrate closes idle sessions.")

    def picker_rows(self, extra=()):
        return json.loads(self.m.run("list", "--picker", "--agents-json", self.m.agents, *extra).stdout)

    def test_rehydrate_repeat_in_place_and_corrupt_transcript(self):
        m = self.m
        sid = "d1d1d1d1-0000-0000-0000-000000000001"
        w, rid = self.merged_session("rep", sid, "d1d1d1d1")
        json.dump([], open(m.agents, "w"))  # `claude rm` dropped its row
        m.run("rehydrate", rid)
        self.assertTrue(os.path.isdir(w))
        self.assertEqual(len(self.events(rid)), 1)
        write(os.path.join(w, "edit.txt"), "made after the restore\n")
        r = m.run("rehydrate", rid)
        self.assertIn(f"already restored at {w}, nothing changed", r.stdout)
        self.assertEqual(len(self.events(rid)), 1)  # a no-op is not another rehydration
        self.assertTrue(os.path.isfile(os.path.join(w, "edit.txt")))
        row = [x for x in self.picker_rows()["rows"] if x["cwd"] == w]
        self.assertEqual(len(row), 1, row)  # the worktree folds into its session's row
        self.assertEqual((row[0]["kind"], row[0]["restored"], row[0]["rehydrations"]), ("session", True, 1))
        # Enter on the restored row: launch only, recorded as in place
        out = json.loads(m.run("rehydrate", rid, "--launch", "--json", env={"FAKE_AGENTS_JSON": m.agents}).stdout)
        self.assertEqual(out["launched"][0]["bg_id"], "1be4ed48")
        self.assertIn("already restored", out["notes"][0])
        self.assertTrue(self.events(rid)[-1]["in_place"])
        row = [x for x in self.picker_rows()["rows"] if x["cwd"] == w][0]
        self.assertEqual(row["rehydrations"], 1)
        # transcript swept and its archived copy corrupt: the worktree still comes back, the event is recorded,
        # the session is not launched, and the reason is in the JSON
        rec = [x for x in m.records() if x.get("event") == "dehydrated" and x["id"] == rid][0]
        for dp, _, fs in os.walk(os.path.join(m.home, "projects")):
            for f in fs:
                if sid in f:
                    os.unlink(os.path.join(dp, f))
        import gzip
        with gzip.open(rec["sessions"][0]["transcript_copy"], "wb") as g:
            g.write(b"corrupted\n")
        sh(m.repo, "git", "worktree", "remove", "--force", w)
        n = len(self.events(rid))
        r = m.run("rehydrate", rid, "--launch", "--json", env={"FAKE_AGENTS_JSON": m.agents})
        out = json.loads(r.stdout)
        self.assertTrue(os.path.isdir(w))
        self.assertTrue(any("fails its checksum" in x for x in out["notes"]), out)
        self.assertEqual([(l["skipped"], l["bg_id"]) for l in out["launched"]], [(True, None)])
        self.assertEqual(len(self.events(rid)), n + 1)
        self.assertNotIn("in_place", self.events(rid)[-1])

    def test_launch_without_an_id_is_recorded_and_not_repeated(self):
        m = self.m
        sid = "e1e1e1e1-0000-0000-0000-000000000001"
        m.session(sid, "e1e1e1e1", m.repo, "Quiet one", listed=False)
        self.put({"id": "r1", "kind": "session", "at": self.iso(time.time()), "repo": {"path": m.repo},
                  "worktree": None, "linked_worktree_id": None, "removed": True,
                  "sessions": [{"session_id": sid, "bg_id": "e1e1e1e1", "name": "Quiet one", "cwd": m.repo}]})
        silent = os.path.join(m.root, "silent-claude")
        write(silent, f"#!/bin/sh\necho \"$*\" >> {m.log}\ncase \"$1\" in agents) echo '[]';; esac\nexit 0\n")
        os.chmod(silent, 0o755)

        def launch(env=None):
            cmd = [sys.executable, SCRIPT, "rehydrate", "r1", "--launch", "--json", "--claude-home", m.home,
                   "--claude-bin", silent, "--state-dir", m.state]
            return json.loads(subprocess.run(cmd, capture_output=True, text=True, env=dict(m.env, **(env or {})),
                                             cwd=m.root).stdout)["launched"][0]
        first = launch()
        self.assertTrue(first["unconfirmed"])
        self.assertNotIn(": .", first["note"])
        second = launch()
        self.assertTrue(second["skipped"])
        self.assertIn("reported no id", second["note"])
        self.assertEqual(sum("--bg" in c for c in m.calls()), 1)
        launch(env={"DEHYDRATE_UNCONFIRMED_WINDOW_S": "0"})  # past the window it tries again
        self.assertEqual(sum("--bg" in c for c in m.calls()), 2)

    def test_match_running_counts_listed_and_stateful_rows(self):
        d = load_module()
        done = {"id": "aa", "sessionId": "aa-0", "state": "done", "name": "n", "cwd": "/tmp"}
        working = {"id": "bb", "sessionId": "bb-0", "state": "working", "name": "w", "cwd": "/tmp"}
        self.assertIs(d.match_running([done], "aa-0", "x", "/nowhere"), done)  # listed at all: still open
        self.assertFalse(d.running_ref(done)["live"])
        self.assertIs(d.match_running([working], "zz", "w", "/tmp"), working)  # no pid, but working
        self.assertIsNone(d.match_running([done], "zz", "n", "/tmp"))  # a done stranger of the same name
        self.assertIs(d.match_running([done], "zz", "x", "/x", extra_ids={"aa"}), done)

    def test_auto_leaves_a_rehydrated_session_until_it_runs_again(self):
        m = self.m
        sid = "f2f2f2f2-0000-0000-0000-000000000001"
        w, rid = self.merged_session("back", sid, "f2f2f2f2", how="squash")
        m.run("rehydrate", rid)  # the agents row is still listed, done
        out = json.loads(m.run("auto", "--dry-run", "--json").stdout)
        d = [x for x in out["decisions"] if x["session_id"] == sid][0]
        self.assertEqual(d["decision"], "refused")
        self.assertIn("not used since", d["reason"])
        tp = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(m.home, "projects")) for f in fs if sid in f][0]
        later = time.time() + 120
        os.utime(tp, (later, later))  # it ran (its transcript moved on) and ended
        out = json.loads(m.run("auto", "--dry-run", "--json", "--now", str(later + 900)).stdout)
        self.assertEqual([x["decision"] for x in out["decisions"] if x["session_id"] == sid], ["dehydrate"])

    def test_auto_kick_defers_on_a_held_lock_and_the_next_run_drains_it(self):
        import fcntl
        m = self.m
        w = m.wt("lk", [("l.txt", "l\n")])
        m.merge("lk")
        sid = "a3a3a3a3-0000-0000-0000-000000000001"
        m.session(sid, None, w, "", kind="interactive", ended=time.time(), listed=False)
        env = {"DEHYDRATE_AUTO_WAIT_S": "1", "DEHYDRATE_AUTO_LOCK_WAIT_S": "1"}
        for lock in (".auto.lock", ".lock"):
            held = open(os.path.join(m.state, lock), "w")
            fcntl.flock(held, fcntl.LOCK_EX)
            out = json.loads(m.run("auto", "--session", sid, "--json", env=env).stdout)
            held.close()
            self.assertEqual([x["decision"] for x in out["decisions"]], ["deferred"], (lock, out))
            self.assertTrue(os.path.isdir(w))
            self.assertEqual(os.listdir(os.path.join(m.state, "auto-pending")), [sid + ".json"])
            self.assertEqual(m.auto_log()[-1]["decision"], "deferred")
            if lock == ".auto.lock":
                os.unlink(os.path.join(m.state, "auto-pending", sid + ".json"))
        out = json.loads(m.run("auto", "--json").stdout)  # a sweep (SessionStart) drains the queue
        self.assertEqual([(x["decision"], x["trigger"]) for x in out["decisions"]],
                         [("dehydrated", "session.end (deferred)")])
        self.assertFalse(os.path.exists(w))
        self.assertEqual(os.listdir(os.path.join(m.state, "auto-pending")), [])

    def test_config_types_unknown_keys_cli_and_status(self):
        m = self.m
        d = load_module()
        w = m.wt("cf", [("c.txt", "c\n")])
        m.merge("cf")
        m.session("b4b4b4b4-0000-0000-0000-000000000001", "b4b4b4b4", w, "configured")
        m.config({"auto_on_close": "false", "auto_on_clsoe": False, "auto_apply": "true"})
        cfg = d.load_config(m.state)
        self.assertIn("auto_on_close must be true or false", cfg["_config_error"])
        self.assertIs(cfg["auto_apply"], False)  # a string never turns a switch on
        self.assertEqual(cfg["_config_unknown"], ["auto_on_clsoe"])
        r = m.run("auto", "--dry-run")
        self.assertIn("auto: nothing ran (config error", r.stdout)
        self.assertIn("auto_on_clsoe", r.stdout)
        self.assertIn("auto-dehydrate on close: off (config error)", m.run("auto", "--status").stdout)
        self.assertNotEqual(m.run("config", "set", "auto_on_close", '"false"', check=False).returncode, 0)
        self.assertNotEqual(m.run("config", "set", "auto_on_clsoe", "false", check=False).returncode, 0)
        m.config({"days": 3})
        m.run("config", "set", "auto_on_close", "false")
        self.assertEqual(json.load(open(os.path.join(m.state, "config.json"))),
                         {"days": 3, "auto_on_close": False, "disk_floor_gb": 0, "auto_fetch_timeout_s": SLOW_FETCH_S})
        self.assertIn("auto_on_close is off", m.run("auto").stdout)
        self.assertTrue(m.run("auto", "--status").stdout.startswith("auto-dehydrate on close: off (auto_on_close is false)"))
        write(os.path.join(m.state, "config.json"), "not json")
        r = m.run("config", "set", "auto_on_close", "true", check=False)
        self.assertIn("is not valid JSON", r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        # the nudge says once that auto is on, with the off switch (it honours $DEHYDRATE_HOME via --state-dir)
        os.unlink(os.path.join(m.state, "config.json"))
        write(os.path.join(m.state, "last-plan.json"), json.dumps({"totals": {
            "sessions_close": 0, "worktrees_dehydrate": 0, "orphans_archive": 0, "reclaim_kb": 0}}))
        first, second = m.run("nudge").stdout, m.run("nudge").stdout
        self.assertIn("auto-dehydrate on close is on", first)
        self.assertIn("config set auto_on_close false", first)
        self.assertEqual(second, "")
        h = " ".join(m.run("auto", "--help").stdout.split())
        self.assertIn("merged into origin's default branch", h)
        self.assertNotIn("--days", h)

    def test_record_id_and_at_share_a_clock(self):
        m = self.m
        w = m.wt("clk", [("k.txt", "k\n")])
        m.merge("clk")
        m.session("c5c5c5c5-0000-0000-0000-000000000001", "c5c5c5c5", w, "clocked")
        later = time.time() + 40 * 86400
        m.run("auto", "--json", "--now", str(later))
        rec = [r for r in m.records() if r.get("event") == "dehydrated" and r["kind"] == "worktree"][0]
        import datetime as dt
        day = dt.datetime.fromtimestamp(later, dt.timezone.utc).strftime("%Y%m%d")
        self.assertTrue(rec["id"].startswith(day), rec["id"])
        self.assertEqual(rec["at"][:10].replace("-", ""), day)


@contextlib.contextmanager
def mock_env(**kw):
    old = {k: os.environ.get(k) for k in kw}
    os.environ.update(kw)
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class WorktreePathTests(unittest.TestCase):
    def test_worktree_path_from_state_json(self):
        """agents rows carry no worktreePath on 2.1.312; the job's state.json does, and the guard must see it."""
        f = Fixture()
        try:
            sid = f.sessions["main"][0]
            write(os.path.join(f.home, "jobs", "b0000003", "state.json"),
                  json.dumps({"state": "blocked", "worktreePath": f.wt["locked"], "intent": "the old question"}))
            r = f.run("apply", "--yes", "--only", sid, check=False)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("Claude-managed worktree", r.stdout)
            calls = open(f.calls).read().splitlines() if os.path.exists(f.calls) else []
            self.assertNotIn("rm b0000003", calls)
            self.assertTrue(os.path.isdir(f.wt["locked"]))
        finally:
            f.cleanup()


if __name__ == "__main__":
    unittest.main()


# ---- 0.2.1: job-dir holds, re-checks between items, big-tree timeouts (bugs found 2026-10-29)

class SafetyFixTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.mod = load_module()

    def tearDown(self):
        self.f.cleanup()

    def actions(self, plan):
        return {w["path"]: (w["action"], w["reason"]) for w in plan["worktrees"]}

    def add_wt(self, path, branch):
        sh(self.f.repo, "git", "worktree", "add", "-q", "-b", branch, path)
        return os.path.realpath(path)

    def add_agent(self, bid, state, name, ended_days_before_now):
        """A background session whose job dir was last written ended_days_before_now before NOW."""
        f = self.f
        agents = json.load(open(f.agents))
        agents.append({"id": bid, "sessionId": f"aaaaaaaa-0000-0000-0000-0000{bid}", "name": name, "cwd": f.repo,
                       "kind": "background", "state": state, "startedAt": int((time.time() - 40 * 86400) * 1000)})
        json.dump(agents, open(f.agents, "w"))
        st = os.path.join(f.home, "jobs", bid, "state.json")
        write(st, json.dumps({"state": state}))
        t = NOW - ended_days_before_now * 86400  # against the fixed NOW, however long the suite runs
        os.utime(st, (t, t))

    def in_process(self, argv, **patches):
        import io
        from contextlib import redirect_stdout
        from unittest import mock
        buf = io.StringIO()
        with contextlib.ExitStack() as st:
            st.enter_context(mock.patch.dict(os.environ, ENV, clear=True))
            for k, v in patches.items():
                st.enter_context(mock.patch.object(self.mod, k, v))
            st.enter_context(redirect_stdout(buf))
            rc = self.mod.main(argv)
        return rc, buf.getvalue()

    def apply_argv(self, *extra):
        f = self.f
        return ["apply", "--yes", "--json", *extra, "--roots", f.src, "--agents-json", f.agents, "--now", str(NOW),
                "--claude-home", f.home, "--claude-bin", f.claude, "--state-dir", f.state]

    def test_job_dir_worktrees_are_held_for_live_sessions(self):
        f = self.f
        jobs = os.path.join(f.home, "jobs")
        live = self.add_wt(os.path.join(jobs, "b0000002", "tmp", "typed", "verify-pp"), "verify-pp")  # working
        done = self.add_wt(os.path.join(jobs, "b0000001", "tmp", "x", "worktree"), "job-done")       # done 30d
        gone = self.add_wt(os.path.join(jobs, "zzzzzzzz", "tmp", "worktree"), "job-gone")            # not listed
        self.add_agent("b0000009", "done", "Just finished", 0.001)                                    # ~1.5 min
        grace = self.add_wt(os.path.join(jobs, "b0000009", "tmp", "worktree"), "job-grace")
        for extra in ((), ("--no-sessions",)):
            a = self.actions(f.plan(*extra))
            self.assertEqual(a[live], ("hold", "inside the job dir of working session b0000002 Busy work"), extra)
            self.assertEqual(a[done][0], "dehydrate", extra)
            self.assertEqual(a[gone][0], "dehydrate", extra)
            self.assertEqual(a[grace][0], "hold", extra)
            self.assertIn("inside the job dir of done session b0000009 Just finished (ended", a[grace][1])
        r = f.run("plan", "--json", "--pressure", "--target-gb", "10", check=False)
        self.assertEqual(self.actions(json.loads(r.stdout))[live][0], "hold")
        open(f.agents, "w").write("not json")                    # unreadable roster: every job-dir tree is held
        a = self.actions(f.plan("--no-sessions"))
        self.assertEqual(a[done][0], "hold")
        self.assertIn("agents list unavailable", a[done][1])
        self.assertEqual(a[f.wt["clean"]][0], "dehydrate")       # trees outside the job dirs are not affected

    def test_pressure_holds_a_tree_touched_in_the_last_two_hours(self):
        f = self.f
        write(os.path.join(f.wt["clean"], "fresh.txt"), "just written\n")
        # relative to the fixed NOW, not the wall clock: a slow suite must not move these past NOW
        os.utime(os.path.join(f.wt["clean"], "fresh.txt"), (NOW - 900, NOW - 900))  # a file changed 15 min ago
        logs = os.path.join(f.repo, ".git", "worktrees", "unpushed", "logs", "HEAD")
        os.utime(logs, (NOW - 3600, NOW - 3600))                                     # HEAD moved an hour ago
        r = f.run("plan", "--json", "--pressure", "--target-gb", "10", check=False)
        a = self.actions(json.loads(r.stdout))
        for name in ("clean", "unpushed"):
            self.assertEqual(a[f.wt[name]][0], "hold", name)
            self.assertIn("pressure: touched", a[f.wt[name]][1])
        self.assertEqual(a[f.wt["recent"]][0], "dehydrate")                        # a day ago: still a candidate

    def test_initializing_lock_reads_as_an_interrupted_checkout(self):
        f = self.f
        p = f.wt["clean"]
        sh(f.repo, "git", "worktree", "lock", "--reason", "initializing", p)
        a = self.actions(f.plan())
        self.assertEqual(a[p], ("hold", "interrupted checkout (git lock 'initializing' left by a killed worktree "
                                        f"add); unlock with: git worktree unlock {p}"))
        self.assertEqual(a[f.wt["locked"]], ("hold", "locked (held by test)"))

    def test_config_and_holds_are_read_again_between_items(self):
        """Exclusions written while apply runs (and a lock taken) stop the items they match (2026-10-29 15:18)."""
        f = self.f
        seen = []
        cfg_path = os.path.join(f.state, "config.json")

        def hook(event, item):
            if event != "item":
                return
            seen.append(item["path"])
            if len(seen) == 2:                                    # after the first item, before the second
                c = json.load(open(cfg_path))
                c["exclude_globs"] = [item["path"]]
                json.dump(c, open(cfg_path, "w"))
            if len(seen) == 3:
                sh(f.repo, "git", "worktree", "lock", "--reason", "owner is back", item["path"])
        rc, out = self.in_process(self.apply_argv("--no-sessions"), test_hook=hook)
        res = json.loads(out)
        self.assertEqual(rc, 0, out)                              # a skip is not a failure
        by = {w["path"]: w for w in res["worktrees"]}
        first, second, third = seen[:3]
        self.assertTrue(by[first]["removed"])
        self.assertTrue(by[second]["skipped"])
        self.assertIn(f"excluded by {second} (config.json re-read before capture)", by[second]["error"])
        self.assertTrue(os.path.isdir(second))
        self.assertTrue(by[third]["skipped"])
        self.assertIn("locked (owner is back)", by[third]["error"])
        self.assertTrue(os.path.isdir(third))
        ids = {r["worktree"]["path"] for r in f.manifest()}
        self.assertNotIn(second, ids)                             # nothing was captured for a skipped item
        self.assertNotIn(third, ids)

    def test_exclusion_written_during_capture_stops_the_removal(self):
        f = self.f
        cfg_path = os.path.join(f.state, "config.json")
        hit = []

        def hook(event, item):
            if event == "captured" and not hit:
                hit.append(item["path"])
                c = json.load(open(cfg_path))
                c["exclude_globs"] = [item["path"]]
                json.dump(c, open(cfg_path, "w"))
        rc, out = self.in_process(self.apply_argv("--no-sessions"), test_hook=hook)
        res = json.loads(out)
        w = next(x for x in res["worktrees"] if x["path"] == hit[0])
        self.assertTrue(w["skipped"] and not w["removed"])
        self.assertIn("captured as", w["error"])
        self.assertIn("before removal", w["error"])
        self.assertTrue(os.path.isdir(hit[0]))
        evs = [json.loads(x) for x in open(os.path.join(f.state, "manifest.jsonl"))]
        self.assertTrue(any(e.get("event") == "left-in-place" and e["id"] == w["id"] for e in evs))
        self.assertFalse(any(e.get("event") == "removed" and e["id"] == w["id"] for e in evs))
        self.assertTrue(any(x.get("removed") for x in res["worktrees"]))   # the other items went on

    def test_rehydrate_timeout_removes_the_partial_checkout(self):
        f = self.f
        f.run("apply", "--yes", "--no-sessions", "--only", "clean")
        rec = next(r for r in f.manifest() if r["worktree"]["path"] == f.wt["clean"])
        real_git = self.mod.git
        calls = []

        def killed_add(cwd, *a, **k):
            calls.append((a[:2], k.get("timeout")))
            if a[:2] == ("worktree", "add"):
                real_git(cwd, *a, **k)                            # what a killed add leaves: a registered tree...
                real_git(cwd, "worktree", "lock", "--reason", "initializing", a[-2] if a[-1] == "wt-clean" else a[-1])
                raise subprocess.TimeoutExpired(["git", "-C", cwd, *a], k.get("timeout"))   # ...locked "initializing"
            return real_git(cwd, *a, **k)
        argv = ["rehydrate", rec["id"], "--state-dir", f.state, "--claude-home", f.home, "--claude-bin", f.claude]
        with self.assertRaises(SystemExit) as cm:
            self.in_process(argv, git=killed_add)
        msg = str(cm.exception.code)
        self.assertIn("git worktree add timed out after 3600s", msg)
        self.assertIn("Nothing is marked rehydrated", msg)
        self.assertIn(f"rehydrate {rec['id']}", msg)
        self.assertFalse(os.path.lexists(f.wt["clean"]))
        self.assertNotIn(f.wt["clean"], sh(f.repo, "git", "worktree", "list"))
        evs = [json.loads(x) for x in open(os.path.join(f.state, "manifest.jsonl"))]
        self.assertFalse(any(e.get("event") == "rehydrated" and e["id"] == rec["id"] for e in evs))
        # the retry works, and every whole-tree git call gets the long timeout
        calls.clear()

        def counting(cwd, *a, **k):
            calls.append((a[:2], k.get("timeout")))
            return real_git(cwd, *a, **k)
        rc, _ = self.in_process(argv, git=counting)
        self.assertFalse(rc)
        self.assertTrue(os.path.isdir(f.wt["clean"]))
        big = {c: t for c, t in calls if c in (("worktree", "add"), ("checkout", rec["snapshot"]["commit"]))
               or c[0] == "read-tree"}
        self.assertIn(("worktree", "add"), big)
        self.assertTrue(all(t == 3600 for t in big.values()), big)


class AgentsTimeoutTests(unittest.TestCase):
    """0.2.2: a slow `claude agents` is retried once, then treated as unavailable: plan and apply do not crash,
    no session closes, and every session-bound or job-dir worktree is held."""

    def setUp(self):
        self.f = Fixture()

    def tearDown(self):
        self.f.cleanup()

    def run_slow(self, *a):
        f = self.f
        log = os.path.join(f.root, "agents-calls.log")
        env = dict(ENV, FAKE_AGENTS_SLEEP="30", FAKE_CLAUDE_LOG=log, DEHYDRATE_AGENTS_TIMEOUT_S="3")
        cmd = [sys.executable, SCRIPT, *a, "--roots", f.src, "--now", str(NOW), "--claude-home", f.home,
               "--claude-bin", FAKE_CLAUDE, "--state-dir", f.state]
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=f.root)
        calls = [x for x in open(log).read().splitlines()] if os.path.exists(log) else []
        return r, calls

    def test_plan_and_apply_hold_instead_of_crashing(self):
        f = self.f
        job = os.path.join(f.home, "jobs", "b0000001", "tmp", "wt")
        sh(f.repo, "git", "worktree", "add", "-q", "-b", "job-wt", job)
        job = os.path.realpath(job)
        r, calls = self.run_slow("plan", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([c for c in calls if c.startswith("agents")], ["agents --json --all"] * 2)   # one retry
        p = json.loads(r.stdout)
        self.assertIn("agents list unavailable", p["agents_unavailable"])
        self.assertEqual(p["sessions"], [])
        a = {w["path"]: (w["action"], w["reason"]) for w in p["worktrees"]}
        self.assertEqual(a[f.wt["dirty"]][0], "hold")                          # its transcript's cwd is inside
        self.assertTrue(a[f.wt["dirty"]][1].startswith("agents list unavailable: bound to session"))
        self.assertEqual(a[job][0], "hold")
        self.assertTrue(a[job][1].startswith("agents list unavailable: inside the job dir"))
        self.assertEqual(a[f.wt["clean"]][0], "dehydrate")                     # no session, not a job dir
        r, calls = self.run_slow("apply", "--yes", "--json")
        self.assertIn(r.returncode, (0, 1), r.stdout + r.stderr)
        res = json.loads(r.stdout)
        self.assertEqual(res["sessions"], [])
        self.assertTrue(os.path.isdir(f.wt["dirty"]) and os.path.isdir(job))
        self.assertFalse(os.path.isdir(f.wt["clean"]))                          # unbound work still goes
        self.assertFalse(any(c.startswith(("stop", "rm")) for c in calls))


class SparseCheckoutTests(unittest.TestCase):
    """0.2.2: a sparse-checkout worktree is captured with its skip-worktree files intact (never as deletions),
    its sparse config is recorded, and rehydrate brings the same sparse tree back."""

    def setUp(self):
        self.f = Fixture()

    def tearDown(self):
        self.f.cleanup()

    def test_sparse_worktree_round_trip(self):
        f = self.f
        p = os.path.realpath(os.path.join(f.repo, ".claude", "worktrees")) + "/sparse"
        sh(f.repo, "git", "worktree", "add", "-q", "-b", "wt-sparse", p)
        write(os.path.join(p, "keep", "k.txt"), "k1\n")
        write(os.path.join(p, "skip", "s.txt"), "outside the cone\n")
        sh(p, "git", "add", "-A")
        sh(p, "git", "commit", "-qm", "two dirs")
        sh(p, "git", "sparse-checkout", "set", "--cone", "keep")
        self.assertFalse(os.path.exists(os.path.join(p, "skip")))
        write(os.path.join(p, "keep", "k.txt"), "k2 modified\n")
        write(os.path.join(p, "keep", "st.txt"), "staged\n")
        sh(p, "git", "add", "keep/st.txt")
        write(os.path.join(p, "keep", "u.txt"), "untracked\n")
        before = status_set(p)
        r = f.run("apply", "--yes", "--json", "--no-sessions", "--only", "sparse", check=False)
        res = json.loads(r.stdout)
        self.assertTrue(res["worktrees"] and res["worktrees"][0].get("removed"), res)
        self.assertFalse(os.path.exists(p))
        rec = next(x for x in f.manifest() if x["worktree"]["path"] == p)
        self.assertEqual(rec["worktree"]["sparse"], {"cone": True, "patterns": ["keep"]})
        files = sh(f.repo, "git", "ls-tree", "-r", "--name-only", rec["snapshot"]["commit"]).split("\n")
        self.assertIn("skip/s.txt", files)                          # kept, not recorded as deleted
        self.assertIn("keep/u.txt", files)
        r = f.run("rehydrate", rec["id"], "--json")
        notes = json.loads(r.stdout)["notes"]
        self.assertFalse([n for n in notes if "WARNING" in n], notes)
        self.assertTrue(any("restored sparse-checkout" in n for n in notes), notes)
        self.assertFalse(os.path.exists(os.path.join(p, "skip")))   # still outside the cone
        self.assertIn("S skip/s.txt", sh(p, "git", "ls-files", "-t").split("\n"))
        self.assertEqual(sh(p, "git", "sparse-checkout", "list"), "keep")
        self.assertEqual(status_set(p), before)
        self.assertEqual(open(os.path.join(p, "keep", "k.txt")).read(), "k2 modified\n")
