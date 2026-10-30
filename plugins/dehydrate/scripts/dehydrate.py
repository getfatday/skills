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
             With auto_on_close it first runs the auto sweep (at most once per auto_sweep_minutes).
  auto       dehydrate ended sessions whose worktree branch is merged into the remote default branch.
             No --session: sweep `claude agents`. --session SID: that one session (the mod's session.end).
             --status: is it on, the last sweep and decision.
  config     show the effective settings, or get/set/unset one key in <state>/config.json (type-checked).

Everything it decides is deterministic: the same census and the same --now give the same plan.

Storage (user level, one place for every repo)
  <state> = $DEHYDRATE_HOME or ~/.claude/dehydrated
  <state>/manifest.jsonl     append-only event log, one JSON object per line
  <state>/index.md           human-readable view, regenerated from the manifest
  <state>/archive/<id>/      snapshot.bundle, ignored.tar.gz, transcripts/*.jsonl.gz, job.tar.gz
  <state>/config.json        optional overrides (days, roots, exclude_globs, caps, auto_apply, auto_*)
  <state>/auto.log           JSONL, one line per auto decision (why a session was or was not auto-dehydrated)
  <state>/agents-cache.json  last good `claude agents --json` listing (list --picker falls back to it)

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
import signal
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
ENDED_STATES = {"done", "stopped", "failed"}  # a job dir's worktree may go only once its session ended (and the grace passed)
PRESSURE_RECENT_S = 2 * 3600  # --pressure: a tree touched this recently is in use, whatever its session says
PRESSURE_MARGIN_BYTES = 200 * 2 ** 20  # --pressure: free space an item's capture must leave over its estimate
BIG_TREE_TIMEOUT_S = 3600  # git calls that check out, read or remove a whole tree (300k files take minutes)

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
    # auto: dehydrate a session and its worktree once it has ended and its branch is merged (DESIGN 6)
    "auto_on_close": True,
    "auto_grace_minutes": 10,     # a swept session must have ended at least this long ago
    "auto_sweep_minutes": 10,     # minimum gap between SessionStart sweeps
    "auto_use_gh": True,          # allow the gh merged-PR check; False = git only
    "auto_fetch_timeout_s": 30,
    "auto_require_clean": False,  # True: a dirty or untracked tree is never auto-dehydrated
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


EXTRA_KEYS = {"workers": 8}  # read with a default, not in DEFAULTS (thread pool size)


def config_type_error(k, v):
    """Why value v does not fit key k (None when it fits). Types follow DEFAULTS; a bool is never a number."""
    want = DEFAULTS.get(k, EXTRA_KEYS.get(k))
    if isinstance(want, bool):
        return None if isinstance(v, bool) else f"{k} must be true or false (got {json.dumps(v)})"
    if isinstance(want, (int, float)):
        return None if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else \
            f"{k} must be a number of zero or more (got {json.dumps(v)})"
    if isinstance(want, list):
        return None if isinstance(v, list) and all(isinstance(x, str) for x in v) else \
            f"{k} must be a list of strings (got {json.dumps(v)})"
    if isinstance(want, dict):
        return None if isinstance(v, dict) else f"{k} must be an object (got {json.dumps(v)})"
    return None


def load_config(sd):
    """DEFAULTS with config.json merged over them. A value of the wrong type keeps its default and sets
    `_config_error`, which turns auto off (so `"auto_on_close": "false"` is off, never on). Keys this version
    does not know are kept in `_config_unknown`, for `auto --dry-run`, `auto --status`, `config` and `nudge`."""
    cfg = json.loads(json.dumps(DEFAULTS))
    p = os.path.join(sd, "config.json")
    if os.path.isfile(p):
        try:
            user = json.load(open(p))
            if not isinstance(user, dict):
                raise ValueError("config.json must hold one JSON object")
            errors, unknown = [], []
            for k, v in user.items():
                if k not in DEFAULTS and k not in EXTRA_KEYS:
                    unknown.append(k)
                    continue
                why = config_type_error(k, v)
                if why:
                    errors.append(why)
                elif isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
            if errors:
                cfg["_config_error"] = "; ".join(errors)
            if unknown:
                cfg["_config_unknown"] = sorted(unknown)
        except Exception as e:  # a broken config must not break a SessionStart hook
            cfg["_config_error"] = str(e)
    return cfg


def config_warnings(cfg):
    out = []
    if cfg.get("_config_error"):
        out.append(f"config error, auto is off until it is fixed: {cfg['_config_error']}")
    if cfg.get("_config_unknown"):
        out.append(f"config keys this version does not know (typo?): {', '.join(cfg['_config_unknown'])}")
    return out


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

class AgentsUnavailable(RuntimeError):
    """`claude agents --json --all` could not be read (twice). Callers hold what it would have decided."""


def agents_timeout_s():
    return float(os.environ.get("DEHYDRATE_AGENTS_TIMEOUT_S", "300"))  # it takes minutes on a host short of disk


def load_agents(args):
    """The agents roster: --agents-json, or `claude agents --json --all` with a 300 s timeout, tried twice. Raises
    AgentsUnavailable; a failure is remembered on args so one plan does not wait for it again."""
    if getattr(args, "_agents", None) is not None:
        return args._agents
    if getattr(args, "_agents_error", None):
        raise AgentsUnavailable(args._agents_error)
    if args.agents_json:
        try:
            with open(args.agents_json) as fh:
                return json.load(fh)
        except (OSError, ValueError) as e:
            args._agents_error = f"agents list unavailable ({args.agents_json}: {e})"
            raise AgentsUnavailable(args._agents_error)
    why, tmo = None, agents_timeout_s()
    for _ in range(2):
        try:
            r = subprocess.run([args.claude_bin, "agents", "--json", "--all"], capture_output=True, text=True,
                               timeout=tmo, stdin=subprocess.DEVNULL)
            if r.returncode == 0:
                return json.loads(r.stdout or "[]")
            why = f"exit {r.returncode}: {r.stderr.strip()[:200]}"
        except subprocess.TimeoutExpired:
            why = f"no answer in {tmo:g}s"
        except (OSError, ValueError) as e:
            why = f"{e.__class__.__name__}: {str(e)[:200]}"
    args._agents_error = f"agents list unavailable (claude agents --json --all, tried twice: {why})"
    raise AgentsUnavailable(args._agents_error)


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
    out = {"title": None, "first_prompt": None, "last_text": None, "git_branch": None, "agent_name": None}
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
                elif t == "agent-name" and o.get("agentName"):
                    out["agent_name"] = o["agentName"]  # the last one wins: it tracks renames
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
        st = {}
        with contextlib.suppress(Exception):  # agents rows never carry worktreePath (2.1.312); the job's state.json does
            st = json.load(open(os.path.join(jobd, "state.json"))) if jobd else {}
        st = st if isinstance(st, dict) else {}
        wtp = a.get("worktreePath") or st.get("worktreePath")
        row = {"bg_id": bid, "session_id": sid, "name": a.get("name") or "", "cwd": a.get("cwd") or "",
               "kind": a.get("kind") or "", "state": state, "pid": a.get("pid"),
               "last_activity": last, "idle_days": round((now - last) / 86400, 2),
               "transcript": t["path"] if t else None, "project_dir": t["project_dir"] if t else None,
               "job_dir": jobd if jobd and os.path.isdir(jobd) else None,
               "worktree_path": os.path.realpath(wtp) if wtp else None,
               "worktree_branch": a.get("worktreeBranch") or st.get("worktreeBranch"),
               "intent": st.get("intent") if isinstance(st.get("intent"), str) else None,
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


def worktree_rows(cfg, sessions, tidx, now, only=None, pressure=False, jobs=None):
    from concurrent.futures import ThreadPoolExecutor
    repos = find_repos(cfg)
    cwds = process_cwds()
    me_cwd = os.path.realpath(os.getcwd())
    keep_sessions = [s for s in sessions if s["action"] == "keep" and s.get("rcwd")]
    with ThreadPoolExecutor(max_workers=cfg.get("workers", 8)) as ex:
        parts = list(ex.map(lambda r: repo_rows(r, cfg, sessions, keep_sessions, tidx, now, only, cwds, me_cwd, pressure,
                                                jobs), repos))
    rows = [x for p in parts for x in p[0]]
    mains = [x for p in parts for x in p[1]]
    orphans = [x for p in parts for x in p[2]]
    return rows, mains, orphans


def job_sessions(args, cfg, tidx, now, sessions=None):
    """{"root": realpath of <claude home>/jobs, "rows": bg id -> session row}; rows is None when `claude agents`
    cannot be read, which holds every worktree under a job dir (fail closed)."""
    root = os.path.realpath(os.path.join(claude_home(args), "jobs"))
    if sessions is None:
        try:
            sessions = session_rows(args, cfg, tidx, now)
        except Exception:
            return {"root": root, "rows": None}
    return {"root": root, "rows": {s["bg_id"]: s for s in sessions if s.get("bg_id")}}


def job_dir_hold(path, jobs, cfg, now):
    """Why a worktree inside ~/.claude/jobs/<id>/ must stay: its session <id> is listed and has not ended at least
    auto_grace_minutes ago (or its process still runs). None when it is not in a job dir or that session is gone."""
    if not jobs or not under(path, jobs["root"]) or path.rstrip("/") == jobs["root"]:
        return None
    jid = os.path.relpath(path, jobs["root"]).split(os.sep)[0]
    if jobs["rows"] is None:
        return f"agents list unavailable: inside the job dir of session {jid}, which may still be running"
    s = jobs["rows"].get(jid)
    if s is None:
        return None
    state = s.get("state") or "unknown"
    label = f"inside the job dir of {state} session {jid}" + (f" {s['name']}" if s.get("name") else "")
    if state not in ENDED_STATES:
        return label
    grace = cfg["auto_grace_minutes"] * 60
    if now - s["last_activity"] < grace:
        return f"{label} (ended {(now - s['last_activity']) / 60:.0f} min ago, < auto_grace_minutes {cfg['auto_grace_minutes']})"
    if s.get("pid") and pid_alive(s["pid"]):
        return f"{label} (its process {s['pid']} is still alive)"
    return None


def git_processes_on(path, live=()):
    """pids of running git commands that name path or have their cwd inside it (`git worktree add` runs in the repo)."""
    try:
        out = subprocess.run(["ps", "-axww", "-o", "pid=,args="], capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return ["unknown (ps failed)"]
    hits = []
    for line in out.splitlines():
        pid, _, cmd = line.strip().partition(" ")
        exe = os.path.basename(cmd.split(" ", 1)[0]) if cmd else ""
        if (exe == "git" or exe.startswith("git-")) and (path in cmd or pid in live):
            hits.append(pid)
    return hits


def lock_hold(w, path, live):
    if w["lock_reason"] != "initializing":
        return f"locked ({w['lock_reason'] or 'no reason'})"
    busy = git_processes_on(path, live)
    if busy:
        return f"checkout in progress (git lock 'initializing'; git process {busy[0]} is still writing it)"
    return ("interrupted checkout (git lock 'initializing' left by a killed worktree add); "
            f"unlock with: git worktree unlock {shlex.quote(path)}")


def repo_rows(repo, cfg, sessions, keep_sessions, tidx, now, only, cwds, me_cwd, pressure=False, jobs=None):
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
            job = job_dir_hold(path, jobs, cfg, now)
            if under(me_cwd, path):
                row.update(action="keep", reason="this session's cwd")
            elif kept:
                row.update(action="keep", reason=f"bound to kept session {kept[0]['bg_id'] or kept[0]['session_id'][:8]}")
            elif job:
                row.update(action="hold", reason=job)
            elif jobs and jobs["rows"] is None and row["sessions"]:
                row.update(action="hold", reason=f"agents list unavailable: bound to session {row['sessions'][0][:8]}, "
                                                 "which may still be running")
            elif now - row["last_activity"] < wt_days * 86400:
                row.update(action="keep", reason=f"active {row['idle_days']}d ago (< {cfg['days']}d)")
            elif pressure and now - row["last_activity"] < PRESSURE_RECENT_S:
                # last_activity folds in the HEAD reflog, the dir, every dirty or untracked file and bound sessions
                row.update(action="hold", reason=f"pressure: touched {(now - row['last_activity']) / 60:.0f} min ago "
                                                 f"(files or HEAD reflog within {PRESSURE_RECENT_S // 3600}h)")
            elif w["locked"]:
                row.update(action="hold", reason=lock_hold(w, path, live))
            elif not facts:
                row.update(action="hold", reason="could not read worktree state")
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
    sessions, agents_err = [], None
    if not args.no_sessions:
        try:
            sessions = session_rows(args, cfg, tidx, now)
        except AgentsUnavailable as e:  # hold every session-bound and job-dir tree; close no session
            agents_err = str(e)
    jobs = {"root": os.path.realpath(os.path.join(claude_home(args), "jobs")), "rows": None} if agents_err else \
        job_sessions(args, cfg, tidx, now, None if args.no_sessions else sessions)
    if args.no_main or args.only:
        cfg = dict(cfg, snapshot_main=False)
    if args.no_worktrees and not cfg["snapshot_main"]:
        wts, mains, orphans = [], [], []
    else:
        wts, mains, orphans = worktree_rows(cfg, sessions, tidx, now, args.only, pressure, jobs)
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
        free = free_gb()
        est = 0 if free >= args.target_gb else None  # how many candidates apply expects to take; None: not enough
        for i, w in enumerate(order, 1):
            w["pressure_rank"] = i
            free += (w.get("size_kb") or 0) / 2 ** 20
            if est is None and free >= args.target_gb:
                est = i
        press = {"target_gb": args.target_gb, "free_gb": round(free_gb(), 2),
                 "order": [w["path"] for w in order], "estimated_stop_after": est}
    return {"schema": SCHEMA, "now": now, "now_iso": iso(now), "days": cfg["days"], "host": socket.gethostname(),
            "pressure": press, "agents_unavailable": agents_err or (jobs["rows"] is None and getattr(args, "_agents_error", None)) or None,
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
    if plan.get("agents_unavailable"):
        L.insert(1, f"  {plan['agents_unavailable']}: no session closes, and every session-bound or job-dir worktree is held")
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

def sparse_info(path):
    """{"cone": bool, "patterns": [...]} when the worktree uses sparse-checkout, else None."""
    if gout(path, "config", "--bool", "core.sparseCheckout") != "true":
        return None
    pats = [x for x in gout(path, "sparse-checkout", "list").splitlines() if x]
    return {"cone": gout(path, "config", "--bool", "core.sparseCheckoutCone") != "false", "patterns": pats}


def git_at_least(*want):
    m = re.search(r"(\d+)\.(\d+)", gout(os.getcwd(), "--version"))
    return bool(m) and tuple(int(x) for x in m.groups()) >= want


def snapshot_tree(path, skip=()):
    """Tree of the worktree as it stands (tracked + staged + untracked, ignores respected).

    A sparse worktree starts from a copy of its real index, whose skip-worktree bits mark the files outside the
    cone as absent on purpose; a temp index read from HEAD has no such bits, and `add -A` would record every one
    of them as deleted. `--sparse` lets add touch entries outside the cone (git >= 2.34)."""
    fd, idx = tempfile.mkstemp(prefix="dehydrate-idx-")
    os.close(fd)
    os.unlink(idx)
    try:
        env = {"GIT_INDEX_FILE": idx}
        sparse = sparse_info(path) is not None
        if sparse and not git_at_least(2, 34):
            raise RuntimeError("sparse-checkout worktree needs git 2.34+ (git add --sparse) to be captured")
        real = os.path.join(worktree_gitdir(path) or "", "index")
        head_ok = git(path, "rev-parse", "--verify", "-q", "HEAD").returncode == 0
        if sparse and os.path.isfile(real):
            shutil.copyfile(real, idx)
        elif head_ok:
            git(path, "read-tree", "HEAD", env=env, check=True, timeout=BIG_TREE_TIMEOUT_S)
        # excluding an already-ignored path is an error for git add, and unnecessary
        skip = [k for k in skip if git(path, "check-ignore", "-q", "--", k.rstrip("/")).returncode != 0]
        git(path, "add", "-A", *(["--sparse"] if sparse else []), "--", ".", *[f":(exclude){k}" for k in skip],
            env=env, check=True, timeout=1800)
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
        if not info.get("name") and d.get("agent_name"):
            info["name"] = d["agent_name"]
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
    if not info.get("first_prompt") and s.get("intent"):
        info["first_prompt"] = re.sub(r"\s+", " ", s["intent"])[:300]  # transcript missing: the job's intent
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

def capture_estimate(w):
    """Upper bound, in bytes, of what capturing w writes to disk: the raw overlay (dirty + untracked bytes), the
    gitignored-real tarball, and the bundle (objects of unpushed commits, plus the snapshot's blobs, which are the
    same dirty + untracked bytes). Compression only makes the real figure smaller."""
    f = w.get("facts") or {}
    overlay = 0
    for rel in f.get("changed_paths", []):
        with contextlib.suppress(OSError):
            overlay += os.lstat(os.path.join(w["path"], rel)).st_size
    objs = 0
    if f.get("unpushed"):
        revs = gout(w["path"], "rev-list", "--objects", "HEAD", "--not", "--remotes", timeout=600)
        ids = "\n".join(line.split(" ", 1)[0] for line in revs.splitlines() if line)
        if ids:
            r = subprocess.run(["git", "-C", w["path"], "cat-file", "--batch-check=%(objectsize)"], input=ids + "\n",
                               capture_output=True, text=True, timeout=600)
            objs = sum(int(x) for x in r.stdout.split() if x.isdigit())
    return {"overlay": overlay, "ignored": f.get("ignored_real_bytes", 0), "bundle": objs + overlay,
            "total": overlay + f.get("ignored_real_bytes", 0) + objs + overlay}


class LockHeld(SystemExit):
    pass


@contextlib.contextmanager
def run_lock(sd, wait_s=0):
    f = take_lock(os.path.join(sd, ".lock"), wait_s)
    if f is None:
        raise LockHeld("another dehydrate run holds the lock; try again when it finishes")
    try:
        yield
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()


def rid_for(label, key, now):
    """Stable for one run: the same item in the same plan gets the same id."""
    h = hashlib.sha256(f"{key}\0{now}".encode()).hexdigest()[:6]
    day = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y%m%d")  # the date `at` (UTC) shows
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


RECHECK_KEYS = ("days", "roots", "snapshot_main")  # this run's own overrides (CLI flags, auto's waived window)


def test_hook(event, item):
    """Does nothing. Tests patch it to change config.json or the machine between items ("item": before an item's
    first re-check, "captured": after its capture, before the re-check that guards its removal)."""


def fresh_config(sd, cfg):
    """config.json read again now, keeping this run's overrides: only exclusions and holds can change a verdict."""
    fresh = load_config(sd)
    fresh.update({k: cfg[k] for k in RECHECK_KEYS if k in cfg})
    return fresh


def fresh_agents(args):
    """A copy of args whose `claude agents` rows are read again now (auto's filter for ended sessions kept)."""
    fa = argparse.Namespace(**vars(args))
    fa._agents = None
    rows = load_agents(fa)
    flt = getattr(args, "_agents_filter", None)
    fa._agents = flt(rows) if flt else rows
    return fa


def recheck_worktree(args, cfg, sd, w, stage):
    """Why w must stay (None: it may go), from its plan row built again from fresh state: config.json, claude
    agents, transcripts, process cwds and git. Runs right before capture and again right before removal, because
    a plan can be many minutes old by the time an item's turn comes. Any error fails closed."""
    try:
        c = fresh_config(sd, cfg)
        if c.get("_config_error"):
            return f"config.json cannot be read {stage} ({c['_config_error'][:150]})"
        g = excluded(w["path"], c)
        if g:
            return f"excluded by {g} (config.json re-read {stage})"
        now = max(getattr(args, "now", None) or 0, time.time())
        tidx = transcript_index(claude_home(args))
        try:
            fa = fresh_agents(args)
            every = session_rows(fa, c, tidx, now)
            jobs = job_sessions(fa, c, tidx, now, every)
        except AgentsUnavailable as e:  # session-bound and job-dir trees are held; the rest may still go
            args._agents_error = str(e)  # this run does not wait for the roster again
            fa, every = args, []
            jobs = {"root": os.path.realpath(os.path.join(claude_home(args), "jobs")), "rows": None}
        sessions = [] if getattr(args, "no_sessions", False) else every
        keep = [s for s in sessions if s["action"] == "keep" and s.get("rcwd")]
        repo = {"path": w["repo"], "common_dir": os.path.realpath(os.path.join(w["repo"], ".git"))}
        rows, _, _ = repo_rows(repo, dict(c, snapshot_main=False), sessions, keep, tidx, now, [w["path"]],
                               process_cwds(), os.path.realpath(os.getcwd()), getattr(args, "pressure", False), jobs)
    except Exception as e:
        return f"could not re-check it {stage} ({e.__class__.__name__}: {str(e)[:150]})"
    row = next((r for r in rows if r["path"] == w["path"]), None)
    if row is None:
        return f"no longer a registered worktree ({stage})"
    if row["action"] != "dehydrate":
        return f"{row['action']} {stage}: {row['reason']}"
    return None


def recheck_session(args, cfg, sd, s):
    try:
        c = fresh_config(sd, cfg)
        if c.get("_config_error"):
            return f"config.json cannot be read now ({c['_config_error'][:150]})"
        g = s.get("rcwd") and excluded(s["rcwd"], c)
        if g:
            return f"its cwd is excluded by {g} (config.json re-read before closing)"
        now = max(getattr(args, "now", None) or 0, time.time())
        row = next((r for r in session_rows(fresh_agents(args), c, transcript_index(claude_home(args)), now)
                    if r["session_id"] == s["session_id"]), None)
    except Exception as e:
        return f"could not re-check it before closing ({e.__class__.__name__}: {str(e)[:150]})"
    if row is None:
        return "no longer listed in claude agents"
    if row["action"] != "close":
        return f"{row['reason']} (re-checked before closing)"
    return None


def recheck_path(cfg, sd, path, stage):
    """Leftover dirs and main checkouts: exclusions (and, for a removal, process cwds) re-read now."""
    try:
        c = fresh_config(sd, cfg)
        if c.get("_config_error"):
            return f"config.json cannot be read {stage} ({c['_config_error'][:150]})"
        g = excluded(path, c)
        if g:
            return f"excluded by {g} (config.json re-read {stage})"
        if stage != "before capture" and any(under(cw, path) for _, cw in process_cwds()):
            return f"a process has its cwd inside ({stage})"
    except Exception as e:
        return f"could not re-check it {stage} ({e.__class__.__name__}: {str(e)[:150]})"
    return None


def apply_plan(args, cfg, plan, sd):
    res = {"worktrees": [], "sessions": [], "mains": [], "orphans": [], "pruned": [], "paused": None,
           "df_before_gb": round(free_gb(), 2), "pressure": None}
    now = plan["now"]
    # Records carry the plan's clock, the one their ids are dated by: under --now / DEHYDRATE_NOW (tests,
    # evals) `at` is that time plus the time apply has taken, else the wall clock.
    clock_off = (args.now - time.time()) if getattr(args, "now", None) else 0.0

    def stamp():
        return iso(time.time() + clock_off)
    by_sid = {s["session_id"]: s for s in plan["sessions"] if s["session_id"]}
    tidx = transcript_index(claude_home(args))
    host = socket.gethostname()
    press = plan.get("pressure")
    if press:
        res["pressure"] = {"target_gb": press["target_gb"], "reached": False, "free_checked_gb": None}

    last_free = {}

    def room_for(w):
        """--pressure replaces the fixed floor, which blocks every item exactly when disk is lowest: an item goes
        when the free space read for it covers its capture estimate plus PRESSURE_MARGIN_BYTES."""
        if not press:
            return floor_ok()
        est = capture_estimate(w)
        free = last_free.get("gb", free_gb()) * 2 ** 30
        need = est["total"] + PRESSURE_MARGIN_BYTES
        if free < need:
            res["paused"] = (f"free disk {free / 2**30:.2f} GB is under what capturing {short(w['path'])} needs: "
                             f"about {est['total'] / 2**20:.0f} MB (overlay {est['overlay'] / 2**20:.0f} MB, ignored "
                             f"{est['ignored'] / 2**20:.0f} MB, bundle up to {est['bundle'] / 2**20:.0f} MB) plus a "
                             f"{PRESSURE_MARGIN_BYTES // 2**20} MB margin")
            return False
        return True

    def floor_ok():
        if press:  # sessions closed with a removed worktree: transcripts and a capped job archive, plus the margin
            need = cfg["job_tmp_cap_mb"] * 2 ** 20 + PRESSURE_MARGIN_BYTES
            if free_gb() * 2 ** 30 < need:
                res["paused"] = f"free disk {free_gb():.2f} GB under {need / 2**30:.2f} GB (job archive cap plus margin)"
                return False
            return True
        if free_gb() < cfg["disk_floor_gb"]:
            res["paused"] = f"free disk {free_gb():.2f} GB under floor {cfg['disk_floor_gb']} GB"
            return False
        return True

    def target_reached():
        """--pressure only: one free-disk read per item; at or over the target the run stops (not a pause)."""
        if not press:
            return False
        f = pressure_free_gb()
        last_free["gb"] = f
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
        test_hook("item", w)
        why = recheck_worktree(args, cfg, sd, w, "before capture")
        if why:
            res["worktrees"].append({"path": w["path"], "ok": False, "skipped": True, "removed": False,
                                     "error": f"left in place, nothing captured: {why}"})
            return
        rid = unique_rid(sd, rid_for(os.path.basename(w["path"]), f"{w['path']}\0{w['head']}", now))
        archive = os.path.join(sd, "archive", rid)
        os.makedirs(archive, exist_ok=True)
        out = {"id": rid, "path": w["path"]}
        try:
            sess = []
            for sid in w.get("sessions", []):
                s = by_sid.get(sid) or {"session_id": sid, "transcript": (tidx.get(sid) or {}).get("path"),
                                        "project_dir": (tidx.get(sid) or {}).get("project_dir"),
                                        "cwd": (tidx.get(sid) or {}).get("cwd"),
                                        "name": (getattr(args, "_names", None) or {}).get(sid)}
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
            rec = {"event": "dehydrated", "id": rid, "kind": "worktree", "at": stamp(), "host": host,
                   "repo": {"path": w["repo"], "origin": w["origin"]},
                   "worktree": {"path": w["path"], "branch": w["branch"], "head": w["head"],
                                "dirty_count": w["facts"]["dirty_count"], "untracked_count": w["facts"]["untracked_count"],
                                "unpushed": w["facts"]["unpushed"], "upstream": w["facts"]["upstream"],
                                "sparse": sparse_info(w["path"])},
                   "snapshot": snap, "raw": raw, "ignored": itar, "sessions": sess, "size_kb": w.get("size_kb"),
                   "description": describe(sess, w["branch"], w["path"]), "archive": archive, "removed": False,
                   "idle_days": w["idle_days"]}
            if plan.get("auto"):
                rec["auto"] = plan["auto"]
            append_manifest(sd, rec)  # recorded BEFORE anything is removed; a failed write removes nothing
        except Exception as e:
            out.update(ok=False, error=str(e)[:400])
            shutil.rmtree(archive, ignore_errors=True)  # nothing was removed and nothing points here
            with contextlib.suppress(Exception):
                git(w["repo"], "update-ref", "-d", f"refs/dehydrated/{rid}")
            res["worktrees"].append(out)
            return
        test_hook("captured", w)
        why = recheck_worktree(args, cfg, sd, w, "before removal")
        if why:
            with contextlib.suppress(Exception):
                append_manifest(sd, {"event": "left-in-place", "id": rid, "at": stamp(), "reason": why})
            out.update(ok=False, skipped=True, removed=False, error=f"captured as {rid} but not removed: {why}")
            res["worktrees"].append(out)
            return
        try:  # a 300k-file tree can take minutes on a busy disk
            r = git(w["repo"], "worktree", "remove", "--force", w["path"], timeout=BIG_TREE_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            r = subprocess.CompletedProcess([], 1, "", "git worktree remove timed out after 3600s; rerun apply")
        except Exception as e:
            r = subprocess.CompletedProcess([], 1, "", f"git worktree remove failed: {e.__class__.__name__}: {e}")
        if r.returncode != 0:
            out.update(ok=False, removed=False, error=f"captured as {rid} but not removed: {r.stderr.strip()[:300]}")
        else:
            out.update(ok=True, removed=True, description=rec["description"])
            with contextlib.suppress(Exception):
                append_manifest(sd, {"event": "removed", "id": rid, "at": stamp()})
        res["worktrees"].append(out)

    def do_session(s, removed_paths, wrow_by_path):
        wt = s.get("worktree")
        if wt and wt not in removed_paths and s.get("worktree_action") == "dehydrate":
            res["sessions"].append({"bg_id": s["bg_id"], "ok": False, "error": "its worktree was not captured; left open"})
            return
        test_hook("item", s)
        why = recheck_session(args, cfg, sd, s)
        if why:
            res["sessions"].append({"bg_id": s["bg_id"], "ok": False, "skipped": True, "name": s.get("name"),
                                    "error": f"left open: {why}"})
            return
        rid = unique_rid(sd, rid_for("s-" + (s.get("name") or s["bg_id"]), s["session_id"], now))
        archive = os.path.join(sd, "archive", rid)
        os.makedirs(archive, exist_ok=True)
        try:
            info = archive_session(s, archive, cfg, args)
            if s.get("worktree_path") and s["worktree_path"] not in removed_paths and os.path.isdir(s["worktree_path"]):
                raise RuntimeError("session owns a Claude-managed worktree that was not captured; left open")
            linked = next((o["id"] for o in res["worktrees"] if wt and o["path"] == wt and o.get("removed")), None)
            repo_path = (wrow_by_path.get(wt) or {}).get("repo") or \
                (gout(s["cwd"], "rev-parse", "--show-toplevel") if s["cwd"] and os.path.isdir(s["cwd"]) else None)
            rec = {"event": "dehydrated", "id": rid, "kind": "session", "at": stamp(), "host": host,
                   "repo": {"path": repo_path},
                   "worktree": {"path": wt, "branch": (wrow_by_path.get(wt) or {}).get("branch")} if wt else None,
                   "linked_worktree_id": linked, "sessions": [info], "archive": archive,
                   "description": describe([info], None, s["cwd"] or ""), "removed": False,
                   "idle_days": s["idle_days"]}
            if plan.get("auto"):
                rec["auto"] = plan["auto"]
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
                append_manifest(sd, {"event": "removed", "id": rid, "at": stamp(), "close": closed})
            res["sessions"].append({"bg_id": s["bg_id"], "id": rid, "ok": True, "name": s.get("name")})
        else:
            res["sessions"].append({"bg_id": s["bg_id"], "id": rid, "ok": False, "name": s.get("name"),
                                    "error": f"`claude {closed['steps'][-1]['cmd']}` refused ({closed['steps'][-1]['out'][:200]}). "
                                             f"Left open; its transcript is archived as {rid}. Check it, then close it "
                                             f"yourself with `claude rm {s['bg_id']}` if you are done with it."})

    def do_orphan(o):
        test_hook("item", o)
        why = recheck_path(cfg, sd, o["path"], "before capture")
        if why:
            res["orphans"].append({"path": o["path"], "ok": False, "skipped": True, "error": f"left in place: {why}"})
            return
        rid = unique_rid(sd, rid_for(os.path.basename(o["path"]), o["path"], now))
        archive = os.path.join(sd, "archive", rid)
        os.makedirs(archive, exist_ok=True)
        try:
            t = tar_tree(o["path"], os.path.join(archive, "tree.tar.gz"), cfg, cfg["orphan_cap_mb"] * 2 ** 20)
            rec = {"event": "dehydrated", "id": rid, "kind": "orphan", "at": stamp(), "host": host,
                   "repo": {"path": o["repo"], "origin": o["origin"]}, "worktree": {"path": o["path"], "branch": None},
                   "tree_tar": t, "archive": archive, "size_kb": o.get("size_kb"), "removed": False,
                   "description": f"unregistered dir {os.path.basename(o['path'])} under {short(o['repo'])}/.claude/worktrees"}
            append_manifest(sd, rec)
        except Exception as e:
            shutil.rmtree(archive, ignore_errors=True)
            res["orphans"].append({"path": o["path"], "ok": False, "error": str(e)[:300]})
            return
        test_hook("captured", o)
        why = recheck_path(cfg, sd, o["path"], "before removal")
        if why:
            with contextlib.suppress(Exception):
                append_manifest(sd, {"event": "left-in-place", "id": rid, "at": stamp(), "reason": why})
            res["orphans"].append({"id": rid, "path": o["path"], "ok": False, "skipped": True,
                                   "error": f"archived as {rid} but not removed: {why}"})
            return
        try:
            shutil.rmtree(o["path"])
            with contextlib.suppress(Exception):
                append_manifest(sd, {"event": "removed", "id": rid, "at": stamp()})
            res["orphans"].append({"id": rid, "path": o["path"], "ok": True})
        except Exception as e:
            res["orphans"].append({"id": rid, "path": o["path"], "ok": False, "error": f"archived as {rid} but not removed: {e}"})

    def do_main(m, last_tree):
        test_hook("item", m)
        why = recheck_path(cfg, sd, os.path.realpath(m["path"]), "before capture")
        if why:
            res["mains"].append({"path": m["path"], "ok": False, "skipped": True, "error": f"not captured: {why}"})
            return
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
            rec = {"event": "dehydrated", "id": rid, "kind": "main-snapshot", "raw": raw, "at": stamp(), "host": host,
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
            if target_reached() or not room_for(w):
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


# ---------------------------------------------------------------- live sessions (agents rows, launched copies)

def pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True  # someone else's process: alive
    except Exception:
        return False


def fetch_agents(args, timeout):
    """`claude agents --json --all` with a timeout (or --agents-json). Raises on any failure."""
    if getattr(args, "agents_json", None):
        out = json.load(open(args.agents_json))
    else:
        r = subprocess.run([args.claude_bin, "agents", "--json", "--all"], capture_output=True, text=True,
                           timeout=timeout, stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            raise RuntimeError(f"claude agents --json --all failed: {r.stderr.strip()[:300]}")
        out = json.loads(r.stdout or "[]")
    if not isinstance(out, list):
        raise RuntimeError("claude agents --json did not print a list")
    return [a for a in out if isinstance(a, dict)]


def launched_ids(rec):
    """Session ids and short ids of the copies `rehydrate --launch` started (or found running) for a record."""
    ids = set()
    for ev in rec.get("rehydrations", []):
        for l in ev.get("launched") or []:
            if isinstance(l, dict):
                ids.update(x for x in (l.get("bg_id"), l.get("session_id")) if x)
    return ids


def agent_live(a):
    """A `claude agents` row that is running now: it has a pid, or its state says it works or waits."""
    return bool(a.get("pid")) or (a.get("state") or a.get("status")) in ACTIVE_STATES | {"blocked"}


def match_running(agents, sid, name, cwd, extra_ids=()):
    """The `claude agents` row for a session (DESIGN 3.1), so it is never started twice: (1) a row with its own
    session id, in any state (still listed means still open: attach it or `claude rm` it), (2) a row of a copy
    an earlier --launch started (its stored ids), in any state, (3) a live row (a pid, or state working, busy,
    running or blocked) with the same name in the same realpath cwd."""
    for a in agents:
        if sid and a.get("sessionId") == sid:
            return a
    for a in agents:
        if extra_ids and (a.get("sessionId") in extra_ids or a.get("id") in extra_ids):
            return a
    rc = os.path.realpath(cwd) if cwd else None
    for a in agents:
        if agent_live(a) and name and rc and a.get("name") == name and a.get("cwd") \
                and os.path.realpath(a["cwd"]) == rc:
            return a
    return None


def running_ref(a):
    return {"bg_id": a.get("id") or (a.get("sessionId") or "")[:8] or None, "session_id": a.get("sessionId"),
            "state": a.get("state") or a.get("status") or None, "live": agent_live(a)}


# ---------------------------------------------------------------- "has merges on it" (DESIGN 6)

NOPROMPT = {"GIT_TERMINAL_PROMPT": "0"}  # a fetch that would ask for a credential fails instead of hanging


def gh_merged_pr(path, branch, default, head, gh_bin):
    """A PR from this branch merged into the default branch at exactly this HEAD (`gh pr list`), else None.
    Pinned to origin's repo (`-R`), the remote the git checks fetch, never gh's default-repo guess. Runs the
    `gh` on PATH (the account-routing wrapper, which reads -R), never with a GH_TOKEN prefix."""
    origin = gout(path, "remote", "get-url", "origin")
    if not origin:
        return None
    try:
        r = subprocess.run([gh_bin, "pr", "list", "-R", gh_repo_arg(origin), "--head", branch, "--state", "merged",
                            "--json",
                            "number,headRefOid,mergedAt,baseRefName"], cwd=path, capture_output=True, text=True,
                           timeout=20, stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            return None
        for pr in json.loads(r.stdout or "[]"):
            if isinstance(pr, dict) and pr.get("baseRefName") == default and pr.get("headRefOid") == head:
                return pr.get("number") or True
    except Exception:
        pass
    return None


OWN_REFLOG = re.compile(r"^(commit|cherry-pick|revert|am|merge [^:]*: Merge made|pull[^:]*: Merge made|"
                        r"rebase[^:]*\((finish|pick|continue|squash|fixup|reword|edit)\))")


def own_commits_on_head(path, br):
    """Commits made on this branch (its reflog: commit, amend, cherry-pick, a merge it made, a rebase) that
    HEAD still contains. A reset, a fast-forward pull and the creation entry are not its own work."""
    lg = git(path, "reflog", "show", "--format=%H%x09%gs", f"refs/heads/{br}")
    if lg.returncode != 0:
        return []
    own = []
    for line in lg.stdout.splitlines()[:200]:
        sha, _, subj = line.partition("\t")
        if sha and OWN_REFLOG.match(subj) and sha not in own:
            if git(path, "merge-base", "--is-ancestor", sha, "HEAD").returncode == 0:
                own.append(sha)
                break
    return own


def git_cherry_plus(path, base):
    """Branch commits whose patch is not on base (`git cherry`: '+' lines), or None when it fails."""
    r = git(path, "cherry", base, "HEAD", timeout=120)
    if r.returncode != 0:
        return None
    return [x[2:].strip() for x in r.stdout.splitlines() if x.startswith("+ ")]


def empty_commits(path, plus):
    """Of the branch commits not on base, those that change nothing (an --allow-empty commit after a squash)."""
    out = []
    for sha in plus[:200]:
        r = git(path, "diff-tree", "--no-commit-id", "--root", "-r", "--quiet", "-m", "--first-parent", sha)
        if r.returncode == 0:  # --quiet: exit 0 means no difference from its parent
            out.append(sha)
    return out


def gh_repo_arg(url):
    """origin URL -> HOST/OWNER/REPO for `gh -R` (ssh, scp-like and https forms), else the URL as it is."""
    m = re.match(r"^(?:[a-z+]+://)?(?:[^@/]+@)?([^/:]+)[:/]+([^/]+)/([^/]+?)(?:\.git)?/?$", url or "")
    return f"{m.group(1)}/{m.group(2)}/{m.group(3)}" if m and "." in m.group(1) else url


def merge_rule(path, cfg, gh_bin="gh", fetched=None):
    """Whether a worktree's branch is merged into the remote default branch, by commits only (DESIGN 6.1/6.2).

    -> {merged, by (ancestor | merge-tree | gh-pr), reason, pr, default_branch, branch, head}. Every error,
    timeout or missing piece is NOT merged. `fetched` memoizes one fetch per repo and default branch per sweep."""
    res = {"merged": False, "by": None, "reason": None, "pr": None, "default_branch": None, "branch": None,
           "head": None}

    def no(why):
        res["reason"] = why
        return res
    tmo = cfg.get("auto_fetch_timeout_s", 30)
    try:
        if not path or not os.path.isdir(path):
            return no("cwd is gone")
        gd, cd = gout(path, "rev-parse", "--git-dir"), gout(path, "rev-parse", "--git-common-dir")
        if not gd or not cd:
            return no("not a git repo")
        cd = os.path.realpath(os.path.join(path, cd))
        if os.path.realpath(os.path.join(path, gd)) == cd:
            return no("main checkout, not a linked worktree")
        if cfg.get("auto_require_clean"):
            st = git(path, "status", "--porcelain=v1", "--untracked-files=all")
            if st.returncode != 0 or st.stdout.strip():
                return no("uncommitted or untracked files (auto_require_clean)")
        br = gout(path, "symbolic-ref", "-q", "--short", "HEAD")
        if not br:
            return no("detached HEAD")
        res["branch"] = br
        if not gout(path, "remote", "get-url", "origin"):
            return no("no origin remote")
        de = gout(path, "symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD")
        de = de[len("origin/"):] if de.startswith("origin/") else ""
        if not de:
            r = git(path, "ls-remote", "--symref", "origin", "HEAD", env=NOPROMPT, timeout=tmo)
            m = re.search(r"^ref: refs/heads/(\S+)\tHEAD", r.stdout, re.M) if r.returncode == 0 else None
            if not m:
                return no("default branch unknown (no origin/HEAD, ls-remote failed)")
            de = m.group(1)
        res["default_branch"] = de
        if br == de:
            return no(f"on the default branch {de}")
        key = (cd, de)
        if fetched is None or key not in fetched:
            try:
                r = git(path, "fetch", "--quiet", "--no-tags", "origin", f"+refs/heads/{de}:refs/remotes/origin/{de}",
                        env=NOPROMPT, timeout=tmo)
                why = None if r.returncode == 0 else f"fetch of origin/{de} failed: {r.stderr.strip()[:200]}"
            except subprocess.TimeoutExpired:
                why = f"fetch of origin/{de} timed out after {tmo}s"
            if fetched is not None:
                fetched[key] = why
        else:
            why = fetched[key]
        if why:
            return no(why)
        base = f"refs/remotes/origin/{de}"
        head = gout(path, "rev-parse", "--verify", "-q", "HEAD")
        if not head:
            return no("branch has no commits")
        res["head"] = head
        pr_memo = []

        def pr():
            if not pr_memo:
                pr_memo.append(gh_merged_pr(path, br, de, head, gh_bin) if cfg.get("auto_use_gh", True) else None)
            return pr_memo[0]
        n = gout(path, "rev-list", "--count", f"{base}..HEAD")
        if n == "0":
            # contained in the default branch; it must also have commits of its own that are still on it (a
            # branch sitting at an old default tip, or one whose own commit was reset away, is not merged work)
            own = own_commits_on_head(path, br)
            if own or pr():
                res.update(merged=True, by="ancestor", pr=pr() if not own else None,
                           reason=f"{br} is contained in origin/{de}")
                return res
            return no(f"{br} has no commits of its own on it (at or behind origin/{de})")
        if not n.isdigit():
            return no("rev-list failed")
        mt = git(path, "merge-tree", "--write-tree", base, "HEAD")  # exit 0 = clean merge (git >= 2.38)
        if mt.returncode == 0:
            tree = mt.stdout.split("\n", 1)[0].strip()
            if tree and tree == gout(path, "rev-parse", f"{base}^{{tree}}"):
                # Merging changes nothing. That proves a squash or rebase merge only when the branch changed
                # something: a commit and its revert (net zero) also merges as nothing, never having landed.
                mb = gout(path, "merge-base", base, "HEAD")
                files = [x for x in gout(path, "diff", "--name-only", "--no-renames", mb, "HEAD").splitlines() if x] \
                    if mb else []
                if not files:
                    return no(f"{br} has {n} commits that change nothing in total (a commit and its undo); "
                              f"not proof of a merge")
                plus = git_cherry_plus(path, base)
                if plus is None:
                    return no("git cherry failed")
                empty = empty_commits(path, plus)
                if empty:
                    return no(f"{br} has a commit with no changes ({empty[0][:8]}) that is not on origin/{de}")
                res.update(merged=True, by="merge-tree",
                           reason=(f"every commit of {br} has its patch on origin/{de} (rebase or one-commit squash merge)"
                                   if not plus else
                                   f"the {len(files)} file{'s' if len(files) != 1 else ''} {br} changes "
                                   f"{'are' if len(files) != 1 else 'is'} already on origin/{de}; "
                                   f"merging it changes nothing (squash merge)"))
                return res
        if pr():
            res.update(merged=True, by="gh-pr", pr=pr(), reason=f"PR #{pr()} from {br} merged into {de} at this HEAD")
            return res
        return no(f"{br} has {n} commits not in origin/{de}")
    except subprocess.TimeoutExpired as e:
        return no(f"timed out: git {' '.join(str(x) for x in e.cmd[3:5])}")
    except Exception as e:
        return no(f"check failed: {e.__class__.__name__}: {str(e)[:200]}")


# ---------------------------------------------------------------- auto (sweep and the close kick)

def detach():
    """Fork twice and setsid, like a daemon: the caller returns at once (a hook never waits). SIGHUP is
    ignored first: until setsid the child is still in the caller's process group, and a terminal or pane
    closing then hangs that group up (the mod's kick also starts it with HUP ignored, for Python's startup)."""
    with contextlib.suppress(Exception):
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
    if os.fork():
        return False
    os.setsid()
    if os.fork():
        os._exit(0)
    devnull = os.open(os.devnull, os.O_RDWR)
    for fd in (0, 1, 2):
        os.dup2(devnull, fd)
    return True


def session_pid_files(ch, sid):
    """<claude_home>/sessions/<pid>.json rows for a session id: what a running Claude process registers."""
    out = []
    d = os.path.join(ch, "sessions")
    with contextlib.suppress(OSError):
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".json"):
                with contextlib.suppress(Exception):
                    o = json.load(open(os.path.join(d, fn)))
                    if isinstance(o, dict) and o.get("sessionId") == sid:
                        out.append(o)
    return out


def wait_for_exit(ch, sid, wait_s):
    """Poll until no live process holds the session (the close kick fires before the process exits).
    -> (still_alive, {name, cwd} as the process registered them)."""
    seen, deadline = {}, time.time() + wait_s
    while True:
        rows = session_pid_files(ch, sid)
        for o in rows:
            seen.update({k: o[k] for k in ("name", "cwd") if isinstance(o.get(k), str) and o[k]})
        alive = any(o.get("pid") and pid_alive(o["pid"]) for o in rows)
        if not alive or time.time() >= deadline:
            return alive, seen
        time.sleep(1)


def auto_log(sd, decisions):
    last = {}
    p = os.path.join(sd, "auto.log")
    with contextlib.suppress(OSError):
        for line in open(p).readlines()[-5000:]:
            with contextlib.suppress(Exception):
                d = json.loads(line)
                last[d.get("session_id")] = (d.get("decision"), d.get("reason"))
    with open(p, "a") as f:
        for d in decisions:
            if d["decision"] == "refused" and last.get(d.get("session_id")) == ("refused", d["reason"]):
                continue  # a sweep every few minutes: log a refusal again only when its reason changes
            f.write(json.dumps(d, sort_keys=True) + "\n")


def pending_dir(sd):
    return os.path.join(sd, "auto-pending")


def defer(sd, sid, why, trigger):
    """Queue a session for the next auto run (the lock holder drains it, else the next SessionStart sweep)."""
    with contextlib.suppress(OSError):
        os.makedirs(pending_dir(sd), exist_ok=True)
        with open(os.path.join(pending_dir(sd), re.sub(r"[^A-Za-z0-9-]", "_", sid) + ".json"), "w") as f:
            json.dump({"session_id": sid, "at": iso(time.time()), "why": why}, f)
    return {"at": iso(time.time()), "session_id": sid, "bg_id": None, "name": None, "trigger": trigger,
            "decision": "deferred", "reason": why}


def take_lock(path, wait_s):
    """flock with a bounded wait: -> the open file, or None when another run still holds it after wait_s."""
    f = open(path, "w")
    deadline = time.time() + wait_s
    while True:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return f
        except BlockingIOError:
            if time.time() >= deadline:
                f.close()
                return None
            time.sleep(0.5)


def auto_sweep(args, cfg, sd, trigger="sweep"):
    """DESIGN 3.2: dehydrate ended sessions whose worktree has merges on it, through apply_plan with every hold.
    -> {"decisions": [...], "applied": [...] | None, "off": why-nothing-ran | None}. Logs to <state>/auto.log.

    The close kick waits for its session's process to exit BEFORE it takes .auto.lock, then waits for the lock
    up to DEHYDRATE_AUTO_LOCK_WAIT_S (default 120 s). One that still cannot get it, or that meets the apply lock,
    is queued in <state>/auto-pending and logged `deferred`; whoever holds the lock next drains the queue."""
    out = {"decisions": [], "applied": None, "off": None}
    if not cfg.get("auto_on_close") or cfg.get("_config_error"):
        out["off"] = f"config error: {cfg['_config_error']}" if cfg.get("_config_error") else "auto_on_close is off"
        return out
    target = getattr(args, "session", None)
    dry = getattr(args, "dry_run", False)
    if target and getattr(args, "_waited", None) is None:
        args._waited = wait_for_exit(claude_home(args), target, float(os.environ.get("DEHYDRATE_AUTO_WAIT_S", "60")))
    lock = take_lock(os.path.join(sd, ".auto.lock"), float(os.environ.get("DEHYDRATE_AUTO_LOCK_WAIT_S", "120")))
    if lock is None:
        out["off"] = "another auto run holds the lock"
        if target and not dry:
            out["decisions"].append(defer(sd, target, "another auto run held the lock; queued for the next run",
                                          trigger))
            out["off"] += "; deferred"
            with contextlib.suppress(Exception):
                auto_log(sd, out["decisions"])
        return out
    try:
        _auto(args, cfg, sd, trigger, out)
        if not dry:
            drain_pending(args, cfg, sd, out, skip={target} if target else set())
    finally:
        if not dry:
            with contextlib.suppress(Exception):
                auto_log(sd, out["decisions"])
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
    return out


def drain_pending(args, cfg, sd, out, skip=()):
    """Run each queued session id once, as its own close kick would have (no grace, its process long gone)."""
    d = pending_dir(sd)
    with contextlib.suppress(OSError):
        for fn in sorted(os.listdir(d)):
            p = os.path.join(d, fn)
            try:
                sid = json.load(open(p)).get("session_id")
            except Exception:
                sid = None
            if sid and sid in skip:
                continue  # queued by this very run: the next one takes it
            with contextlib.suppress(OSError):
                os.unlink(p)
            if not sid:
                continue
            a2 = argparse.Namespace(**vars(args))
            a2.session, a2._agents = sid, None
            a2._waited = wait_for_exit(claude_home(args), sid, 0)
            _auto(a2, cfg, sd, "session.end (deferred)", out)


def _auto(args, cfg, sd, trigger, out):
    now = args.now or time.time()
    ch = claude_home(args)
    target = getattr(args, "session", None)
    gh_bin = getattr(args, "gh_bin", None) or os.environ.get("DEHYDRATE_GH_BIN") or "gh"
    me = {x for x in (os.environ.get("CLAUDE_CODE_SESSION_ID"),
                      os.path.basename(os.environ.get("CLAUDE_JOB_DIR", "").rstrip("/"))) if x} - {target}
    dec = out["decisions"]

    def decide(c, decision, reason, **kw):
        dec.append(dict({"at": iso(time.time()), "session_id": c.get("session_id"), "bg_id": c.get("bg_id"),
                         "name": c.get("name"), "trigger": trigger, "decision": decision, "reason": reason}, **kw))
    alive, seen = False, {}
    if target:
        alive, seen = getattr(args, "_waited", None) or \
            wait_for_exit(ch, target, float(os.environ.get("DEHYDRATE_AUTO_WAIT_S", "60")))
    try:
        agents = fetch_agents(args, 60)
    except Exception as e:
        decide({"session_id": target}, "refused", f"claude agents unreadable: {str(e)[:200]}")
        return
    args._agents = agents
    tidx = transcript_index(ch)
    rows = session_rows(args, cfg, tidx, now)
    if target and not any(r["session_id"] == target for r in rows):
        # an interactive session has no agents row once it exits: build it from its transcript and pid file
        t = tidx.get(target) or {}
        cwd = seen.get("cwd") or t.get("cwd") or ""
        if not t and not seen:
            decide({"session_id": target}, "refused", "no agents row and no transcript for this session")
            return
        rows.append({"bg_id": None, "session_id": target, "name": seen.get("name") or "", "cwd": cwd,
                     "kind": "interactive", "state": "ended", "pid": None, "last_activity": t.get("mtime") or now,
                     "transcript": t.get("path"), "project_dir": t.get("project_dir"), "job_dir": None,
                     "worktree_path": None, "rcwd": os.path.realpath(cwd) if cwd else None})
    cands = [r for r in rows if r["session_id"] == target] if target else \
        [r for r in rows if r["kind"] == "background" and r["session_id"]]
    cur = current_records(sd)
    done_sids = {x.get("session_id") for r in cur.values() if not r["rehydrations"] for x in r.get("sessions", [])}
    # A session brought back by rehydrate is left alone until it is used and ends again: its activity (transcript,
    # job state) must be newer than the latest rehydration, so restoring a merged worktree to look at it does not
    # lose it again at the next sweep. Rehydrating a session record also covers its linked worktree record.
    rehydrated_at = {}
    for r in cur.values():
        if not r["rehydrations"]:
            continue
        t = max(record_ts(e) for e in r["rehydrations"])
        recs = [r] + ([cur[r["linked_worktree_id"]]] if cur.get(r.get("linked_worktree_id") or "") else []) + \
            [s for s in cur.values() if s.get("linked_worktree_id") == r["id"]]
        for rr in recs:
            for x in rr.get("sessions", []):
                if x.get("session_id"):
                    rehydrated_at[x["session_id"]] = max(t, rehydrated_at.get(x["session_id"], 0))
    done_sids -= set(rehydrated_at)  # brought back: judged by the rule below, not as already dehydrated
    copies = {}
    for r in cur.values():
        for x in r.get("sessions", []):
            copies.setdefault(x.get("session_id"), set()).update(launched_ids(r))
    fetched, accepted = {}, []
    for c in cands:
        sid = c["session_id"]
        ids = {sid} | copies.get(sid, set())
        live = [a for a in agents if (a.get("sessionId") in ids or a.get("id") in ids)
                and (a.get("pid") or (a.get("state") or a.get("status")) in ACTIVE_STATES | {"blocked"})]
        wt = c.get("worktree_path") if c.get("worktree_path") and os.path.isdir(c["worktree_path"]) else None
        cwd = wt or c.get("cwd")
        if sid in me:
            decide(c, "refused", "this session")
        elif sid in done_sids:
            decide(c, "refused", "already dehydrated")
        elif sid in rehydrated_at and c["last_activity"] <= rehydrated_at[sid] + 2:
            decide(c, "refused", f"rehydrated at {iso(rehydrated_at[sid])} and not used since "
                                 f"(auto waits until it runs and ends again)")
        elif alive:
            decide(c, "refused", "its process is still running")
        elif live:
            a = live[0]
            decide(c, "refused", f"live: pid {a['pid']}" if a.get("pid") else f"live: state {a.get('state') or a.get('status')}")
        elif c["kind"] == "background" and c["state"] not in ("done", "failed"):
            decide(c, "refused", f"state {c['state'] or 'unknown'} (not ended)")
        elif not target and now - c["last_activity"] < cfg["auto_grace_minutes"] * 60:
            decide(c, "refused", f"ended {int((now - c['last_activity']) // 60)}m ago "
                                 f"(< auto_grace_minutes {cfg['auto_grace_minutes']})")
        elif not cwd or not os.path.isdir(cwd):
            decide(c, "refused", "its cwd is gone")
        else:
            top = gout(cwd, "rev-parse", "--show-toplevel")
            top = os.path.realpath(top) if top else None
            other = [a for a in agents if a.get("pid") and a.get("sessionId") not in ids and a.get("cwd")
                     and top and under(os.path.realpath(a["cwd"]), top)]
            if not top:
                decide(c, "refused", "its cwd is not in a git repo")
            elif other:
                o = other[0]
                decide(c, "refused", f"{o.get('kind') or 'a'} session {o.get('name') or o.get('id') or ''} is open in {short(top)}".replace("  ", " "))
            else:
                m = merge_rule(top, cfg, gh_bin, fetched)
                if not m["merged"]:
                    decide(c, "refused", f"not merged: {m['reason']}")
                else:
                    accepted.append((c, top, m))
    # a worktree shared with a session that is not itself accepted stays (DESIGN 6.3)
    ok = {c["session_id"] for c, _, _ in accepted}
    by_top = {}
    for c, top, m in accepted:
        shared = [r for r in rows if r["session_id"] and r["session_id"] not in ok
                  and (r.get("worktree_path") or r.get("rcwd")) and under(r.get("worktree_path") or r["rcwd"], top)]
        if shared:
            s = shared[0]
            decide(c, "refused", f"worktree shared with session {s['bg_id'] or s['session_id'][:8]} {s['name']} "
                                 f"that is not ready".rstrip())
        else:
            by_top.setdefault(top, []).append((c, m))
    out["applied"] = []
    for top, group in sorted(by_top.items()):
        sids = [c["session_id"] for c, _ in group]
        m = group[0][1]
        if getattr(args, "dry_run", False):
            for c, _ in group:
                decide(c, "dehydrate", m["reason"], merged_by=m["by"], dry_run=True)
            continue
        a2 = argparse.Namespace(**vars(args))
        a2.only, a2.no_sessions, a2.no_worktrees, a2.no_main, a2.pressure = [top] + sids, False, False, True, False
        a2.now = max(now, time.time())  # days=0 waives the window only if no mtime reads as later than "now"
        # an interactive session that just exited must not be read as a kept (open) session
        a2._agents_filter = lambda rows, sids=sids: [a for a in rows if a.get("sessionId") not in sids
                                                     or a.get("kind") == "background"]
        a2._agents = a2._agents_filter(agents)
        a2._names = {c["session_id"]: c["name"] for c, _ in group if c.get("name")}
        cfg2 = dict(cfg, days=0, snapshot_main=False)  # the idle window is waived for these items only
        try:
            plan = build_plan(a2, cfg2)
            w = next((w for w in plan["worktrees"] if w["path"] == top), None)
            if not w or w["action"] != "dehydrate":
                why = f"{w['action']}: {w['reason']}" if w else "the plan found no worktree there"
                for c, _ in group:
                    decide(c, "refused", f"plan holds it ({why})")
                continue
            plan["sessions"] = [s for s in plan["sessions"] if s["session_id"] in sids and s["action"] == "close"]
            plan["auto"] = {"trigger": trigger, "merged_by": m["by"], "pr": m["pr"], "default_branch": m["default_branch"]}
            with run_lock(sd, wait_s=float(os.environ.get("DEHYDRATE_AUTO_LOCK_WAIT_S", "120"))):
                res = apply_plan(a2, cfg2, plan, sd)
        except LockHeld as e:
            for c, _ in group:
                if target and c["session_id"] == target:
                    dec.append(defer(sd, target, f"{e}; queued for the next run", trigger))
                else:
                    decide(c, "deferred", f"{e}; the next sweep tries again")
            continue
        except (Exception, SystemExit) as e:
            for c, _ in group:
                decide(c, "refused", f"apply failed: {str(e)[:200]}")
            continue
        out["applied"].append(render_apply(res))
        wr = next((x for x in res["worktrees"] if x.get("path") == top), None)
        if wr and wr.get("ok"):
            ids = [wr["id"]] + [x["id"] for x in res["sessions"] if x.get("ok")]
            notes = [x["error"] for x in res["sessions"] if not x.get("ok") and x.get("error")]
            for c, _ in group:
                decide(c, "dehydrated", m["reason"], merged_by=m["by"], ids=ids, **({"notes": notes} if notes else {}))
        else:
            why = (f"paused: {res['paused']}" if res["paused"] else (wr or {}).get("error") or "not captured")
            for c, _ in group:
                decide(c, "refused", why)


def cmd_auto(args, cfg):
    sd = state_dir(args)
    for k in ("state_dir", "claude_home", "agents_json"):
        if getattr(args, k, None):
            setattr(args, k, os.path.abspath(os.path.expanduser(getattr(args, k))))
    os.chdir("/")  # the close kick starts in the ending session's worktree; a cwd there would hold it
    if args.session:  # the kick inherits the ending session's identity: it is the target, not "this session"
        os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        os.environ.pop("CLAUDE_JOB_DIR", None)
    if args.detach and not detach():
        return 0
    try:
        res = auto_sweep(args, cfg, sd, "session.end" if args.session else "sweep")
    except BaseException as e:  # exit 0 on every path; the error is logged
        res = {"decisions": [], "applied": None, "off": f"error: {e.__class__.__name__}: {str(e)[:300]}"}
        with contextlib.suppress(Exception):
            auto_log(sd, [{"at": iso(time.time()), "session_id": args.session, "decision": "refused",
                           "reason": res["off"]}])
    if args.detach:
        os._exit(0)
    warn = config_warnings(cfg) if args.dry_run or not args.session else []
    if args.json:
        print(json.dumps(dict(res, warnings=warn), indent=1))
    else:
        for w in warn:
            print(f"WARNING: {w}")
        if res.get("off"):
            print(f"auto: nothing ran ({res['off']})")
        for d in res["decisions"]:
            print(f"  {d['decision']:10s} {d.get('bg_id') or (d.get('session_id') or '')[:8]:9s} "
                  f"{(d.get('name') or '')[:40]:40s} {d['reason']}")
        for a in res.get("applied") or []:
            print(a)
    return 0


# ---------------------------------------------------------------- rehydrate

def find_record(sd, key):
    cur = current_records(sd)
    if key in cur:
        return cur[key]
    hits = [r for r in cur.values() if key in (
        r["id"], *(s.get("session_id") for s in r.get("sessions", [])),
        *(s.get("bg_id") for s in r.get("sessions", [])),
        *((s.get("session_id") or "")[:8] for s in r.get("sessions", [])),
        *(s.get("name") for s in r.get("sessions", []) if s.get("name")),  # the exact `claude agents` name
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


def gunzip_sha256(path):
    h = hashlib.sha256()
    with gzip.open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def restore_transcript(args, info, tidx):
    """-> (path or None, restored, problem or None). A missing or corrupt archived copy is a problem the caller
    reports (and does not launch), never an exit: the worktree restore must not hang on a transcript."""
    sid = info.get("session_id")
    existing = tidx.get(sid)
    if existing:
        return existing["path"], False, None
    copy = info.get("transcript_copy")
    if not copy or not os.path.isfile(copy):
        return None, False, "no transcript archived; resume will fail"
    want = info.get("transcript_sha256")
    try:
        ok = not want or gunzip_sha256(copy) == want
    except Exception:  # not gzip at all, truncated, unreadable
        ok = False
    if not ok:
        return None, False, f"archived transcript for {sid} fails its checksum; not restored, not launched"
    pd = info.get("project_dir") or re.sub(r"[^A-Za-z0-9]", "-", info.get("cwd") or "unknown")
    dest_dir = os.path.join(claude_home(args), "projects", pd)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f"{sid}.jsonl")
    with gzip.open(copy, "rb") as fi, open(dest + ".tmp", "wb") as fo:
        shutil.copyfileobj(fi, fo)
    if want and sha256(dest + ".tmp") != want:
        os.unlink(dest + ".tmp")
        return None, False, f"archived transcript for {sid} fails its checksum; not restored, not launched"
    os.replace(dest + ".tmp", dest)
    return dest, True, None


def current_branch(path):
    return gout(path, "symbolic-ref", "-q", "--short", "HEAD") or None if path and os.path.isdir(path) else None


def in_place(rec, target):
    """The record's restore is still standing at target: its last good rehydration put it there, the dir is
    that worktree's top level, and it is on the branch that rehydration left it on."""
    evs = [e for e in rec.get("rehydrations", []) if not e.get("error") and e.get("path")]
    if not evs or not target or not os.path.isdir(target):
        return False
    last = evs[-1]
    if os.path.realpath(last["path"]) != os.path.realpath(target):
        return False
    if rec["kind"] == "orphan":
        return True
    top = gout(target, "rev-parse", "--show-toplevel")
    if not top or os.path.realpath(top) != os.path.realpath(target):
        return False
    br = current_branch(target)
    if "branch" in last:
        return br == last["branch"]
    want = (rec.get("worktree") or {}).get("branch")  # an event from before 0.2.0 names no branch
    return want is None or br == want or bool(br and br.startswith(want + "-rehydrated-"))


def rehydrate_worktree(rec, target, args, touched=None):
    """Every archive check runs before anything changes; `touched["disk"]` is set once the worktree is added."""
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
        git(repo, "fetch", "-q", b, f"{ref}:{ref}", check=True, timeout=BIG_TREE_TIMEOUT_S)
    branch = (rec.get("worktree") or {}).get("branch")
    parent = snap.get("parent")
    notes = []
    big = {"check": True, "timeout": BIG_TREE_TIMEOUT_S}
    sp = (rec.get("worktree") or {}).get("sparse")
    nc = ["--no-checkout"] if sp else []  # a sparse tree is checked out only after its patterns are set
    made = None  # (branch, start) when worktree add creates the branch, so a timed-out add can take it back
    if touched is not None:
        touched["disk"] = True
    try:
        if branch and git(repo, "rev-parse", "--verify", "-q", f"refs/heads/{branch}").returncode == 0:
            tip = gout(repo, "rev-parse", f"refs/heads/{branch}")
            in_use = any(w["branch"] == branch for w in list_worktrees(repo))
            if tip == parent and not in_use:
                git(repo, "worktree", "add", "-q", *nc, target, branch, **big)
            else:
                nb = f"{branch}-rehydrated-{dt.date.today():%Y%m%d}"
                why = "checked out elsewhere" if in_use else f"moved since dehydrate ({tip[:8]} != {str(parent)[:8]})"
                made = (nb, parent or snap["commit"])
                git(repo, "worktree", "add", "-q", *nc, "-b", nb, target, parent or snap["commit"], **big)
                notes.append(f"branch {branch} {why}; restored on new branch {nb}")
        elif branch:
            made = (branch, parent or snap["commit"])
            git(repo, "worktree", "add", "-q", *nc, "-b", branch, target, parent or snap["commit"], **big)
            notes.append(f"branch {branch} was deleted; recreated at {str(parent)[:8]}")
        else:
            git(repo, "worktree", "add", "-q", *nc, "--detach", target, parent or snap["commit"], **big)
        if sp:
            r = subprocess.run(["git", "-C", target, "sparse-checkout", "set", "--cone" if sp["cone"] else "--no-cone",
                                "--stdin"], input="\n".join(sp["patterns"]) + "\n", capture_output=True, text=True,
                               timeout=BIG_TREE_TIMEOUT_S)
            if r.returncode != 0:
                raise RuntimeError(f"sparse-checkout set failed: {r.stderr.strip()[:300]}")
            git(target, "checkout", "-q", **big)
            notes.append(f"restored sparse-checkout ({'cone' if sp['cone'] else 'patterns'}: {', '.join(sp['patterns'])[:200]})")
        # working tree := snapshot tree, index := HEAD (changes come back unstaged, untracked stays untracked)
        git(target, "checkout", snap["commit"], "--", ".", **big)
        git(target, "reset", "-q", **big)
        gone = gout(target, "diff", "--name-only", "--no-renames", "--diff-filter=D", "-z", "HEAD", snap["commit"],
                    timeout=BIG_TREE_TIMEOUT_S)
        for rel in [x for x in gone.split("\0") if x]:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(os.path.join(target, rel))
        if snap.get("index_tree") and gout(target, "rev-parse", "HEAD") == parent:
            git(target, "read-tree", snap["index_tree"], **big)  # staged changes come back staged
        else:
            notes.append("staging not restored (no index recorded or branch moved); all changes are unstaged")
        if sp:
            git(target, "sparse-checkout", "reapply", **big)  # read-tree drops the skip-worktree bits
    except subprocess.TimeoutExpired as e:
        raise SystemExit(abandon_partial(rec, repo, target, made, e, touched))
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
    try:
        if snapshot_tree(target) != snap["tree"]:
            notes.append("WARNING: restored tree differs from the snapshot tree")
    except subprocess.TimeoutExpired:
        notes.append("restored, but the check against the snapshot tree timed out; run `git status` there to look")
    return notes


def abandon_partial(rec, repo, target, made, e, touched):
    """A timed-out checkout leaves a half-written worktree that git keeps locked "initializing". It holds only a
    fresh checkout (the work is in the snapshot), so unlock and remove it, take back a branch the add created,
    and leave the record un-rehydrated. Returns the error to print."""
    cmd = " ".join(str(x) for x in (e.cmd or [])[3:5]) or "checkout"
    git(repo, "worktree", "unlock", target)
    try:
        git(repo, "worktree", "remove", "--force", "--force", target, timeout=BIG_TREE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        pass
    if os.path.lexists(target):
        shutil.rmtree(target, ignore_errors=True)
    git(repo, "worktree", "prune")
    if made and gout(repo, "rev-parse", "--verify", "-q", f"refs/heads/{made[0]}") == gout(repo, "rev-parse", made[1]):
        git(repo, "branch", "-D", made[0])
    gone = not os.path.lexists(target) and \
        all(os.path.realpath(w["path"]) != os.path.realpath(target) for w in list_worktrees(repo))
    snap = rec["snapshot"]
    head = f"git {cmd} timed out after {int(e.timeout)}s while restoring {target} (a very large tree on a busy disk). "
    if gone:
        if touched is not None:
            touched["disk"] = False  # nothing is left on disk, so no rehydrated event: the record stays dehydrated
        return (head + "The partial checkout was unlocked and removed; it held only a fresh checkout, and the work is "
                f"still in {snap['ref']} and {snap['bundle']}. Nothing is marked rehydrated. Run the same rehydrate "
                f"again when the disk is quieter: dehydrate.py rehydrate {rec['id']}")
    return (head + "The partial checkout could not be removed (the work is still in the snapshot). Remove it, then run "
            f"rehydrate again: git -C {shlex.quote(repo)} worktree unlock {shlex.quote(target)} && "
            f"git -C {shlex.quote(repo)} worktree remove --force --force {shlex.quote(target)}")


UNCONFIRMED_WINDOW_S = 600  # a launch that reported no id blocks another launch of that session this long


def launch_sessions(args, rec, resumes):
    """--launch: resume each restored session in the background (`claude --bg --resume`) unless a copy runs.

    Fails closed: when `claude agents` cannot be read nothing is launched, so no duplicate copy is started.
    The copy keeps the agents name (-n). Its new short id is parsed from the CLI's output. Every session that is
    not launched gets an entry with `skipped: true` and the reason in `note`."""
    launched = []

    def skip(r, note):
        launched.append({"from_session_id": r["session_id"], "bg_id": None, "session_id": None, "name": r["name"],
                         "rc": None, "reused": False, "skipped": True, "note": note})
    todo = []
    for r in resumes:
        if r["transcript"]:
            todo.append(r)
        else:
            skip(r, r.get("problem") or "no transcript archived; resume will fail")
    if not todo:
        return launched
    try:
        agents = fetch_agents(args, 60)
    except Exception:
        for r in todo:
            skip(r, f"could not check claude agents; not launched. Run: cd {shlex.quote(r['cwd'])} "
                    f"&& claude --bg --resume {r['session_id']}")
        return launched
    extra, ch = launched_ids(rec), claude_home(args)
    window = float(os.environ.get("DEHYDRATE_UNCONFIRMED_WINDOW_S", UNCONFIRMED_WINDOW_S))
    for r in todo:
        hit = match_running(agents, r["session_id"], r["name"], r["cwd"], extra)
        if hit:
            ref = running_ref(hit)
            note = None if ref["live"] else \
                f"still open in claude agents as {ref['bg_id']} (state {ref['state'] or 'unknown'}); " \
                f"claude attach {ref['bg_id']}, or claude rm {ref['bg_id']} and rehydrate again"
            launched.append(dict(ref, from_session_id=r["session_id"], name=hit.get("name") or r["name"],
                                 rc=0, reused=True, note=note))
            continue
        recent = [l for ev in rec.get("rehydrations", []) for l in (ev.get("launched") or [])
                  if isinstance(l, dict) and l.get("unconfirmed") and l.get("from_session_id") == r["session_id"]
                  and time.time() - record_ts({"at": l.get("at") or ev.get("at") or ""}) < window]
        if recent:
            skip(r, f"an earlier --launch at {recent[-1].get('at')} reported no id and may still be starting; "
                    f"not starting another for {int(window // 60)} min. Check claude agents for "
                    f"{r['name'] or r['session_id'][:8]}, or run: {r['command']}")
            continue
        argv = [args.claude_bin, "--bg", "--resume", r["session_id"]] + (["-n", r["agents_name"]] if r.get("agents_name") else [])
        try:
            p = subprocess.run(argv, cwd=r["cwd"], capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
            out, rc = p.stdout + p.stderr, p.returncode
        except Exception as e:
            out, rc = f"{e.__class__.__name__}: {e}", -1
        m = re.search(r"started a copy as ([0-9a-f]{8})", out) or re.search(r"backgrounded · ([0-9a-f]{8})", out)
        bg, sid = (m.group(1) if m else None), None
        if bg:
            with contextlib.suppress(Exception):
                sid = json.load(open(os.path.join(ch, "jobs", bg, "state.json"))).get("sessionId")
            if not sid:
                with contextlib.suppress(Exception):
                    sid = next((a.get("sessionId") for a in fetch_agents(args, 60) if a.get("id") == bg), None)
        tail = out.strip()[-200:]
        entry = {"from_session_id": r["session_id"], "bg_id": bg, "session_id": sid, "name": r["name"],
                 "rc": rc, "reused": False, "note": None, "out": out.strip()[-300:]}
        if not bg and rc == 0:
            # it may well be starting: record that, so the next --launch does not start a second copy
            entry.update(unconfirmed=True, at=iso(time.time()),
                         note="launch did not report a background id; it may still be starting. Check claude agents"
                              + (f" ({tail})" if tail else "") + f" before running: {r['command']}")
        elif not bg or rc != 0:
            entry["note"] = f"launch failed (rc {rc})" + (f": {tail}" if tail else "") + f". Run: {r['command']}"
        launched.append(entry)
    return launched


def cmd_rehydrate(args):
    sd = state_dir(args)
    find_record(sd, args.key)  # an unknown key fails before the lock
    notes, where, resumes, launched = [], None, [], []
    touched, changed, err = {"disk": False}, False, None
    with run_lock(sd):
        rec = find_record(sd, args.key)  # re-read under the lock
        cur = current_records(sd)
        prior = bool(rec["rehydrations"])
        try:
            if rec["kind"] == "session" and rec.get("linked_worktree_id") and not args.session_only:
                wrec = cur.get(rec["linked_worktree_id"])
                if wrec:
                    wp = wrec["worktree"]["path"]
                    if not os.path.exists(wp):
                        notes += rehydrate_worktree(wrec, wp, args, touched)
                        changed = True
                        append_manifest(sd, {"event": "rehydrated", "id": wrec["id"], "at": iso(time.time()),
                                             "path": wp, "branch": current_branch(wp), "via": rec["id"]})
                    elif in_place(wrec, wp):
                        notes.append(f"worktree already restored at {wp}, nothing changed")
                    else:
                        notes.append(f"{wp} exists and is not this record's restored worktree; left as it is")
                where = wrec["worktree"]["path"] if wrec else None
            elif rec["kind"] in ("worktree", "main-snapshot"):
                target = os.path.realpath(os.path.expanduser(args.path)) if args.path else rec["worktree"]["path"]
                if rec["kind"] == "main-snapshot" and not args.path:
                    raise SystemExit("a main-snapshot is restored next to the checkout, never over it: pass --path <dir>")
                if in_place(rec, target):
                    notes.append(f"already restored at {target}, nothing changed")
                else:
                    notes += rehydrate_worktree(rec, target, args, touched)
                    changed = True
                where = target
            elif rec["kind"] == "orphan":
                target = os.path.expanduser(args.path) if args.path else rec["worktree"]["path"]
                if in_place(rec, target):
                    notes.append(f"already restored at {target}, nothing changed")
                else:
                    if os.path.exists(target):
                        raise SystemExit(f"{target} already exists; pass --path")
                    touched["disk"] = True
                    os.makedirs(target)
                    with tarfile.open(rec["tree_tar"]["path"], "r:gz") as tf:
                        safe_extract(tf, target)
                    changed = True
                where = target
            tidx = transcript_index(claude_home(args))
            for info in rec.get("sessions", []):
                if not info.get("session_id"):
                    continue
                path, restored, problem = restore_transcript(args, info, tidx)
                changed = changed or restored
                if problem:
                    notes.append(f"{info.get('name') or info['session_id'][:8]}: {problem}")
                cwd = where if where and os.path.isdir(where) else (info.get("cwd") if info.get("cwd") and os.path.isdir(info["cwd"]) else None)
                cwd = cwd or rec["repo"].get("path") or os.path.expanduser("~")
                resumes.append({"session_id": info["session_id"], "name": info.get("name") or info.get("agent_name")
                                or info.get("title"), "agents_name": info.get("name"),
                                "cwd": cwd, "transcript": path, "transcript_restored": restored, "problem": problem,
                                "command": f"cd {shlex.quote(cwd)} && claude --resume {info['session_id']}"})
            if args.launch:
                launched = launch_sessions(args, rec, resumes)
        except BaseException as e:
            err = e
            raise
        finally:
            # A restore that touched the disk is always recorded (even when it then failed: `error` says so). A
            # rerun that changed nothing and launched nothing new adds no event, so it does not count again.
            started = any(not l.get("reused") and not l.get("skipped") for l in launched)
            if touched["disk"] or changed or started or (not prior and err is None):
                ev = {"event": "rehydrated", "id": rec["id"], "at": iso(time.time()), "path": where}
                if where and rec["kind"] != "orphan" and os.path.isdir(where):
                    ev["branch"] = current_branch(where)
                if not (touched["disk"] or changed):
                    ev["in_place"] = True
                if err is not None:
                    ev["error"] = str(getattr(err, "code", None) or err)[:300]
                if args.launch:
                    ev["launched"] = [{k: l.get(k) for k in ("from_session_id", "bg_id", "session_id", "name", "rc",
                                                             "reused", "skipped", "unconfirmed", "at") if k in l}
                                      for l in launched]
                with contextlib.suppress(Exception):
                    append_manifest(sd, ev)
            with contextlib.suppress(Exception):
                write_index(sd)
    out = {"id": rec["id"], "kind": rec["kind"], "path": where, "notes": notes, "resume": resumes, "launched": launched}
    if args.json:
        print(json.dumps(out, indent=1))
    else:
        print(f"rehydrated {rec['id']} ({rec['kind']})" + (f" at {where}" if where else ""))
        for n in notes:
            print(f"  note: {n}")
        for r in resumes:
            print(f"  resume {r['name'] or r['session_id'][:8]}: {r['command']}"
                  + ("" if r["transcript"] else f"   ({r['problem'] or 'no transcript archived; resume will fail'})"))
        for l in launched:
            if l.get("skipped") and any(l["note"] in n for n in notes):
                continue  # its reason is a note above
            if l["reused"]:
                print(f"  {l['note']}" if l.get("note") else
                      f"  already running as {l['bg_id']} ({l['name'] or ''}); not started again")
            elif l.get("note"):
                print(f"  {l['note']}")
            else:
                print(f"  launched as {l['bg_id']} ({l['name'] or ''}); it is in `claude agents`")


# ---------------------------------------------------------------- list / show / nudge

def record_repo_name(r):
    rp = (r.get("repo") or {}).get("path")
    if rp:
        return os.path.basename(rp.rstrip("/"))
    o = (r.get("repo") or {}).get("origin")
    return re.sub(r"\.git$", "", re.split(r"[/:]", o.rstrip("/"))[-1]) or None if o else None


def session_haystack(x):
    return [x.get("name"), x.get("agent_name"), x.get("title"), x.get("first_prompt"), x.get("session_id"),
            x.get("bg_id")]


def record_haystack(r, only=None):
    """What `list <words>` searches, lowercased: the record's fields, every session's and the launched-copy ids.
    `only` (a picker row) keeps the record's fields and that one session's, so each row stays small (DESIGN 7)."""
    vals = [r["id"], r.get("description"), (r.get("repo") or {}).get("path"), (r.get("repo") or {}).get("origin"),
            record_repo_name(r), (r.get("worktree") or {}).get("path"), (r.get("worktree") or {}).get("branch")]
    for x in ([only] if only is not None else r.get("sessions", [])):
        vals += session_haystack(x)
    vals += sorted(launched_ids(r))
    return "\n".join(str(v) for v in vals if v).lower()


SEARCH_CAP = 2048  # a picker row's haystack, in characters (the pane's output and store stay far under 4 MiB)


def record_ts(r):
    with contextlib.suppress(Exception):
        return dt.datetime.fromisoformat(r["at"].replace("Z", "+00:00")).timestamp()
    return 0.0


def age_group(ts, now):
    """today (same local calendar date), week (< 7 days), month (< 30 days), older. The pane never recomputes it."""
    if dt.datetime.fromtimestamp(ts).date() == dt.datetime.fromtimestamp(now).date():
        return "today"
    age = now - ts
    return "week" if age < 7 * 86400 else "month" if age < 30 * 86400 else "older"


def picker_agents(args, sd):
    """(agents, "live" | "cached" | "unavailable"): a good listing is cached for when `claude agents` is slow."""
    cache = os.path.join(sd, "agents-cache.json")
    try:
        agents = fetch_agents(args, args.agents_timeout)
        with contextlib.suppress(Exception):
            json.dump({"at": iso(time.time()), "agents": agents}, open(cache + ".tmp", "w"))
            os.replace(cache + ".tmp", cache)
        return agents, "live"
    except Exception:
        with contextlib.suppress(Exception):
            got = json.load(open(cache))["agents"]
            if isinstance(got, list):
                return [a for a in got if isinstance(a, dict)], "cached"
    return [], "unavailable"


def restored_state(r, cur):
    """True when the record's restore is still standing: for a worktree, leftover dir or main snapshot its last
    rehydration's path exists; for a session, its linked worktree's does (or, with none, it was rehydrated)."""
    if r["kind"] == "session":
        w = cur.get(r.get("linked_worktree_id") or "")
        if w is None:
            return bool(r["rehydrations"])
        r = w
    evs = [e for e in r.get("rehydrations", []) if not e.get("error") and e.get("path")]
    return bool(evs) and os.path.isdir(evs[-1]["path"])


def restores(r, cur):
    """How many times the item came back: its own restores (an in-place launch is not one) and, for a session
    record, its linked worktree's restores that were not made through it."""
    n = len([e for e in r["rehydrations"] if not e.get("in_place")])
    w = cur.get(r.get("linked_worktree_id") or "") if r["kind"] == "session" else None
    if w:
        n += len([e for e in w["rehydrations"] if not e.get("in_place") and e.get("via") != r["id"]])
    return n


def picker_rows(args, sd):
    """Flat rows for the rehydrate picker: one per session of each record (its agents name and short id).

    A worktree record and the session record dehydrated with it (`linked_worktree_id`) are one item: the session
    row stands for both (rehydrating it restores the worktree too), and the worktree shows on its own only for
    sessions no session record covers, or when that session record was left open (`claude rm` refused)."""
    now = args.now or time.time()
    agents, how = picker_agents(args, sd)
    words = [w.lower() for w in args.words]
    cur = current_records(sd)
    folded = {}  # worktree record id -> session ids its linked session records stand for
    for r in cur.values():
        if r["kind"] == "session" and r.get("linked_worktree_id") and r.get("removed"):
            folded.setdefault(r["linked_worktree_id"], set()).update(
                x.get("session_id") for x in r.get("sessions", []) if isinstance(x, dict))
    rows = []
    for r in cur.values():
        if args.kind and r["kind"] != args.kind:
            continue
        ts, wt, extra = record_ts(r), r.get("worktree") or {}, launched_ids(r)
        restored = restored_state(r, cur)
        sess = [x for x in r.get("sessions", []) if isinstance(x, dict)]
        if r["id"] in folded and not args.kind:  # --kind worktree asks for the worktree rows themselves
            left = [x for x in sess if x.get("session_id") not in folded[r["id"]]]
            if sess and not left:
                continue
            sess = left
        for x in sess or [{}]:
            sid = x.get("session_id")
            name = x.get("name") or x.get("agent_name") or x.get("title") or \
                os.path.basename((wt.get("path") or "").rstrip("/")) or r["id"]
            cwd = wt.get("path") or x.get("cwd")
            # a cached listing may be stale: there only a live row counts as running
            hit = match_running(agents if how == "live" else [a for a in agents if agent_live(a)], sid, name, cwd, extra)
            run = running_ref(hit) if hit else None
            row = {"id": r["id"], "kind": r["kind"], "name": name, "bg_id": x.get("bg_id") or (sid or "")[:8] or None,
                   "session_id": sid, "group": age_group(ts, now), "dehydrated_at": r["at"], "dehydrated_ts": ts,
                   "description": (r.get("description") or "")[:400], "first_prompt": (x.get("first_prompt") or "")[:300],
                   "branch": wt.get("branch"), "repo": record_repo_name(r), "repo_path": (r.get("repo") or {}).get("path"),
                   "cwd": cwd, "removed": bool(r.get("removed")), "restored": restored, "auto": bool(r.get("auto")),
                   "rehydrations": restores(r, cur), "running": run}
            hay = record_haystack(r, only=x)
            row["search"] = "\n".join(v for v in (name.lower(), ((run or {}).get("bg_id") or "").lower(), hay) if v)[:SEARCH_CAP]
            if all(w in row["search"] for w in words):
                rows.append(row)
    rows.sort(key=lambda x: (-x["dehydrated_ts"], x["id"], x["bg_id"] or ""))
    return {"now": now, "agents": how, "total": len(rows), "rows": rows[: args.limit or 500]}


EMPTY_STORE = "Nothing has been dehydrated yet. /dehydrate closes idle sessions."


def cmd_list(args):
    sd = state_dir(args)
    if args.picker:
        print(json.dumps(picker_rows(args, sd)))
        return
    cur = sorted(current_records(sd).values(), key=lambda r: r["at"], reverse=True)
    words = [w.lower() for w in args.words]
    hits = [r for r in cur if all(w in record_haystack(r) for w in words) and (args.kind is None or r["kind"] == args.kind)]
    hits = hits[: args.limit or 50]
    if args.json:
        print(json.dumps(hits, indent=1))
        return
    if not hits:
        print(EMPTY_STORE if not cur else "no matching dehydrated records")
    for r in hits:
        st = "rehydrated" if r["rehydrations"] else ("removed" if r.get("removed") else "in place")
        names = ", ".join(f"{x.get('name') or x.get('agent_name') or x.get('title') or '(no name)'}"
                          f" ({x.get('bg_id') or (x.get('session_id') or '')[:8] or 'no id'})"
                          for x in r.get("sessions", []) if isinstance(x, dict))
        print(f"{r['id']}  {r['at'][:10]}  {r['kind']:13s} {short((r.get('worktree') or {}).get('path') or (r.get('repo') or {}).get('path') or '')}  [{st}]")
        if names:
            print(f"    {names}")
        print(f"    {(r.get('description') or '')[:200]}")


def cmd_show(args):
    print(json.dumps(find_record(state_dir(args), args.key), indent=1))


def cmd_refresh(args, cfg):
    sd = state_dir(args)
    if args.detach and not detach():
        return
    try:
        lock = open(os.path.join(sd, ".refresh.lock"), "w")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        swept = False
        stamp = os.path.join(sd, "last-auto")
        if cfg.get("auto_on_close") and not cfg.get("_config_error") and (
                not os.path.isfile(stamp) or time.time() - os.path.getmtime(stamp) >= cfg["auto_sweep_minutes"] * 60):
            open(stamp, "w").write(iso(time.time()))
            with contextlib.suppress(Exception):
                a2 = argparse.Namespace(**vars(args), session=None, dry_run=False)
                swept = any(d["decision"] == "dehydrated" for d in auto_sweep(a2, cfg, sd, "sweep")["decisions"])
        lp = os.path.join(sd, "last-plan.json")
        if args.if_stale and not swept and os.path.isfile(lp) and time.time() - os.path.getmtime(lp) < cfg["refresh_after_hours"] * 3600:
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


def off_switch_cmd():
    return f"python3 {shlex.quote(os.path.abspath(__file__))} config set auto_on_close false"


def cmd_nudge(args):
    """At most one DEHYDRATE line per nudge_cooldown_hours, plus config problems in the same throttle, and once
    (the first nudge with a cached plan after an upgrade to 0.2.0) the line saying auto-on-close is on."""
    try:
        sd = state_dir(args)
        cfg = load_config(sd)
        lp = os.path.join(sd, "last-plan.json")
        if not os.path.isfile(lp):
            return
        lines = []
        stamp = os.path.join(sd, "last-nudged")
        if not (os.path.isfile(stamp) and time.time() - os.path.getmtime(stamp) < cfg["nudge_cooldown_hours"] * 3600):
            t = json.load(open(lp))["totals"]
            n = t["sessions_close"] + t["worktrees_dehydrate"] + t["orphans_archive"]
            if n:
                lines.append(f"DEHYDRATE: {t['sessions_close']} sessions and {t['worktrees_dehydrate'] + t['orphans_archive']} "
                             f"worktrees idle over {cfg['days']}d (about {t['reclaim_kb'] / 2**20:.1f} GB). "
                             f"Run /dehydrate when this turn's work is done.")
            lines += [f"DEHYDRATE: {w}" for w in config_warnings(cfg)]
            if lines:
                open(stamp, "w").write(iso(time.time()))
        told = os.path.join(sd, "auto-announced")
        if cfg.get("auto_on_close") and not cfg.get("_config_error") and not os.path.isfile(told):
            lines.append("DEHYDRATE: auto-dehydrate on close is on: an ended session whose worktree branch is merged "
                         f"is dehydrated by itself (log: {short(os.path.join(sd, 'auto.log'))}). "
                         f"Turn it off with: {off_switch_cmd()}")
            open(told, "w").write(iso(time.time()))
        if lines:
            print("\n".join(lines))
    except Exception:
        pass


def cmd_config(args):
    """config: print the effective settings; config get KEY; config set KEY VALUE; config unset KEY."""
    sd = state_dir(args)
    p = os.path.join(sd, "config.json")
    if args.action in (None, "show", "get"):
        cfg = load_config(sd)
        if args.action == "get":
            if not args.key:
                raise SystemExit("config get KEY")
            print(json.dumps(cfg.get(args.key)))
            return 0
        print(f"config: {short(p)}" + ("" if os.path.isfile(p) else " (none: every key at its default)"))
        for k in sorted(DEFAULTS):
            print(f"  {k} = {json.dumps(cfg[k])}" + ("" if cfg[k] == DEFAULTS[k] else "   (default " + json.dumps(DEFAULTS[k]) + ")"))
        for w in config_warnings(cfg):
            print(f"WARNING: {w}")
        return 0
    if not args.key:
        raise SystemExit(f"config {args.action} KEY" + (" VALUE" if args.action == "set" else ""))
    if args.key not in DEFAULTS and args.key not in EXTRA_KEYS:
        raise SystemExit(f"unknown config key {args.key!r}; keys: {', '.join(sorted(DEFAULTS))}")
    cur = {}
    if os.path.isfile(p):
        try:
            cur = json.load(open(p))
        except Exception as e:
            raise SystemExit(f"{short(p)} is not valid JSON ({e}); fix or remove it first")
        if not isinstance(cur, dict):
            raise SystemExit(f"{short(p)} does not hold a JSON object; fix or remove it first")
    if args.action == "unset":
        cur.pop(args.key, None)
    else:
        if args.value is None:
            raise SystemExit("config set KEY VALUE")
        try:
            v = json.loads(args.value)
        except ValueError:
            v = args.value  # a bare word: a string (and then the type check says what it should be)
        why = config_type_error(args.key, v)
        if why:
            raise SystemExit(why)
        cur[args.key] = v
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cur, f, indent=1, sort_keys=True)
        f.write("\n")
    os.replace(tmp, p)
    cfg = load_config(sd)
    print(f"{args.key} = {json.dumps(cfg.get(args.key))}  ({short(p)})")
    return 0


def auto_status(args, cfg):
    sd = state_dir(args)
    on = cfg.get("auto_on_close") and not cfg.get("_config_error")
    L = [f"auto-dehydrate on close: {'on' if on else 'off'}"
         + ("" if on else f" ({'config error' if cfg.get('_config_error') else 'auto_on_close is false'})"),
         f"  config: {short(os.path.join(sd, 'config.json'))}   turn {'off' if on else 'on'}: "
         f"python3 {shlex.quote(os.path.abspath(__file__))} config set auto_on_close {'false' if on else 'true'}",
         f"  grace {cfg['auto_grace_minutes']} min, sweep at most every {cfg['auto_sweep_minutes']} min, "
         f"gh check {'on' if cfg.get('auto_use_gh') else 'off'}, clean trees only: "
         f"{'yes' if cfg.get('auto_require_clean') else 'no'}"]
    stamp = os.path.join(sd, "last-auto")
    if os.path.isfile(stamp):
        L.append(f"  last sweep: {iso(os.path.getmtime(stamp))}")
    with contextlib.suppress(OSError):
        n = len([f for f in os.listdir(pending_dir(sd)) if f.endswith(".json")])
        if n:
            L.append(f"  queued (deferred) sessions: {n}")
    with contextlib.suppress(Exception):
        last = open(os.path.join(sd, "auto.log")).readlines()[-1]
        d = json.loads(last)
        L.append(f"  last decision: {d.get('at')} {d.get('decision')} {d.get('name') or (d.get('session_id') or '')[:8]}: "
                 f"{d.get('reason')}")
    L += [f"WARNING: {w}" for w in config_warnings(cfg)]
    print("\n".join(L))
    return 0


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(prog="dehydrate", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd")

    def common(p, plan_flags=True):
        hide = (lambda h: h) if plan_flags else (lambda h: argparse.SUPPRESS)  # auto reads them, never takes them
        p.add_argument("--days", type=float, help=hide("idle threshold in days (default 7, config 'days')"))
        p.add_argument("--roots", nargs="+", help="dirs to search for repos (default ~/src)")
        p.add_argument("--only", nargs="+", help=hide("limit to these worktree paths/basenames/branches or session ids"))
        p.add_argument("--no-sessions", action="store_true", help=hide("leave sessions alone"))
        p.add_argument("--no-worktrees", action="store_true", help=hide("leave worktrees alone"))
        p.add_argument("--mains", action="store_true",
                       help=hide("also snapshot uncommitted work in main checkouts (never resets them)"))
        p.add_argument("--no-main", action="store_true", help=hide("skip main-checkout snapshots even if config enables them"))
        p.add_argument("--state-dir", help="manifest/archive dir (default $DEHYDRATE_HOME or ~/.claude/dehydrated)")
        p.add_argument("--claude-home", help="Claude config dir (default ~/.claude)")
        p.add_argument("--agents-json", default=os.environ.get("DEHYDRATE_AGENTS_JSON"),
                       help="read sessions from this file instead of `claude agents --json --all`")
        p.add_argument("--claude-bin", default=os.environ.get("DEHYDRATE_CLAUDE_BIN", "claude"), help=argparse.SUPPRESS)
        p.add_argument("--now", type=float, default=float(os.environ["DEHYDRATE_NOW"]) if os.environ.get("DEHYDRATE_NOW") else None,
                       help="epoch seconds to treat as now (tests)")
        p.add_argument("--json", action="store_true", help="print JSON")

    desc = {
        "plan": "Read-only census: which sessions and worktrees are idle past the window, which are held and why, "
                "and what apply would do. Deterministic for the same machine state and --now.",
        "apply": "Do what plan says: snapshot each stale worktree (ref + bundle + archives), record it, then remove "
                 "it and close its sessions with claude stop/rm. Needs --yes. Exit 1: some items not done; 3: "
                 "paused at the disk floor.",
        "refresh": "Rewrite <state>/last-plan.json, what the SessionStart nudge reads (the hook runs it detached). "
                   "With auto_on_close it first runs the auto sweep, at most once per auto_sweep_minutes.",
        "auto": "Auto-dehydrate on close. Dehydrates a session that has ended (a background session done or failed "
                "at least auto_grace_minutes ago, or the one --session names, once its process exits) when its "
                "cwd is a linked worktree whose branch is merged into origin's default branch: contained in it "
                "with commits of its own, or merging it changes nothing and its changes are already there "
                "(squash or rebase merge), or gh shows a PR from it merged at exactly its HEAD. Not live, not "
                "this session, every plan hold kept. Every decision is a line in <state>/auto.log. Rehydrated "
                "items wait until they run and end again. Off: `config set auto_on_close false`; --status says "
                "whether it is on.",
    }
    for name in ("plan", "apply", "refresh", "auto"):
        p = sub.add_parser(name, help=desc[name].split(". ")[0], description=desc[name])
        common(p, plan_flags=name != "auto")
        if name in ("refresh", "auto"):
            p.add_argument("--detach", action="store_true", help="fork into the background and return at once (hooks)")
            p.add_argument("--gh-bin", default=os.environ.get("DEHYDRATE_GH_BIN", "gh"),
                           help="gh for the merged-PR check (config auto_use_gh)")
        if name == "refresh":
            p.add_argument("--if-stale", action="store_true", help="rebuild the plan only when it is over "
                                                                   "refresh_after_hours old")
        if name == "auto":
            p.add_argument("--session", help="only this session id (the mod's session.end kick); waits for it to exit")
            p.add_argument("--dry-run", action="store_true", help="print the decisions, change nothing")
            p.add_argument("--status", action="store_true", help="say whether auto is on, the last sweep and decision")
        if name == "apply":
            p.add_argument("--yes", action="store_true", help="required: apply acts without a prompt")
        if name in ("plan", "apply"):
            p.add_argument("--pressure", action="store_true",
                           help="disk-pressure mode: ignore --days for worktrees, go least recently active first, "
                                "stop once free disk reaches --target-gb (every hold still applies)")
            p.add_argument("--target-gb", type=float, help="with --pressure: stop when free disk is at least this")
    p = sub.add_parser("list", help="search what was dehydrated",
                       description="Search the manifest: every word must appear (case-insensitive) in a record's id, "
                                   "description, session names, titles and first prompts, branch, repo, paths or "
                                   "session ids. No words: the newest 50.")
    p.add_argument("words", nargs="*", help="words that must all match")
    p.add_argument("--kind", choices=["worktree", "session", "orphan", "main-snapshot"])
    p.add_argument("--limit", type=int, help="most records shown (default 50; 500 with --picker)")
    p.add_argument("--state-dir")
    p.add_argument("--json", action="store_true", help="full records as JSON")
    p.add_argument("--picker", action="store_true", help="flat JSON rows for the rehydrate picker (one per session)")
    p.add_argument("--agents-json", default=os.environ.get("DEHYDRATE_AGENTS_JSON"))
    p.add_argument("--agents-timeout", type=float, default=20, help="seconds for `claude agents --json` (--picker)")
    p.add_argument("--claude-bin", default=os.environ.get("DEHYDRATE_CLAUDE_BIN", "claude"), help=argparse.SUPPRESS)
    p.add_argument("--claude-home")
    p.add_argument("--now", type=float, default=float(os.environ["DEHYDRATE_NOW"]) if os.environ.get("DEHYDRATE_NOW") else None,
                   help="epoch seconds to treat as now (tests)")
    p = sub.add_parser("show", help="print one manifest record", description="Print one manifest record as JSON.")
    p.add_argument("key", help="the same keys rehydrate takes")
    p.add_argument("--state-dir")
    p = sub.add_parser("rehydrate", help="bring a dehydrated worktree and its sessions back",
                       description="Recreate a dehydrated worktree at its path on its branch with every uncommitted, "
                                   "untracked and gitignored file, restore swept transcripts, and print the resume "
                                   "commands. Every archive file is checked before anything changes. A worktree "
                                   "already restored at its path is left as it is (--launch still launches). "
                                   "--launch resumes each session with claude --bg --resume unless a copy runs.")
    p.add_argument("key", help="manifest id, session id (or first 8), background id, exact claude agents name, "
                               "branch or worktree path")
    p.add_argument("--path", help="restore the worktree here instead of its original path")
    p.add_argument("--session-only", action="store_true", help="restore the transcript only, not the worktree")
    p.add_argument("--launch", action="store_true",
                   help="resume the sessions in the background (claude --bg --resume) unless a copy already runs")
    p.add_argument("--state-dir")
    p.add_argument("--claude-home")
    p.add_argument("--claude-bin", default=os.environ.get("DEHYDRATE_CLAUDE_BIN", "claude"), help=argparse.SUPPRESS)
    p.add_argument("--agents-json", default=os.environ.get("DEHYDRATE_AGENTS_JSON"))
    p.add_argument("--json", action="store_true", help="print the result (or {error}) as JSON")
    p = sub.add_parser("nudge", help="SessionStart hook: one throttled DEHYDRATE line",
                       description="SessionStart hook: print one DEHYDRATE line when the cached plan has work, at most "
                                   "once per nudge_cooldown_hours. Never fails.")
    p.add_argument("--state-dir")
    p.add_argument("--claude-home")
    p.add_argument("--claude-bin", help=argparse.SUPPRESS)
    p = sub.add_parser("config", help="show or change config.json",
                       description="Show the effective settings (no action), get one, or set/unset one in "
                                   "<state>/config.json ($DEHYDRATE_HOME or ~/.claude/dehydrated). Other keys are kept. "
                                   "Values are JSON (true, false, 10, [\"~/src\"]) and are type-checked.")
    p.add_argument("action", nargs="?", choices=["show", "get", "set", "unset"])
    p.add_argument("key", nargs="?")
    p.add_argument("value", nargs="?")
    p.add_argument("--state-dir")
    p.add_argument("--claude-home", help=argparse.SUPPRESS)
    p.add_argument("--claude-bin", help=argparse.SUPPRESS)

    args = ap.parse_args(argv)
    if not args.cmd:
        args = ap.parse_args(["plan"] + (argv or sys.argv[1:]))
    if os.environ.get("CLAUDE_CODE_REMOTE") == "true" and args.cmd in ("plan", "apply", "refresh", "auto"):
        print("dehydrate is local-desktop only (cloud sessions have no ~/src or background sessions)")
        return 0
    if args.cmd == "list":
        return cmd_list(args)
    if args.cmd == "show":
        return cmd_show(args)
    if args.cmd == "rehydrate":
        try:
            return cmd_rehydrate(args)
        except SystemExit as e:
            if args.json and isinstance(e.code, str):  # the picker reads the reason from JSON
                print(json.dumps({"error": e.code}))
                return 1
            raise
    if args.cmd == "nudge":
        return cmd_nudge(args)
    if args.cmd == "config":
        return cmd_config(args)
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
    if args.cmd == "auto":
        if args.status:
            return auto_status(args, cfg)
        return cmd_auto(args, cfg)
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
