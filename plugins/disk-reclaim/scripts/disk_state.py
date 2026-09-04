"""Shared state-directory resolution for the disk-reclaim scripts.

State lives in ONE place per user, not per repo: ~/.claude/disk-reclaim/ (override with
DISK_RECLAIM_DIR). The disk is a machine-wide resource; a per-project ledger would fork the
threshold, snooze, and staleness clocks across every repo a person works in.
"""
import os


def state_dir():
    d = os.environ.get("DISK_RECLAIM_DIR") or os.path.join(os.path.expanduser("~"), ".claude", "disk-reclaim")
    os.makedirs(d, exist_ok=True)
    return d
