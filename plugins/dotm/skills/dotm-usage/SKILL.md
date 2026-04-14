---
name: dotm-usage
description: Use when the user asks to install, add, remove, or upgrade anything at user level on macOS — brew formulae, brew casks, brew taps, Mac App Store apps, npm/pip/cargo/go/gem/uv globals, gh extensions, Claude Code plugins/skills/agents, MCP servers, or manual edits to ~/.zshrc, ~/.config/*, or ~/.local/bin/. Also triggers on phrases like "install X", "brew install", "add to my path", "npm install -g", "pip install --user", "set up on new machine", "sync my dotfiles", "why is X missing after reinstall". Routes capture-worthy installs through dotm so they survive reinstall and propagate across machines.
---

# dotm Usage

Routing trigger that teaches Claude Code to capture user-level installs through dotm instead of running raw `brew install` / `npm -g` / `mas install` / direct `~/.zshrc` edits. The procedural content lives in the `/dotm:*` commands (stowed from the `getfatday/dotfiles` repo via the dotm module). This skill is the discovery layer that points at them.

## The contract

Nothing installed at user level is real until it's captured in a dotm module. Raw installs and direct edits are drift — they live on one machine, disappear on reinstall, and don't propagate. Before running any install command, route it through the `/dotm:*` commands below.

## Routing table

| User intent | Command to invoke |
|---|---|
| Install a brew formula, brew cask, or MAS app | `/dotm:install <package>` — searches brew/mas, finds or creates the right module, verifies |
| Scaffold a brand-new module from scratch | `/dotm:create <description>` — proposal phase + approval, then creates |
| Multi-file or non-trivial dotfiles change (edit source files, not symlinks) | `/dotm:plan <task>` — full orchestration including file edits, verification, push |
| Check current drift before deciding | `/dotm:analyze` — structured drift report with priority scoring |
| Pull latest + apply across this machine | `/dotm:sync` |
| System health check | `/dotm:status` |

When in doubt about which command fits, start with `/dotm:analyze` to see current state, then pick.

## Known gaps — log, don't fake

dotm doesn't yet model every install pathway. For these, **do not pretend to capture**. Tell the user what isn't being captured, log the gap (for example in the user's `Projects/Dotfiles/` note if it exists), and then proceed with the raw install.

- **Brew taps** (`brew tap user/repo`) — module schema has no tap field. Use `brew tap` directly; log it.
- **Language globals** — `npm install -g`, `pip install --user`, `cargo install`, `go install`, `gem install`, `uv tool install`. Prefer pinning via `.tool-versions` or a repo-local dependency first. If a global install is unavoidable, run it and log it.
- **Claude Code plugins, skills, agents, commands** beyond `~/.config/claude/`. The `claude` module currently only owns `.config/claude/`. Extending to cover `~/.claude/` is a future project.
- **gh extensions** (`gh extension install`) — unmodeled. Install and log.
- **MCP servers** in `~/.claude/settings.json` — unmodeled separately from the `claude` module.

MAS apps specifically are handled by `/dotm:install --mas <id>` for single-app captures; bulk Xcode/Okta/etc. setup deserves its own session.

## Anti-patterns

- **Don't run `brew install X` directly.** Use `/dotm:install X` so the package lands in a module.
- **Don't edit `~/.zshrc` (or any file under `~/.config/`) directly.** Those are symlinks into `modules/*/files/`. Writing to the live symlink modifies the file in the repo but bypasses the module's merge strategy for `mergeable_files` and can corrupt multi-module shell configs. Edit the source file in the module, or use `/dotm:plan` for anything non-trivial.
- **Don't skip `dotm push` after a capture.** A module edit that only lives locally defeats the point — other machines won't get it, and a fresh machine definitely won't.
- **Don't pad the managed/unmanaged ratio by capturing noise.** Transitive brew dependencies aren't worth capturing. Only capture what you'd notice if it disappeared.

## When drift is acceptable

Session-scoped experiments are fine. The test: **"if this disappears on reinstall, will I notice?"** If no — it's a one-off try of a tool you might not keep, a temporary debugging aid, a package you're about to uninstall anyway — don't bother with dotm. Capture only what you want to survive.

## References

- `/dotm:install`, `/dotm:create`, `/dotm:plan`, `/dotm:analyze`, `/dotm:sync`, `/dotm:status`
- dotm CLI source: `~/src/dotfiles/modules/dotm/src/dotm/`
- dotm commands source: `~/src/dotfiles/modules/dotm/files/.claude/commands/dotm/`
- User's dotfiles architecture review (if vault available): `Projects/Dotfiles/Architecture Review.md`
