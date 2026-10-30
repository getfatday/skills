# Storage layout

Events: `dehydrated` (written before anything is removed), `removed` (the worktree or session
is gone), `rehydrated` (with `launched` when `--launch` ran). A record whose `removed` event is missing was captured but left in place.

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
| `config.json` | Optional overrides, see the skill. `dehydrate.py config set <key> <value>` writes it. A value of the wrong type keeps its default and is a config error (auto off); an unknown key is warned about |
| `auto.log` | JSONL, one line per auto-dehydrate decision: `at`, `session_id`, `bg_id`, `name`, `trigger` (`sweep`, `session.end` or `session.end (deferred)`), `decision` (`dehydrated`, `refused` or `deferred`), `reason`, plus `merged_by` and `ids` when dehydrated. A refusal is logged again only when its reason changes |
| `agents-cache.json` | `{at, agents}`: the last good `claude agents --json --all` listing. `list --picker` falls back to it when the live call times out (`"agents": "cached"`) |
| `last-auto` | Its mtime gates the SessionStart sweep to once per `auto_sweep_minutes` |
| `.auto.lock` | flock held by one `auto` run at a time. A close kick takes it only after its session's process exits, and waits up to `DEHYDRATE_AUTO_LOCK_WAIT_S` (120 s) for it |
| `.lock` | flock held by apply and rehydrate (auto's apply waits for it the same way) |
| `auto-pending/<session id>.json` | A close kick that could not get a lock: `{session_id, at, why}`. The next `auto` run (the lock holder, or the next SessionStart sweep) takes each one as that session's kick and deletes the file |
| `auto-announced` | Written by the first nudge that said auto-on-close is on (said once) |

The mod keeps one value in the plugin's `$.store`: `picker-cache`, the last `list --picker` JSON
(at most 500 rows, descriptions cut to 200 characters, haystacks to 2048), drawn at once while the
next listing loads.

## A `dehydrated` record

- `id`: `<YYYYMMDD>-<slug>-<6 hex>`, dated in UTC by the plan's clock, the same clock as `at`
  (under `--now` / `DEHYDRATE_NOW`, both follow it). Same item in the same run gets the same id.
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
- `auto` (records `auto` wrote): `{trigger: "sweep" | "session.end", merged_by: "ancestor" |
  "merge-tree" | "gh-pr", pr: <number> | null, default_branch}`.
- `sessions[].name` is the `claude agents` name at dehydrate time. `agent_name` is the last
  `agent-name` entry in the transcript (it tracks renames) and is the fallback, then `title`.
  When the transcript is missing, `first_prompt` falls back to the job's `intent`.

A session "ended" for the sweep's grace period at its last activity: the newest of its
`startedAt`, transcript mtime and job `state.json` / `timeline.jsonl` mtimes.

## A `rehydrated` event

`{event, id, at, path, branch, via?, in_place?, error?}`. `branch` is the branch the worktree was
left on; a later rehydrate that finds the worktree still at `path` on that branch changes nothing.
Such a rerun writes no event unless it launched something, and then `in_place: true` (not counted
as a restore). `error` marks a restore that changed the disk and then failed. With `--launch` it
also carries `launched`: one entry per session, `{from_session_id, bg_id, session_id, name, rc,
reused, skipped?, unconfirmed?, at?}`. `bg_id` and `session_id` are the background copy's new ids
(`reused: true` when a copy was already running or listed and nothing was started, `skipped: true`
when it was not launched, `unconfirmed: true` with `at` when the launch printed no id: another
launch of that session is refused for 10 minutes). `list --picker` and the next `--launch` match
copies against these ids.

## `list --picker` rows

`{now, agents: "live" | "cached" | "unavailable", total, rows: [...]}`. One row per session of each
current record (a record with no session gives one row). A worktree record's session that a
session record covers (`linked_worktree_id`, that session record closed) is drawn only as the
session record's row. `total` counts every matching row, `rows` holds the 500 newest. Fields: `id`, `kind`, `name`, `bg_id`,
`session_id`, `group` (`today` = the same local date as now, `week` under 7 days, `month` under
30, else `older`), `dehydrated_at`, `dehydrated_ts`, `description` (400 chars), `first_prompt`
(300), `branch`, `repo` (basename of the repo path, else of the origin URL), `repo_path`, `cwd`,
`removed`, `restored` (its last rehydration's path still exists; for a session record, its linked
worktree's), `auto`, `rehydrations` (restores, not in-place launches), `running` (`{bg_id,
session_id, state, live}` of the agents row it still has: listed under its own or a launched copy's
id in any state, or a live row with the same name and cwd; with a cached listing only live rows;
or null) and `search`, the lowercased haystack of the record's fields and this row's session (at
most 2048 characters; `list <words>` matches every session of a record). Newest first.

## Snapshot recipe

A temporary index outside the worktree: `read-tree HEAD`, `add -A`, `write-tree`,
`commit-tree -p HEAD -p <index commit>`, `update-ref refs/dehydrated/<id>`. The index commit is
`write-tree` of a copy of the real index, so partial staging round-trips and the source index is
never written. That captures modified, staged, deleted and untracked files and respects
`.gitignore`. Not reproduced: empty directories, sparse-checkout settings, intent-to-add (`git add -N`) entries (they come back untracked).
