---
name: init
description: Scaffold the current repository for hypothesis experiments — create the hypotheses and runs directories, install the spec template and the deterministic preflight script, and extend CLAUDE.md with the experiment-loop rules block. Requires the lab-intake plugin to be installed and initialized first; refuses with instructions when it is not. Idempotent; safe to re-run.
disable-model-invocation: true
---

# Initialize the experiment loop in this repository

Run the deterministic scaffold script, then commit the result. This plugin extends
lab-intake: the journal and capture discipline live in the base, so the scaffold refuses
to run until the base is initialized here. The plugin's hooks are only active while the plugin
is enabled; the artifacts this step writes into the repository (the spec template, the
preflight script, the CLAUDE.md rules block) are the durable layer that survives a plugin
disable.

## Steps

1. **Check the base.** `.claude/lab-intake.json` must exist at the repository root. If it
   does not, stop and tell the user to install the lab-intake plugin (declared in this
   plugin's manifest dependencies) and run `/lab-intake:init` first. The scaffold script
   makes the same check and refuses, writing nothing, with the same instructions.
2. **Choose paths.** Defaults: specs `hypotheses/`, template `hypotheses/TEMPLATE.md`, runs
   `experiments/runs/`, preflight `experiments/preflight.py`. Use the defaults unless the user
   asked for different locations; pass overrides as flags below.
3. **Run the scaffold** from the repository root:

   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/init-scaffold.py" . \
     [--hypotheses-dir DIR] [--runs-dir DIR] [--template-file FILE] [--preflight-file FILE]
   ```

   The script is idempotent: it creates what is missing, repairs the plugin-owned artifacts
   (the config file, the installed preflight script, the CLAUDE.md marker block), and never
   overwrites consumer-owned content (registered specs, run artifacts, or a template you have
   edited). Read its per-artifact output and report it to the user verbatim.
4. **Review what changed** (`git status`, `git diff`) and explain the three layers:
   - hooks (from the plugin, active while enabled): the preflight gate on run-shaped commands
     and the advisory commit backstop;
   - durable repository artifacts (survive plugin disable): the spec template, the installed
     preflight script, and the CLAUDE.md rules block;
   - procedure: the `hypothesis` skill carries the loop itself.
5. **Commit** the scaffold as one attributed commit, separate from other work.
6. **Verify** the preflight is installed and runnable:

   ```
   python3 experiments/preflight.py hypotheses/TEMPLATE.md
   ```

   It should print the per-check PASS/FAIL lines and end in ESCALATE — the template is a
   shape, not a runnable spec. A registered spec that fills every section correctly exits 0.

## Notes

- Re-running init is the supported way to repair the plugin-owned artifacts.
- All scaffolded content is rendered from `${CLAUDE_PLUGIN_ROOT}/templates/` and the plugin's
  shipped scripts; nothing is generated from timestamps, so re-running with the same inputs is
  byte-stable.
