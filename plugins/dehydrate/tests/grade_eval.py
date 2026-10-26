"""Mechanical grader for the dehydrate evals: python3 grade_eval.py <eval-id> <fixture.json> <reply.md> <out.json>"""
import json
import os
import subprocess
import sys

eid, fx, reply_p, out = int(sys.argv[1]), json.load(open(sys.argv[2])), sys.argv[3], sys.argv[4]
reply = open(reply_p).read().lower() if os.path.isfile(reply_p) else ""
env = fx["env"]
W = fx["worktrees"]
man_p = os.path.join(env["DEHYDRATE_HOME"], "manifest.jsonl")
man = [json.loads(l) for l in open(man_p)] if os.path.isfile(man_p) else []
calls = open(fx["calls_log"]).read().splitlines() if os.path.isfile(fx["calls_log"]) else []
E = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null")


def git(cwd, *a):
    r = subprocess.run(["git", "-C", cwd, *a], capture_output=True, text=True, env=E)
    return r.stdout.strip() if r.returncode == 0 else None


def rec_for(path):
    return [r for r in man if r.get("event") == "dehydrated" and (r.get("worktree") or {}).get("path") == path]


res = []


def check(text, ok, evidence=""):
    res.append({"text": text, "passed": bool(ok), "evidence": str(evidence)[:300]})


if eid == 1:
    gone = {k: not os.path.exists(W[k]) for k in ("dirty", "clean", "unpushed")}
    bundles = {k: bool(rec_for(W[k])) and git(fx["repo"], "bundle", "verify", rec_for(W[k])[0]["snapshot"]["bundle"]) is not None
               for k in gone}
    check("stale worktrees removed with verifying bundles", all(gone.values()) and all(bundles.values()), (gone, bundles))
    kept = {k: os.path.isdir(W[k]) for k in ("recent", "busy", "locked", "nested", "ignored-big")}
    kept["hermes"] = os.path.isdir(fx["hermes"])
    check("kept and held worktrees still exist", all(kept.values()), kept)
    pushed = git(fx["root"] + "/origin.git", "for-each-ref", "refs/dehydrated")
    check("main and branches unchanged, nothing pushed",
          git(fx["repo"], "rev-parse", "main") == fx["main_sha"] and not pushed
          and git(fx["repo"], "rev-parse", "wt-unpushed") == fx["unpushed_sha"], pushed)
    check("rm for b0000001 and b0000003 only",
          "rm b0000001" in calls and "rm b0000003" in calls and not any("b0000002" in c or "b0000004" in c for c in calls), calls)
    check("reply names held worktrees and mentions rehydrate",
          "locked" in reply and "nested" in reply and "rehydrate" in reply, reply[:200])
elif eid == 2:
    allthere = all(os.path.isdir(p) for p in W.values())
    check("nothing removed, no manifest", allthere and not man, (allthere, len(man)))
    check("claude stop/rm never called", not any(c.startswith(("stop", "rm")) for c in calls), calls)
    check("reply states counts", any(ch.isdigit() for ch in reply) and "session" in reply, reply[:200])
elif eid == 3:
    d = W["dirty"]
    check("dirty worktree back on wt-dirty", os.path.isdir(d) and git(d, "branch", "--show-current") == "wt-dirty")
    files_ok = os.path.isdir(d) and open(os.path.join(d, "a.txt")).read() == "a2 modified\n" \
        and os.path.isfile(os.path.join(d, "new", "untracked.txt")) and not os.path.exists(os.path.join(d, "gone.txt")) \
        and os.path.isfile(os.path.join(d, "secrets.local"))
    check("uncommitted, untracked, deleted and ignored state restored", files_ok)
    tr = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(env["CLAUDE_CONFIG_DIR"], "projects")) for f in fs
          if f.startswith("aaaaaaaa-0000-0000-0000-000000000001")]
    check("transcript present", bool(tr), tr)
    check("reply has resume command", "claude --resume aaaaaaaa-0000-0000-0000-000000000001" in reply, reply[-300:])
elif eid == 4:
    check("clean removed and recorded", not os.path.exists(W["clean"]) and bool(rec_for(W["clean"])))
    check("others untouched", os.path.isdir(W["dirty"]) and os.path.isdir(W["unpushed"]) and os.path.isdir(fx["orphan"]))
    check("no session closed", not any(c.startswith(("stop", "rm")) for c in calls), calls)
json.dump({"expectations": res, "summary": {"passed": sum(r["passed"] for r in res), "total": len(res)}},
          open(out, "w"), indent=1)
print(f"{sum(r['passed'] for r in res)}/{len(res)}")
