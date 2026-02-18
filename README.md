# code-agnostic

One config, every AI editor. Keep MCP servers, rules, skills, and agents in a single hub and sync them into editor-specific layouts.

## Why

AI coding tools each want config in a different place and format. When you use more than one, you end up copy-pasting MCP servers, duplicating rules, and manually keeping things in sync. `code-agnostic` removes that overhead: define once, sync everywhere.

## How it works

```
~/.config/code-agnostic/          Your single source of truth
├── config/
│   └── mcp.base.json             MCP servers (editor-agnostic)
├── rules/
│   └── python-style.md           Rules with YAML frontmatter
├── skills/
│   └── code-reviewer/SKILL.md    Skills with YAML frontmatter
└── agents/
    └── architect.md              Agents with YAML frontmatter

        ↓ plan / apply ↓

~/.config/opencode/               Compiled & synced for OpenCode
~/.cursor/                        Compiled & synced for Cursor
~/.codex/                         Compiled & synced for Codex
```

Each resource is cross-compiled to the target editor's native format. Rules become `.mdc` files for Cursor, `AGENTS.md` sections for OpenCode/Codex, etc.

## Install

```bash
uv tool install code-agnostic
```

Or run without installing:

```bash
uvx code-agnostic
```

Or run the published Docker image to isolate filesystem access to mounted paths only:

```bash
docker run --rm -it \
  -v "$(pwd):/workspace" \
  -w /workspace \
  ghcr.io/dhvcc/code-agnostic:latest plan
```

By default, config stays inside the container at `/root/.config` unless you mount a host path.

## Quick start

```bash
# Import existing config from an editor you already use
code-agnostic import plan -a codex
code-agnostic import apply -a codex

# Enable target editors
code-agnostic apps enable -a cursor
code-agnostic apps enable -a opencode

# Preview and apply
code-agnostic plan
code-agnostic apply
```

## Editor compatibility

| Feature | OpenCode | Cursor | Codex |
|---------|:--------:|:------:|:-----:|
| MCP sync | yes | yes | yes |
| Rules sync (cross-compiled) | yes | yes | yes |
| Skills sync | yes | yes | yes |
| Agents sync | yes | yes | -- |
| Workspace propagation | yes | -- | yes |
| Import from | yes | yes | yes |
| Interactive import (TUI) | yes | yes | yes |

Codex does not support agents natively. Workspace propagation is intentionally disabled for Cursor to avoid duplicate MCP initialization in multi-root workspaces: https://forum.cursor.com/t/mcp-multi-root-workspace-causes-duplicate-mcp-server-initialization-4x-createclient-actions/144003

## Features

### Sync engine

Plan-then-apply workflow. Preview every change before it touches disk.

```bash
code-agnostic plan -a cursor        # dry-run for one editor
code-agnostic plan                   # dry-run for all
code-agnostic apply                  # apply changes
code-agnostic status                 # check drift
```

### MCP management

Add, remove, and list MCP servers without editing JSON by hand.

```bash
code-agnostic mcp add github --command npx --args @modelcontextprotocol/server-github --env GITHUB_TOKEN
code-agnostic mcp list
code-agnostic mcp remove github
```

Env vars without a value (`--env GITHUB_TOKEN`) are stored as `${GITHUB_TOKEN}` references.

### Rules with metadata

Rules live in `rules/` as markdown files with optional YAML frontmatter:

```markdown
---
description: "Python coding standards"
globs: ["*.py"]
always_apply: false
---

Always use type hints. Prefer dataclasses over dicts.
```

Cross-compiled per editor: Cursor gets `.mdc` files with native frontmatter, OpenCode/Codex get `AGENTS.md` sections.

```bash
code-agnostic rules list
code-agnostic rules remove --name python-style
```

### Skills and agents

Canonical YAML frontmatter format, cross-compiled per editor.

```bash
code-agnostic skills list
code-agnostic agents list
```

### Workspaces

Register workspace directories. Repos inside them get rules, skills, and agents propagated as symlinks for OpenCode and Codex.

`.cursor` workspace propagation is intentionally disabled to avoid duplicate MCP initialization when opening multi-root workspaces in Cursor (related issue: https://forum.cursor.com/t/mcp-multi-root-workspace-causes-duplicate-mcp-server-initialization-4x-createclient-actions/144003).

```bash
code-agnostic workspaces add --name myproject --path ~/code/myproject
code-agnostic workspaces list
```

### Git exclude

Prevent synced paths from showing up in `git status`. Managed per-workspace with customizable patterns.

```bash
code-agnostic workspaces git-exclude                            # all workspaces
code-agnostic workspaces git-exclude -w myproject               # one workspace
code-agnostic workspaces exclude-add --pattern "*.generated" -w myproject
code-agnostic workspaces exclude-list -w myproject
```

### Import

Migrate existing config from any supported editor into the hub.

```bash
code-agnostic import plan -a codex
code-agnostic import apply -a codex
code-agnostic import apply -a cursor --include mcp --on-conflict overwrite
code-agnostic import plan -a codex -i    # interactive TUI picker
```

### CLI conventions

All commands use named flags (`-a`, `-w`, `-v`). Singular aliases work too: `app` = `apps`, `workspace` = `workspaces`.

## Roadmap

- [x] Plan/apply/status sync engine
- [x] MCP server sync across editors
- [x] Skills and agents sync (symlink-based)
- [x] Workspace propagation into git repos
- [x] Import from existing editor configs
- [x] Consistent CLI with named flags and aliases
- [x] MCP add/remove/list commands
- [x] Rules system with YAML frontmatter and per-editor compilation
- [x] Cross-compilation for skills and agents
- [x] Per-workspace git-exclude customization
- [x] Interactive TUI for import selection
- [ ] Claude Code support
- [ ] `rules add` / `skills add` / `agents add` commands (open `$EDITOR` with template)
- [ ] Planner integration for cross-compiled skills and agents
- [ ] Shell auto-complete
- [ ] Full TUI mode (command palette + menus)

## Testing

```bash
uv sync --dev
uv run test
```
