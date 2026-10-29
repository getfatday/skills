#!/usr/bin/env python3
"""The only sanctioned way this plugin deletes anything. Refuses without a recorded decision.

Usage:
  disk_reclaim.py                 dry run over every census row that has a recorded decision to reclaim
  disk_reclaim.py --path P        dry run for one path
  disk_reclaim.py --execute ...   actually remove (still gated)
  disk_reclaim.py --explain P     say what decision P would need and print the ask to send
  disk_reclaim.py --auto [--execute]
                                  automatic mode: when container free space is under target-gb, reclaim the
                                  auto classes in a fixed order until free >= target-gb + headroom-gb

Gate, checked per path before anything is removed:
  1. The path must appear in <state>/last-census.json (the census is the inventory; nothing off-census
     is ever deleted here).
  2. There must be a ledger record in <state>/ledger.jsonl for that exact path with decision "reclaim",
     whose decided_by is either a human (contains "@") or an owner session verdict SAFE
     ("owner:<session name>" with owner_verdict SAFE). "auto:cache" is accepted ONLY for rows whose
     class is pkg-cache or build-cache AND whose path lies under one of the ownerless cache roots below.
     "auto:<class>" is accepted ONLY for the auto classes in auto_classes.py (spool rotation, old CLI
     versions, job scratch, the delegated dehydrate call), only when <class> is the row's own class,
     and only when that class's live checks pass again at the moment of acting.
  3. Rows under ~/src, ~/.claude (other than the census's own state dir), any *worktrees* directory,
     ~/Library/Developer/CoreSimulator, or any simulator runtime asset can never use the cache rule.
     Someone owns them; someone has to say so.
  4. The path must still exist and be inside the user's home or a simulator asset root. Never /, never
     /System, /Applications, /Library, /private.

Why so strict: on 2026-09-06 a session following the previous skill text was one step from removing
five repos' node_modules on the strength of a "regenerable" label, without asking the sessions that
might have been mid-install in those repos. A label is a hint. A decision is a record with a name on
it. The gate makes the difference mechanical instead of a matter of the model's judgment on the day.

Every removal appends a ledger line with reclaimed_bytes and reclaimed_at; an attempt that fails is
recorded as decision "failed" with reclaimed_bytes 0. Automatic actions also append a line to
<state>/free-log.jsonl, which the SessionStart nudge summarizes once. Exit codes: 0 done or
dry-run clean, 2 refused (nothing removed for the refused paths), 3 bad arguments.
"""
import argparse
import contextlib
import fcntl
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from disk_state import state_dir  # noqa: E402
import auto_classes  # noqa: E402

HOME = os.path.expanduser("~")
OWNERLESS_CACHE_ROOTS = [
    os.path.join(HOME, "Library/Caches"),
    os.path.join(HOME, ".cache"),
    os.path.join(HOME, ".npm"),
    os.path.join(HOME, "Library/Developer/Xcode/DerivedData"),
    os.path.join(HOME, "Library/pnpm/store"),
]
NEVER_CACHE_RULE = [
    os.path.join(HOME, "src"),
    os.path.join(HOME, ".claude"),
    os.path.join(HOME, "Library/Developer/CoreSimulator"),
    "/System/Library/AssetsV2",
]
FORBIDDEN_PREFIXES = ["/System", "/Applications", "/Library", "/private", "/usr", "/bin", "/sbin", "/opt", "/etc", "/var"]


def acting_session():
    """Who is running the executor: the job's name from ~/.claude/jobs/<id>/state.json when CLAUDE_JOB_DIR is set,
    else the session id if the harness exports one, else the user. Recorded on every removal so the ledger can
    answer 'which session removed this' (H-443 run 2 found four removals nobody could attribute)."""
    jd = os.environ.get("CLAUDE_JOB_DIR", "")
    if jd:
        try:
            st = json.load(open(os.path.join(jd, "state.json")))
            return f"session:{st.get('name') or os.path.basename(jd)}"
        except Exception:
            return f"job:{os.path.basename(jd.rstrip('/'))}"
    sid = os.environ.get("CLAUDE_SESSION_ID", "")
    return f"session-id:{sid}" if sid else f"user:{os.environ.get('USER', 'unknown')}"


def real(p):
    return os.path.realpath(os.path.expanduser(p.split(" [")[0]))


def under(p, root):
    p, root = real(p), real(root)
    return p == root or p.startswith(root + "/")


def load_census(d):
    try:
        return json.load(open(os.path.join(d, "last-census.json")))["rows"]
    except Exception:
        return []


def load_ledger(d):
    out = []
    try:
        for line in open(os.path.join(d, "ledger.jsonl")):
            line = line.strip()
            if line:
                out.append(json.loads(line))
    except FileNotFoundError:
        pass
    return out


def decision_for(path, ledger):
    """Latest ledger record for this exact path, or None."""
    hits = [r for r in ledger if real(r.get("path", "")) == real(path)]
    return hits[-1] if hits else None


def gate(row, ledger):
    """Return (allowed, reason, decided_by)."""
    p = row["path"]
    rp = real(p)
    if rp == "/" or any(rp == f or rp.startswith(f + "/") for f in FORBIDDEN_PREFIXES):
        if not rp.startswith("/System/Library/AssetsV2"):
            return False, "system path; this tool never removes here", ""
    if not (rp.startswith(HOME + "/") or rp.startswith("/System/Library/AssetsV2")):
        return False, "outside the home directory", ""
    if under(rp, os.path.join(HOME, ".claude", "disk-reclaim")):
        return False, "the census's own state dir", ""
    if not os.path.exists(rp):
        return False, "already gone", ""
    if row.get("class") in auto_classes.REPORT_ONLY and auto_classes.desktop_running():
        return False, "the Claude desktop app is running (or the process list is unreadable); quit it first", ""
    dec = decision_for(p, ledger)
    if dec and dec.get("decision") == "keep":
        until = dec.get("keep_until", "")
        return False, f"owner or human said KEEP{(' until ' + until) if until else ''}", dec.get("decided_by", "")
    if dec and dec.get("decision") == "reclaim":
        by = dec.get("decided_by", "")
        if "@" in by:
            return True, "human decision in ledger", by
        if by.startswith("owner:") and dec.get("owner_verdict") == "SAFE":
            return True, "owner verdict SAFE in ledger", by
        if by.startswith("auto:") and by[5:] in auto_classes.AUTO_CLASSES:
            cls = by[5:]
            if row.get("class") != cls:
                return False, f"decision {by} does not match the row's class {row.get('class')}", by
            ok, why = auto_classes.eligible(row, d=state_dir())
            if not ok:
                return False, f"{by} live re-check failed: {why}", by
            return True, f"{by}, live re-check passed: {why}", by
        if by == "auto:cache":
            pass  # fall through to the cache rule below
        else:
            return False, f"ledger decision by '{by}' is not a human or an owner SAFE", by
    # cache rule: only ownerless caches, only pkg-cache/build-cache, never under owned roots
    if any(under(rp, r) for r in NEVER_CACHE_RULE) or "worktrees" in rp.split("/"):
        return False, "inside an owned root (src, .claude, worktrees, simulators); needs an owner SAFE or a human decision", ""
    if row.get("class") in ("pkg-cache", "build-cache") and any(under(rp, r) for r in OWNERLESS_CACHE_ROOTS):
        if dec and dec.get("decided_by") == "auto:cache":
            return True, "ownerless cache with a recorded auto:cache decision", "auto:cache"
        return False, "ownerless cache, but record the decision first: disk_reclaim_record.py --decided-by auto:cache", ""
    return False, "no decision recorded for this path", ""


def explain(row, reason):
    home = HOME
    p = row["path"].replace(home, "~")
    print(f"REFUSED  {p}\n  reason: {reason}")
    owner = row.get("owner_session") or ""
    if owner:
        print(f"  owner:  {owner}. Send the ask in references/ask-format.md, then record the reply:")
        print(f"  disk_reclaim_record.py --path '{row['path'].split(' [')[0]}' --bytes {row['measured_bytes']} --cmd \"{row['reclaim_cmd']}\" --decided-by 'owner:{owner.split(' (')[0]}' --verdict SAFE")
    else:
        print("  no owner attributed. Put it to the human, then record their choice:")
        print(f"  disk_reclaim_record.py --path '{row['path'].split(' [')[0]}' --bytes {row['measured_bytes']} --cmd \"{row['reclaim_cmd']}\" --decided-by <email>")


def remove(row, execute, goal_gb=None):
    """Returns (bytes measured before, what happened, succeeded)."""
    rp = real(row["path"])
    cmd = row.get("reclaim_cmd", "")
    before = 0
    if cmd != "dehydrate-pressure":  # the plugin dir is not what that row frees
        try:
            before = auto_classes.du_bytes(rp)
            before = max(before, 0)
        except Exception:
            pass
    if not execute:
        if cmd == "dehydrate-pressure":
            return before, f"dry-run: would run dehydrate apply --yes --pressure --target-gb {goal_gb or '<target-gb>'}", True
        return before, "dry-run", True
    try:
        if cmd.startswith("rm -rf"):
            if os.path.isdir(rp) and not os.path.islink(rp):
                shutil.rmtree(rp)
            else:
                os.remove(rp)
            if row.get("class") == "claude-job-scratch":
                os.makedirs(rp, exist_ok=True)  # an empty tmp/ for a session that is resumed later
            return before, "removed", True
        if cmd == "rotate-gzip":
            ok, note, freed = auto_classes.rotate_spool(rp, f"disk-reclaim, {acting_session()}")
            return freed, note, ok
        if cmd == "dehydrate-pressure":
            if goal_gb is None:
                cfg = auto_classes.auto_config(state_dir())
                goal_gb = cfg["target_gb"] + cfg["headroom_gb"]
            ok, note = auto_classes.run_dehydrate(rp, goal_gb)
            return 0, note, ok
    except Exception as e:
        return before, f"failed: {e.__class__.__name__}: {str(e)[:200]}", False
    if cmd == "none" or not cmd:
        return before, "no reclaim command on this row; nothing done", False
    # a tool's own command (uv cache prune, xcrun simctl delete, git worktree remove ...): run it as given
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600)
    if r.returncode == 0:
        return before, "ran: " + cmd, True
    return before, f"command failed rc={r.returncode}: {r.stderr.strip()[:200]}", False


def record_removal(d, row, before, by, what, ok, freed=None):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    got = (before if freed is None else freed) if ok else 0
    rec = {"ts": now, "path": row["path"].split(" [")[0],
           "class": row.get("class", ""), "measured_bytes": before, "reclaim_cmd": row.get("reclaim_cmd", ""),
           "decided_by": by, "decision": "reclaimed" if ok else "failed", "reclaimed_bytes": got,
           "removed_by": acting_session(), "reclaimed_at": now, "note": what}
    with open(os.path.join(d, "ledger.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def free_log(d, rec):
    rec = dict({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "free_mb": auto_classes.free_bytes(consume=False) // 2 ** 20}, **rec)
    with open(os.path.join(d, "free-log.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")


def run_auto(d, execute):
    """One automatic pass. Cheap exit first; then one lock, niced; then the fixed order until free reaches
    target + headroom. Every action is a ledger decision (auto:<class>), a ledger outcome and a free-log line."""
    cfg = auto_classes.auto_config(d)
    if not cfg["auto"]:
        print(f"auto-reclaim is off ({d}/auto says false)")
        return 0
    target, goal = cfg["target_gb"] * 1e9, (cfg["target_gb"] + cfg["headroom_gb"]) * 1e9
    free = auto_classes.free_bytes()
    if free >= target:
        print(f"auto-reclaim: {free/1e9:.1f} GB free, at or over target {cfg['target_gb']:g} GB; nothing to do")
        return 0
    lock = open(os.path.join(d, "auto.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("auto-reclaim: another pass holds auto.lock")
        return 0
    with contextlib.suppress(OSError):
        os.nice(max(0, 19 - os.nice(0)))
    rows = load_census(d)
    if not rows:
        print("auto-reclaim: no census yet; run disk_census.py --ledger first", file=sys.stderr)
        return 3
    start = free
    if execute:
        free_log(d, {"event": "auto-run", "phase": "start", "target_gb": cfg["target_gb"], "headroom_gb": cfg["headroom_gb"]})
    ledger = load_ledger(d)
    done = failed = 0
    for row in auto_classes.auto_order(rows):
        free = auto_classes.free_bytes()
        if free >= goal:
            break
        cls, path = row["class"], row["path"]
        by = f"auto:{cls}"
        dec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "path": path, "class": cls,
               "measured_bytes": row.get("measured_bytes", 0), "reclaim_cmd": row.get("reclaim_cmd", ""),
               "decided_by": by, "owner_session": row.get("owner_session", ""), "owner_verdict": "", "keep_until": "",
               "decision": "reclaim", "note": f"auto-reclaim: {free/1e9:.1f} GB free under target {cfg['target_gb']:g} GB"}
        ok, reason, _ = gate(row, ledger + [dec])
        if not ok:
            print(f"SKIPPED  {path.replace(HOME, '~')}  ({reason})")
            continue
        if execute:
            with open(os.path.join(d, "ledger.jsonl"), "a") as f:
                f.write(json.dumps(dec) + "\n")
            ledger.append(dec)
        before, what, succeeded = remove(row, execute, goal_gb=goal / 1e9)
        if not execute:
            print(f"WOULD RECLAIM  {before/1e9:5.1f} GB  {path.replace(HOME, '~')}  ({by})  {what}")
            continue
        after = auto_classes.free_bytes(consume=False)
        freed = max(after - free, 0) if cls == "stale-worktrees" else None
        rec = record_removal(d, row, before, by, what, succeeded, freed)
        free_log(d, {"event": "auto-reclaim", "class": cls, "path": path, "decided_by": by,
                     "outcome": "done" if succeeded else "failed", "freed_bytes": rec["reclaimed_bytes"], "note": what[:300]})
        done += succeeded
        failed += not succeeded
        print(f"{'RECLAIMED' if succeeded else 'FAILED'}  {rec['reclaimed_bytes']/1e9:5.1f} GB  {path.replace(HOME, '~')}  ({by})  {what}")
    end = auto_classes.free_bytes(consume=False)
    if execute:
        free_log(d, {"event": "auto-run", "phase": "end", "done": done, "failed": failed,
                     "start_free_mb": start // 2 ** 20, "reached": end >= goal})
    print(f"auto-reclaim {'done' if execute else 'dry run'}: {done} reclaimed, {failed} failed; "
          f"free {start/1e9:.1f} -> {end/1e9:.1f} GB (goal {goal/1e9:g} GB)")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", action="append", default=[], help="limit to these paths (repeatable)")
    ap.add_argument("--execute", action="store_true", help="actually remove; default is dry run")
    ap.add_argument("--explain", metavar="PATH", help="show what decision this path needs")
    ap.add_argument("--auto", action="store_true",
                    help="automatic mode: reclaim the auto classes in order while free space is under target-gb")
    a = ap.parse_args()
    d = state_dir()
    if a.auto:
        return run_auto(d, a.execute)
    rows = load_census(d)
    ledger = load_ledger(d)
    if not rows:
        print("no census; run disk_census.py --ledger first", file=sys.stderr)
        return 3
    if a.explain:
        for row in rows:
            if real(row["path"]) == real(a.explain):
                ok, reason, by = gate(row, ledger)
                print("ALLOWED" if ok else "REFUSED", reason, by)
                if not ok:
                    explain(row, reason)
                return 0
        print("not in the census; this tool only acts on census rows", file=sys.stderr)
        return 2
    wanted = {real(p) for p in a.path} if a.path else None
    if wanted is None:
        # default: every census row that has a ledger decision to reclaim (never "all regenerable")
        decided = {real(r["path"]) for r in ledger if r.get("decision") == "reclaim"}
        wanted = decided
    refused = 0
    freed = 0
    for row in rows:
        if real(row["path"]) not in wanted:
            continue
        ok, reason, by = gate(row, ledger)
        if not ok:
            refused += 1
            explain(row, reason)
            continue
        before, what, ok = remove(row, a.execute)
        freed += before if a.execute and ok else 0
        label = ("REMOVED" if ok else "FAILED") if a.execute else "WOULD REMOVE"
        print(f"{label}  {before/1e9:5.1f} GB  {row['path'].replace(HOME, '~')}  ({reason}: {by})  {what}")
        if a.execute:
            record_removal(d, row, before, by, what, ok)
    if a.execute:
        print(f"freed {freed/1e9:.1f} GB; refused {refused} path(s)")
    else:
        print(f"dry run; refused {refused} path(s); add --execute to remove the allowed ones")
    return 2 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
