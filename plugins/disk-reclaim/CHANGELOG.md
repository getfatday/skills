# Changelog

## 0.4.2

- Fix: the `stale-worktrees` step never ran after a dehydrate upgrade. `last-census.json` is a
  snapshot, and one taken between two installs (0.2.0 and 0.2.1 landed in the plugin cache within
  minutes) recorded the older plugin dir; the 0.4.1 live re-check then refused it as "not the
  newest installed dehydrate" on every run until the next census. Rows are now resolved again when
  they are loaded to act on: the dehydrate dir is always the newest installed version by the
  `find_dehydrate` rule, never the path a census, cache or plugin registry recorded. The ledger
  decision and outcome carry that resolved dir.

## 0.4.1

- `stale-worktrees` needs dehydrate 0.2.1 or later, the first that holds worktrees inside a live
  session's job dir, holds trees touched in the last 2 hours under `--pressure`, and re-reads its
  config and holds right before each capture and removal. An older installed dehydrate makes the
  class not eligible (it is skipped with the reason), so automatic reclaim never delegates to it.
- The dry run and the printed lines for `stale-worktrees` name the worktrees instead of the
  dehydrate plugin dir: the dry run asks dehydrate's read-only `plan --pressure --json` and lists
  its order up to the estimated stop; an executed run lists what dehydrate removed, also recorded
  as `targets` on the ledger outcome and the `free-log.jsonl` line. The ledger `path` stays the
  plugin dir, the key the gate matches decisions on.

Earlier versions are described in the git history (0.4.0: Claude waste classes and automatic
reclaim).
