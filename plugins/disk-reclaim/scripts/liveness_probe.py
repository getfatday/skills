#!/usr/bin/env python3
"""Classify every Claude Code session on this machine as live, idle, or dead, from two surfaces.

Why two surfaces: the job store's `state` field is not liveness. On 2026-09-07 a job whose state
read "done" answered a cross-session ask within minutes, and a session whose row read "idle" for
five days never answered at all. So:

  roster  = `claude agents --json` (what ListAgents shows): a session in the roster is reachable
            and its status (busy / idle / waiting / shell) says whether it is mid-turn right now.
  store   = ~/.claude/jobs/*/state.json: name, cwd, state, and the file's mtime as a last-activity
            proxy. A job in the store but NOT in the roster is not reachable by SendMessage.

Classes (what the orchestrator does with each):
  live-busy   in roster, status busy/shell     -> do not message now; subscribe notify_when_idle
  live-idle   in roster, status idle/waiting/blocked -> message now, 10-minute deadline
              ("blocked" is the job store's word for a session waiting on a permission prompt;
              it is reachable and will read a message at its next turn)
  dead        in store only                    -> nobody to ask; rows it owns default to the human
  unknown     in roster but no store record    -> message; owner attribution unavailable

Usage: liveness_probe.py [--json] [--self <job-id>]   (read-only; exit 0 always)
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

HOME = os.path.expanduser("~")


def roster():
    try:
        p = subprocess.run(["claude", "agents", "--json"], capture_output=True, text=True, timeout=30)
        data = json.loads(p.stdout or "[]")
    except Exception as e:  # noqa: BLE001
        return None, f"{e.__class__.__name__}: {e}"
    rows = data if isinstance(data, list) else data.get("agents") or data.get("sessions") or []
    return rows, ""


def store():
    out = {}
    for sp in glob.glob(os.path.join(HOME, ".claude", "jobs", "*", "state.json")):
        jid = os.path.basename(os.path.dirname(sp))
        try:
            s = json.load(open(sp))
        except Exception:
            continue
        out[jid] = {"job": jid, "name": s.get("name") or s.get("title") or "", "cwd": s.get("cwd") or "",
                    "store_state": s.get("state") or s.get("status") or "", "age_h": round((time.time() - os.stat(sp).st_mtime) / 3600, 1)}
    return out


def classify(roster_rows, jobs, self_id=""):
    by_name = {}
    for r in roster_rows or []:
        name = r.get("name") or r.get("title") or ""
        status = (r.get("status") or r.get("state") or "").lower()
        by_name[name] = {"roster_status": status, "kind": r.get("kind") or r.get("type") or ""}
    result = []
    seen = set()
    for jid, j in jobs.items():
        if jid == self_id:
            continue
        ro = by_name.get(j["name"])
        if ro is None:
            cls = "dead"
        elif ro["roster_status"] in ("idle", "waiting", "blocked"):
            cls = "live-idle"
        else:
            cls = "live-busy"
        seen.add(j["name"])
        result.append({**j, "roster_status": ro["roster_status"] if ro else "", "class": cls})
    for name, ro in by_name.items():
        if name not in seen:
            result.append({"job": "", "name": name, "cwd": "", "store_state": "", "age_h": None,
                           "roster_status": ro["roster_status"], "class": "unknown"})
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self", default=os.environ.get("CLAUDE_JOB_DIR", "").rstrip("/").split("/")[-1])
    a = ap.parse_args()
    rows, err = roster()
    jobs = store()
    result = classify(rows, jobs, a.self)
    summary = {"roster_ok": rows is not None, "roster_error": err, "sessions": len(result),
               "by_class": {c: sum(1 for r in result if r["class"] == c) for c in ("live-busy", "live-idle", "dead", "unknown")}}
    if a.json:
        print(json.dumps({"summary": summary, "sessions": result}, indent=1))
    else:
        print(json.dumps(summary))
        for r in sorted(result, key=lambda r: (r["class"], r["name"])):
            print(f"{r['class']:<9} {r['roster_status'] or '-':<8} {str(r['age_h'])+'h' if r['age_h'] is not None else '-':>7}  {r['name'][:40]:<40} {r['job']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": f"{e.__class__.__name__}: {e}"}))
        sys.exit(0)
