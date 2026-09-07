#!/usr/bin/env python3
"""asks.jsonl: the record of every question the reclaim loop asks, and the answers.

Subcommands (all exit 0; state dir = $DISK_RECLAIM_DIR or ~/.claude/disk-reclaim):
  sent    --to NAME --to-class CLS --paths P [P ...] --bytes N --by ASKER [--msg-id ID] [--deadline-s 600]
          -> prints the ask_id; refuses (exit 0, prints DUPLICATE) if the same (to, path) was asked <24 h ago
  reply   --ask-id ID --from NAME --path P --verdict KEEP|SAFE|UNKNOWN [--until COND] [--artifact A] [--self-cleaned-bytes N]
  status  -> counts, per-owner latency, timeouts
  pending -> sent lines past deadline with no reply (the orchestrator's "default to human" list)
  dedup-check --to NAME --path P -> prints OK or DUPLICATE
Shape and rules: the skill's references/ask-format.md. Measured by H-442.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from disk_state import state_dir  # noqa: E402


def log_path():
    return os.path.join(state_dir(), "asks.jsonl")


def now_ts(t=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t if t is not None else time.time()))


def parse_ts(s):
    import calendar
    return calendar.timegm(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ"))


def read():
    p = log_path()
    if not os.path.exists(p):
        return []
    out = []
    for line in open(p):
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def append(rec):
    with open(log_path(), "a") as f:
        f.write(json.dumps(rec) + "\n")


def is_duplicate(recs, to, path, window_s=86400):
    cutoff = time.time() - window_s
    for r in recs:
        if r.get("kind") == "sent" and r.get("to") == to and path in r.get("paths", []) and parse_ts(r["ts"]) >= cutoff:
            return r["ask_id"]
    return None


def cmd_sent(a):
    recs = read()
    dups = [p for p in a.paths if is_duplicate(recs, a.to, p)]
    if dups and len(dups) == len(a.paths):
        print("DUPLICATE all paths asked of this owner within 24h:", *dups)
        return 0
    paths = [p for p in a.paths if p not in dups]
    t = time.time()
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in a.to)[:24].strip("-")
    ask_id = f"a-{time.strftime('%Y%m%d-%H%M%S', time.gmtime(t))}-{slug}"
    append({"kind": "sent", "ts": now_ts(t), "ask_id": ask_id, "to": a.to, "to_class": a.to_class,
            "paths": paths, "bytes": a.bytes, "deadline_ts": now_ts(t + a.deadline_s), "by": a.by, "msg_id": a.msg_id})
    if dups:
        print("SKIPPED duplicates:", *dups)
    print(ask_id)
    return 0


def cmd_reply(a):
    recs = read()
    sent = next((r for r in recs if r.get("kind") == "sent" and r["ask_id"] == a.ask_id), None)
    received = parse_ts(a.received_ts) if a.received_ts else time.time()
    latency = int(received - parse_ts(sent["ts"])) if sent else -1
    append({"kind": "reply", "ts": now_ts(), "received_ts": now_ts(received), "ask_id": a.ask_id, "from": a.from_, "path": a.path,
            "verdict": a.verdict, "until": a.until, "artifact": a.artifact,
            "self_cleaned_bytes": a.self_cleaned_bytes, "latency_s": latency})
    print(json.dumps({"ask_id": a.ask_id, "path": a.path, "verdict": a.verdict, "latency_s": latency}))
    return 0


def pending(recs, now=None):
    now = now or time.time()
    replied = {(r["ask_id"], r["path"]) for r in recs if r.get("kind") == "reply"}
    out = []
    for r in recs:
        if r.get("kind") != "sent":
            continue
        if parse_ts(r["deadline_ts"]) > now:
            continue
        for p in r["paths"]:
            if (r["ask_id"], p) not in replied:
                out.append({"ask_id": r["ask_id"], "to": r["to"], "path": p, "sent": r["ts"], "deadline": r["deadline_ts"]})
    return out


def cmd_pending(a):
    for row in pending(read()):
        print(json.dumps(row))
    return 0


def cmd_status(a):
    recs = read()
    sent = [r for r in recs if r.get("kind") == "sent"]
    rep = [r for r in recs if r.get("kind") == "reply"]
    per = {}
    for r in rep:
        per.setdefault(r["from"], []).append(r["latency_s"])
    timeouts = pending(recs)
    summary = {"asks_sent": len(sent), "paths_asked": sum(len(r["paths"]) for r in sent),
               "replies": len(rep), "timeouts": len(timeouts),
               "verdicts": {v: sum(1 for r in rep if r["verdict"] == v) for v in ("KEEP", "SAFE", "UNKNOWN")},
               "per_owner_median_latency_s": {k: sorted(v)[len(v) // 2] for k, v in per.items() if v}}
    print(json.dumps(summary, indent=1))
    return 0


def cmd_dedup(a):
    print("DUPLICATE" if is_duplicate(read(), a.to, a.path) else "OK")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sent"); s.add_argument("--to", required=True); s.add_argument("--to-class", default="")
    s.add_argument("--paths", nargs="+", required=True); s.add_argument("--bytes", type=int, default=0)
    s.add_argument("--by", required=True); s.add_argument("--msg-id", default=""); s.add_argument("--deadline-s", type=int, default=600)
    s.set_defaults(fn=cmd_sent)
    r = sub.add_parser("reply"); r.add_argument("--ask-id", required=True); r.add_argument("--from", dest="from_", required=True)
    r.add_argument("--path", required=True); r.add_argument("--verdict", required=True, choices=["KEEP", "SAFE", "UNKNOWN"])
    r.add_argument("--until", default=""); r.add_argument("--artifact", default=""); r.add_argument("--self-cleaned-bytes", type=int, default=0)
    r.add_argument("--received-ts", default="", help="UTC time the reply arrived (YYYY-MM-DDTHH:MM:SSZ); default now. Use it when recording after the fact.")
    r.set_defaults(fn=cmd_reply)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("pending").set_defaults(fn=cmd_pending)
    d = sub.add_parser("dedup-check"); d.add_argument("--to", required=True); d.add_argument("--path", required=True); d.set_defaults(fn=cmd_dedup)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        print(f"asks error: {e.__class__.__name__}: {e}", file=sys.stderr)
        sys.exit(0)
