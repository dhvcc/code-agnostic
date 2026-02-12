# llm-sync

OpenCode-first sync for shared LLM configuration.

## Install

```bash
uv tool install llm-sync
```


## Commands

```bash
llm-sync plan
llm-sync apply             # sync all targets
llm-sync apply opencode    # sync OpenCode only
llm-sync status
llm-sync workspaces add workspace-example ~/microservice-workspace
llm-sync workspaces list
llm-sync workspaces remove workspace-example
```

Or run directly from this repo:

```bash
python3 -m llm_sync plan
python3 -m llm_sync apply
```

## Source Of Truth

Shared config root defaults to `~/.config/llm-sync`.

Expected layout:

- `~/.config/llm-sync/config/mcp.base.json`
- `~/.config/llm-sync/config/opencode.base.json`
- `~/.config/llm-sync/skills/<skill>/SKILL.md`
- `~/.config/llm-sync/agents/*`

## Targets (OpenCode Only)

- `~/.config/opencode/opencode.json`
- `~/.config/opencode/skills/*`
- `~/.config/opencode/agents/*` (or `~/.config/opencode/agent/*` if that directory already exists)

## Notes

- Cursor sync is intentionally disabled in this version.
- MCP entries in `mcp.base.json` are normalized to OpenCode schema (`type: remote/local`, command arrays).
- `plan` is side-effect free; writes only happen in `apply`.
- Workspace sync propagates a root rules file (`AGENTS.md`/`CLAUDE.md`) to repo subdirectories as symlinked `AGENTS.md`.
- `status` prints a high-level editor sync view plus a workspace repo tree (git repos only).
