"""Tests for the auto classes, the auto:<class> gate and automatic mode. Stdlib only:
python3 -m unittest discover -s tests

Every test builds a throwaway HOME (jobs, CLI versions, a spool, a fake installed dehydrate), puts fake
`claude`, `lsof` and `ps` first on PATH, and fakes free disk with DISK_RECLAIM_FAKE_FREE_GB, so nothing
here reads or changes the real machine.
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
SCRIPTS = os.path.join(HERE, "..", "scripts")
OLD = time.time() - 3 * 86400
MB = 1024 * 1024


def write(path, data=b"", mtime=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    if mtime:
        os.utime(path, (mtime, mtime))


def age_tree(root, mtime=OLD):
    for dp, dns, fns in os.walk(root, topdown=False):
        for n in fns + dns:
            os.utime(os.path.join(dp, n), (mtime, mtime))
    os.utime(root, (mtime, mtime))


def script(path, body):
    write(path, body.encode())
    os.chmod(path, 0o755)


class Fixture:
    def __init__(self):
        # not under the system temp dir: it resolves to /private/var, which the executor refuses on principle
        self.root = os.path.realpath(tempfile.mkdtemp(prefix=".disk-reclaim-test-", dir=HERE))
        self.home = os.path.join(self.root, "home")
        self.state = os.path.join(self.home, ".claude", "disk-reclaim")
        self.bin = os.path.join(self.root, "bin")
        os.makedirs(self.state)
        jobs = os.path.join(self.home, ".claude", "jobs")
        self.jobs = {}
        for jid, size, recent in (("j-idle", 20, False), ("j-gone", 30, False), ("j-busy", 25, False),
                                  ("j-recent", 25, True), ("j-open", 25, False), ("j-small", 1, False)):
            write(os.path.join(jobs, jid, "state.json"), b"{}")
            tmp = os.path.join(jobs, jid, "tmp")
            write(os.path.join(tmp, "sub", "blob.bin"), b"x" * size * MB)
            age_tree(tmp)
            if recent:
                write(os.path.join(tmp, "fresh.txt"), b"now")
            self.jobs[jid] = os.path.realpath(tmp)
        self.agents = [{"id": "j-idle", "state": "done"}, {"id": "j-busy", "state": "working"},
                       {"id": "j-recent", "state": "idle"}, {"id": "j-open", "state": "done"},
                       {"id": "j-small", "state": "done"}]
        self.agents_file = os.path.join(self.root, "agents.json")
        self.set_agents(self.agents)
        vd = os.path.join(self.home, ".local", "share", "claude", "versions")
        self.versions = {}
        for v in ("1.0.0", "1.0.1", "1.0.2", "1.0.3"):
            write(os.path.join(vd, v), b"b" * 2 * MB, OLD)
            self.versions[v] = os.path.realpath(os.path.join(vd, v))
        os.makedirs(os.path.join(self.home, ".local", "bin"))
        os.symlink(os.path.join(vd, "1.0.2"), os.path.join(self.home, ".local", "bin", "claude"))
        self.spool = os.path.join(self.home, ".claude", "observatory", "spool.jsonl")
        write(self.spool, b"".join(json.dumps({"i": i, "pad": "p" * 80}).encode() + b"\n" for i in range(30000)))
        with open(os.path.join(self.state, "spool-threshold-gb"), "w") as f:
            f.write("0.001")
        base = os.path.join(self.home, ".claude", "plugins", "cache", "getfatday-skills", "dehydrate")
        self.dehydrate_log = os.path.join(self.root, "dehydrate-calls.log")
        for v in ("0.2.0", "0.2.9", "0.2.10"):
            script(os.path.join(base, v, "scripts", "dehydrate.py"), f"""#!/usr/bin/env python3
import json, sys
open({self.dehydrate_log!r}, "a").write("{v} " + " ".join(sys.argv[1:]) + "\\n")
if sys.argv[1] == "plan":  # read-only: what the dry run lists
    print(json.dumps({{"pressure": {{"order": ["/x/wt", "/x/wt2", "/x/wt3"], "estimated_stop_after": 2}}}}))
    sys.exit(0)
print(json.dumps({{"worktrees": [{{"path": "/x/wt", "ok": True, "removed": True}}], "sessions": [],
                  "paused": None, "pressure": {{"target_gb": 20, "reached": True, "free_checked_gb": 21}}}}))
""")
        self.dehydrate_dir = os.path.realpath(os.path.join(base, "0.2.10"))
        self.lsof_open = os.path.join(self.root, "lsof-open.txt")
        write(self.lsof_open, (self.jobs["j-open"] + "\n" + self.versions["1.0.0"] + "\n").encode())
        self.ps_out = os.path.join(self.root, "ps.txt")
        write(self.ps_out, b"/usr/sbin/syslogd\nclaude bg-pty-host -- /h/.local/share/claude/versions/1.0.0 --x\n")
        script(os.path.join(self.bin, "claude"), f"""#!/bin/sh
[ -f {self.root}/claude-fails ] && exit 1
cat {self.agents_file}
""")
        script(os.path.join(self.bin, "lsof"), f"""#!/bin/sh
for a in "$@"; do
  if grep -qxF -- "$a" {self.lsof_open}; then echo "proc 123 u REG $a"; exit 0; fi
done
exit 1
""")
        script(os.path.join(self.bin, "ps"), f"#!/bin/sh\ncat {self.ps_out}\n")
        self.env = dict(os.environ, HOME=self.home, PATH=self.bin + ":" + os.environ["PATH"],
                        DISK_RECLAIM_DIR=self.state, DISK_RECLAIM_FAKE_FREE_GB="1")
        for k in ("CLAUDE_JOB_DIR", "CLAUDE_SESSION_ID"):
            self.env.pop(k, None)

    def set_agents(self, agents):
        with open(self.agents_file, "w") as f:
            json.dump(agents, f)

    def py(self, name, *a, free=None, check=True):
        env = dict(self.env, DISK_RECLAIM_FAKE_FREE_GB=free) if free else self.env
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, name), *a], capture_output=True, text=True,
                           env=env, cwd=self.root, timeout=300)
        if check and r.returncode != 0:
            raise AssertionError(f"{name} {a} rc={r.returncode}\n{r.stdout}\n{r.stderr}")
        return r

    def census(self, classes="auto"):
        self.py("disk_census.py", "--classes", classes, "--ledger")
        with open(os.path.join(self.state, "last-census.json")) as fh:
            return {r["path"]: r for r in json.load(fh)["rows"]}

    def jsonl(self, name):
        p = os.path.join(self.state, name)
        if not os.path.exists(p):
            return []
        with open(p) as fh:
            return [json.loads(x) for x in fh]

    def ledger(self):
        return self.jsonl("ledger.jsonl")

    def free_log(self):
        return self.jsonl("free-log.jsonl")

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


class AutoClassTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()

    def tearDown(self):
        self.f.cleanup()

    def eligible(self, rows, path):
        return rows[path]["reclaim_cmd"] != "none"

    def test_census_job_scratch(self):
        f = self.f
        rows = f.census()
        self.assertTrue(self.eligible(rows, f.jobs["j-idle"]))        # done, old, nothing open
        self.assertTrue(self.eligible(rows, f.jobs["j-gone"]))        # no longer listed
        self.assertIn("no longer listed", rows[f.jobs["j-gone"]]["safety_basis"])
        self.assertFalse(self.eligible(rows, f.jobs["j-busy"]))       # working
        self.assertFalse(self.eligible(rows, f.jobs["j-recent"]))     # a file modified in the last 24 h
        self.assertFalse(self.eligible(rows, f.jobs["j-open"]))       # lsof sees an open file
        self.assertNotIn(f.jobs["j-small"], rows)                     # under the row floor
        self.assertEqual(rows[f.jobs["j-idle"]]["class"], "claude-job-scratch")

    def test_roster_failure_fails_closed(self):
        f = self.f
        write(os.path.join(f.root, "claude-fails"))
        rows = f.census()
        scratch = [r for r in rows.values() if r["class"] == "claude-job-scratch"]
        self.assertTrue(scratch)
        self.assertTrue(all(r["reclaim_cmd"] == "none" for r in scratch))
        self.assertIn("roster", scratch[0]["safety_basis"])

    def test_census_cli_versions(self):
        f = self.f
        rows = f.census()
        v = f.versions
        self.assertTrue(self.eligible(rows, v["1.0.1"]))
        self.assertIn("current version", rows[v["1.0.2"]]["safety_basis"])
        self.assertIn("newer", rows[v["1.0.3"]]["safety_basis"])
        self.assertIn("running process", rows[v["1.0.0"]]["safety_basis"])   # matched in ps
        write(f.ps_out, b"/usr/sbin/syslogd\n")                               # lsof alone still holds it
        rows = f.census()
        self.assertIn("open by a running process", rows[v["1.0.0"]]["safety_basis"])

    def test_census_spool_and_dehydrate_rows(self):
        f = self.f
        rows = f.census()
        self.assertEqual(rows[os.path.realpath(f.spool)]["reclaim_cmd"] if os.path.realpath(f.spool) in rows
                         else rows[f.spool]["reclaim_cmd"], "rotate-gzip")
        dr = [r for r in rows.values() if r["class"] == "stale-worktrees"]
        self.assertEqual(len(dr), 1)
        self.assertEqual(os.path.realpath(dr[0]["path"]), f.dehydrate_dir)  # 0.2.10 sorts after 0.2.9
        self.assertEqual(dr[0]["reclaim_cmd"], "dehydrate-pressure")
        # only a dehydrate older than 0.2.1 (no job-dir holds, no re-checks): never delegated to
        base = os.path.dirname(f.dehydrate_dir)
        for v in ("0.2.9", "0.2.10"):
            shutil.rmtree(os.path.join(base, v))
        dr = [r for r in f.census().values() if r["class"] == "stale-worktrees"]
        self.assertEqual(dr[0]["reclaim_cmd"], "none")
        self.assertIn("needs 0.2.1+", dr[0]["safety_basis"])

    def test_desktop_vm_is_report_only(self):
        f = self.f
        vm = os.path.join(f.home, "Library", "Application Support", "Claude", "vm_bundles")
        write(os.path.join(vm, "bundle.img"), b"v" * 60 * MB)
        write(f.ps_out, b"/Applications/Claude.app/Contents/MacOS/Claude\n")
        rows = f.census("desktop-vm")
        self.assertEqual(rows[vm]["class"], "claude-desktop-vm")
        self.assertEqual(rows[vm]["reclaim_cmd"], "none")
        write(f.ps_out, b"/usr/sbin/syslogd\n")
        rows = f.census("desktop-vm,auto")
        self.assertTrue(rows[vm]["reclaim_cmd"].startswith("rm -rf"))
        f.py("disk_reclaim_record.py", "--path", vm, "--bytes", "1", "--cmd", "x", "--decided-by", "auto:claude-desktop-vm")
        r = f.py("disk_reclaim.py", "--path", vm, "--execute", check=False)
        self.assertEqual(r.returncode, 2)
        self.assertTrue(os.path.isdir(vm))
        write(f.ps_out, b"/Applications/Claude.app/Contents/MacOS/Claude\n")
        f.py("disk_reclaim_record.py", "--path", vm, "--bytes", "1", "--cmd", "x", "--decided-by", "h@x")
        r = f.py("disk_reclaim.py", "--path", vm, "--execute", check=False)
        self.assertEqual(r.returncode, 2)                                    # a human said yes, but the app runs
        self.assertIn("desktop app is running", r.stdout)
        self.assertTrue(os.path.isdir(vm))
        r = f.py("disk_reclaim.py", "--auto", "--execute")
        self.assertTrue(os.path.isdir(vm))                                   # never in the auto order

    def test_gate_auto_class_must_match_and_recheck(self):
        f = self.f
        f.census()
        old = f.versions["1.0.1"]
        f.py("disk_reclaim_record.py", "--path", old, "--bytes", "1", "--cmd", "x", "--decided-by", "auto:claude-job-scratch")
        r = f.py("disk_reclaim.py", "--path", old, "--execute", check=False)
        self.assertEqual(r.returncode, 2)
        self.assertIn("does not match", r.stdout)
        self.assertTrue(os.path.exists(old))
        # right class, but the job became busy after the census: the live re-check refuses
        tmp = f.jobs["j-idle"]
        f.py("disk_reclaim_record.py", "--path", tmp, "--bytes", "1", "--cmd", "x", "--decided-by", "auto:claude-job-scratch")
        f.set_agents([{"id": "j-idle", "state": "busy"}])
        r = f.py("disk_reclaim.py", "--path", tmp, "--execute", check=False)
        self.assertEqual(r.returncode, 2)
        self.assertIn("live re-check failed", r.stdout)
        self.assertTrue(os.path.exists(os.path.join(tmp, "sub", "blob.bin")))

    def test_failed_command_is_recorded_as_failed(self):
        f = self.f
        p = os.path.join(f.home, ".cache", "thing")
        write(os.path.join(p, "a"), b"a")
        census = {"summary": {}, "rows": [{"class": "pkg-cache", "path": p, "measured_bytes": 1, "safety": "regenerable",
                                           "safety_basis": "", "reclaim_cmd": "false", "reclaim_cost": "", "owner_session": ""}]}
        with open(os.path.join(f.state, "last-census.json"), "w") as fh:
            json.dump(census, fh)
        f.py("disk_reclaim_record.py", "--path", p, "--bytes", "1", "--cmd", "false", "--decided-by", "h@x")
        r = f.py("disk_reclaim.py", "--path", p, "--execute")
        self.assertIn("FAILED", r.stdout)
        last = f.ledger()[-1]
        self.assertEqual(last["decision"], "failed")
        self.assertEqual(last["reclaimed_bytes"], 0)


class AutoModeTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.f.census()

    def tearDown(self):
        self.f.cleanup()

    def test_order_and_stop_at_goal(self):
        f = self.f
        # target 15 + headroom 5 = goal 20: the first check (1) starts the pass, three actions run at 1 GB,
        # the fourth check sees 30 and stops before the smaller scratch dir and the dehydrate call
        r = f.py("disk_reclaim.py", "--auto", "--execute", free="1,1,1,1,30")
        acts = [x for x in f.free_log() if x.get("event") == "auto-reclaim"]
        self.assertEqual([a["class"] for a in acts], ["hook-spool-rotation", "claude-cli-versions", "claude-job-scratch"],
                         r.stdout)
        self.assertEqual(acts[2]["path"], f.jobs["j-gone"])                  # largest scratch first
        self.assertTrue(all(a["outcome"] == "done" for a in acts))
        self.assertFalse(os.path.exists(f.versions["1.0.1"]))
        self.assertTrue(all(os.path.exists(f.versions[v]) for v in ("1.0.0", "1.0.2", "1.0.3")))
        self.assertEqual(os.listdir(f.jobs["j-gone"]), [])                    # tmp/ emptied, job dir kept
        self.assertTrue(os.path.isfile(os.path.join(os.path.dirname(f.jobs["j-gone"]), "state.json")))
        self.assertTrue(os.path.exists(os.path.join(f.jobs["j-idle"], "sub", "blob.bin")))
        self.assertFalse(os.path.exists(f.dehydrate_log))
        obs = os.path.dirname(f.spool)
        gz = [n for n in os.listdir(obs) if n.endswith(".jsonl.gz")]
        self.assertEqual(len(gz), 1)
        self.assertFalse(os.path.exists(f.spool))
        with gzip.open(os.path.join(obs, gz[0])) as g:
            self.assertEqual(sum(1 for _ in g), 30000)                       # every byte kept
        self.assertIn(gz[0], open(os.path.join(obs, "README-rotation.txt")).read())
        led = f.ledger()
        decided = [x for x in led if x.get("decision") == "reclaim"]
        outcomes = [x for x in led if x.get("decision") == "reclaimed"]
        self.assertEqual([x["decided_by"] for x in decided],
                         ["auto:hook-spool-rotation", "auto:claude-cli-versions", "auto:claude-job-scratch"])
        self.assertEqual(len(outcomes), 3)
        nudge = f.py("disk_nudge.py").stdout
        self.assertIn("DISK_RECLAIM_AUTO:", nudge)
        self.assertIn("3 action(s)", nudge)
        self.assertNotIn("DISK_RECLAIM_AUTO:", f.py("disk_nudge.py").stdout)  # reported once

    def test_runs_through_to_dehydrate(self):
        f = self.f
        f.py("disk_reclaim.py", "--auto", "--execute", free="1")
        calls = open(f.dehydrate_log).read().split("\n")
        self.assertEqual(calls[0], "0.2.10 apply --yes --json --pressure --target-gb 20")
        acts = [x["class"] for x in f.free_log() if x.get("event") == "auto-reclaim"]
        self.assertEqual(acts, ["hook-spool-rotation", "claude-cli-versions", "claude-job-scratch",
                                "claude-job-scratch", "stale-worktrees"])
        last = [x for x in f.ledger() if x.get("class") == "stale-worktrees"][-1]
        self.assertEqual(last["decision"], "reclaimed")
        self.assertIn('"reached": true', last["note"])
        self.assertEqual(last["path"], f.dehydrate_dir)          # still the ledger key the gate matches on
        self.assertEqual(last["targets"], ["/x/wt"])             # what dehydrate actually removed
        self.assertEqual([x.get("targets") for x in f.free_log() if x.get("class") == "stale-worktrees"], [["/x/wt"]])

    def test_census_older_than_a_dehydrate_install_uses_the_newest(self):
        """0.4.2: a census taken before a newer dehydrate was installed still delegates to the newest one."""
        f = self.f
        f.census()
        base = os.path.dirname(f.dehydrate_dir)
        src = open(os.path.join(f.dehydrate_dir, "scripts", "dehydrate.py")).read().replace('"0.2.10 "', '"0.2.11 "')
        script(os.path.join(base, "0.2.11", "scripts", "dehydrate.py"), src)
        newest = os.path.realpath(os.path.join(base, "0.2.11"))
        with open(os.path.join(f.state, "last-census.json")) as fh:   # the census still names 0.2.10
            self.assertIn(f.dehydrate_dir, [r["path"] for r in json.load(fh)["rows"]])
        r = f.py("disk_reclaim.py", "--auto", "--execute", free="1")
        self.assertNotIn("not the newest", r.stdout)
        calls = [c for c in open(f.dehydrate_log).read().split("\n") if c]
        self.assertEqual(calls, ["0.2.11 apply --yes --json --pressure --target-gb 20"])
        rows = [x for x in f.ledger() if x.get("class") == "stale-worktrees"]
        self.assertEqual({x["path"] for x in rows}, {newest})            # decision and outcome both
        self.assertEqual(rows[-1]["decision"], "reclaimed")

    def test_dry_run_changes_nothing(self):
        f = self.f
        r = f.py("disk_reclaim.py", "--auto", free="1")
        self.assertIn("WOULD RECLAIM", r.stdout)
        self.assertIn("would run dehydrate", r.stdout)
        line = next(x for x in r.stdout.splitlines() if "auto:stale-worktrees" in x)
        self.assertIn("/x/wt, /x/wt2  (auto:stale-worktrees)", line)   # the plan's worktrees up to its stop
        self.assertNotIn("/x/wt3", line)
        self.assertNotIn("plugins/cache", line)                          # not the plugin dir
        self.assertTrue(os.path.exists(f.spool))
        self.assertTrue(os.path.exists(f.versions["1.0.1"]))
        self.assertEqual(f.ledger(), [])
        self.assertEqual(f.free_log(), [])
        calls = [c for c in open(f.dehydrate_log).read().split("\n") if c]
        self.assertEqual(calls, ["0.2.10 plan --json --pressure --target-gb 20"])   # read-only, never apply
        self.assertFalse(os.path.exists(os.path.join(f.state, "auto.lock")))   # not even the lock

    def test_nudge_help_is_inert(self):
        r = self.f.py("disk_nudge.py", "--help")
        self.assertIn("SessionStart hook", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.f.state, "hook-log.jsonl")))

    def test_off_and_above_target_do_nothing(self):
        f = self.f
        r = f.py("disk_reclaim.py", "--auto", "--execute", free="40")
        self.assertIn("nothing to do", r.stdout)
        with open(os.path.join(f.state, "auto"), "w") as fh:
            fh.write("false\n")
        r = f.py("disk_reclaim.py", "--auto", "--execute", free="1")
        self.assertIn("off", r.stdout)
        self.assertTrue(os.path.exists(f.spool))
        self.assertEqual(f.ledger(), [])

    def test_lock_held_skips(self):
        import fcntl
        f = self.f
        with open(os.path.join(f.state, "auto.lock"), "w") as lk:
            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
            r = f.py("disk_reclaim.py", "--auto", "--execute", free="1")
        self.assertIn("holds auto.lock", r.stdout)
        self.assertTrue(os.path.exists(f.spool))


if __name__ == "__main__":
    unittest.main()
