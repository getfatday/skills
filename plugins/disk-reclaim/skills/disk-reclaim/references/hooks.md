# Disk hooks: what runs, where state lives, how to tune

The plugin's `hooks/hooks.json` registers the nudge and the census at SessionStart, and the census again at SessionEnd. The census is heavy
(2 to 5 minutes, I/O bound), so it always runs detached and niced, and only when the ledger is over six hours old; SessionStart fires immediately at session start; SessionEnd fires too, but in headless sessions it runs one to three minutes after the CLI has returned, at final process teardown. Registering both means the ledger refreshes at whichever comes first, and the lock makes the second a no-op. The nudge is
light (about 0.2 s end to end, sub-millisecond in-process) and runs at SessionStart, where one line
of context reaches the next session. Nothing runs on Stop, which in many repos already carries
several hooks.

Both scripts follow one contract: fast, silent, every error caught, exit 0 always. A hook that can
block a session is worse than no hook.

## Why the census is detached and launched from SessionStart

Measured with headless sessions: the CLI waits for a 20-second inline SessionEnd hook, but a
150-second census never wrote its ledger, while a `nohup`-detached command finished after the CLI
had exited. So the hook starts the census with `--detach`, which double-forks into its own process session (`setsid`) and returns at once; plain `nohup … &` is not enough, because the CLI kills the hook's process group at teardown and a probe showed a nohup'd child dying with it. A later probe showed that plugin-declared SessionEnd hooks in headless sessions fire late, one to three minutes after the CLI returns, so a census that must be fresh for the next session cannot rely on them alone. The census is therefore also launched from SessionStart (detached, `nice -n 19`); whichever of the two starts first takes the lock and the other exits at once.
`--if-stale 21600` makes it a no-op when the ledger is under six hours old or another census holds
`census.lock`, so a dozen sessions ending in a day cost one census, not twelve.

## State directory: `~/.claude/disk-reclaim/` (override with `DISK_RECLAIM_DIR`)

| File | Written by | Purpose |
|---|---|---|
| `threshold-gb` | you | integer GB of free space below which the nudge fires; default 30 when absent |
| `cooldown-hours` | you | minimum hours between nudges across all sessions; default 4 |
| `snooze` | you (`touch`) | silences the nudge while the file's mtime is under 24 hours old |
| `last-nudged` | nudge | stamp for the cooldown |
| `last-census.json` | census `--ledger` | full rows plus summary; the nudge names its top three regenerable rows |
| `census-log.jsonl` | census `--ledger` | one summary line per run: elapsed, container figures, measured and regenerable bytes |
| `census.lock` | census | pid of a running census; removed on completion |
| `hook-log.jsonl` | nudge | one line per firing: free_gb, threshold, snoozed, cooling, fired, ms_in_process |
| `ledger.jsonl` | `disk_reclaim_record.py` | one line per reclaim decision: path, bytes, command, who decided, when |

One directory per user, not per repo. The disk is machine-wide; a per-project ledger would fork
the threshold, snooze, and staleness clocks across every repo you work in and miss most session
ends.

## The nudge line

```
DISK_RECLAIM: 37 GB free on / (threshold 40 GB). Run the disk-reclaim skill when this turn's work
is done. Regenerable now: 6.2 GB ~/Library/pnpm/store/v3; 2.5 GB ~/src/app/node_modules;
2.3 GB ~/Library/Caches/ms-playwright. Snooze 24h: touch ~/.claude/disk-reclaim/snooze
```

It appears in the session's context at start. "Finish the current turn first" is the point: the
hook surfaces the condition, the model chooses the moment.

## Tuning

- Raise `threshold-gb` on a machine that routinely runs simulators; 40 to 50 GB leaves room for a
  runtime download.
- Lower `cooldown-hours` if you want every fresh session to hear it; raise it if you run many.
- `touch ~/.claude/disk-reclaim/snooze` after a deliberate "not today"; it expires on its own.
- If `census-log.jsonl` shows `elapsed_s` climbing toward several hundred seconds, the machine has
  many worktrees; that is fine for a detached run.

## Running the census by hand

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/disk_census.py"            # human table, read-only
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/disk_census.py" --json     # ledger records
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/disk_census.py" --ledger   # refresh the state files
```

## Uninstall

Uninstall the plugin; the hooks go with it. Delete `~/.claude/disk-reclaim/` if you do not want
the ledger history.
