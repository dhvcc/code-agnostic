# Code-agnostic

Centralized hub for LLM coding config: MCP, skills, rules, and agents.

`code-agnostic` is built around one idea: keep your AI coding setup in one place, then sync it into editor/app-specific layouts.

Similar to how OpenCode is provider-agnostic for models, `code-agnostic` aims to be app-agnostic for coding clients. App selection is intentionally limited for now and expanding over time.

## App Feature Matrix

| App | MCP Sync | Skills Sync | Agents Sync | Rules Sync | Workspace Sync |
| --- | --- | --- | --- | --- | --- |
| OpenCode / OpenCode Desktop | ✅ | ✅ | ✅ | ✅ | ✅ |
| Cursor IDE | ✅ | ❌ | ❌ | ❌ | ❌ |
| Claude Code | ❌ | ❌ | ❌ | ❌ | ❌ |
| Codex CLI | ✅ | ❌ | ❌ | ❌ | ❌ |
| Cursor CLI | ❌ | ❌ | ❌ | ❌ | ❌ |

- ✅ supported
- ❌ not supported yet

## Install

```bash
uv tool install code-agnostic
```

Or run without installing:

```bash
uvx code-agnostic
```

## Project Status

- WIP: CLI surface is evolving quickly between iterations.
- WIP: file layout and config schemas are not finalized yet.
- Prefer using current help output for exact command behavior.

## Source Of Truth

Shared config root defaults to `~/.config/code-agnostic`.

Expected layout:

- `~/.config/code-agnostic/config/mcp.base.json`
- `~/.config/code-agnostic/config/opencode.base.json`
- `~/.config/code-agnostic/skills/<skill>/SKILL.md`
- `~/.config/code-agnostic/agents/*`

## Synced Targets (Current)

- `~/.config/opencode/opencode.json`
- `~/.config/opencode/skills/*`
- `~/.config/opencode/agents/*` (or `~/.config/opencode/agent/*` if that directory already exists)

Cursor and Codex MCP payload sync are gated behind app toggles.

## Notes

- App sync is opt-in: apps start disabled by default to reduce accidental data changes.
- OpenCode sync normalizes MCP entries from `mcp.base.json` into OpenCode-compatible `mcp` config.
- Workspace sync propagates a root rules file (`AGENTS.md`/`CLAUDE.md`) into git repos as symlinked `AGENTS.md`.
- Plan/apply/status behavior is stable in intent, but UX and command shape are still being refined.
- Schema validation is part of tests for generated OpenCode config; Cursor schema coverage is intentionally scoped to fields we manage.

## Roadmap

- Add full rules sync: current behavior only propagates root `AGENTS.md` at global/workspace levels; planned direction is a dedicated `rules/` directory (syntax still being investigated).
- Expand MCP sync with broader auth and edge-case coverage.
- Add import flows (for example, importing Claude skills) into `code-agnostic` as an onboarding path.
- Make mappers bidirectional for import/export use cases, with DTO-based transformations.
- Add dynamic inline TUI selectors for tool enable/disable and import selection (similar interaction model to Mole CLI).
- Enable shell auto-complete.
- Explore an optional full-size `textual` TUI mode (`code-agnostic` opens command palette + menus) while keeping one-liner CLI workflows for non-interactive use.
