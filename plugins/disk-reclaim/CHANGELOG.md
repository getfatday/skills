# Changelog

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
