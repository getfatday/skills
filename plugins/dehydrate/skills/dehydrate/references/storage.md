# Storage layout

Events: `dehydrated` (written before anything is removed), `removed` (the worktree or session
is gone), `rehydrated`. A record whose `removed` event is missing was captured but left in place.

Everything lives at the user level, one place for every repo: `$DEHYDRATE_HOME` or
`~/.claude/dehydrated/`.

| Path | What |
|---|---|
| `manifest.jsonl` | Append-only event log. One JSON object per line, `event` = `dehydrated` or `rehydrated`. Never edit it |
| `index.md` | Readable table, regenerated from the manifest after every apply and rehydrate |
| `archive/<id>/snapshot.bundle` | Git bundle holding `refs/dehydrated/<id>` and every commit not on origin's default branch, so unpushed commits and branches later deleted upstream both survive |
| `archive/<id>/raw.tar.gz`, `raw-files.json` | Every modified and untracked file as raw bytes with mode and sha256, restored last so CRLF, filter input, 0600 and symlinks come back exactly |
| `archive/<id>/ignored.tar.gz` | Gitignored files that are not build output (`.env`, local notes, settings.local.json) |
| `archive/<id>/transcripts/<session>.jsonl.gz` | Transcript copies, checksummed against the original |
| `archive/<id>/job-<bg-id>.tar.gz` | The background job dir (state, timeline, tmp/ up to 200 MB) |
| `archive/<id>/tree.tar.gz` | For an unregistered leftover dir: its files minus build output |
| `last-plan.json`, `last-apply.json` | Latest plan (what the nudge reads; written by `refresh`, never by a pressure plan) and apply result. `last-apply.json` from `apply --pressure` carries `pressure: {target_gb, reached, free_checked_gb}`. `plan --pressure --json` prints `pressure: {target_gb, free_gb, order, estimated_stop_after}`: `order` is the worktree paths in the order apply takes them, `estimated_stop_after` how many of them apply expects to take from their measured sizes (0 when free disk already meets the target, null when all of them together would not) |
| `config.json` | Optional overrides, see the skill |

## A `dehydrated` record

- `id`: `<YYYYMMDD>-<slug>-<6 hex>`. Same item in the same run gets the same id.
- `kind`: `worktree`, `session`, `orphan` (unregistered dir) or `main-snapshot`.
- `repo`: `{path, origin}`. `worktree`: `{path, branch, head, dirty_count, untracked_count, unpushed, upstream}`.
- `snapshot`: `{ref, commit, tree, parent, bundle, bundle_sha256, bundle_bytes}`.
- `ignored`: `{path, count, sha256}` or null.
- `sessions`: one entry per bound session: `session_id`, `bg_id`, `name`, `title`, `first_prompt`,
  `last_text`, `cwd`, `project_dir`, `transcript_copy`, `transcript_sha256`, `job_archive`.
- `description`: the session's title or name plus its first prompt. A worktree with no session
  gets "worktree <name> on <branch>".
- `removed`: true when the worktree was removed or the session closed. `remove_error` / `close`
  carry the reason when not.
- `linked_worktree_id` (session records): the worktree record dehydrated in the same run.

## Snapshot recipe

A temporary index outside the worktree: `read-tree HEAD`, `add -A`, `write-tree`,
`commit-tree -p HEAD -p <index commit>`, `update-ref refs/dehydrated/<id>`. The index commit is
`write-tree` of a copy of the real index, so partial staging round-trips and the source index is
never written. That captures modified, staged, deleted and untracked files and respects
`.gitignore`. Not reproduced: empty directories, sparse-checkout settings, intent-to-add (`git add -N`) entries (they come back untracked).
