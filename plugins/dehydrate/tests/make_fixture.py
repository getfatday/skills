"""Build a sandbox for evals: python3 make_fixture.py <out-json>. Prints the env to export.

The sandbox is the unit-test fixture (bare origin, clone with worktrees in known states, fake
~/.claude, fake claude binary). Exporting the printed env makes every dehydrate.py call, including
the ones a skill-following agent types, see only the sandbox.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_dehydrate as T  # noqa: E402

f = T.Fixture()
os.makedirs(os.path.join(f.root, "bin"))
os.symlink(f.claude, os.path.join(f.root, "bin", "claude"))
env = {"PATH": os.path.join(f.root, "bin") + ":" + os.environ["PATH"],"DEHYDRATE_ROOTS": f.src, "DEHYDRATE_AGENTS_JSON": f.agents, "DEHYDRATE_NOW": str(T.NOW),
       "CLAUDE_CONFIG_DIR": f.home, "DEHYDRATE_CLAUDE_BIN": f.claude, "DEHYDRATE_HOME": f.state,
       "GIT_CONFIG_GLOBAL": "/dev/null", "DEHYDRATE_GH_BIN": T.FAKE_GH}
info = {"root": f.root, "repo": f.repo, "worktrees": f.wt, "hermes": f.hermes, "orphan": f.orphan,
        "calls_log": f.calls, "env": env, "sessions": f.sessions, "unpushed_sha": f.unpushed_sha,
        "main_sha": f.main_sha}
json.dump(info, open(sys.argv[1], "w"), indent=1)
print(" ".join(f"export {k}={v};" for k, v in env.items()))
