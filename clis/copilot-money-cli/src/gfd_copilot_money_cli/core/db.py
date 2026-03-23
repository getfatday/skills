"""LevelDB access for Copilot Money's local Firestore cache."""

from __future__ import annotations

import atexit
import glob
import os
import shutil
import tempfile

import plyvel

COPILOT_BASE = os.path.expanduser(
    "~/Library/Containers/com.copilot.production/Data/Library/"
    "Application Support/firestore/__FIRAPP_DEFAULT"
)


def find_cache_dir() -> str:
    """Locate the Copilot Money LevelDB cache directory."""
    pattern = os.path.join(COPILOT_BASE, "copilot-*/main")
    matches = glob.glob(pattern)
    if not matches:
        raise FileNotFoundError(
            "Copilot Money cache not found. Is the app installed and synced?\n"
            "Install: https://copilot.money"
        )
    return matches[0]


def open_db() -> plyvel.DB:
    """Open a read-only copy of the LevelDB cache.

    Copies the database to a temp directory (skipping the LOCK file)
    so we don't interfere with the running Copilot app.
    """
    src = find_cache_dir()
    tmp = tempfile.mkdtemp(prefix="copilot-leveldb-")
    for item in os.listdir(src):
        if item == "LOCK":
            continue
        s = os.path.join(src, item)
        d = os.path.join(tmp, item)
        if os.path.isfile(s):
            shutil.copy2(s, d)
    db = plyvel.DB(tmp, create_if_missing=False)
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    return db
