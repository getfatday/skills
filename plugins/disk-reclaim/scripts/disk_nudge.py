#!/usr/bin/env python3
"""SessionStart hook: print one DISK_RECLAIM line when free disk is below threshold, else nothing.

Contract: fast, silent, never fails visibly, exit 0 always. Sub-millisecond in-process; the cost
is the interpreter start (about 0.2 s end to end).

Reads  <state>/threshold-gb     integer GB; default 30
       <state>/cooldown-hours   hours between nudges across ALL sessions; default 4
       <state>/snooze           regular file; silent while its mtime is under 24 h old
       <state>/last-census.json optional; names the top three regenerable items
Writes <state>/last-nudged      stamp, so twelve sessions starting in an hour produce one line
       <state>/hook-log.jsonl   one line per firing

Free space is os.statvfs("/").f_bavail: the container-wide free figure. (df's USED column
understates on macOS because it reads the sealed system volume; AVAIL is fine.)
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from disk_state import state_dir  # noqa: E402

T0 = time.perf_counter()


def read_int(path, default):
    try:
        return int("".join(ch for ch in open(path).read() if ch.isdigit()) or default)
    except Exception:
        return default


def main():
    d = state_dir()
    threshold = read_int(os.path.join(d, "threshold-gb"), 30)
    cooldown_s = read_int(os.path.join(d, "cooldown-hours"), 4) * 3600
    st = os.statvfs("/")
    free_gb = st.f_bavail * st.f_frsize // (1024 ** 3)
    snooze = os.path.join(d, "snooze")
    snoozed = os.path.isfile(snooze) and time.time() - os.stat(snooze).st_mtime < 86400
    stamp = os.path.join(d, "last-nudged")
    cooling = os.path.isfile(stamp) and time.time() - os.stat(stamp).st_mtime < cooldown_s
    fired = False
    if not snoozed and not cooling and free_gb < threshold:
        fired = True
        top = ""
        try:
            c = json.load(open(os.path.join(d, "last-census.json")))
            regen = sorted((r for r in c.get("rows", [])
                            if r.get("safety") == "regenerable" and r.get("measured_bytes", 0) > 0),
                           key=lambda r: -r["measured_bytes"])[:3]
            home = os.path.expanduser("~")
            top = "; ".join(f"{r['measured_bytes']/1e9:.1f} GB {r['path'].replace(home, '~')}" for r in regen)
        except Exception:
            pass
        print(f"DISK_RECLAIM: {free_gb} GB free on / (threshold {threshold} GB). "
              f"Run the disk-reclaim skill when this turn's work is done."
              + (f" Regenerable now: {top}." if top else "")
              + f" Snooze 24h: touch {d}/snooze")
        with open(stamp, "w") as f:
            f.write(str(int(time.time())))
    ms = int((time.perf_counter() - T0) * 1000)
    with open(os.path.join(d, "hook-log.jsonl"), "a") as f:
        f.write(json.dumps({"hook": "disk-nudge", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "free_gb": free_gb, "threshold_gb": threshold, "snoozed": snoozed,
                            "cooling": cooling, "fired": fired, "ms_in_process": ms}) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
