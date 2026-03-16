# getfatday/skills

Personal skills and CLIs for Claude Code plugins. Public repo, no secrets.

## Structure

- `clis/` — Python CLI packages (uv workspace members). Each CLI is a standalone tool that a plugin can depend on.
- `plugins/` — Claude Code plugins (agents, commands, skills). Each plugin is self-contained with a `.claude-plugin/plugin.json` manifest.
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

## CLIs

### monarch-cli
Personal finance CLI wrapping the Monarch Money API.
Command: `gfd-monarch`
