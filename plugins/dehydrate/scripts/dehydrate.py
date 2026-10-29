#!/usr/bin/env python3
"""dehydrate: close stale Claude Code sessions and worktrees without losing work, and bring them back.

Subcommands
  plan       read-only census + decision (default). Prints what apply would do.
  apply      snapshot, verify, archive, then remove stale worktrees and close stale sessions.
             plan/apply --pressure --target-gb N: disk-pressure mode (idle window ignored for worktrees,
             least recently active first, one at a time, stop once free disk >= N; every hold applies).
  list       search the manifest (what was dehydrated, when, what it was about).
  show       print one manifest record.
  rehydrate  recreate a dehydrated worktree (branch, dirty state, ignored files) and its sessions.
  nudge      SessionStart hook: one line when the cached plan has work, throttled. Never fails.
  refresh    write <state>/last-plan.json (what the nudge reads). --detach to run in background.

Everything it decides is deterministic: the same census and the same --now give the same plan.

Storage (user level, one place for every repo)
  <state> = $DEHYDRATE_HOME or ~/.claude/dehydrated
  <state>/manifest.jsonl     append-only event log, one JSON object per line
  <state>/index.md           human-readable view, regenerated from the manifest
  <state>/archive/<id>/      snapshot.bundle, ignored.tar.gz, transcripts/*.jsonl.gz, job.tar.gz
  <state>/config.json        optional overrides (days, roots, exclude_globs, caps, auto_apply)

A worktree snapshot is a commit built on a temporary index (tracked changes, staged changes and
untracked files; HEAD as parent) stored at refs/dehydrated/<id> in its repo and in a git bundle in
the archive. No branch moves, nothing is committed to main, nothing is pushed.
Stdlib only, Python 3.9+.
"""
import argparse
import contextlib
import datetime as dt
import fcntl
import fnmatch
import gzip
import hashlib
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time

SCHEMA = 1
HERE = os.path.dirname(os.path.abspath(__file__))
ACTIVE_STATES = {"working", "busy", "running"}
PRESSURE_RELEASE_STATES = {"done", "blocked"}

DEFAULTS = {
    "days": 7,
    "roots": ["~/src"],
    "root_depth": 2,
    # Worktrees another system owns (Hermes kanban workspaces). Reported, never touched.
    "exclude_globs": ["*/.worktrees/t_*", "~/.hermes/*"],
    "untracked_cap_mb": 500,
    "untracked_file_cap_mb": 100,
    "ignored_cap_mb": 300,
    "orphan_cap_mb": 1024,
    "job_tmp_cap_mb": 200,
    "disk_floor_gb": 2,
    "snapshot_main": False,  # main checkouts: opt in with --mains (git status on every repo is slow)
    "nudge_cooldown_hours": 24,
    "refresh_after_hours": 6,
    "auto_apply": False,
    "regenerable": {
        # Only names that are always tool output. Ambiguous ones (build, dist, out, target, .cache,
        # *.log) are archived like any other gitignored file, subject to ignored_cap_mb.
        "dir_names": ["node_modules", ".gradle", "DerivedData", ".venv", "venv", "__pycache__",
                      ".pytest_cache", ".mypy_cache", ".ruff_cache", ".next", ".turbo", "Pods", ".build",
                      ".parcel-cache", ".tox", ".eggs", ".swiftpm", ".kotlin"],
        "file_names": [".DS_Store"],
        "file_suffixes": [".pyc", ".pyo"],
    },
}


# ---------------------------------------------------------------- basics

def expand(p):
    return os.path.realpath(os.path.expanduser(p))


def state_dir(args=None):
    d = (getattr(args, "state_dir", None) or os.environ.get("DEHYDRATE_HOME")
         or os.path.join(claude_home(args), "dehydrated"))
    d = os.path.expanduser(d)
    os.makedirs(os.path.join(d, "archive"), exist_ok=True)
    return d


def claude_home(args=None):
    return os.path.expanduser(getattr(args, "claude_home", None) or os.environ.get("CLAUDE_CONFIG_DIR")
                              or "~/.claude")


def load_config(sd):
    cfg = json.loads(json.dumps(DEFAULTS))
    p = os.path.join(sd, "config.json")
    if os.path.isfile(p):
        try:
            user = json.load(open(p))
            for k, v in user.items():
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
        except Exception as e:  # a broken config must not break a SessionStart hook
            cfg["_config_error"] = str(e)
    return cfg


def git(cwd, *a, env=None, check=False, text=True, timeout=120):
    e = dict(os.environ)
    e.pop("GIT_DIR", None)
    e.pop("GIT_WORK_TREE", None)
    e.pop("GIT_INDEX_FILE", None)
    e["GIT_OPTIONAL_LOCKS"] = "0"  # a census must never rewrite an index (it would fake activity)
    if env:
        e.update(env)
    r = subprocess.run(["git", "-C", cwd, *a], capture_output=True, text=text, env=e, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(a)} in {cwd}: {r.stderr.strip()[:400]}")
    return r


def gout(cwd, *a, **k):
    r = git(cwd, *a, **k)
    return r.stdout.strip() if r.returncode == 0 else ""


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def free_gb(path="/"):
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize / (1024 ** 3)


_FAKE_FREE = []


def pressure_free_gb():
    """Free GB for the --pressure stop check, read once per item. DEHYDRATE_FAKE_FREE_GB="5,20" (tests)
    returns 5 for the first check, 20 for the second, then repeats the last value."""
    fake = os.environ.get("DEHYDRATE_FAKE_FREE_GB")
    if not fake:
        return free_gb()
    if not _FAKE_FREE:
        _FAKE_FREE.extend(float(x) for x in fake.split(","))
    return _FAKE_FREE.pop(0) if len(_FAKE_FREE) > 1 else _FAKE_FREE[0]


def du_kb(path):
    r = subprocess.run(["du", "-sk", path], capture_output=True, text=True)
    try:
        return int(r.stdout.split()[0])
    except Exception:
        return 0


def iso(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat(timespec="seconds")


def slugify(s, n=40):
    s = re.sub(r"[^A-Za-z0-9]+", "-", s or "").strip("-").lower()
    return s[:n].strip("-") or "x"


def under(path, root):
    path, root = path.rstrip("/"), root.rstrip("/")
    return path == root or path.startswith(root + "/")


def excluded(path, cfg):
    for g in cfg["exclude_globs"]:
        g = os.path.expanduser(g)
        if fnmatch.fnmatch(path, g) or fnmatch.fnmatch(path + "/", g):
            return g
    return None


# ---------------------------------------------------------------- sessions

def load_agents(args):
    if args.agents_json:
        return json.load(open(args.agents_json))
    r = subprocess.run([args.claude_bin, "agents", "--json", "--all"], capture_output=True, text=True,
                       timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"claude agents --json --all failed: {r.stderr.strip()[:300]}")
    return json.loads(r.stdout or "[]")


def transcript_index(ch):
    """sessionId -> {path, project_dir, mtime, cwd}. Reads only the head of each transcript."""
    idx = {}
    proj = os.path.join(ch, "projects")
    if not os.path.isdir(proj):
        return idx
    for pd in os.listdir(proj):
        d = os.path.join(proj, pd)
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if not fn.endswith(".jsonl"):
                continue
            p = os.path.join(d, fn)
            sid = fn[:-6]
            try:
                st = os.stat(p)
            except OSError:
                continue
            cwd = None
            try:
                with open(p, "rb") as f:
                    for i, line in enumerate(f):
                        if i > 60:
                            break
                        if b'"cwd"' in line:
                            try:
                                cwd = json.loads(line).get("cwd")
                            except Exception:
                                pass
                            if cwd:
                                break
            except OSError:
                pass
            idx[sid] = {"path": p, "project_dir": pd, "mtime": st.st_mtime, "cwd": cwd,
                        "rcwd": os.path.realpath(cwd) if cwd else None}
    return idx


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
    return ""


NOISE = re.compile(r"<(system-reminder|command-[a-z]+|local-command-[a-z]+|pasted_content)[^>]*>.*?</\1[^>]*>",
                   re.S)


def describe_transcript(path):
    """Deterministic summary fields from a transcript: titles, first human prompt, last assistant text."""
    out = {"title": None, "first_prompt": None, "last_text": None, "git_branch": None}
    try:
        with open(path, "rb") as f:
            for line in f:
                if not (b'"custom-title"' in line or b'"ai-title"' in line or b'"agent-name"' in line
                        or b'"type":"user"' in line or b'"type": "user"' in line
                        or b'"type":"assistant"' in line or b'"type": "assistant"' in line):
                    continue
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                t = o.get("type")
                if t == "custom-title" and o.get("customTitle"):
                    out["title"] = o["customTitle"]
                elif t == "ai-title" and o.get("aiTitle") and not out["title"]:
                    out["title"] = o["aiTitle"]
                elif t == "user" and not out["first_prompt"] and not o.get("isSidechain") \
                        and o.get("origin", {}).get("kind", "human") == "human":
                    txt = NOISE.sub(" ", _text((o.get("message") or {}).get("content"))).strip()
                    if txt and not txt.startswith("<"):
                        out["first_prompt"] = re.sub(r"\s+", " ", txt)[:300]
                        out["git_branch"] = o.get("gitBranch")
                elif t == "assistant" and not o.get("isSidechain"):
                    txt = _text((o.get("message") or {}).get("content")).strip()
                    if txt:
                        out["last_text"] = re.sub(r"\s+", " ", txt)[-300:]
    except OSError:
        pass
    return out


def session_rows(args, cfg, tidx, now):
    me_sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    me_job = os.path.basename(os.environ.get("CLAUDE_JOB_DIR", "").rstrip("/"))
    ch = claude_home(args)
    rows = []
    for a in load_agents(args):
        sid = a.get("sessionId") or ""
        bid = a.get("id") or ""
        state = a.get("state") or a.get("status") or ""
        t = tidx.get(sid)
        jobd = os.path.join(ch, "jobs", bid) if bid else ""
        acts = [(a.get("startedAt") or 0) / 1000]
        if t:
            acts.append(t["mtime"])
        for fn in ("state.json", "timeline.jsonl"):
            p = os.path.join(jobd, fn) if jobd else ""
            if p and os.path.isfile(p):
                acts.append(os.path.getmtime(p))
        last = max(acts)
        row = {"bg_id": bid, "session_id": sid, "name": a.get("name") or "", "cwd": a.get("cwd") or "",
               "kind": a.get("kind") or "", "state": state, "pid": a.get("pid"),
               "last_activity": last, "idle_days": round((now - last) / 86400, 2),
               "transcript": t["path"] if t else None, "project_dir": t["project_dir"] if t else None,
               "job_dir": jobd if jobd and os.path.isdir(jobd) else None,
               "worktree_path": a.get("worktreePath"),
               "rcwd": os.path.realpath(a["cwd"]) if a.get("cwd") else None}
        if sid and (sid == me_sid) or (bid and bid == me_job):
            row.update(action="keep", reason="this session")
        elif not sid:
            row.update(action="keep", reason="no session id")
        elif row["kind"] != "background":
            row.update(action="keep", reason=f"{row['kind'] or 'unknown'} session (close it in its terminal)")
        elif state in ACTIVE_STATES:
            row.update(action="keep", reason=f"state {state}")
        elif getattr(args, "pressure", False) and state in PRESSURE_RELEASE_STATES and now - last >= 86400:
            # under disk pressure a finished or stuck session stops protecting its worktree after a day
            row.update(action="close", reason=f"pressure: state {state}, idle {row['idle_days']}d (> 24h)")
        elif now - last < cfg["days"] * 86400:
            row.update(action="keep", reason=f"active {row['idle_days']}d ago (< {cfg['days']}d)")
        else:
            row.update(action="close", reason=f"idle {row['idle_days']}d, state {state or 'unknown'}")
        rows.append(row)
    rows.sort(key=lambda r: (r["action"], -r["idle_days"]))
    return rows


# ---------------------------------------------------------------- worktrees

def find_repos(cfg):
    seen, repos = set(), []
    for root in cfg["roots"]:
        root = expand(root)
        frontier = [root]
        for depth in range(cfg["root_depth"]):
            nxt = []
            for d in frontier:
                try:
                    names = sorted(os.listdir(d))
                except OSError:
                    continue
                for n in names:
                    p = os.path.join(d, n)
                    if not os.path.isdir(p) or os.path.islink(p) and depth > 0:
                        continue
                    if os.path.isdir(os.path.join(p, ".git")):
                        key = os.path.realpath(os.path.join(p, ".git"))  # symlinked clones dedupe here
                        if key not in seen:
                            seen.add(key)
                            repos.append({"path": os.path.realpath(p), "common_dir": key})
                    elif depth + 1 < cfg["root_depth"]:
                        nxt.append(p)
            frontier = nxt
    return repos


def list_worktrees(repo):
    out = gout(repo, "worktree", "list", "--porcelain")
    wts = []
    for block in out.split("\n\n"):
        kv = {}
        for line in block.splitlines():
            k, _, v = line.partition(" ")
            kv[k] = v if v else True
        if "worktree" in kv:
            wts.append({"path": kv["worktree"], "head": kv.get("HEAD"),
                        "branch": kv["branch"].replace("refs/heads/", "") if isinstance(kv.get("branch"), str) else None,
                        "locked": "locked" in kv, "lock_reason": kv.get("locked") if isinstance(kv.get("locked"), str) else "",
                        "prunable": "prunable" in kv, "bare": "bare" in kv})
    return wts


def process_cwds():
    r = subprocess.run(["lsof", "-a", "-d", "cwd", "-F", "pn"], capture_output=True, text=True, timeout=60)
    cwds, pid = [], None
    for line in r.stdout.splitlines():
        if line.startswith("p"):
            pid = line[1:]
        elif line.startswith("n") and pid and pid != str(os.getpid()):
            cwds.append((pid, line[1:]))
    return cwds


def regenerable(rel, cfg):
    rg = cfg["regenerable"]
    parts = rel.rstrip("/").split("/")
    if any(p in rg["dir_names"] for p in parts):
        return True
    base = parts[-1]
    return base in rg["file_names"] or any(base.endswith(s) for s in rg["file_suffixes"])


def ignored_scan(path, cfg, skip=()):
    """Gitignored paths that are not regenerable -> {files: [(relpath, bytes)], nested: [git repos inside]}."""
    out = gout(path, "ls-files", "--others", "--ignored", "--exclude-standard", "--directory", "-z")
    res, nested = [], []
    for rel in [x for x in out.split("\0") if x]:
        if any(rel.startswith(k) for k in skip):
            continue
        full = os.path.join(path, rel)
        if regenerable(rel, cfg):
            if rel.endswith("/") and os.path.isdir(full):  # e.g. a pip editable git checkout in .venv/src
                hit = subprocess.run(["find", full, "-name", ".git", "-print", "-quit"], capture_output=True,
                                     text=True, timeout=300).stdout.strip()
                if hit:
                    nested.append(os.path.relpath(os.path.dirname(hit), path) + "/")
            continue
        if os.path.isdir(full) and not os.path.islink(full):
            for dp, dns, fns in os.walk(full):
                if ".git" in dns or ".git" in fns:
                    nested.append(os.path.relpath(dp, path) + "/")
                    dns[:] = []
                    continue
                keep = []
                for d in dns:
                    if os.path.islink(os.path.join(dp, d)):
                        fns.append(d)  # a symlink to a dir is archived as the link itself
                    elif d not in cfg["regenerable"]["dir_names"]:
                        keep.append(d)
                dns[:] = keep
                for fn in fns:
                    fp = os.path.join(dp, fn)
                    r2 = os.path.relpath(fp, path)
                    if not regenerable(r2, cfg):
                        try:
                            res.append((r2, os.lstat(fp).st_size))
                        except OSError:
                            pass
        else:
            try:
                res.append((rel, os.lstat(full).st_size))
            except OSError:
                pass
    return {"files": res, "nested": nested}


def ignored_real(path, cfg, skip=()):
    return ignored_scan(path, cfg, skip)["files"]


def worktree_gitdir(path):
    g = os.path.join(path, ".git")
    if os.path.isdir(g):
        return g
    try:
        line = open(g).read().strip()
    except OSError:
        return None
    if line.startswith("gitdir:"):
        d = line[7:].strip()
        return d if os.path.isabs(d) else os.path.normpath(os.path.join(path, d))
    return None


def cheap_touch(path):
    """Last real activity without git or a tree walk: top-level dir, reflog and HEAD mtimes."""
    mt = []
    with contextlib.suppress(OSError):
        mt.append(os.stat(path).st_mtime)
    gd = worktree_gitdir(path)
    found = False
    for fn in ("logs/HEAD", "HEAD"):
        with contextlib.suppress(OSError, TypeError):
            mt.append(os.stat(os.path.join(gd, fn)).st_mtime)
            found = found or fn == "logs/HEAD"
    if not found:
        ct = gout(path, "log", "-1", "--format=%ct")
        if ct.isdigit():
            mt.append(int(ct))
    return max(mt) if mt else 0


def quick_status(path):
    st = git(path, "status", "--porcelain=v1", "-z", timeout=600)
    entries = [e for e in st.stdout.split("\0") if e] if st.returncode == 0 else []
    return {"dirty_count": sum(not e.startswith("??") for e in entries),
            "untracked_count": sum(e.startswith("??") for e in entries)}


def worktree_facts(w, cfg, skip=()):
    """One porcelain-v2 status (dirt, untracked, nested repos, submodules, ahead count) + one ignored scan."""
    p = w["path"]
    st = git(p, "status", "--porcelain=v2", "-z", "--branch", "--untracked-files=all", "--ignore-submodules=none",
             timeout=600)
    if st.returncode != 0:
        raise RuntimeError(f"git status failed: {st.stderr.strip()[:200]}")
    fields = st.stdout.split("\0")
    dirty, untracked, sub_dirty, upstream, ahead = [], [], [], None, None
    i = 0
    while i < len(fields):
        e = fields[i]
        i += 1
        if not e:
            continue
        if e.startswith("# branch.upstream "):
            upstream = e.split(" ", 2)[2]
        elif e.startswith("# branch.ab "):
            ahead = int(e.split()[2].lstrip("+"))
        elif e[0] in "12u":
            parts = e.split(" ")
            n = {"1": 8, "2": 9, "u": 10}[e[0]]
            rel = " ".join(parts[n:])
            dirty.append(rel)
            if parts[2].startswith("S") and parts[2] != "S...":
                sub_dirty.append(rel)
            if e[0] == "2":
                i += 1  # rename: next field is the original path
        elif e[0] == "?":
            untracked.append(e[2:])
    usize, ubig, nested = 0, [], []
    for rel in untracked:
        full = os.path.join(p, rel)
        if rel.endswith("/"):
            if rel in skip or any(rel.startswith(k) for k in skip):
                continue
            if os.path.exists(os.path.join(full, ".git")):
                nested.append(rel)
            continue
        try:
            s = os.lstat(full).st_size
        except OSError:
            continue
        usize += s
        if s > cfg["untracked_file_cap_mb"] * 2 ** 20:
            ubig.append(rel)
    mt = []
    for rel in (dirty + untracked)[:2000]:
        with contextlib.suppress(OSError):
            mt.append(os.lstat(os.path.join(p, rel.rstrip("/"))).st_mtime)
    if ahead is None:
        n = gout(p, "rev-list", "--count", "HEAD", "--not", "--remotes")
        ahead = int(n) if n.isdigit() else 0
    scan = ignored_scan(p, cfg, skip)
    ign = scan["files"]
    gd = worktree_gitdir(p)
    links = [e.split("\t", 1)[1] for e in gout(p, "ls-files", "-s", "-z").split("\0") if e.startswith("160000 ")]
    sub_checkouts = [r for r in links if os.path.lexists(os.path.join(p, r, ".git"))]
    in_progress = [n for n in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply",
                               "BISECT_LOG") if gd and os.path.exists(os.path.join(gd, n))]
    return {"sub_checkouts": sub_checkouts, "in_progress": in_progress,
            "conflicted": any(e.startswith("u ") for e in fields if e),
            "unborn": git(p, "rev-parse", "--verify", "-q", "HEAD").returncode != 0,
            "ignored_real_count": len(ign), "ignored_real_bytes": sum(b for _, b in ign),
            "ignored_nested": scan["nested"],
            "submodule_clones": bool(gd) and os.path.isdir(os.path.join(gd, "modules")),
            "changed_paths": sorted(set(r.rstrip("/") for r in dirty + untracked if not r.endswith("/"))),
            "dirty_count": len(dirty), "untracked_count": len(untracked), "untracked_bytes": usize,
            "untracked_big": ubig[:10], "last_touch": max(mt + [cheap_touch(p)]),
            "unpushed": ahead, "upstream": upstream,
            "submodule_dirty": sub_dirty, "nested_repos": nested}


def read_origin(common_dir):
    try:
        txt = open(os.path.join(common_dir, "config")).read()
    except OSError:
        return None
    m = re.search(r'\[remote "origin"\][^\[]*?\n\s*url\s*=\s*(\S+)', txt)
    return m.group(1) if m else None


def read_head_branch(common_dir):
    try:
        h = open(os.path.join(common_dir, "HEAD")).read().strip()
    except OSError:
        return None
    return h[len("ref: refs/heads/"):] if h.startswith("ref: refs/heads/") else None


def worktree_rows(cfg, sessions, tidx, now, only=None, pressure=False):
    from concurrent.futures import ThreadPoolExecutor
    repos = find_repos(cfg)
    cwds = process_cwds()
    me_cwd = os.path.realpath(os.getcwd())
    keep_sessions = [s for s in sessions if s["action"] == "keep" and s.get("rcwd")]
    with ThreadPoolExecutor(max_workers=cfg.get("workers", 8)) as ex:
        parts = list(ex.map(lambda r: repo_rows(r, cfg, sessions, keep_sessions, tidx, now, only, cwds, me_cwd, pressure), repos))
    rows = [x for p in parts for x in p[0]]
    mains = [x for p in parts for x in p[1]]
    orphans = [x for p in parts for x in p[2]]
    return rows, mains, orphans


def repo_rows(repo, cfg, sessions, keep_sessions, tidx, now, only, cwds, me_cwd, pressure=False):
    rows, mains, orphans = [], [], []
    wt_days = 0 if pressure else cfg["days"]  # --pressure ignores the idle window for worktrees only
    if True:
        has_linked = os.path.isdir(os.path.join(repo["common_dir"], "worktrees"))
        wdir = os.path.join(repo["path"], ".claude", "worktrees")
        if not has_linked and not os.path.isdir(wdir) and not cfg["snapshot_main"]:
            return rows, mains, orphans
        wts = list_worktrees(repo["path"]) if has_linked or os.path.isdir(wdir) else \
            [{"path": repo["path"], "head": None, "branch": read_head_branch(repo["common_dir"]),
              "locked": False, "lock_reason": "", "prunable": False, "bare": False}]
        if not wts or wts[0].get("bare"):
            return rows, mains, orphans
        origin = read_origin(repo["common_dir"])
        registered = {os.path.realpath(w["path"]) for w in wts}
        main = wts[0]
        if cfg["snapshot_main"] and not only and os.path.isdir(main["path"]) \
                and not excluded(os.path.realpath(main["path"]), cfg):
            mf = quick_status(main["path"])
            mains.append({"repo": repo["path"], "origin": origin, "path": main["path"], "branch": main["branch"],
                          "head": main["head"], "facts": mf,
                          "action": "snapshot" if mf["dirty_count"] or mf["untracked_count"] else "skip"})
        pending = []
        reg_paths = [os.path.realpath(w["path"]) for w in wts[1:] if os.path.exists(w["path"])]
        inside = {p: [q for q in reg_paths if q != p and under(q, p)] for p in reg_paths}
        for w in wts[1:]:
            path = os.path.realpath(w["path"]) if os.path.exists(w["path"]) else w["path"]
            row = {"repo": repo["path"], "origin": origin, "path": path, "branch": w["branch"], "head": w["head"],
                   "locked": w["locked"], "lock_reason": w["lock_reason"]}
            if only and not any(o in (path, os.path.basename(path), w["branch"]) for o in only):
                continue
            if w["prunable"] or not os.path.isdir(w["path"]):
                row.update(action="prune", reason="worktree dir is gone; prune the record")
                rows.append(row)
                continue
            g = excluded(path, cfg)
            if g:
                row.update(action="skip", reason=f"excluded by {g} (owned by another system)", facts={})
                rows.append(row)
                continue
            bound = sorted({sid for sid, t in tidx.items() if t.get("rcwd") and under(t["rcwd"], path)})
            bound_bg = [s for s in sessions if s.get("rcwd") and under(s["rcwd"], path)]
            row["sessions"] = sorted(set(bound) | {s["session_id"] for s in bound_bg if s["session_id"]})
            acts = [cheap_touch(path)] + [tidx[s]["mtime"] for s in bound if s in tidx] + \
                   [s["last_activity"] for s in bound_bg]
            pending.append((w, row, path, acts))
        # only stale candidates pay for a full look, in parallel
        stale = [x for x in pending if now - max(x[3]) >= wt_days * 86400]

        def facts_or_none(w):
            try:
                return worktree_facts(w, cfg)
            except Exception:
                return None
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=cfg.get("workers", 8)) as ex:
            got = dict(zip([id(x[0]) for x in stale], ex.map(lambda x: facts_or_none(x[0]), stale)))
        for w, row, path, acts in pending:
            facts = got.get(id(w)) or {}
            if facts:
                acts = acts + [facts["last_touch"]]
            row["facts"] = facts
            row["last_activity"] = max(acts)
            row["idle_days"] = round((now - row["last_activity"]) / 86400, 2)
            live = [pid for pid, c in cwds if under(c, path)]
            kept = [s for s in keep_sessions if under(s["rcwd"], path)]
            if under(me_cwd, path):
                row.update(action="keep", reason="this session's cwd")
            elif kept:
                row.update(action="keep", reason=f"bound to kept session {kept[0]['bg_id'] or kept[0]['session_id'][:8]}")
            elif now - row["last_activity"] < wt_days * 86400:
                row.update(action="keep", reason=f"active {row['idle_days']}d ago (< {cfg['days']}d)")
            elif not facts:
                row.update(action="hold", reason="could not read worktree state")
            elif w["locked"]:
                row.update(action="hold", reason=f"locked ({w['lock_reason'] or 'no reason'})")
            elif live:
                row.update(action="hold", reason=f"process {live[0]} has its cwd inside")
            elif facts["unborn"]:
                row.update(action="hold", reason="branch has no commits yet (nothing to anchor a snapshot to)")
            elif facts["conflicted"] or facts["in_progress"]:
                row.update(action="hold", reason=f"{'conflicts in the index' if facts['conflicted'] else facts['in_progress'][0] + ' in progress'} (finish or abort it first)")
            elif facts["sub_checkouts"]:
                row.update(action="hold", reason=f"submodule checkout {facts['sub_checkouts'][0]} (its local commits are not captured)")
            elif inside.get(path):
                row.update(action="hold", reason=f"another worktree lives inside it: {short(inside[path][0])}")
            elif facts["submodule_clones"]:
                row.update(action="hold", reason="has submodule clones in its gitdir (their local commits are not captured)")
            elif facts["ignored_nested"]:
                row.update(action="hold", reason=f"nested git repo under a gitignored path: {facts['ignored_nested'][0]}")
            elif facts["submodule_dirty"]:
                row.update(action="hold", reason=f"dirty submodule {facts['submodule_dirty'][0]}")
            elif facts["nested_repos"]:
                row.update(action="hold", reason=f"nested git repo {facts['nested_repos'][0]} (not capturable)")
            elif facts["untracked_big"]:
                row.update(action="hold", reason=f"untracked file over {cfg['untracked_file_cap_mb']} MB: {facts['untracked_big'][0]}")
            elif facts["untracked_bytes"] > cfg["untracked_cap_mb"] * 2 ** 20:
                row.update(action="hold", reason=f"untracked files total {facts['untracked_bytes'] / 2**20:.1f} MB (cap {cfg['untracked_cap_mb']} MB)")
            elif facts["ignored_real_bytes"] > cfg["ignored_cap_mb"] * 2 ** 20:
                row.update(action="hold", reason=f"gitignored files to archive total {facts['ignored_real_bytes'] / 2**20:.1f} MB (cap {cfg['ignored_cap_mb']} MB)")
            else:
                row.update(action="dehydrate", reason=f"idle {row['idle_days']}d")
            rows.append(row)
        # unregistered leftovers in Claude's own worktree dir
        if os.path.isdir(wdir) and not only:
            for n in sorted(os.listdir(wdir)):
                p = os.path.realpath(os.path.join(wdir, n))
                if not os.path.isdir(p) or p in registered:
                    continue
                if any(under(q, p) for q in registered):
                    orphans.append({"repo": repo["path"], "origin": origin, "path": p, "idle_days": 0,
                                    "action": "hold", "reason": "a registered worktree lives inside it"})
                    continue
                newest = max([os.lstat(os.path.join(dp, f)).st_mtime for dp, _, fs in os.walk(p) for f in fs] or [0])
                age = (now - max(newest, os.stat(p).st_mtime)) / 86400
                o = {"repo": repo["path"], "origin": origin, "path": p, "idle_days": round(age, 2)}
                if os.path.isdir(os.path.join(p, ".git")):
                    o.update(action="hold", reason="nested clone, not a worktree")
                elif any(under(c, p) for _, c in cwds):
                    o.update(action="hold", reason="a process has its cwd inside")
                elif age < cfg["days"]:
                    o.update(action="keep", reason=f"touched {round(age, 1)}d ago")
                else:
                    o.update(action="archive", reason=f"unregistered leftover, idle {round(age, 1)}d")
                orphans.append(o)
    return rows, mains, orphans


# ---------------------------------------------------------------- plan

def build_plan(args, cfg):
    now = args.now or time.time()
    pressure = getattr(args, "pressure", False)
    ch = claude_home(args)
    tidx = transcript_index(ch)
    sessions = session_rows(args, cfg, tidx, now) if not args.no_sessions else []
    if args.no_main or args.only:
        cfg = dict(cfg, snapshot_main=False)
    if args.no_worktrees and not cfg["snapshot_main"]:
        wts, mains, orphans = [], [], []
    else:
        wts, mains, orphans = worktree_rows(cfg, sessions, tidx, now, args.only, pressure)
        if args.no_worktrees:
            wts, orphans = [], []
    if args.only:
        sessions = [s for s in sessions if any(o in (s["bg_id"], s["session_id"], s["session_id"][:8]) for o in args.only)
                    or any(w["action"] == "dehydrate" and s["session_id"] in w.get("sessions", []) for w in wts)]
    # a session whose worktree is held or kept must not take the worktree with it
    for s in sessions:
        if s["action"] != "close":
            continue
        for w in wts:
            if s.get("rcwd") and under(s["rcwd"], w["path"]):
                s["worktree"] = w["path"]
                s["worktree_action"] = w["action"]
    for w in wts:
        if w["action"] == "dehydrate":
            w["size_kb"] = du_kb(w["path"])
    for o in orphans:
        if o["action"] == "archive":
            o["size_kb"] = du_kb(o["path"])
            if o["size_kb"] > cfg["orphan_cap_mb"] * 1024:
                o.update(action="hold", reason=f"{o['size_kb'] // 1024} MB over orphan cap")
    if args.no_main or args.only or pressure:
        mains = []
    press = None
    if pressure:
        # least recently active first, then largest; only worktrees (and their sessions) free disk here
        orphans = []
        for s in sessions:
            if s["action"] == "close" and s.get("worktree_action") != "dehydrate":
                s.update(action="keep", reason="pressure: closes only with a dehydrated worktree")
        order = sorted([w for w in wts if w["action"] == "dehydrate"],
                       key=lambda w: (w.get("last_activity") or 0, -(w.get("size_kb") or 0)))
        free, est = free_gb(), None
        for i, w in enumerate(order, 1):
            w["pressure_rank"] = i
            free += (w.get("size_kb") or 0) / 2 ** 20
            if est is None and free >= args.target_gb:
                est = i
        press = {"target_gb": args.target_gb, "free_gb": round(free_gb(), 2),
                 "order": [w["path"] for w in order], "estimated_stop_after": est}
    return {"schema": SCHEMA, "now": now, "now_iso": iso(now), "days": cfg["days"], "host": socket.gethostname(),
            "pressure": press,
            "sessions": sessions, "worktrees": wts, "mains": mains, "orphans": orphans,
            "totals": {
                "sessions_close": sum(s["action"] == "close" for s in sessions),
                "sessions_keep": sum(s["action"] == "keep" for s in sessions),
                "worktrees_dehydrate": sum(w["action"] == "dehydrate" for w in wts),
                "worktrees_keep": sum(w["action"] == "keep" for w in wts),
                "worktrees_hold": sum(w["action"] == "hold" for w in wts),
                "worktrees_prune": sum(w["action"] == "prune" for w in wts),
                "worktrees_excluded": sum(w["action"] == "skip" for w in wts),
                "orphans_archive": sum(o["action"] == "archive" for o in orphans),
                "mains_snapshot": sum(m["action"] == "snapshot" for m in mains),
                "reclaim_kb": sum(w.get("size_kb", 0) for w in wts if w["action"] == "dehydrate")
                + sum(o.get("size_kb", 0) for o in orphans if o["action"] == "archive"),
            }}


def short(p):
    return p.replace(os.path.expanduser("~"), "~") if p else ""


def render_plan(plan, applied=False):
    t = plan["totals"]
    L = [f"dehydrate plan @ {plan['now_iso']} (stale = idle >= {plan['days']}d)",
         f"  sessions: close {t['sessions_close']}, keep {t['sessions_keep']}",
         f"  worktrees: dehydrate {t['worktrees_dehydrate']}, keep {t['worktrees_keep']}, hold {t['worktrees_hold']}, "
         f"prune {t['worktrees_prune']}, excluded {t['worktrees_excluded']} (other systems' trees, never touched)",
         f"  leftover dirs: archive {t['orphans_archive']}   main checkouts: snapshot {t['mains_snapshot']}",
         f"  frees about {t['reclaim_kb'] / 2**20:.2f} GB", ""]
    pr = plan.get("pressure")
    if pr:
        L[0] = f"dehydrate plan @ {plan['now_iso']} (PRESSURE: idle window ignored, stop at {pr['target_gb']} GB free)"
        est = pr["estimated_stop_after"]
        L.insert(-1, f"  free now {pr['free_gb']} GB; worktrees go least recently active first, one at a time; "
                     + (f"target reached after about {est}" if est else "all candidates together may not reach the target"))
    for title, rows, acts in (("Worktrees", plan["worktrees"], ("dehydrate", "hold", "prune")),
                              ("Leftover dirs", plan["orphans"], ("archive", "hold"))):
        sel = [r for r in rows if r["action"] in acts]
        if pr:
            sel.sort(key=lambda r: r.get("pressure_rank") or 10 ** 6)
        if sel:
            L.append(f"{title}:")
            for r in sel:
                f = r.get("facts") or {}
                L.append(f"  {r['action']:9s} {short(r['path'])}  [{r.get('branch') or ''}] {r['reason']}"
                         + (f"  dirty={f.get('dirty_count')} untracked={f.get('untracked_count')} unpushed={f.get('unpushed')}" if f else "")
                         + (f"  {r.get('size_kb', 0) // 1024} MB" if r.get("size_kb") else ""))
            L.append("")
    sel = [s for s in plan["sessions"] if s["action"] == "close"]
    if sel:
        L.append("Sessions to close:")
        for s in sel:
            L.append(f"  {s['bg_id']:9s} {s['idle_days']:6.1f}d {s['state']:8s} {s['name'][:44]:44s} {short(s['cwd'])}")
        L.append("")
    sel = [m for m in plan["mains"] if m["action"] == "snapshot"]
    if sel:
        L.append("Main checkouts with uncommitted work (snapshot only, never reset):")
        for m in sel:
            L.append(f"  {short(m['path'])} [{m['branch']}] dirty={m['facts']['dirty_count']} untracked={m['facts']['untracked_count']}")
        L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------- manifest

def manifest_path(sd):
    return os.path.join(sd, "manifest.jsonl")


def append_manifest(sd, rec):
    rec.setdefault("schema", SCHEMA)
    p = manifest_path(sd)
    with open(p, "a+b") as f:
        f.seek(0, os.SEEK_END)
        if f.tell():
            f.seek(-1, os.SEEK_END)
            if f.read(1) != b"\n":  # a torn last line must not swallow this record
                f.write(b"\n")
        f.write((json.dumps(rec, sort_keys=True) + "\n").encode())
        f.flush()
        os.fsync(f.fileno())


def read_manifest(sd):
    recs = []
    p = manifest_path(sd)
    if os.path.isfile(p):
        for line in open(p):
            line = line.strip()
            if line:
                with contextlib.suppress(Exception):
                    r = json.loads(line)
                    if isinstance(r, dict) and isinstance(r.get("id"), str) and r.get("event") and \
                            isinstance(r.get("at"), str) and (r["event"] != "dehydrated" or r.get("kind")):
                        recs.append(r)
    return recs


def current_records(sd):
    """id -> dehydrated record with 'rehydrations' folded in."""
    cur = {}
    for r in read_manifest(sd):
        if r.get("event") == "dehydrated":
            cur[r["id"]] = dict(r, rehydrations=[])
        elif r.get("event") == "rehydrated" and r.get("id") in cur:
            cur[r["id"]]["rehydrations"].append(r)
        elif r.get("event") == "removed" and r.get("id") in cur:
            cur[r["id"]].update(removed=True, **{k: v for k, v in r.items() if k in ("close",)})
    for r in cur.values():
        p = (r.get("worktree") or {}).get("path")
        if not r.get("removed") and r["kind"] in ("worktree", "orphan") and p and not os.path.exists(p) \
                and not r["rehydrations"]:
            r["removed"] = True  # its `removed` event could not be written, but the tree is gone
    return cur


def write_index(sd):
    cur = current_records(sd)
    L = ["# Dehydrated sessions and worktrees", "",
         f"Generated from `manifest.jsonl` ({len(cur)} records). Bring one back with `/rehydrate <id>` "
         f"(or `dehydrate.py rehydrate <id>` from the dehydrate plugin's scripts dir); search with `list <words>`.", "",
         "| id | when | kind | repo | branch | what it was | state |", "|---|---|---|---|---|---|---|"]
    for r in sorted(cur.values(), key=lambda r: r["at"], reverse=True):
        st = "rehydrated" if r["rehydrations"] else ("removed" if r.get("removed") else "kept in place")
        desc = (r.get("description") or "").replace("|", "/").replace("\n", " ")[:140]
        L.append(f"| `{r['id']}` | {r['at'][:10]} | {r['kind']} | {short(r.get('repo', {}).get('path', ''))} | "
                 f"{(r.get('worktree') or {}).get('branch') or ''} | {desc} | {st} |")
    tmp = os.path.join(sd, "index.md.tmp")
    open(tmp, "w").write("\n".join(L) + "\n")
    os.replace(tmp, os.path.join(sd, "index.md"))


# ---------------------------------------------------------------- snapshot

def snapshot_tree(path, skip=()):
    """Tree of the worktree as it stands (tracked + staged + untracked, ignores respected)."""
    fd, idx = tempfile.mkstemp(prefix="dehydrate-idx-")
    os.close(fd)
    os.unlink(idx)
    try:
        env = {"GIT_INDEX_FILE": idx}
        head_ok = git(path, "rev-parse", "--verify", "-q", "HEAD").returncode == 0
        if head_ok:
            git(path, "read-tree", "HEAD", env=env, check=True)
        # excluding an already-ignored path is an error for git add, and unnecessary
        skip = [k for k in skip if git(path, "check-ignore", "-q", "--", k.rstrip("/")).returncode != 0]
        git(path, "add", "-A", "--", ".", *[f":(exclude){k}" for k in skip], env=env, check=True, timeout=1800)
        return gout(path, "write-tree", env=env) or None
    finally:
        with contextlib.suppress(OSError):
            os.unlink(idx)


def new_gitlinks(path, tree, head):
    def links(t):
        out = gout(path, "ls-tree", "-r", "-z", t)
        return {e.split("\t", 1)[1] for e in out.split("\0") if e.startswith("160000 ")}
    return sorted(links(tree) - (links(head) if head else set()))


def bundle_base(path):
    """The remote default branch (durable: it is never deleted), or None for a self-contained bundle.
    Not --remotes: a pushed feature branch deleted upstream would leave the bundle unrestorable."""
    for ref in ("refs/remotes/origin/HEAD", "refs/remotes/origin/main", "refs/remotes/origin/master"):
        sha = gout(path, "rev-parse", "--verify", "-q", ref)
        if sha:
            return sha
    return None


def make_snapshot(path, rid, msg, archive, strict=True, skip=()):
    head = gout(path, "rev-parse", "--verify", "-q", "HEAD") or None
    tree = snapshot_tree(path, skip)
    if not tree:
        raise RuntimeError("write-tree failed")
    gl = new_gitlinks(path, tree, head)
    if gl:
        raise RuntimeError(f"snapshot would record nested repo {gl[0]} as a bare gitlink; holding")
    env = {"GIT_AUTHOR_NAME": "dehydrate", "GIT_AUTHOR_EMAIL": "dehydrate@localhost",
           "GIT_COMMITTER_NAME": "dehydrate", "GIT_COMMITTER_EMAIL": "dehydrate@localhost"}
    # Staging, like git stash: the real index (read from a copy, so the source is untouched) becomes
    # a second parent commit. Skipped when the index has conflicts.
    index_tree, index_commit = None, None
    gd = worktree_gitdir(path)
    if head and gd and os.path.isfile(os.path.join(gd, "index")):
        fd, cp = tempfile.mkstemp(prefix="dehydrate-realidx-")
        os.close(fd)
        try:
            shutil.copyfile(os.path.join(gd, "index"), cp)
            index_tree = gout(path, "write-tree", env={"GIT_INDEX_FILE": cp}) or None
        finally:
            with contextlib.suppress(OSError):
                os.unlink(cp)
        if index_tree:
            index_commit = git(path, "commit-tree", index_tree, "-p", head, "-m", f"index of {rid}", env=env,
                               check=True).stdout.strip()
    cmd = ["commit-tree", tree, "-m", msg] + (["-p", head] if head else []) + (["-p", index_commit] if index_commit else [])
    commit = git(path, *cmd, env=env, check=True).stdout.strip()
    ref = f"refs/dehydrated/{rid}"
    git(path, "update-ref", ref, commit, check=True)
    bundle = os.path.join(archive, "snapshot.bundle")
    base = bundle_base(path)
    b = git(path, "bundle", "create", bundle, ref, *(["--not", base] if base else []), timeout=1800)
    if b.returncode != 0:
        raise RuntimeError(f"bundle create failed: {b.stderr.strip()[:300]}")
    v = git(path, "bundle", "verify", bundle)
    if v.returncode != 0:
        raise RuntimeError(f"bundle verify failed: {v.stderr.strip()[:300]}")
    again = snapshot_tree(path, skip)
    if again != tree and strict:
        raise RuntimeError("worktree changed while it was being captured; holding")
    return {"index_tree": index_tree, "bundle_base": base, "changed_during_capture": again != tree, "ref": ref, "commit": commit, "tree": tree, "parent": head,
            "bundle": bundle, "bundle_sha256": sha256(bundle), "bundle_bytes": os.path.getsize(bundle)}


def raw_overlay(root, rels, archive):
    """Changed and untracked paths as raw bytes (modes, symlinks, CRLF, pre-filter content), with hashes."""
    rels = [r for r in rels if os.path.lexists(os.path.join(root, r))]
    if not rels:
        return None
    t = tar_paths(root, rels, os.path.join(archive, "raw.tar.gz"))
    hashes = {}
    for r in rels:
        fp = os.path.join(root, r)
        if os.path.islink(fp):
            hashes[r] = "link:" + os.readlink(fp)
        elif os.path.isfile(fp):
            hashes[r] = sha256(fp) + ":" + oct(os.stat(fp).st_mode & 0o7777)
    fp = os.path.join(archive, "raw-files.json")
    with open(fp, "w") as fh:
        json.dump(hashes, fh, indent=0, sort_keys=True)
    t["files"] = fp
    t["files_sha256"] = sha256(fp)
    return t


def safe_extract(tf, target):
    """Extract an archive this tool wrote, refusing members that would land outside target."""
    root = os.path.realpath(target)
    for m in tf.getmembers():
        dest = os.path.realpath(os.path.join(root, m.name))
        if not under(dest, root):
            raise SystemExit(f"refusing archive member outside the target: {m.name}")
    try:
        tf.extractall(target, filter="tar")  # keeps modes (the raw-files check depends on them)
    except TypeError:  # Python without extraction filters
        tf.extractall(target)  # members were validated above


def tar_paths(root, rels, out):
    with tarfile.open(out, "w:gz") as tf:
        for rel in rels:
            tf.add(os.path.join(root, rel), arcname=rel, recursive=False)
    with tarfile.open(out, "r:gz") as tf:
        names = set(tf.getnames())
    missing = [r for r in rels if r not in names]
    if missing:
        raise RuntimeError(f"tar verify: {len(missing)} paths missing, first {missing[0]}")
    return {"path": out, "count": len(rels), "sha256": sha256(out)}


def tar_tree(src, out, cfg, cap_bytes=None):
    rels, total = [], 0
    for dp, dns, fns in os.walk(src):
        dns[:] = sorted(d for d in dns if d not in cfg["regenerable"]["dir_names"])
        for d in dns:
            full = os.path.join(dp, d)
            if os.path.islink(full):
                rels.append(os.path.relpath(full, src))
        for fn in sorted(fns):
            fp = os.path.join(dp, fn)
            rel = os.path.relpath(fp, src)
            if regenerable(rel, cfg):
                continue
            with contextlib.suppress(OSError):
                total += os.lstat(fp).st_size
            rels.append(rel)
    if cap_bytes and total > cap_bytes:
        raise RuntimeError(f"{total // 2**20} MB over cap")
    return tar_paths(src, rels, out)


def archive_session(s, archive, cfg, args):
    os.makedirs(os.path.join(archive, "transcripts"), exist_ok=True)
    info = {"session_id": s["session_id"], "bg_id": s.get("bg_id"), "name": s.get("name"), "cwd": s.get("cwd"),
            "project_dir": s.get("project_dir"), "state": s.get("state"), "idle_days": s.get("idle_days")}
    tp = s.get("transcript")
    if tp and os.path.isfile(tp):
        d = describe_transcript(tp)
        info.update(d)
        out = os.path.join(archive, "transcripts", os.path.basename(tp) + ".gz")
        with open(tp, "rb") as fi, gzip.open(out, "wb") as fo:
            shutil.copyfileobj(fi, fo)
        h = hashlib.sha256()
        with gzip.open(out, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        src = sha256(tp)
        if h.hexdigest() != src:
            raise RuntimeError(f"transcript copy mismatch for {s['session_id']}")
        info.update(transcript_copy=out, transcript_sha256=src)
    jd = s.get("job_dir")
    if jd and os.path.isdir(jd):
        out = os.path.join(archive, f"job-{os.path.basename(jd)}.tar.gz")
        cap = cfg["job_tmp_cap_mb"] * 2 ** 20
        try:
            info["job_archive"] = tar_tree(jd, out, cfg, cap)["path"]
        except RuntimeError as e:  # oversized job tmp: keep metadata files only
            rels = [f for f in sorted(os.listdir(jd)) if os.path.isfile(os.path.join(jd, f))]
            info["job_archive"] = tar_paths(jd, rels, out)["path"]
            info["job_archive_note"] = f"tmp/ skipped: {e}"
    return info


def describe(sessions, branch, path):
    for s in sessions:
        label = s.get("title") or s.get("name")
        if label or s.get("first_prompt"):
            return f"{label or ''}: {s.get('first_prompt') or ''}".strip(": ")[:400]
    return f"worktree {os.path.basename(path)} on {branch or 'detached HEAD'}"


# ---------------------------------------------------------------- apply

@contextlib.contextmanager
def run_lock(sd):
    f = open(os.path.join(sd, ".lock"), "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("another dehydrate run holds the lock; try again when it finishes")
    try:
        yield
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()


def rid_for(label, key, now):
    """Stable for one run: the same item in the same plan gets the same id."""
    h = hashlib.sha256(f"{key}\0{now}".encode()).hexdigest()[:6]
    day = dt.datetime.fromtimestamp(now).strftime("%Y%m%d")
    return f"{day}-{slugify(label, 32)}-{h}"


def unique_rid(sd, rid):
    known = {r["id"] for r in read_manifest(sd)}
    base, n = rid, 1
    while rid in known or os.path.exists(os.path.join(sd, "archive", rid)):
        n += 1
        rid = f"{base}-{n}"
    return rid


def claude(args, *a):
    r = subprocess.run([args.claude_bin, *a], capture_output=True, text=True, timeout=120)
    return r.returncode, (r.stdout + r.stderr).strip()


def close_session(args, s):
    steps = []
    pid = s.get("pid")
    alive = False
    if pid:
        with contextlib.suppress(Exception):
            os.kill(int(pid), 0)
            alive = True
    if alive or s.get("state") in ("blocked", "idle"):
        steps.append(("stop",) + claude(args, "stop", s["bg_id"]))
    rc, out = claude(args, "rm", s["bg_id"])
    steps.append(("rm", rc, out))
    return {"closed": rc == 0, "steps": [{"cmd": c, "rc": r, "out": o[-400:]} for c, r, o in steps]}


def apply_plan(args, cfg, plan, sd):
    res = {"worktrees": [], "sessions": [], "mains": [], "orphans": [], "pruned": [], "paused": None,
           "df_before_gb": round(free_gb(), 2), "pressure": None}
    now = plan["now"]
    by_sid = {s["session_id"]: s for s in plan["sessions"] if s["session_id"]}
    tidx = transcript_index(claude_home(args))
    host = socket.gethostname()
    press = plan.get("pressure")
    if press:
        res["pressure"] = {"target_gb": press["target_gb"], "reached": False, "free_checked_gb": None}

    def floor_ok():
        if free_gb() < cfg["disk_floor_gb"]:
            res["paused"] = f"free disk {free_gb():.2f} GB under floor {cfg['disk_floor_gb']} GB"
            return False
        return True

    def target_reached():
        """--pressure only: one free-disk read per item; at or over the target the run stops (not a pause)."""
        if not press:
            return False
        f = pressure_free_gb()
        res["pressure"]["free_checked_gb"] = round(f, 2)
        res["pressure"]["reached"] = f >= press["target_gb"]
        return res["pressure"]["reached"]

    def guarded(kind, item, fn):
        """One item's crash is a "not done" line; the loop goes on and prune/index still run."""
        try:
            fn()
        except Exception as e:
            res[kind].append(dict(item, ok=False, error=f"{e.__class__.__name__}: {str(e)[:300]}"))

    def do_worktree(w):
        rid = unique_rid(sd, rid_for(os.path.basename(w["path"]), f"{w['path']}\0{w['head']}", now))
        archive = os.path.join(sd, "archive", rid)
        os.makedirs(archive, exist_ok=True)
        out = {"id": rid, "path": w["path"]}
        try:
            sess = []
            for sid in w.get("sessions", []):
                s = by_sid.get(sid) or {"session_id": sid, "transcript": (tidx.get(sid) or {}).get("path"),
                                        "project_dir": (tidx.get(sid) or {}).get("project_dir"),
                                        "cwd": (tidx.get(sid) or {}).get("cwd")}
                sess.append(archive_session(s, archive, cfg, args))
            msg = (f"dehydrate {rid}\n\nworktree: {w['path']}\nbranch: {w['branch'] or '(detached)'}\n"
                   f"sessions: {', '.join(w.get('sessions', [])) or 'none'}\n")
            snap = make_snapshot(w["path"], rid, msg, archive)
            raw = raw_overlay(w["path"], w["facts"].get("changed_paths", []), archive)
            ign = ignored_real(w["path"], cfg)
            itar = None
            if ign:
                tot = sum(b for _, b in ign)
                if tot > cfg["ignored_cap_mb"] * 2 ** 20:
                    raise RuntimeError(f"gitignored real files total {tot // 2**20} MB over cap; holding")
                itar = tar_paths(w["path"], [r for r, _ in ign], os.path.join(archive, "ignored.tar.gz"))
            rec = {"event": "dehydrated", "id": rid, "kind": "worktree", "at": iso(time.time()), "host": host,
                   "repo": {"path": w["repo"], "origin": w["origin"]},
                   "worktree": {"path": w["path"], "branch": w["branch"], "head": w["head"],
                                "dirty_count": w["facts"]["dirty_count"], "untracked_count": w["facts"]["untracked_count"],
                                "unpushed": w["facts"]["unpushed"], "upstream": w["facts"]["upstream"]},
                   "snapshot": snap, "raw": raw, "ignored": itar, "sessions": sess, "size_kb": w.get("size_kb"),
                   "description": describe(sess, w["branch"], w["path"]), "archive": archive, "removed": False,
                   "idle_days": w["idle_days"]}
            append_manifest(sd, rec)  # recorded BEFORE anything is removed; a failed write removes nothing
        except Exception as e:
            out.update(ok=False, error=str(e)[:400])
            shutil.rmtree(archive, ignore_errors=True)  # nothing was removed and nothing points here
            with contextlib.suppress(Exception):
                git(w["repo"], "update-ref", "-d", f"refs/dehydrated/{rid}")
            res["worktrees"].append(out)
            return
        try:  # a 300k-file tree can take minutes on a busy disk
            r = git(w["repo"], "worktree", "remove", "--force", w["path"], timeout=3600)
        except subprocess.TimeoutExpired:
            r = subprocess.CompletedProcess([], 1, "", "git worktree remove timed out after 3600s; rerun apply")
        except Exception as e:
            r = subprocess.CompletedProcess([], 1, "", f"git worktree remove failed: {e.__class__.__name__}: {e}")
        if r.returncode != 0:
            out.update(ok=False, removed=False, error=f"captured as {rid} but not removed: {r.stderr.strip()[:300]}")
        else:
            out.update(ok=True, removed=True, description=rec["description"])
            with contextlib.suppress(Exception):
                append_manifest(sd, {"event": "removed", "id": rid, "at": iso(time.time())})
        res["worktrees"].append(out)

    def do_session(s, removed_paths, wrow_by_path):
        wt = s.get("worktree")
        if wt and wt not in removed_paths and s.get("worktree_action") == "dehydrate":
            res["sessions"].append({"bg_id": s["bg_id"], "ok": False, "error": "its worktree was not captured; left open"})
            return
        rid = unique_rid(sd, rid_for("s-" + (s.get("name") or s["bg_id"]), s["session_id"], now))
        archive = os.path.join(sd, "archive", rid)
        os.makedirs(archive, exist_ok=True)
        try:
            info = archive_session(s, archive, cfg, args)
            if s.get("worktree_path") and s["worktree_path"] not in removed_paths:
                raise RuntimeError("session owns a Claude-managed worktree that was not captured; left open")
            linked = next((o["id"] for o in res["worktrees"] if wt and o["path"] == wt and o.get("removed")), None)
            repo_path = (wrow_by_path.get(wt) or {}).get("repo") or \
                (gout(s["cwd"], "rev-parse", "--show-toplevel") if s["cwd"] and os.path.isdir(s["cwd"]) else None)
            rec = {"event": "dehydrated", "id": rid, "kind": "session", "at": iso(time.time()), "host": host,
                   "repo": {"path": repo_path},
                   "worktree": {"path": wt, "branch": (wrow_by_path.get(wt) or {}).get("branch")} if wt else None,
                   "linked_worktree_id": linked, "sessions": [info], "archive": archive,
                   "description": describe([info], None, s["cwd"] or ""), "removed": False,
                   "idle_days": s["idle_days"]}
            append_manifest(sd, rec)
        except Exception as e:
            shutil.rmtree(archive, ignore_errors=True)
            res["sessions"].append({"bg_id": s["bg_id"], "ok": False, "error": str(e)[:400]})
            return
        try:
            closed = close_session(args, s)
        except Exception as e:
            closed = {"closed": False, "steps": [{"cmd": "stop/rm", "rc": -1, "out": f"{e.__class__.__name__}: {e}"}]}
        if closed["closed"]:
            with contextlib.suppress(Exception):
                append_manifest(sd, {"event": "removed", "id": rid, "at": iso(time.time()), "close": closed})
            res["sessions"].append({"bg_id": s["bg_id"], "id": rid, "ok": True, "name": s.get("name")})
        else:
            res["sessions"].append({"bg_id": s["bg_id"], "id": rid, "ok": False, "name": s.get("name"),
                                    "error": f"`claude {closed['steps'][-1]['cmd']}` refused ({closed['steps'][-1]['out'][:200]}). "
                                             f"Left open; its transcript is archived as {rid}. Check it, then close it "
                                             f"yourself with `claude rm {s['bg_id']}` if you are done with it."})

    def do_orphan(o):
        rid = unique_rid(sd, rid_for(os.path.basename(o["path"]), o["path"], now))
        archive = os.path.join(sd, "archive", rid)
        os.makedirs(archive, exist_ok=True)
        try:
            t = tar_tree(o["path"], os.path.join(archive, "tree.tar.gz"), cfg, cfg["orphan_cap_mb"] * 2 ** 20)
            rec = {"event": "dehydrated", "id": rid, "kind": "orphan", "at": iso(time.time()), "host": host,
                   "repo": {"path": o["repo"], "origin": o["origin"]}, "worktree": {"path": o["path"], "branch": None},
                   "tree_tar": t, "archive": archive, "size_kb": o.get("size_kb"), "removed": False,
                   "description": f"unregistered dir {os.path.basename(o['path'])} under {short(o['repo'])}/.claude/worktrees"}
            append_manifest(sd, rec)
        except Exception as e:
            shutil.rmtree(archive, ignore_errors=True)
            res["orphans"].append({"path": o["path"], "ok": False, "error": str(e)[:300]})
            return
        try:
            shutil.rmtree(o["path"])
            with contextlib.suppress(Exception):
                append_manifest(sd, {"event": "removed", "id": rid, "at": iso(time.time())})
            res["orphans"].append({"id": rid, "path": o["path"], "ok": True})
        except Exception as e:
            res["orphans"].append({"id": rid, "path": o["path"], "ok": False, "error": f"archived as {rid} but not removed: {e}"})

    def do_main(m, last_tree):
        try:
            mp = os.path.realpath(m["path"])
            skip = sorted(os.path.relpath(os.path.realpath(w["path"]), mp) + "/" for w in list_worktrees(m["repo"])[1:]
                          if under(os.path.realpath(w["path"]), mp) and os.path.realpath(w["path"]) != mp)
            f = worktree_facts(m, cfg, skip)
            tree = snapshot_tree(m["path"], skip)
        except Exception as e:  # one unreadable checkout must not stop the rest
            res["mains"].append({"path": m["path"], "ok": False, "error": f"not captured: {str(e)[:300]}"})
            return
        why = (f["submodule_dirty"] and f"dirty submodule {f['submodule_dirty'][0]}") or \
              (f["nested_repos"] and f"nested git repo {f['nested_repos'][0]}") or \
              (f["untracked_big"] and f"untracked file over cap: {f['untracked_big'][0]}") or \
              (f["untracked_bytes"] > cfg["untracked_cap_mb"] * 2 ** 20 and f"untracked total {f['untracked_bytes'] // 2**20} MB over cap")
        if why:
            res["mains"].append({"path": m["path"], "ok": False, "error": f"not captured: {why}"})
            return
        if tree and last_tree.get(m["repo"]) == tree:
            res["mains"].append({"path": m["path"], "ok": True, "skipped": "unchanged since last snapshot"})
            return
        rid = unique_rid(sd, rid_for(os.path.basename(m["repo"]) + "-main", f"{m['path']}\0{tree}", now))
        archive = os.path.join(sd, "archive", rid)
        os.makedirs(archive, exist_ok=True)
        try:
            snap = make_snapshot(m["path"], rid, f"dehydrate {rid}\n\nmain checkout snapshot: {m['path']}\n", archive,
                                 strict=False, skip=skip)
            raw = raw_overlay(m["path"], f.get("changed_paths", []), archive)
            ign = ignored_real(m["path"], cfg)
            rec = {"event": "dehydrated", "id": rid, "kind": "main-snapshot", "raw": raw, "at": iso(time.time()), "host": host,
                   "repo": {"path": m["repo"], "origin": m["origin"]},
                   "worktree": {"path": m["path"], "branch": m["branch"], "head": m["head"],
                                "dirty_count": m["facts"]["dirty_count"], "untracked_count": m["facts"]["untracked_count"]},
                   "snapshot": snap, "archive": archive, "removed": False,
                   "ignored_not_captured": len(ign),
                   "description": f"uncommitted work in the {os.path.basename(m['repo'])} main checkout ({m['branch']})"}
            append_manifest(sd, rec)
            res["mains"].append({"path": m["path"], "id": rid, "ok": True})
        except Exception as e:
            shutil.rmtree(archive, ignore_errors=True)
            res["mains"].append({"path": m["path"], "ok": False, "error": str(e)[:300]})

    try:
        # 1. worktrees: smallest first so the floor check frees space early; under --pressure the plan's
        # order (least recently active, then largest) and a stop as soon as free disk reaches the target
        wl = [w for w in plan["worktrees"] if w["action"] == "dehydrate"]
        if press:
            rank = {p: i for i, p in enumerate(press["order"])}
            wl.sort(key=lambda w: rank.get(w["path"], len(rank)))
        else:
            wl.sort(key=lambda w: w.get("size_kb", 0))
        for w in wl:
            if target_reached() or not floor_ok():
                break
            guarded("worktrees", {"path": w["path"]}, lambda: do_worktree(w))
        else:
            target_reached()

        removed_paths = {o["path"] for o in res["worktrees"] if o.get("removed")}
        wrow_by_path = {w["path"]: w for w in plan["worktrees"]}

        # 2. sessions. A session whose worktree is kept or held stays bound to it; closing is fine
        # (the conversation survives), but never let `claude rm` take a worktree we did not capture.
        # Under --pressure only the sessions of worktrees actually removed close, with their worktree.
        sl = [s for s in plan["sessions"] if s["action"] == "close"]
        if press:
            sl = [s for s in sl if s.get("worktree") in removed_paths]
        for s in sl:
            if res["paused"] or not floor_ok():
                break
            guarded("sessions", {"bg_id": s["bg_id"], "name": s.get("name")},
                    lambda: do_session(s, removed_paths, wrow_by_path))

        # 3. unregistered leftover dirs
        for o in [o for o in plan["orphans"] if o["action"] == "archive"]:
            if res["paused"] or not floor_ok():
                break
            guarded("orphans", {"path": o["path"]}, lambda: do_orphan(o))

        # 4. main checkouts: capture only, never touch the checkout
        last_tree = {}
        for r in read_manifest(sd):
            if r.get("event") == "dehydrated" and r.get("kind") == "main-snapshot":
                last_tree[r["repo"]["path"]] = r["snapshot"]["tree"]
        for m in [m for m in plan["mains"] if m["action"] == "snapshot"]:
            if res["paused"] or not floor_ok():
                break
            guarded("mains", {"path": m["path"]}, lambda: do_main(m, last_tree))
    finally:
        # 5. always: prune records of worktrees whose dirs are gone, and rewrite the index
        for repo in sorted({w["repo"] for w in plan["worktrees"] if w["action"] in ("prune", "dehydrate")}):
            try:
                r = git(repo, "worktree", "prune")
                res["pruned"].append({"repo": repo, "ok": r.returncode == 0})
            except Exception as e:
                res["pruned"].append({"repo": repo, "ok": False, "error": str(e)[:200]})
        with contextlib.suppress(Exception):
            res["df_after_gb"] = round(free_gb(), 2)
        with contextlib.suppress(Exception):
            write_index(sd)
    return res


def render_apply(res):
    L = [f"dehydrate apply: free disk {res['df_before_gb']} GB -> {res.get('df_after_gb')} GB"]
    if res["paused"]:
        L.append(f"PAUSED: {res['paused']}")
    pr = res.get("pressure")
    if pr:
        L.append(f"PRESSURE: target {pr['target_gb']} GB free "
                 + ("reached; stopped there" if pr["reached"] else "not reached; no candidates left")
                 + f" (last check {pr['free_checked_gb']} GB)")
    for k in ("worktrees", "orphans", "sessions", "mains"):
        ok = [x for x in res[k] if x.get("ok")]
        bad = [x for x in res[k] if not x.get("ok")]
        L.append(f"  {k}: {len(ok)} done, {len(bad)} not done")
        for x in ok:
            label = short(x.get("path")) or f"{x.get('bg_id')} {x.get('name') or ''}".strip()
            L.append(f"    + {label}" + (f"  -> {x['id']}" if x.get("id") else "") + (f"  ({x['skipped']})" if x.get("skipped") else ""))
        for x in bad:
            L.append(f"    - {x.get('path') or x.get('bg_id')}: {x.get('error')}")
    return "\n".join(L)


# ---------------------------------------------------------------- rehydrate

def find_record(sd, key):
    cur = current_records(sd)
    if key in cur:
        return cur[key]
    hits = [r for r in cur.values() if key in (
        r["id"], *(s.get("session_id") for s in r.get("sessions", [])),
        *(s.get("bg_id") for s in r.get("sessions", [])),
        *((s.get("session_id") or "")[:8] for s in r.get("sessions", [])),
        (r.get("worktree") or {}).get("path"), (r.get("worktree") or {}).get("branch"))]
    if len(hits) > 1:
        sess = [h for h in hits if h["kind"] == "session"]
        if len(sess) == 1:
            return sess[0]  # a session id names the session; its record restores the linked worktree too
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        lines = "\n".join(f"  {h['id']}  {h['at'][:10]}  {h['kind']}  {(h.get('description') or '')[:90]}" for h in hits)
        raise SystemExit(f"'{key}' matches {len(hits)} records; rerun with one of these ids:\n{lines}")
    raise SystemExit(f"no manifest record matches '{key}'. Search by words with: list <words>")


def restore_transcript(args, info):
    sid = info.get("session_id")
    ch = claude_home(args)
    existing = transcript_index(ch).get(sid)
    if existing:
        return existing["path"], False
    copy = info.get("transcript_copy")
    if not copy or not os.path.isfile(copy):
        return None, False
    pd = info.get("project_dir") or re.sub(r"[^A-Za-z0-9]", "-", info.get("cwd") or "unknown")
    dest_dir = os.path.join(ch, "projects", pd)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f"{sid}.jsonl")
    with gzip.open(copy, "rb") as fi, open(dest + ".tmp", "wb") as fo:
        shutil.copyfileobj(fi, fo)
    if info.get("transcript_sha256") and sha256(dest + ".tmp") != info["transcript_sha256"]:
        os.unlink(dest + ".tmp")
        raise SystemExit(f"archived transcript for {sid} fails its checksum")
    os.replace(dest + ".tmp", dest)
    return dest, True


def rehydrate_worktree(rec, target, args):
    repo = rec["repo"]["path"]
    if not repo or not os.path.isdir(repo):
        raise SystemExit(f"repo {repo} is gone; clone it there first")
    if os.path.exists(target):
        raise SystemExit(f"{target} already exists; pass --path to put the worktree elsewhere")
    snap = rec["snapshot"]
    ref = snap["ref"]
    checks = [(rec.get("ignored") or {}).get("path"), (rec.get("ignored") or {}).get("sha256"), "ignored"], \
        [(rec.get("raw") or {}).get("path"), (rec.get("raw") or {}).get("sha256"), "raw"], \
        [(rec.get("raw") or {}).get("files"), (rec.get("raw") or {}).get("files_sha256"), "raw"]
    for path_, want, part in checks:
        if path_ and (not os.path.isfile(path_) or (want and sha256(path_) != want)):
            a = {"path": path_}
            raise SystemExit(f"archive file {a['path']} is missing or corrupt, so the {part} files cannot be restored; "
                             f"nothing was changed")
    if git(repo, "cat-file", "-e", snap["commit"] + "^{commit}").returncode != 0:
        b = snap["bundle"]
        if not os.path.isfile(b) or sha256(b) != snap["bundle_sha256"]:
            raise SystemExit(f"snapshot {snap['commit']} is not in {repo} and the bundle is missing or corrupt")
        git(repo, "fetch", "-q", b, f"{ref}:{ref}", check=True)
    branch = (rec.get("worktree") or {}).get("branch")
    parent = snap.get("parent")
    notes = []
    if branch and git(repo, "rev-parse", "--verify", "-q", f"refs/heads/{branch}").returncode == 0:
        tip = gout(repo, "rev-parse", f"refs/heads/{branch}")
        in_use = any(w["branch"] == branch for w in list_worktrees(repo))
        if tip == parent and not in_use:
            git(repo, "worktree", "add", "-q", target, branch, check=True)
        else:
            nb = f"{branch}-rehydrated-{dt.date.today():%Y%m%d}"
            why = "checked out elsewhere" if in_use else f"moved since dehydrate ({tip[:8]} != {str(parent)[:8]})"
            git(repo, "worktree", "add", "-q", "-b", nb, target, parent or snap["commit"], check=True)
            notes.append(f"branch {branch} {why}; restored on new branch {nb}")
    elif branch:
        git(repo, "worktree", "add", "-q", "-b", branch, target, parent or snap["commit"], check=True)
        notes.append(f"branch {branch} was deleted; recreated at {str(parent)[:8]}")
    else:
        git(repo, "worktree", "add", "-q", "--detach", target, parent or snap["commit"], check=True)
    # working tree := snapshot tree, index := HEAD (changes come back unstaged, untracked stays untracked)
    git(target, "checkout", snap["commit"], "--", ".", check=True)
    git(target, "reset", "-q", check=True)
    gone = gout(target, "diff", "--name-only", "--no-renames", "--diff-filter=D", "-z", "HEAD", snap["commit"])
    for rel in [x for x in gone.split("\0") if x]:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(os.path.join(target, rel))
    if snap.get("index_tree") and gout(target, "rev-parse", "HEAD") == parent:
        git(target, "read-tree", snap["index_tree"], check=True)  # staged changes come back staged
    else:
        notes.append("staging not restored (no index recorded or branch moved); all changes are unstaged")
    if rec.get("ignored"):
        with tarfile.open(rec["ignored"]["path"], "r:gz") as tf:
            safe_extract(tf, target)
        notes.append(f"restored {rec['ignored']['count']} gitignored files")
    if rec.get("raw"):
        with tarfile.open(rec["raw"]["path"], "r:gz") as tf:  # exact bytes, modes and links win over git's view
            safe_extract(tf, target)
        bad = []
        for r, want in json.load(open(rec["raw"]["files"])).items():
            fp = os.path.join(target, r)
            got = ("link:" + os.readlink(fp)) if os.path.islink(fp) else \
                (sha256(fp) + ":" + oct(os.stat(fp).st_mode & 0o7777) if os.path.isfile(fp) else None)
            if got != want:
                bad.append(r)
        if bad:
            notes.append(f"WARNING: {len(bad)} restored files differ from what was captured, first {bad[0]}")
    if snapshot_tree(target) != snap["tree"]:
        notes.append("WARNING: restored tree differs from the snapshot tree")
    return notes


def cmd_rehydrate(args):
    sd = state_dir(args)
    rec = find_record(sd, args.key)
    notes, where = [], None
    with run_lock(sd):
        if rec["kind"] == "session" and rec.get("linked_worktree_id") and not args.session_only:
            wrec = current_records(sd).get(rec["linked_worktree_id"])
            if wrec and not os.path.exists(wrec["worktree"]["path"]):
                notes += rehydrate_worktree(wrec, wrec["worktree"]["path"], args)
                append_manifest(sd, {"event": "rehydrated", "id": wrec["id"], "at": iso(time.time()),
                                     "path": wrec["worktree"]["path"], "via": rec["id"]})
            where = wrec["worktree"]["path"] if wrec else None
        elif rec["kind"] in ("worktree", "main-snapshot"):
            target = os.path.realpath(os.path.expanduser(args.path)) if args.path else rec["worktree"]["path"]
            if rec["kind"] == "main-snapshot" and not args.path:
                raise SystemExit("a main-snapshot is restored next to the checkout, never over it: pass --path <dir>")
            notes += rehydrate_worktree(rec, target, args)
            where = target
        elif rec["kind"] == "orphan":
            target = os.path.expanduser(args.path) if args.path else rec["worktree"]["path"]
            if os.path.exists(target):
                raise SystemExit(f"{target} already exists; pass --path")
            os.makedirs(target)
            with tarfile.open(rec["tree_tar"]["path"], "r:gz") as tf:
                safe_extract(tf, target)
            where = target
        resumes = []
        for info in rec.get("sessions", []):
            if not info.get("session_id"):
                continue
            path, restored = restore_transcript(args, info)
            cwd = where if where and os.path.isdir(where) else (info.get("cwd") if info.get("cwd") and os.path.isdir(info["cwd"]) else None)
            cwd = cwd or rec["repo"].get("path") or os.path.expanduser("~")
            resumes.append({"session_id": info["session_id"], "name": info.get("name") or info.get("title"),
                            "cwd": cwd, "transcript": path, "transcript_restored": restored,
                            "command": f"cd {shlex.quote(cwd)} && claude --resume {info['session_id']}"})
        append_manifest(sd, {"event": "rehydrated", "id": rec["id"], "at": iso(time.time()), "path": where})
        write_index(sd)
    launched = []
    if args.launch:
        running = set()
        with contextlib.suppress(Exception):
            p = subprocess.run([args.claude_bin, "agents", "--json"], capture_output=True, text=True, timeout=60)
            running = {a.get("sessionId") for a in json.loads(p.stdout or "[]")}
        for r in resumes:
            if not r["transcript"]:
                continue
            if r["session_id"] in running:
                launched.append({"session_id": r["session_id"], "rc": 0, "out": "already running; not started again"})
                continue
            p = subprocess.run([args.claude_bin, "--bg", "--resume", r["session_id"]], cwd=r["cwd"],
                               capture_output=True, text=True, timeout=120)
            launched.append({"session_id": r["session_id"], "rc": p.returncode, "out": (p.stdout + p.stderr).strip()[-300:]})
    out = {"id": rec["id"], "kind": rec["kind"], "path": where, "notes": notes, "resume": resumes, "launched": launched}
    if args.json:
        print(json.dumps(out, indent=1))
    else:
        print(f"rehydrated {rec['id']} ({rec['kind']})" + (f" at {where}" if where else ""))
        for n in notes:
            print(f"  note: {n}")
        for r in resumes:
            print(f"  resume {r['name'] or r['session_id'][:8]}: {r['command']}"
                  + ("" if r["transcript"] else "   (no transcript archived; resume will fail)"))
        for l in launched:
            print(f"  launched {l['session_id'][:8]} rc={l['rc']} {l['out']}")


# ---------------------------------------------------------------- list / show / nudge

def cmd_list(args):
    sd = state_dir(args)
    cur = sorted(current_records(sd).values(), key=lambda r: r["at"], reverse=True)
    words = [w.lower() for w in args.words]
    hits = []
    for r in cur:
        vals = [r["id"], r.get("description"), (r.get("repo") or {}).get("path"), (r.get("repo") or {}).get("origin"),
                (r.get("worktree") or {}).get("path"), (r.get("worktree") or {}).get("branch")]
        for x in r.get("sessions", []):
            vals += [x.get("name"), x.get("title"), x.get("first_prompt"), x.get("session_id"), x.get("bg_id")]
        hay = "\n".join(str(v) for v in vals if v).lower()
        if all(w in hay for w in words) and (args.kind is None or r["kind"] == args.kind):
            hits.append(r)
    hits = hits[: args.limit]
    if args.json:
        print(json.dumps(hits, indent=1))
        return
    if not hits:
        print("no matching dehydrated records")
    for r in hits:
        st = "rehydrated" if r["rehydrations"] else ("removed" if r.get("removed") else "in place")
        print(f"{r['id']}  {r['at'][:10]}  {r['kind']:13s} {short((r.get('worktree') or {}).get('path') or (r.get('repo') or {}).get('path') or '')}  [{st}]")
        print(f"    {(r.get('description') or '')[:200]}")


def cmd_show(args):
    print(json.dumps(find_record(state_dir(args), args.key), indent=1))


def cmd_refresh(args, cfg):
    sd = state_dir(args)
    if args.detach:
        if os.fork():
            return
        os.setsid()
        if os.fork():
            os._exit(0)
        devnull = os.open(os.devnull, os.O_RDWR)
        for fd in (0, 1, 2):
            os.dup2(devnull, fd)
    try:
        lock = open(os.path.join(sd, ".refresh.lock"), "w")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lp = os.path.join(sd, "last-plan.json")
        if args.if_stale and os.path.isfile(lp) and time.time() - os.path.getmtime(lp) < cfg["refresh_after_hours"] * 3600:
            return
        plan = build_plan(args, cfg)
        if cfg.get("auto_apply"):
            with run_lock(sd):
                res = apply_plan(args, cfg, plan, sd)
            plan["auto_applied"] = {"at": iso(time.time()), "summary": render_apply(res)}
            plan = build_plan(args, cfg)
        tmp = lp + ".tmp"
        json.dump(plan, open(tmp, "w"))
        os.replace(tmp, lp)
    except Exception:
        pass
    finally:
        if args.detach:
            os._exit(0)


def cmd_nudge(args):
    try:
        sd = state_dir(args)
        cfg = load_config(sd)
        stamp = os.path.join(sd, "last-nudged")
        if os.path.isfile(stamp) and time.time() - os.path.getmtime(stamp) < cfg["nudge_cooldown_hours"] * 3600:
            return
        lp = os.path.join(sd, "last-plan.json")
        if not os.path.isfile(lp):
            return
        t = json.load(open(lp))["totals"]
        n = t["sessions_close"] + t["worktrees_dehydrate"] + t["orphans_archive"]
        if n:
            print(f"DEHYDRATE: {t['sessions_close']} sessions and {t['worktrees_dehydrate'] + t['orphans_archive']} "
                  f"worktrees idle over {cfg['days']}d (about {t['reclaim_kb'] / 2**20:.1f} GB). "
                  f"Run /dehydrate when this turn's work is done.")
            open(stamp, "w").write(iso(time.time()))
    except Exception:
        pass


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(prog="dehydrate", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd")

    def common(p):
        p.add_argument("--days", type=float, help="idle threshold in days (default 7, config 'days')")
        p.add_argument("--roots", nargs="+", help="dirs to search for repos (default ~/src)")
        p.add_argument("--only", nargs="+", help="limit to these worktree paths/basenames/branches or session ids")
        p.add_argument("--no-sessions", action="store_true", help="leave sessions alone")
        p.add_argument("--no-worktrees", action="store_true", help="leave worktrees alone")
        p.add_argument("--mains", action="store_true", help="also snapshot uncommitted work in main checkouts (never resets them)")
        p.add_argument("--no-main", action="store_true", help="skip main-checkout snapshots even if config enables them")
        p.add_argument("--state-dir", help="manifest/archive dir (default ~/.claude/dehydrated)")
        p.add_argument("--claude-home", help="Claude config dir (default ~/.claude)")
        p.add_argument("--agents-json", default=os.environ.get("DEHYDRATE_AGENTS_JSON"),
                       help="read sessions from this file instead of `claude agents --json --all`")
        p.add_argument("--claude-bin", default=os.environ.get("DEHYDRATE_CLAUDE_BIN", "claude"))
        p.add_argument("--now", type=float, default=float(os.environ["DEHYDRATE_NOW"]) if os.environ.get("DEHYDRATE_NOW") else None,
                       help="epoch seconds to treat as now (tests)")
        p.add_argument("--json", action="store_true")

    for name in ("plan", "apply", "refresh"):
        p = sub.add_parser(name)
        common(p)
        if name == "refresh":
            p.add_argument("--detach", action="store_true")
            p.add_argument("--if-stale", action="store_true")
        if name == "apply":
            p.add_argument("--yes", action="store_true", help="required: apply acts without a prompt")
        if name in ("plan", "apply"):
            p.add_argument("--pressure", action="store_true",
                           help="disk-pressure mode: ignore --days for worktrees, go least recently active first, "
                                "stop once free disk reaches --target-gb (every hold still applies)")
            p.add_argument("--target-gb", type=float, help="with --pressure: stop when free disk is at least this")
    p = sub.add_parser("list")
    p.add_argument("words", nargs="*")
    p.add_argument("--kind", choices=["worktree", "session", "orphan", "main-snapshot"])
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--state-dir")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("show")
    p.add_argument("key")
    p.add_argument("--state-dir")
    p = sub.add_parser("rehydrate")
    p.add_argument("key", help="manifest id, session id (or first 8), background id, branch or worktree path")
    p.add_argument("--path", help="restore the worktree here instead of its original path")
    p.add_argument("--session-only", action="store_true", help="restore the transcript only, not the worktree")
    p.add_argument("--launch", action="store_true", help="resume the sessions in the background (claude --bg --resume)")
    p.add_argument("--state-dir")
    p.add_argument("--claude-home")
    p.add_argument("--claude-bin", default=os.environ.get("DEHYDRATE_CLAUDE_BIN", "claude"))
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("nudge")
    p.add_argument("--state-dir")
    p.add_argument("--claude-home")

    args = ap.parse_args(argv)
    if not args.cmd:
        args = ap.parse_args(["plan"] + (argv or sys.argv[1:]))
    if os.environ.get("CLAUDE_CODE_REMOTE") == "true" and args.cmd in ("plan", "apply", "refresh"):
        print("dehydrate is local-desktop only (cloud sessions have no ~/src or background sessions)")
        return 0
    if args.cmd == "list":
        return cmd_list(args)
    if args.cmd == "show":
        return cmd_show(args)
    if args.cmd == "rehydrate":
        return cmd_rehydrate(args)
    if args.cmd == "nudge":
        return cmd_nudge(args)
    sd = state_dir(args)
    cfg = load_config(sd)
    if args.days is not None:
        if args.days < 0:
            ap.error("--days must be zero or more")
        cfg["days"] = args.days
    if args.roots or os.environ.get("DEHYDRATE_ROOTS"):
        cfg["roots"] = args.roots or os.environ["DEHYDRATE_ROOTS"].split(":")
    if getattr(args, "mains", False):
        cfg["snapshot_main"] = True
    if args.cmd == "refresh":
        return cmd_refresh(args, cfg)
    if getattr(args, "pressure", False) != (getattr(args, "target_gb", None) is not None):
        ap.error("--pressure and --target-gb go together")
    if getattr(args, "pressure", False) and (args.only or args.target_gb <= 0):
        ap.error("--pressure takes a positive --target-gb and no --only")
    plan = build_plan(args, cfg)
    if args.only and not any(plan[k] for k in ("sessions", "worktrees", "orphans")):
        print(f"--only {' '.join(args.only)} matched no worktree path, basename or branch and no session id")
        return 4
    if args.cmd == "plan":
        print(json.dumps(plan, indent=1, default=str) if args.json else render_plan(plan))
        return 0
    if not args.yes:
        print("apply acts without asking: rerun with --yes (run `plan` first to see what it will do)")
        return 2
    with run_lock(sd):
        res = apply_plan(args, cfg, plan, sd)
    res["plan_totals"] = plan["totals"]
    json.dump(res, open(os.path.join(sd, "last-apply.json"), "w"), indent=1)
    print(json.dumps(res, indent=1) if args.json else render_apply(res))
    if res["paused"]:
        return 3
    return 1 if any(not x.get("ok") and not x.get("skipped") for k in ("worktrees", "orphans", "sessions", "mains")
                    for x in res[k]) else 0


if __name__ == "__main__":
    sys.exit(main() or 0)
