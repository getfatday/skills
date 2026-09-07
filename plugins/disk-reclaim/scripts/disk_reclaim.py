#!/usr/bin/env python3
"""The only sanctioned way this plugin deletes anything. Refuses without a recorded decision.

Usage:
  disk_reclaim.py                 dry run over every census row that has a recorded decision to reclaim
  disk_reclaim.py --path P        dry run for one path
  disk_reclaim.py --execute ...   actually remove (still gated)
  disk_reclaim.py --explain P     say what decision P would need and print the ask to send

Gate, checked per path before anything is removed:
  1. The path must appear in <state>/last-census.json (the census is the inventory; nothing off-census
     is ever deleted here).
  2. There must be a ledger record in <state>/ledger.jsonl for that exact path with decision "reclaim",
     whose decided_by is either a human (contains "@") or an owner session verdict SAFE
     ("owner:<session name>" with owner_verdict SAFE). "auto:cache" is accepted ONLY for rows whose
     class is pkg-cache or build-cache AND whose path lies under one of the ownerless cache roots below.
  3. Rows under ~/src, ~/.claude (other than the census's own state dir), any *worktrees* directory,
     ~/Library/Developer/CoreSimulator, or any simulator runtime asset can never use the cache rule.
     Someone owns them; someone has to say so.
  4. The path must still exist and be inside the user's home or a simulator asset root. Never /, never
     /System, /Applications, /Library, /private.

Why so strict: on 2026-09-06 a session following the previous skill text was one step from removing
five repos' node_modules on the strength of a "regenerable" label, without asking the sessions that
might have been mid-install in those repos. A label is a hint. A decision is a record with a name on
it. The gate makes the difference mechanical instead of a matter of the model's judgment on the day.

Every removal appends a ledger line with reclaimed_bytes and reclaimed_at. Exit codes: 0 done or
dry-run clean, 2 refused (nothing removed for the refused paths), 3 bad arguments.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from disk_state import state_dir  # noqa: E402

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


def remove(row, execute):
    rp = real(row["path"])
    cmd = row.get("reclaim_cmd", "")
    before = 0
    try:
        out = subprocess.run(["du", "-sk", rp], capture_output=True, text=True, timeout=120).stdout
        before = int(out.split()[0]) * 1024 if out.strip() else 0
    except Exception:
        pass
    if not execute:
        return before, "dry-run"
    if cmd.startswith("rm -rf"):
        if os.path.isdir(rp) and not os.path.islink(rp):
            shutil.rmtree(rp)
        else:
            os.remove(rp)
        return before, "removed"
    if cmd == "none" or not cmd:
        return before, "no reclaim command on this row; nothing done"
    # a tool's own command (uv cache prune, xcrun simctl delete, git worktree remove ...): run it as given
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600)
    return before, ("ran: " + cmd if r.returncode == 0 else f"command failed rc={r.returncode}: {r.stderr.strip()[:200]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", action="append", default=[], help="limit to these paths (repeatable)")
    ap.add_argument("--execute", action="store_true", help="actually remove; default is dry run")
    ap.add_argument("--explain", metavar="PATH", help="show what decision this path needs")
    a = ap.parse_args()
    d = state_dir()
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
        before, what = remove(row, a.execute)
        freed += before if a.execute and what == "removed" else 0
        print(f"{'REMOVED' if a.execute else 'WOULD REMOVE'}  {before/1e9:5.1f} GB  {row['path'].replace(HOME, '~')}  ({reason}: {by})  {what}")
        if a.execute:
            rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "path": row["path"].split(" [")[0],
                   "class": row.get("class", ""), "measured_bytes": before, "reclaim_cmd": row.get("reclaim_cmd", ""),
                   "decided_by": by, "decision": "reclaimed", "reclaimed_bytes": before,
                   "reclaimed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "note": what}
            with open(os.path.join(d, "ledger.jsonl"), "a") as f:
                f.write(json.dumps(rec) + "\n")
    if a.execute:
        print(f"freed {freed/1e9:.1f} GB; refused {refused} path(s)")
    else:
        print(f"dry run; refused {refused} path(s); add --execute to remove the allowed ones")
    return 2 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
