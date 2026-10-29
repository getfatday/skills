# Changelog

## 0.1.3

- `apply` no longer crashes when `git worktree remove` is slow: it runs with a 3600 s timeout and
  a timeout becomes a "not done" item (captured, not removed; rerun apply). A 330k-file worktree
  took over 120 s and the crash also skipped `worktree prune` and the index rewrite.
- `apply` isolates every item: an exception while handling one worktree, session, leftover dir or
  main checkout is recorded as "not done" and the loop continues. `worktree prune` and
  `write_index` always run (finally).
- Disk-pressure mode: `plan|apply --pressure --target-gb N`. The idle window is ignored for
  worktrees; candidates go least recently active first, then largest, one at a time, and apply
  stops as soon as free disk reaches N (exit 0, `pressure.reached` in the JSON). Every hold still
  applies. A session that is `done` or `blocked` for more than 24 h no longer protects its
  worktree and is archived and closed with it; other sessions, leftover dirs and main checkouts
  are left alone. `DEHYDRATE_FAKE_FREE_GB` feeds the stop check in tests.

## 0.1.2

- `--mains` no longer crashes when a linked worktree sits under a gitignored path inside a main
  checkout. `git add` rejects a `:(exclude)` pathspec for an already-ignored path, so ignored
  worktree paths are dropped from the exclude list (they are not captured anyway).
- One failing main checkout no longer aborts the whole `--mains` pass. It is recorded as
  `ok: false` with a `not captured: ...` error and the remaining checkouts are still snapshotted.

## 0.1.1

- Record ids hash with sha256 instead of sha1 (CodeQL `py/weak-sensitive-data-hashing`). Nothing
  secret was hashed; stored ids are unchanged.

## 0.1.0

- Initial release: `dehydrate` and `rehydrate` skills, SessionStart nudge hook, `scripts/dehydrate.py`.
