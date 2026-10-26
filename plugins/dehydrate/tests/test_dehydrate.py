"""End-to-end tests for dehydrate.py on throwaway repos. Stdlib only: python3 -m unittest discover tests

Every test builds its own fixture under a temp dir: a bare origin, a clone with linked worktrees in
known states, a fake ~/.claude (transcripts, jobs), a fake `claude` binary that logs its calls, and a
fixed --now 30 days in the future so "stale" never depends on the wall clock.
"""
import gzip
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
for k in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_JOB_DIR", "DEHYDRATE_HOME", "CLAUDE_CONFIG_DIR"):
    ENV.pop(k, None)


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
        # rehydrating onto an existing path refuses
        r = f.run("rehydrate", rec["id"], check=False)
        self.assertNotEqual(r.returncode, 0)

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


if __name__ == "__main__":
    unittest.main()
