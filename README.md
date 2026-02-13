# Code-agnostic

Centralized hub for LLM coding config: MCP, skills, rules, and agents.

`code-agnostic` is built around one idea: keep your AI coding setup in one place, then sync it into editor/app-specific layouts.

Similar to how OpenCode is provider-agnostic for models, `code-agnostic` aims to be app-agnostic for coding clients. App selection is intentionally limited for now and expanding over time.

## App Feature Matrix

| App | MCP Sync | Skills Sync | Agents Sync | Workspace Sync | Import |
| --- | --- | --- | --- | --- | --- |
| OpenCode / OpenCode Desktop | ✅ | ✅ | ✅ | ✅ | ✅ |
| Cursor IDE | ✅ | ✅ | ✅ | ✅ | ✅ |
| Codex CLI | ✅ | ✅ | ❌ | ✅ | ✅ |

- ✅ supported
- ❌ not supported (Codex does not support agents natively)

### Not Yet Supported

| App | Status |
| --- | --- |
| Claude Code | Planned |
| Windsurf | Not started |

### Limitations

- **Skills/Agents sync** uses symlinks from central `~/.config/code-agnostic/skills/` and `agents/` directories into each app's directory. This means all apps share the same skill/agent content.
- **Codex** does not support agents or commands natively; only MCP and skills are synced.
- **Workspace sync** propagates a root rules file (AGENTS.md/CLAUDE.md) into git repos as symlinked AGENTS.md. This is app-agnostic.
- **Commands sync** (as seen in vsync) is not yet implemented.

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

## Testing

This repo is built around `uv` workflows.

```bash
uv sync --dev
uv run test
```

- `uv run test` is the default test entrypoint and runs `pytest`.
- You can pass any pytest args through it, for example: `uv run test -q tests/e2e`.

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
- `plan`, `apply`, and `status` all accept an optional target argument: `all|opencode|cursor|codex`.
- `plan`/`apply` and `import plan`/`import apply` default to app labels in Source/Target columns; use `-v`/`--verbose` to include Source Path/Target Path columns.
- Workspace actions are app-agnostic building blocks and are included even when targeting a specific app.
- Plan/apply/status behavior is stable in intent, but UX and command shape are still being refined.
- Schema validation is part of tests for generated OpenCode config; Cursor schema coverage is intentionally scoped to fields we manage.

## Import Existing App Config

Use import when you already have MCP/skills/agents configured in a source app and want to migrate into `code-agnostic` as the new source of truth.

Recommended flow:

```bash
code-agnostic import plan codex
code-agnostic import apply codex
```

Useful options:

- Import defaults to all supported sections for the source app.
- `--exclude skills --exclude agents` (repeatable)
- `--include mcp --include skills --include agents` (repeatable, optional narrowing)
- `--on-conflict skip|overwrite|fail` (default: `skip`)
- `--source-root <path>` (import from a custom app root)
- `--follow-symlinks` (off by default)
- `-v, --verbose` (show Source Path/Target Path columns)

Conflict behavior:

- MCP is merged into existing `mcp.base.json`.
- Existing identical MCP entries are no-op.
- Existing conflicting MCP entries are skipped by default (`--on-conflict skip`).
- Skills/agents are additive by name; same-name conflicts are skipped by default, or overwritten with `--on-conflict overwrite`.

After importing, enable target apps and sync outward:

```bash
code-agnostic apps enable cursor
code-agnostic apply cursor
```

## Roadmap

- Add full rules sync: current behavior only propagates root `AGENTS.md` at global/workspace levels; planned direction is a dedicated `rules/` directory (syntax still being investigated).
- Expand MCP sync with broader auth and edge-case coverage.
- Add import flows (for example, importing Claude skills) into `code-agnostic` as an onboarding path.
- Make mappers bidirectional for import/export use cases, with DTO-based transformations.
- Add dynamic inline TUI selectors for tool enable/disable and import selection (similar interaction model to Mole CLI).
- Enable shell auto-complete.
- Explore an optional full-size `textual` TUI mode (`code-agnostic` opens command palette + menus) while keeping one-liner CLI workflows for non-interactive use.
