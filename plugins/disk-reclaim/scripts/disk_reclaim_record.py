#!/usr/bin/env python3
"""Append one reclaim decision to <state>/ledger.jsonl.

Usage:
  disk_reclaim_record.py --path P --bytes N --cmd "C" --decided-by WHO
   WHO is a human email, 'owner:<session name>' (with --verdict), or 'auto:cache' (ownerless caches only).
                         [--class CLS] [--owner SESSION] [--verdict KEEP|SAFE|UNKNOWN]
                         [--until COND] [--note TEXT]

The ledger is the memory that survives sessions: what was removed, who said it was safe, and
what a later census should re-ask (a KEEP with --until). Never edits earlier lines.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from disk_state import state_dir  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    ap.add_argument("--bytes", type=int, required=True, help="measured bytes before the reclaim")
    ap.add_argument("--cmd", required=True)
    ap.add_argument("--decided-by", required=True,
                    help="who decided: a human email, 'owner:<session name>' for a session verdict, or 'auto:cache' for an ownerless cache row")
    ap.add_argument("--class", dest="cls", default="")
    ap.add_argument("--owner", default="")
    ap.add_argument("--verdict", default="", choices=["", "KEEP", "SAFE", "UNKNOWN"])
    ap.add_argument("--until", default="", help="for time-bounded KEEP: path-exists=<p> or a date")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "path": a.path, "class": a.cls, "measured_bytes": a.bytes,
        "reclaim_cmd": a.cmd, "decided_by": a.decided_by,
        "owner_session": a.owner, "owner_verdict": a.verdict, "keep_until": a.until,
        "decision": {"KEEP": "keep", "UNKNOWN": "asked"}.get(a.verdict, "reclaim"),
        "note": a.note,
    }
    with open(os.path.join(state_dir(), "ledger.jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec))
    return 0


if __name__ == "__main__":
    sys.exit(main())
