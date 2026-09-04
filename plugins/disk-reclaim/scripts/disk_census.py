#!/usr/bin/env python3
"""Read-only disk census for a macOS developer laptop.

Measures a fixed inventory of waste classes against the APFS container total and prints a ranked
table (default) or JSON ledger records (--json). Never deletes anything.

Every row carries: class, path, bytes, safety (regenerable | evidence | unknown), safety_basis,
reclaim_cmd (or "none"), reclaim_cost, owner_session where known.

--ledger writes <state>/last-census.json and appends one summary line to <state>/census-log.jsonl,
where <state> is ~/.claude/disk-reclaim (or $DISK_RECLAIM_DIR). --detach forks the census into its own
process session and returns immediately, so a hook can start it and exit; nohup alone is not enough
because the CLI kills the hook's process group at teardown. --if-stale N makes the run a no-op
when the ledger is younger than N seconds or another census holds <state>/census.lock, which is
what lets a SessionEnd hook call it from every session without running it from every session.

Design notes:
- `df /` on macOS reports the sealed system volume's usage; only `diskutil apfs list` gives the
  container truth. Both are reported so the gap is visible.
- Simulator runtimes are separate disk images; `simctl delete unavailable` never removes them.
  Runtimes with zero devices are listed as regenerable.
- Worktrees are classified from git facts: dirty tree, unpushed commits, or no upstream means
  evidence; clean and pushed means unknown (an owner may still be using it); a live job whose
  cwd is inside the worktree means evidence.
- `du` exits 1 on any permission-denied subdirectory but still prints the total; the total is
  trusted whenever it is printed. Only a timeout yields -1.
- Every external command has a timeout; a timeout yields a row with bytes=-1 and safety=unknown
  rather than a crash. Exit code is always 0.
- A full census on a machine with 150 worktrees takes 2 to 5 minutes and is I/O bound. Run it
  detached (the hook does) or in a background shell, never inline in a turn someone is waiting on.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import glob
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from disk_state import state_dir  # noqa: E402

HOME = os.path.expanduser("~")
NOW = datetime.now(timezone.utc).isoformat(timespec="seconds")


def run(cmd, timeout=60):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except FileNotFoundError:
        return 127, "", "missing"


def du_bytes(path, timeout=90):
    if not os.path.exists(path):
        return 0
    rc, out, _ = run(["du", "-sk", path], timeout=timeout)
    if not out.strip():
        return -1
    return int(out.split()[0]) * 1024


def row(cls, path, nbytes, safety, basis, cmd="none", cost="", owner=""):
    return {
        "class": cls, "path": path, "measured_bytes": nbytes, "measured_at": NOW,
        "safety": safety, "safety_basis": basis, "reclaim_cmd": cmd, "reclaim_cost": cost,
        "owner_session": owner, "decision": "pending",
    }


# ---------- container truth ----------

def container_totals():
    """Return (container_size, in_use, not_allocated, df_used, df_avail) in bytes."""
    size = in_use = free = None
    rc, out, _ = run(["diskutil", "apfs", "list"], timeout=30)
    if rc == 0:
        block = out.split("+-- Container", 2)[1] if "+-- Container" in out else out
        m = re.search(r"Size \(Capacity Ceiling\):\s+(\d+) B", block)
        size = int(m.group(1)) if m else None
        m = re.search(r"Capacity In Use By Volumes:\s+(\d+) B", block)
        in_use = int(m.group(1)) if m else None
        m = re.search(r"Capacity Not Allocated:\s+(\d+) B", block)
        free = int(m.group(1)) if m else None
    df_used = df_avail = None
    rc, out, _ = run(["df", "-k", "/"], timeout=10)
    if rc == 0 and len(out.splitlines()) > 1:
        parts = out.splitlines()[1].split()
        df_used = int(parts[2]) * 1024
        df_avail = int(parts[3]) * 1024
    return size, in_use, free, df_used, df_avail


# ---------- live jobs (owner attribution) ----------

def live_jobs():
    jobs = {}
    for sp in glob.glob(os.path.join(HOME, ".claude", "jobs", "*", "state.json")):
        jid = os.path.basename(os.path.dirname(sp))
        try:
            s = json.load(open(sp))
        except Exception:
            continue
        jobs[jid] = {"name": s.get("name") or s.get("title") or "",
                     "status": s.get("status") or s.get("state") or "",
                     "cwd": s.get("cwd") or ""}
    return jobs


def owner_for(path, jobs):
    real = os.path.realpath(path)
    for jid, j in jobs.items():
        cwd = j.get("cwd") or ""
        if cwd and os.path.realpath(cwd).startswith(real):
            return f"{j['name'] or jid} ({j['status'] or 'unknown'})"
    return ""


# ---------- classes ----------

def class_simulators(rows):
    rc, out, _ = run(["xcrun", "simctl", "list", "devices", "-j"], timeout=30)
    devices_by_rt = {}
    if rc == 0:
        try:
            for rt, devs in json.loads(out)["devices"].items():
                devices_by_rt[rt] = devs
        except Exception:
            pass
    rc, out, _ = run(["xcrun", "simctl", "runtime", "list", "-j"], timeout=30)
    if rc == 0:
        try:
            for key, r in json.loads(out).items():
                ident = r.get("runtimeIdentifier") or key
                path = r.get("path") or ""
                size = r.get("sizeBytes") or (du_bytes(path) if path else -1)
                n = len(devices_by_rt.get(ident, []))
                if n == 0:
                    rows.append(row("sim-runtime", path or ident, size, "regenerable",
                                    "zero devices use this runtime",
                                    f"xcrun simctl runtime delete {r.get('identifier', ident)}",
                                    "re-download ~8 GB via Xcode > Components"))
                else:
                    rows.append(row("sim-runtime", path or ident, size, "evidence",
                                    f"{n} device(s) still use this runtime", "none",
                                    "delete devices first, then the runtime"))
        except Exception:
            pass
    dev_root = os.path.join(HOME, "Library/Developer/CoreSimulator/Devices")
    for rt, devs in devices_by_rt.items():
        for d in devs:
            p = os.path.join(dev_root, d["udid"])
            b = du_bytes(p, timeout=60)
            name = d.get("name", "")
            if b < 64 * 1024 * 1024:
                continue  # default shells are ~17 MB; not worth a row
            tagged = bool(re.search(r"[A-Z]-?\d{3}|run-\d|\(.+\)", name))
            rows.append(row("sim-device", f"{p} [{name}]", b,
                            "evidence" if tagged else "unknown",
                            "name carries an experiment or project tag" if tagged else "no owner tag in name",
                            f"xcrun simctl delete {d['udid']}", "recreate from runtime in seconds"))


def _worktree_row(wt, jobs):
    b = du_bytes(wt, timeout=120)
    rc, dirty, _ = run(["git", "-C", wt, "status", "--porcelain"], timeout=30)
    dirty_n = len(dirty.splitlines()) if rc == 0 else -1
    rc, ahead, _ = run(["git", "-C", wt, "rev-list", "--count", "@{u}..HEAD"], timeout=30)
    ahead_n = int(ahead.strip()) if rc == 0 and ahead.strip().isdigit() else -1
    rc, last, _ = run(["git", "-C", wt, "log", "-1", "--format=%cs"], timeout=30)
    owner = owner_for(wt, jobs)
    if owner and "done" not in owner:
        safety, basis = "evidence", f"live job cwd inside: {owner}"
    elif dirty_n > 0 or ahead_n > 0 or ahead_n == -1:
        safety, basis = "evidence", f"dirty={dirty_n} unpushed={'no upstream' if ahead_n == -1 else ahead_n} last={last.strip()}"
    else:
        safety, basis = "unknown", f"clean, pushed, last={last.strip()}; owner may still use it"
    main = wt.split("/.claude/worktrees/")[0] if "/.claude/worktrees/" in wt else ""
    cmd = f"git -C {main or '<main-checkout>'} worktree remove {wt} && git -C {main or '<main-checkout>'} worktree prune"
    return row("git-worktree", wt, b, safety, basis, cmd,
               "re-checkout seconds; node_modules reinstall 1-3 min", owner)


def class_worktrees(rows, jobs):
    patterns = [os.path.join(HOME, "src", "*__worktrees", "*"),
                os.path.join(HOME, "src", "*", ".claude", "worktrees", "*")]
    wts = [wt for pat in patterns for wt in sorted(glob.glob(pat))
           if os.path.isdir(wt) and not os.path.basename(wt).startswith("wf_")]
    with ThreadPoolExecutor(max_workers=8) as ex:
        rows.extend(ex.map(lambda wt: _worktree_row(wt, jobs), wts))


def _repo_row(repo):
    rc, out, _ = run(["du", "-sk", "-I", ".git", "-I", "node_modules", "-I", "worktrees", repo], timeout=120)
    b = int(out.split()[0]) * 1024 if out.strip() else -1
    rc, dirty, _ = run(["git", "-C", repo, "status", "--porcelain"], timeout=30)
    dirty_n = len(dirty.splitlines()) if rc == 0 else -1
    rc, last, _ = run(["git", "-C", repo, "log", "-1", "--format=%cs"], timeout=30)
    return row("repo-checkout", repo, b, "evidence",
               f"main checkout, dirty={dirty_n} last={last.strip()}", "none",
               "re-clone; check it is not a __worktrees parent")


def class_repos(rows):
    repos = [p for p in sorted(glob.glob(os.path.join(HOME, "src", "*")))
             if os.path.isdir(os.path.join(p, ".git")) and not p.endswith("__worktrees")]
    with ThreadPoolExecutor(max_workers=8) as ex:
        rows.extend(r for r in ex.map(_repo_row, repos) if r["measured_bytes"] > 200 * 1024 * 1024)


def class_node_modules(rows):
    seen = set()
    for pat in [os.path.join(HOME, "src", "*", "node_modules"),
                os.path.join(HOME, "src", "*", "*", "node_modules")]:
        for p in glob.glob(pat):
            if "/.claude/worktrees/" in p or "__worktrees" in p or p in seen:
                continue  # counted inside the worktree row
            seen.add(p)
            b = du_bytes(p, timeout=90)
            if b > 100 * 1024 * 1024:
                rows.append(row("node-modules", p, b, "regenerable", "package install output",
                                f"rm -rf {p}", "pnpm install ~1 min from store; npm 3-10 min"))


def class_caches(rows):
    fixed = [
        ("pkg-cache", os.path.join(HOME, ".cache/uv"), "uv cache prune", "re-download on next uv run"),
        ("pkg-cache", os.path.join(HOME, ".cache/puppeteer"), "rm -rf ~/.cache/puppeteer", "browser re-download ~300 MB"),
        ("pkg-cache", os.path.join(HOME, ".npm/_npx"), "rm -rf ~/.npm/_npx", "npx re-downloads on demand"),
        ("pkg-cache", os.path.join(HOME, ".npm/_cacache"), "npm cache clean --force", "re-download on next install"),
        ("pkg-cache", os.path.join(HOME, "Library/Caches/ms-playwright"), "rm -rf ~/Library/Caches/ms-playwright", "browsers re-download ~2 GB on next test run"),
        ("pkg-cache", os.path.join(HOME, "Library/Caches/org.swift.swiftpm"), "rm -rf ~/Library/Caches/org.swift.swiftpm", "packages re-resolve"),
        ("pkg-cache", os.path.join(HOME, "Library/Caches/node-gyp"), "rm -rf ~/Library/Caches/node-gyp", "headers re-download"),
        ("pkg-cache", os.path.join(HOME, "Library/Caches/pip"), "rm -rf ~/Library/Caches/pip", "wheels re-download"),
        ("build-cache", os.path.join(HOME, "Library/Developer/Xcode/DerivedData"), "rm -rf ~/Library/Developer/Xcode/DerivedData", "full rebuild"),
        ("vm-bundle", os.path.join(HOME, "Library/Application Support/Claude/vm_bundles"), "quit Claude desktop, then rm -rf the bundle", "re-download ~12 GB on next Cowork use"),
        ("docker-image", os.path.join(HOME, "Library/Containers/com.docker.docker/Data/vms/0/data"), "docker system prune, then Docker Desktop Clean/Purge", "images rebuild or re-pull"),
        ("plugin-cache", os.path.join(HOME, ".claude/plugins"), "reinstall plugins", "re-download"),
    ]
    for cls, p, cmd, cost in fixed:
        b = du_bytes(p)
        if b > 50 * 1024 * 1024:
            safety = "regenerable" if cls in ("pkg-cache", "build-cache", "plugin-cache") else "unknown"
            basis = "regenerated on demand" if safety == "regenerable" else "app-owned; check the app is not running"
            rows.append(row(cls, p, b, safety, basis, cmd, cost))
    rc, out, _ = run(["pnpm", "store", "path"], timeout=15)
    current = out.strip() if rc == 0 else ""
    for p in glob.glob(os.path.join(HOME, "Library/pnpm/store/v*")):
        b = du_bytes(p)
        if b <= 0:
            continue
        if current and os.path.realpath(p) == os.path.realpath(current):
            rows.append(row("pkg-store", p, b, "evidence", "current pnpm store; projects symlink into it",
                            "pnpm store prune", "removes only unreferenced packages"))
        else:
            rows.append(row("pkg-store", p, b, "regenerable", f"orphaned store; current is {current or 'unknown'}",
                            f"rm -rf {p}", "nothing; installs already use the current store"))


def class_claude(rows, jobs):
    for jid, j in jobs.items():
        p = os.path.join(HOME, ".claude/jobs", jid)
        b = du_bytes(p)
        if b < 50 * 1024 * 1024:
            continue
        live = j["status"] not in ("done", "stopped", "")
        rows.append(row("claude-job", p, b, "evidence" if live else "unknown",
                        f"job '{j['name']}' status={j['status'] or 'unknown'}",
                        "none" if live else f"rm -rf {p} after confirming no process has cwd under it",
                        "job scratch; ask the owning session", f"{j['name']} ({j['status']})"))
    for p in glob.glob(os.path.join(HOME, ".claude/projects/*")):
        b = du_bytes(p)
        if b > 200 * 1024 * 1024:
            rows.append(row("claude-transcripts", p, b, "unknown", "needed for claude --resume of those sessions",
                            f"rm -rf {p} (loses resume history for that project)", "resume history only"))


def class_git_objects(rows):
    for g in glob.glob(os.path.join(HOME, "src", "*", ".git")):
        if not os.path.isdir(g):
            continue
        b = du_bytes(g, timeout=60)
        if b > 500 * 1024 * 1024:
            repo = os.path.dirname(g)
            rows.append(row("git-objects", g, b, "unknown",
                            "mostly packs and worktree admin; gc saves little",
                            f"git -C {repo} maintenance run --task=incremental-repack; git -C {repo} worktree prune",
                            "minutes; never plain gc on a repo with live worktrees"))


def class_home(rows):
    for name in ("Downloads", "Documents", "Desktop", "Movies", "Pictures", "Music"):
        p = os.path.join(HOME, name)
        b = du_bytes(p, timeout=120)
        if b > 1024 ** 3:
            rows.append(row("home-folder", p, b, "unknown", "user files; never auto-reclaim", "none", "human decision only"))
    for p in glob.glob(os.path.join(HOME, "Library/Application Support/*")):
        if p.endswith("/Claude"):
            continue  # vm_bundles is its own row
        b = du_bytes(p, timeout=90)
        if b > 1024 ** 3:
            rows.append(row("app-support", p, b, "unknown", "app-owned data; reclaim through the app", "none", "app settings"))
    counted = {"Application Support", "Caches", "Developer", "pnpm", "Containers"}
    system = [p for p in glob.glob(os.path.join(HOME, "Library/*")) if os.path.basename(p) not in counted]
    system += ["/Applications", "/Library", "/private/var", "/opt", "/usr/local"]
    with ThreadPoolExecutor(max_workers=6) as ex:
        sizes = list(ex.map(lambda p: (p, du_bytes(p, timeout=120)), system))
    for p, b in sizes:
        if b > 1024 ** 3:
            rows.append(row("system", p, b, "evidence", "OS, applications, or app containers; not developer waste",
                            "none", "not reclaimable by this skill"))
    listed = {"ms-playwright", "org.swift.swiftpm", "node-gyp", "pip"}
    for p in glob.glob(os.path.join(HOME, "Library/Caches/*")):
        if os.path.basename(p) in listed:
            continue
        b = du_bytes(p, timeout=60)
        if b > 200 * 1024 * 1024:
            rows.append(row("library-cache", p, b, "regenerable", "app cache; rebuilt on next launch",
                            f"rm -rf '{p}' while the app is closed", "cold start once"))


# ---------- output ----------

def human(rows, totals, elapsed):
    size, in_use, free, df_used, df_avail = totals
    gb = lambda b: f"{b/1e9:6.1f} GB" if isinstance(b, int) and b >= 0 else "   n/a  "
    print(f"container: size {gb(size)}  in use {gb(in_use)}  free {gb(free)}")
    print(f"df /     : used {gb(df_used)}  avail {gb(df_avail)}   (df understates; trust the container line)")
    measured = sum(r["measured_bytes"] for r in rows if r["measured_bytes"] > 0)
    cov = (measured / in_use * 100) if in_use else 0
    print(f"measured : {gb(measured)} across {len(rows)} rows = {cov:.0f}% of in-use   ({elapsed:.0f}s)")
    print()
    print(f"{'size':>9}  {'safety':<11} {'class':<18} path  [basis]")
    for r in sorted(rows, key=lambda r: -r["measured_bytes"]):
        p = r["path"].replace(HOME, "~")
        print(f"{gb(r['measured_bytes'])}  {r['safety']:<11} {r['class']:<18} {p}  [{r['safety_basis']}]")
    by = {}
    for r in rows:
        by[r["safety"]] = by.get(r["safety"], 0) + max(r["measured_bytes"], 0)
    print()
    print("by safety: " + "  ".join(f"{k}={gb(v).strip()}" for k, v in sorted(by.items())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="print ledger records as JSON")
    ap.add_argument("--ledger", action="store_true", help="write last-census.json and append census-log.jsonl in the state dir")
    ap.add_argument("--if-stale", type=int, default=0, metavar="SECONDS",
                    help="skip when last-census.json is younger than this, or another census holds the lock")
    ap.add_argument("--detach", action="store_true",
                    help="fork into a new process session and return at once; the census survives the caller's exit")
    a = ap.parse_args()
    d = state_dir()
    if a.detach:
        # Hooks run in the CLI's process group, which is killed at teardown; nohup does not help.
        # Double-fork with setsid puts the census in its own session so it outlives the hook.
        if os.fork() != 0:
            return 0
        os.setsid()
        if os.fork() != 0:
            os._exit(0)
        devnull = os.open(os.devnull, os.O_RDWR)
        for fd in (0, 1, 2):
            os.dup2(devnull, fd)
        a.ledger = True
    if a.if_stale:
        last = os.path.join(d, "last-census.json")
        if os.path.exists(last) and time.time() - os.stat(last).st_mtime < a.if_stale:
            return 0
        lock = os.path.join(d, "census.lock")
        try:
            pid = int(open(lock).read().strip() or 0)
            os.kill(pid, 0)
            return 0  # a live census owns the lock
        except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
            pass
        with open(lock, "w") as f:
            f.write(str(os.getpid()))
    t0 = time.time()
    rows = []
    totals = container_totals()
    jobs = live_jobs()
    for fn in (lambda: class_simulators(rows), lambda: class_worktrees(rows, jobs),
               lambda: class_repos(rows), lambda: class_node_modules(rows),
               lambda: class_caches(rows), lambda: class_claude(rows, jobs),
               lambda: class_git_objects(rows), lambda: class_home(rows)):
        try:
            fn()
        except Exception as e:  # a broken class never kills the census
            rows.append(row("census-error", fn.__name__, -1, "unknown", f"{e.__class__.__name__}: {e}"))
    elapsed = time.time() - t0
    size, in_use, free, df_used, df_avail = totals
    summary = {
        "measured_at": NOW, "elapsed_s": round(elapsed, 1),
        "container_bytes": size, "in_use_bytes": in_use, "free_bytes": free,
        "df_used_bytes": df_used, "df_avail_bytes": df_avail,
        "rows": len(rows),
        "measured_bytes": sum(r["measured_bytes"] for r in rows if r["measured_bytes"] > 0),
        "regenerable_bytes": sum(r["measured_bytes"] for r in rows if r["safety"] == "regenerable" and r["measured_bytes"] > 0),
        "top": [{"path": r["path"], "bytes": r["measured_bytes"], "safety": r["safety"], "reclaim_cmd": r["reclaim_cmd"]}
                for r in sorted(rows, key=lambda r: -r["measured_bytes"])[:5]],
    }
    if a.ledger:
        tmp = os.path.join(d, "last-census.json.tmp")
        with open(tmp, "w") as f:
            json.dump({"summary": summary, "rows": rows}, f, indent=1)
        os.replace(tmp, os.path.join(d, "last-census.json"))
        with open(os.path.join(d, "census-log.jsonl"), "a") as f:
            f.write(json.dumps(summary) + "\n")
        try:
            os.remove(os.path.join(d, "census.lock"))
        except FileNotFoundError:
            pass
    if a.json:
        print(json.dumps({"summary": summary, "rows": rows}, indent=1))
    elif not a.ledger:
        human(rows, totals, elapsed)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"census failed: {e.__class__.__name__}: {e}", file=sys.stderr)
        sys.exit(0)
