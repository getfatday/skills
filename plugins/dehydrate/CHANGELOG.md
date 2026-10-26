# Changelog

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
