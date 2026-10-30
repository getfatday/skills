# getfatday/skills

Personal skills and CLIs for Claude Code plugins. Public repo, no secrets.

## Structure

- `clis/` — Python CLI packages (uv workspace members). Each CLI is a standalone tool that a plugin can depend on.
- `plugins/` — Claude Code plugins (agents, commands, skills). Each plugin is self-contained with a `.claude-plugin/plugin.json` manifest.
- `scripts/` — Release orchestration, version bumping, and scaffolding.
- `.claude-plugin/marketplace.json` — Registry of all plugins in this repo.

## CLI Conventions

- Python 3.12+, uv for dependency management
- Click for CLI framework
- `--json` flag on every command for machine-readable output
- `--format` flag where multiple output formats make sense (table, csv, json)
- Keyring for credential storage (never in config files or env vars)
- Tests required for all commands
- Type hints on all functions
- Hatchling build backend, src layout
- Exit codes: 0 (ok), 1 (error), 2 (usage), 3 (auth), 4 (not found) — defined in `context.py`
- JSON envelope for machine output: `{"ok": true, ...}` / `{"ok": false, "error": "code", "message": "text"}`

## Plugin Conventions

Each plugin follows this layout:
```
plugins/{name}/
├── .claude-plugin/plugin.json
├── agents/
├── commands/
└── skills/
    └── {skill-name}/
        ├── SKILL.md
        ├── references/
        ├── workflows/
        └── templates/
```

## TUI Guidelines

When calling CLIs via the Bash tool, the `description` parameter controls what appears in the Claude Code TUI. Make it human-readable.

- Describe the action, not the command. "Searching IMDB for Tom Jacobson" not "Run gfd-imdb search people Tom Jacobson".
- Use present progressive tense: "Searching...", "Fetching...", "Loading...", "Checking...".
- Never include file paths, `cd` commands, `--format` flags, or CLI names in the description.
- The description should read like a loading spinner message.
- Always use `--format json` when calling CLIs, but parse the JSON and present formatted results to the user. Never dump raw JSON output.

## Development

```bash
make lint          # ruff check
make test          # pytest
make typecheck     # mypy
make new-cli NAME=foo   # scaffold new CLI at clis/foo-cli/
make release CLI=foo    # release clis/foo-cli/
```

## CI/CD

- **CI**: Runs lint + test on PRs (path-filtered per CLI). Checks for towncrier news fragments.
- **Release**: On merge to main, detects news fragments, bumps version, generates changelog, builds wheel, creates GitHub Release.
- **CodeQL**: Security scanning on pushes and PRs to main.

## Changelog

Each CLI maintains its own `CHANGELOG.md` via towncrier. PRs that change a CLI must include a news fragment in `clis/{name}/newsfragments/` (e.g., `1.feature`, `2.bugfix`).

## CLIs

### copilot-money-cli
Personal finance CLI reading local Copilot Money cache (LevelDB/Firestore). No API needed.
Command: `gfd-copilot-money`

### imdb-cli
IMDB movie and TV data CLI using Cinemagoer.
Command: `gfd-imdb`

## Plugins

### copilot-money
Personal finance data access. Wraps `gfd-copilot-money` CLI.
Commands: `/copilot-money`, `/copilot-money:transactions`, `/copilot-money:budget`, `/copilot-money:summary`, `/copilot-money:status`

### imdb
IMDB movie and TV data. Wraps `gfd-imdb` CLI.
Commands: `/imdb`, `/imdb:movie`, `/imdb:person`, `/imdb:top`

### main-refresh
Keeps a local main checkout equal to origin/main for people who branch through Claude worktrees.
Checks safety before acting, fast-forwards only when safe, and parks dirty files or local-only
commits on a wip branch instead of stashing. A UserPromptSubmit hook applies it on every prompt.

### disk-reclaim
Recovers disk on a macOS dev laptop without losing work: read-only census, owner asks, a ledger-gated
executor (`disk_reclaim.py`) as the only delete path. Automatic mode (on by default) reclaims spools,
old Claude CLI versions, idle job scratch and, through dehydrate `--pressure`, stale worktrees when free
space is under `target-gb`. Tests: `python3 -m unittest discover -s plugins/disk-reclaim/tests`.

### dehydrate
Closes stale Claude Code sessions and git worktrees without losing work: snapshots each idle
worktree into a ref, bundle and tarballs, archives transcripts, records a user-level manifest,
then removes the worktree and closes the session. `/rehydrate` restores it exactly and resumes.
A SessionStart hook nudges when stale sessions pile up. Since 0.2.0 a mod (`hooks/register.tsx`, listed
under `modules` in `hooks.json`) opens a searchable picker on a bare `/rehydrate`, grouped by age, and Enter
relaunches the session with `claude --bg --resume` (never a duplicate of a listed session). A `session.end`
hook runs a detached `dehydrate.py auto` that dehydrates the ended session only when its branch is merged
into the remote default branch; `dehydrate.py config set auto_on_close false` turns it off.
Tests: `python3 -m unittest discover -s plugins/dehydrate/tests`; `claude plugin test plugins/dehydrate`.
