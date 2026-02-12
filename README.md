# Code-agnostic

Centralized hub for LLM coding config: MCP, skills, rules, and agents.

`code-agnostic` is built around one idea: keep your AI coding setup in one place, then sync it into editor/app-specific layouts.

Similar to how OpenCode is provider-agnostic for models, `code-agnostic` aims to be app-agnostic for coding clients. App selection is intentionally limited for now and expanding over time.

## App Feature Matrix

| App | MCP Sync | Skills Sync | Agents Sync | Rules Sync | Workspace Sync |
| --- | --- | --- | --- | --- | --- |
| OpenCode / OpenCode Desktop | ✅ | ✅ | ✅ | ✅ | ✅ |
| Cursor IDE | ⚠️ | ❌ | ❌ | ❌ | ❌ |
| Claude Code | ❌ | ❌ | ❌ | ❌ | ❌ |
| Codex CLI | ❌ | ❌ | ❌ | ❌ | ❌ |
| Cursor CLI | ❌ | ❌ | ❌ | ❌ | ❌ |

- ✅ supported
- ⚠️ partial support (Cursor MCP work is planned, including limited tool enable/disable compatibility)
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

Cursor paths and payloads are intentionally gated behind app toggles while support is being finalized.

## Notes

- App sync is opt-in: apps start disabled by default to reduce accidental data changes.
- OpenCode sync normalizes MCP entries from `mcp.base.json` into OpenCode-compatible `mcp` config.
- Workspace sync propagates a root rules file (`AGENTS.md`/`CLAUDE.md`) into git repos as symlinked `AGENTS.md`.
- Plan/apply/status behavior is stable in intent, but UX and command shape are still being refined.
- Schema validation is part of tests for generated OpenCode config; Cursor schema coverage is intentionally scoped to fields we manage.
