---
name: init
description: Scaffold the current repository for knowledge intake — create the raw/notes/journal directories, seed the index and journal shapes, install the marker-delimited capture-rule block into CLAUDE.md, and write the settings deny rules that keep raw files and journal fragments write-once. Idempotent; safe to re-run to repair drift.
disable-model-invocation: true
---

# Initialize knowledge intake in this repository

Run the deterministic scaffold script, then commit the result. The plugin's hooks are only
active while the plugin is enabled; the artifacts this step writes into the repository
(CLAUDE.md rule block, settings deny rules, GOVERNANCE.md, the compile script) are the durable
layer that survives a plugin disable.

## Steps

1. **Choose paths.** Defaults: raw `research/raw/`, notes `research/notes/`, index
   `research/index.md`, journal fragments `experiments/journal-fragments/`. Use the defaults
   unless the user asked for different locations; pass overrides as flags below.
2. **Run the scaffold** from the repository root:

   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/init-scaffold.py" . \
     [--raw-dir DIR] [--notes-dir DIR] [--index-file FILE] \
     [--journal-dir DIR] [--journal-file FILE] [--compiled-file FILE]
   ```

   The script is idempotent: it creates what is missing, repairs the plugin-owned canonical
   artifacts (the CLAUDE.md marker block, the deny rules, `scripts/compile-journal.py`), and
   never overwrites consumer-owned content (the index, notes, raw files, fragments, or an
   existing GOVERNANCE.md). Read its per-artifact output and report it to the user verbatim.
3. **Review what changed** (`git status`, `git diff`) and explain the three layers:
   - hooks (from the plugin, active while enabled): write-once guard on raw files and journal
     fragments, capture-intent nudge, start-of-session drift check, unjournaled-work backstop;
   - durable repository artifacts (survive plugin disable): the CLAUDE.md rule block and the
     `.claude/settings.json` deny rules;
   - procedure: the `intake` skill carries the capture process itself.
4. **Commit** the scaffold as one attributed commit, separate from other work. If the
   repository is not a git repo yet, say so: the stop backstop stays inactive until it is.
5. **Verify**: the next session start should print `lab-intake … drift check: clean`.
   To check immediately:

   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/drift-check.py" < /dev/null
   ```

## Notes

- Re-running init is the supported way to repair drift the session-start check reports.
- All scaffolded content is rendered from `${CLAUDE_PLUGIN_ROOT}/templates/`; nothing is
  generated from timestamps, so re-running with the same inputs is byte-stable.
