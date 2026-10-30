"""The classes disk-reclaim may reclaim on its own (ledger decision auto:<class>), and their live checks.

Shared by disk_census.py, which lists the rows, and disk_reclaim.py, which re-checks every row right
before acting, because a census can be hours old. Every probe fails closed: a timeout, a missing tool
or an unreadable session roster makes a row not eligible, never eligible.

  hook-spool-rotation  append-only spool files over spool-threshold-gb: rename, gzip in place, note it
                       in README-rotation.txt next to the file. Nothing is deleted.
  claude-cli-versions  ~/.local/share/claude/versions/<v> that is not the target of ~/.local/bin/claude,
                       not newer than it, not hard-linked elsewhere, and not used by a running process.
  claude-job-scratch   ~/.claude/jobs/<id>/tmp of a session the roster lists as not working/busy (or no
                       longer lists), with nothing modified in 24 h and nothing open. Only tmp/ goes.
  stale-worktrees      delegated: the installed dehydrate plugin's (0.2.1+) `apply --pressure`, which keeps
                       every one of its own holds. disk-reclaim never removes a worktree or session itself.
                       The ledger row's path is the plugin dir (the gate's key); printed lines and the
                       outcome's `targets` name the worktrees (the dry run asks `plan --pressure --json`).
  claude-desktop-vm    report-only. Never auto; a human may decide it, and only while the app is closed.

Settings are one file each in the state dir, like threshold-gb: auto (true/false, default true),
target-gb (15), headroom-gb (5), spool-threshold-gb (1), spool-files (one path per line).
"""
import glob
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import time

AUTO_CLASSES = ("hook-spool-rotation", "claude-cli-versions", "claude-job-scratch", "stale-worktrees")
REPORT_ONLY = ("claude-desktop-vm",)
ACTIVE_STATES = {"working", "busy", "running"}
SCRATCH_MIN_BYTES = 10 * 1024 * 1024
MIN_DEHYDRATE = (0, 2, 1)  # first dehydrate that holds live sessions' job-dir trees and re-checks before acting


def home():
    return os.path.expanduser("~")


def run(cmd, timeout=60):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except (FileNotFoundError, PermissionError):
        return 127, "", "missing"


def du_bytes(path, timeout=120):
    if os.path.isfile(path) and not os.path.islink(path):
        return os.lstat(path).st_size
    rc, out, _ = run(["du", "-sk", path], timeout=timeout)
    return int(out.split()[0]) * 1024 if out.strip() else -1


def version_key(name):
    return tuple(int(x) for x in re.findall(r"\d+", name or ""))


# ---------- settings ----------

def _read(d, name):
    try:
        return open(os.path.join(d, name)).read().strip()
    except OSError:
        return None


def _num(d, name, default):
    v = _read(d, name)
    try:
        return float(v) if v else default
    except ValueError:
        return default


def auto_config(d):
    raw = (_read(d, "auto") or "true").lower()
    spool = _read(d, "spool-files")
    files = [os.path.expanduser(x.strip()) for x in spool.splitlines() if x.strip() and not x.startswith("#")] \
        if spool is not None else [os.path.join(home(), ".claude", "observatory", "spool.jsonl")]
    return {"auto": raw not in ("false", "0", "no", "off"), "target_gb": _num(d, "target-gb", 15),
            "headroom_gb": _num(d, "headroom-gb", 5), "spool_threshold_gb": _num(d, "spool-threshold-gb", 1),
            "spool_files": files}


# ---------- free space ----------

_FAKE = []


def free_bytes(consume=True):
    """Container free bytes (diskutil apfs list: Capacity Not Allocated), statvfs if diskutil fails.
    DISK_RECLAIM_FAKE_FREE_GB="1,1,30" (tests) feeds the stop checks in order; consume=False peeks."""
    fake = os.environ.get("DISK_RECLAIM_FAKE_FREE_GB")
    if fake:
        if not _FAKE:
            _FAKE.extend(float(x) * 1e9 for x in fake.split(","))
        return int(_FAKE.pop(0) if consume and len(_FAKE) > 1 else _FAKE[0])
    rc, out, _ = run(["diskutil", "apfs", "list"], timeout=30)
    if rc == 0:
        block = out.split("+-- Container", 2)[1] if "+-- Container" in out else out
        m = re.search(r"Capacity Not Allocated:\s+(\d+) B", block)
        if m:
            return int(m.group(1))
    st = os.statvfs("/")
    return st.f_bavail * st.f_frsize


# ---------- shared probes ----------

def lsof_quiet(args, timeout=120):
    """True when lsof lists nothing, False when something is open, None when lsof could not say."""
    rc, out, _ = run(["lsof", *args], timeout=timeout)
    if rc in (124, 127):
        return None
    return not out.strip()


def roster():
    """{background id: state} from `claude agents --json --all`, or None when it cannot be read."""
    rc, out, _ = run(["claude", "agents", "--json", "--all"], timeout=60)
    if rc != 0:
        return None
    try:
        data = json.loads(out or "[]")
    except ValueError:
        return None
    rows = data if isinstance(data, list) else data.get("agents") or data.get("sessions") or []
    return {str(a.get("id")): (a.get("state") or a.get("status") or "").lower() for a in rows if a.get("id")}


def ps_commands():
    rc, out, _ = run(["ps", "-axo", "command"], timeout=30)
    return out if rc == 0 else None


def desktop_running():
    """The Claude desktop app is running. An unreadable process list counts as running."""
    out = ps_commands()
    return out is None or "/Claude.app/Contents/MacOS/Claude" in out


# ---------- claude-job-scratch ----------

def jobs_dir():
    return os.path.join(home(), ".claude", "jobs")


def scratch_eligible(tmp, ro="unset"):
    tmp = os.path.realpath(tmp)
    if os.path.basename(tmp) != "tmp" or os.path.dirname(os.path.dirname(tmp)) != os.path.realpath(jobs_dir()):
        return False, "not a ~/.claude/jobs/<id>/tmp dir"
    if not os.path.isdir(tmp) or os.path.islink(tmp):
        return False, "not a directory"
    jid = os.path.basename(os.path.dirname(tmp))
    if jid == os.path.basename(os.environ.get("CLAUDE_JOB_DIR", "").rstrip("/")):
        return False, "the job running this command"
    if ro == "unset":
        ro = roster()
    if ro is None:
        return False, "session roster (claude agents --json --all) unavailable"
    state = ro.get(jid)
    if state in ACTIVE_STATES:
        return False, f"session {jid} is {state}"
    rc, out, _ = run(["find", tmp, "-mmin", "-1440", "-print", "-quit"], timeout=60)
    if rc == 124:
        return False, "freshness scan timed out"
    if out.strip():
        return False, "a file inside was modified in the last 24 h"
    quiet = lsof_quiet(["+D", tmp])
    if quiet is None:
        return False, "lsof could not finish"
    if not quiet:
        return False, "a process has a file open inside"
    return True, f"session {'no longer listed' if state is None else state}, nothing modified in 24 h, nothing open"


def scratch_rows(row):
    ro = roster()
    out = []
    for tmp in sorted(glob.glob(os.path.join(jobs_dir(), "*", "tmp"))):
        b = du_bytes(tmp)
        if 0 <= b < SCRATCH_MIN_BYTES:
            continue
        ok, why = scratch_eligible(tmp, ro)
        out.append(row("claude-job-scratch", tmp, b, "regenerable" if ok else "evidence", why,
                       f"rm -rf {tmp}" if ok else "none", "job scratch only; state.json and timeline stay",
                       os.path.basename(os.path.dirname(tmp))))
    return out


# ---------- claude-cli-versions ----------

def versions_dir():
    return os.path.join(home(), ".local", "share", "claude", "versions")


def current_version():
    link = os.path.join(home(), ".local", "bin", "claude")
    return os.path.realpath(link) if os.path.lexists(link) else None


def version_eligible(path, ps_out="unset"):
    path = os.path.abspath(path)
    name = os.path.basename(path)
    if os.path.dirname(path) != os.path.realpath(versions_dir()) and os.path.dirname(path) != versions_dir():
        return False, "not under ~/.local/share/claude/versions"
    if not os.path.lexists(path) or os.path.islink(path):
        return False, "missing or a symlink"
    cur = current_version()
    if not cur or not cur.startswith(os.path.realpath(versions_dir()) + "/"):
        return False, "cannot tell the current version (~/.local/bin/claude is not a link into versions/)"
    if os.path.realpath(path) == cur:
        return False, "current version (target of ~/.local/bin/claude)"
    if version_key(name) > version_key(os.path.basename(cur)):
        return False, "newer than the current version (an update in flight)"
    st = os.lstat(path)
    if time.time() - st.st_mtime < 3600:
        return False, "written in the last hour"
    if os.path.isfile(path) and st.st_nlink > 1:
        return False, "hard-linked elsewhere; removing this name frees nothing"
    if ps_out == "unset":
        ps_out = ps_commands()
    if ps_out is None:
        return False, "process list unavailable"
    if re.search(rf"/versions/{re.escape(name)}(\s|/|$)", ps_out, re.M):
        return False, "a running process was started from it"
    quiet = lsof_quiet(["+D", path] if os.path.isdir(path) else [path], timeout=60)
    if quiet is None:
        return False, "lsof could not finish"
    if not quiet:
        return False, "open by a running process"
    return True, f"not current ({os.path.basename(cur)}), older, unused"


def version_rows(row):
    vd = versions_dir()
    if not os.path.isdir(vd):
        return []
    ps_out = ps_commands()
    out = []
    for name in sorted(os.listdir(vd), key=version_key):
        p = os.path.join(vd, name)
        ok, why = version_eligible(p, ps_out)
        out.append(row("claude-cli-versions", p, du_bytes(p), "regenerable" if ok else "evidence", why,
                       f"rm -rf {p}" if ok else "none", "re-downloaded only if you roll back to it"))
    return out


# ---------- hook-spool-rotation ----------

def spool_eligible(path, cfg):
    path = os.path.abspath(os.path.expanduser(path))
    if path not in [os.path.abspath(p) for p in cfg["spool_files"]]:
        return False, "not a configured spool file (spool-files)"
    if not os.path.isfile(path) or os.path.islink(path):
        return False, "missing or not a regular file"
    if not path.startswith(home() + "/"):
        return False, "outside the home directory"
    size = os.path.getsize(path)
    if size < cfg["spool_threshold_gb"] * 1e9:
        return False, f"{size / 1e9:.2f} GB, under the {cfg['spool_threshold_gb']:g} GB threshold"
    return True, f"append-only spool over {cfg['spool_threshold_gb']:g} GB; rotate and gzip, nothing deleted"


def spool_rows(row, cfg):
    out = []
    for p in cfg["spool_files"]:
        if not os.path.isfile(p):
            continue
        ok, why = spool_eligible(p, cfg)
        if ok or os.path.getsize(p) >= 100 * 1024 * 1024:
            out.append(row("hook-spool-rotation", p, os.path.getsize(p), "regenerable" if ok else "evidence", why,
                           "rotate-gzip" if ok else "none", "none: gunzip the archive to get the exact bytes back"))
    return out


def rotate_spool(path, who="disk-reclaim"):
    """Rename, gzip in place, note it. Returns (ok, note, bytes_freed). Writers that reopen by path
    start a fresh file; if the renamed file still grows while it is compressed, the .gz is dropped and
    the renamed file stays as it is, so nothing written meanwhile is lost."""
    d, base = os.path.split(path)
    stem, ext = os.path.splitext(base)
    stamp = time.strftime("%Y-%m-%dT%H%M")
    arch = os.path.join(d, f"{stem}.archive-{stamp}{ext}")
    n = 1
    while os.path.exists(arch) or os.path.exists(arch + ".gz"):
        n += 1
        arch = os.path.join(d, f"{stem}.archive-{stamp}-{n}{ext}")
    size = os.path.getsize(path)
    os.rename(path, arch)
    note_line = f"{base} ({size / 1e9:.2f} GB) renamed to {os.path.basename(arch)}"
    if free_bytes(consume=False) < size:
        note = note_line + "; not compressed (free space under the file's size). Nothing deleted."
    else:
        tmp = arch + ".gz.tmp"
        with open(arch, "rb") as src, gzip.open(tmp, "wb", compresslevel=6) as dst:
            shutil.copyfileobj(src, dst, 1 << 20)
        if os.path.getsize(arch) != size:
            os.remove(tmp)
            note = note_line + "; still being written, left uncompressed. Nothing deleted."
        else:
            os.replace(tmp, arch + ".gz")
            os.remove(arch)
            note = note_line + f" and gzip-compressed to {os.path.basename(arch)}.gz. Nothing deleted: gunzip it to restore the exact bytes."
    with open(os.path.join(d, "README-rotation.txt"), "a") as f:
        f.write(f"spool rotation {time.strftime('%Y-%m-%d %H:%M %Z')} ({who}): {note}\n")
    gz = arch + ".gz"
    freed = size - (os.path.getsize(gz) if os.path.exists(gz) else size)
    return True, note, freed


# ---------- stale-worktrees (delegated to dehydrate) ----------

def find_dehydrate():
    """(plugin dir, script) of the newest installed dehydrate that has --pressure, else (None, why)."""
    base = os.path.join(home(), ".claude", "plugins", "cache", "getfatday-skills", "dehydrate")
    vers = sorted((v for v in glob.glob(os.path.join(base, "*")) if os.path.isfile(os.path.join(v, "scripts", "dehydrate.py"))),
                  key=lambda v: version_key(os.path.basename(v)))
    if not vers:
        return None, "dehydrate plugin not installed"
    v = vers[-1]
    if version_key(os.path.basename(v)) < MIN_DEHYDRATE:
        return None, f"installed dehydrate {os.path.basename(v)} predates the job-dir holds and pre-removal re-checks (needs 0.2.1+)"
    return v, os.path.join(v, "scripts", "dehydrate.py")


def stale_worktrees_eligible(path):
    v, script = find_dehydrate()
    if not v:
        return False, script
    if os.path.realpath(path) != os.path.realpath(v):
        return False, f"not the newest installed dehydrate ({v})"
    return True, f"delegated to dehydrate {os.path.basename(v)} apply --pressure (all of its holds apply)"


def stale_worktrees_rows(row):
    v, script = find_dehydrate()
    if not v:
        return [row("stale-worktrees", "dehydrate", -1, "evidence", script, "none", "install dehydrate 0.2.1+")]
    est = 0
    try:
        plan = json.load(open(os.path.join(home(), ".claude", "dehydrated", "last-plan.json")))
        est = int(plan["totals"]["reclaim_kb"]) * 1024
    except Exception:
        pass
    return [row("stale-worktrees", v, est, "unknown", f"delegated to dehydrate {os.path.basename(v)} apply --pressure "
                "(its last plan's estimate; every dehydrate hold applies)", "dehydrate-pressure",
                "rehydrate brings any worktree and session back")]


def short(p):
    return p.replace(home(), "~", 1) if p.startswith(home()) else p


def pressure_targets(path, goal_gb):
    """The worktrees dehydrate's read-only `plan --pressure` would take, in order, up to its estimated stop (all
    of them when it expects not to reach the goal). None when the plan cannot be read."""
    rc, out, _ = run([sys.executable, os.path.join(path, "scripts", "dehydrate.py"), "plan", "--json", "--pressure",
                      "--target-gb", f"{goal_gb:g}"], timeout=1800)
    try:
        pr = json.loads(out)["pressure"]
        order, est = list(pr["order"]), pr.get("estimated_stop_after")
    except (ValueError, KeyError, TypeError):
        return None
    return order[:est] if est else order


def run_dehydrate(path, goal_gb):
    """Returns (ok, note, worktree paths removed). A held dehydrate lock is a skip, not a failure."""
    ok, why = stale_worktrees_eligible(path)
    if not ok:
        return False, why, []
    script = os.path.join(path, "scripts", "dehydrate.py")
    # dehydrate measures statvfs("/"), this plugin the APFS container; the headroom absorbs the gap
    rc, out, err = run([sys.executable, script, "apply", "--yes", "--json", "--pressure", "--target-gb", f"{goal_gb:g}"],
                       timeout=6 * 3600)
    if "holds the lock" in (out + err):
        return False, "skipped: another dehydrate run holds its lock", []
    try:
        res = json.loads(out)
    except ValueError:
        return False, f"dehydrate rc={rc}: {(err or out).strip()[:300]}", []
    removed = [w["path"] for w in res.get("worktrees", []) if w.get("removed") and w.get("path")]
    done = sum(1 for w in res.get("worktrees", []) if w.get("removed"))
    bad = sum(1 for w in res.get("worktrees", []) if not w.get("ok"))
    closed = sum(1 for s in res.get("sessions", []) if s.get("ok"))
    note = (f"dehydrate rc={rc}: {done} worktree(s) dehydrated, {closed} session(s) closed, {bad} not done; "
            f"pressure={json.dumps(res.get('pressure'))}" + (f"; paused: {res['paused']}" if res.get("paused") else ""))
    return rc in (0, 1, 3), note, removed


# ---------- dispatch ----------

def eligible(row, cfg=None, d=None):
    """Live re-check for one census row of an auto class. (ok, why)."""
    cls, path = row.get("class"), row.get("path", "")
    if cls == "claude-job-scratch":
        return scratch_eligible(path)
    if cls == "claude-cli-versions":
        return version_eligible(path)
    if cls == "hook-spool-rotation":
        return spool_eligible(path, cfg or auto_config(d or os.path.join(home(), ".claude", "disk-reclaim")))
    if cls == "stale-worktrees":
        return stale_worktrees_eligible(path)
    return False, f"class {cls} is not reclaimed automatically"


def census_rows(row, d):
    cfg = auto_config(d)
    rows = []
    for fn in (lambda: spool_rows(row, cfg), lambda: version_rows(row), lambda: scratch_rows(row),
               lambda: stale_worktrees_rows(row)):
        try:
            rows.extend(fn())
        except Exception as e:  # a broken class never kills the census
            rows.append(row("census-error", "auto-classes", -1, "unknown", f"{e.__class__.__name__}: {e}"))
    return rows


def auto_order(rows):
    """The fixed order auto-reclaim works in: spools, old CLI versions, job scratch largest first, dehydrate."""
    rank = {c: i for i, c in enumerate(AUTO_CLASSES)}
    sel = [r for r in rows if r.get("class") in rank and r.get("reclaim_cmd", "none") != "none"]
    return sorted(sel, key=lambda r: (rank[r["class"]], -max(r.get("measured_bytes") or 0, 0)))
