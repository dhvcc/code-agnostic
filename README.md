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
│   └── python-style/
│       ├── meta.yaml             Rule metadata
│       └── prompt.md             Rule instructions
├── skills/
│   └── code-reviewer/
│       ├── meta.yaml             Skill metadata
│       └── prompt.md             Skill instructions
└── agents/
    └── architect/
        ├── meta.yaml             Agent metadata
        └── prompt.md             Agent instructions

        ↓ plan / apply ↓

~/.config/opencode/               Compiled & synced for OpenCode
~/.cursor/                        Compiled & synced for Cursor
~/.codex/                         Compiled & synced for Codex (or CODEX_HOME)
~/.claude.json and ~/.claude/      Compiled & synced for Claude Code
```

Each resource is cross-compiled to the target editor's native format. Rules become `.mdc` files for Cursor, `AGENTS.md` sections for OpenCode/Codex, and `CLAUDE.local.md` memory for Claude Code.

Legacy single-file rules, `skills/<name>/SKILL.md`, and markdown agents are still supported for migration, but bundle directories are the preferred source format for new config.

Today the implementation is still mixed: some assets are compiled and some are symlinked. The active migration plan is to move to generated outputs everywhere with a strict compiler contract instead of implicit per-app behavior.

## Scope model

`code-agnostic` has three managed source scopes:

- global source config under `~/.config/code-agnostic/`, synced to enabled
  user-level app config;
- workspace source config under `~/.config/code-agnostic/workspaces/<name>/`,
  propagated into repos inside a registered workspace;
- project source config under `~/.config/code-agnostic/projects/<name>/`,
  synced to exactly one registered project directory.

Workspace sync may generate repo-local outputs, but those outputs are not
source. Project-local skill folders generated inside a repo, such as
`.agents/skills` or `.opencode/skills`, are also generated outputs; install
skills into managed project source first, then run `plan` / `apply`.

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
code-agnostic apps enable -a claude

# Preview and apply
code-agnostic validate
code-agnostic plan
code-agnostic apply
```

## Editor compatibility

| Feature | OpenCode | Cursor | Codex | Claude Code |
|---------|:--------:|:------:|:-----:|:-----------:|
| MCP sync | yes | yes | yes | yes |
| Rules sync (cross-compiled) | yes | yes | yes | yes |
| Skills sync | yes | yes | yes | yes |
| Agents sync | yes | yes | yes | yes |
| Workspace root `AGENTS.md` link | yes | yes | yes | yes |
| Native repo config include for workspace `AGENTS.md` | yes | -- | -- | -- |
| Repo/subdir gets shared workspace instructions today | yes | -- | yes | yes |
| Nested `AGENTS.md` discovery | -- | yes | yes | -- |
| Workspace propagation | yes | yes | yes | yes |
| Import from | yes | yes | yes | yes |
| Interactive import (TUI) | yes | yes | yes | yes |

`yes` means the resource type is synced for that editor. Some metadata is still
target-specific or lossy; run `code-agnostic explain-lossiness` to see fields
that are omitted or rejected for a selected target.

Cursor workspace propagation writes repo-local MCP, skills, and agents when those resources exist in the workspace source config.

OpenCode workspace configs write project-root `opencode.json` files that include the shared workspace `AGENTS.md` natively via `instructions`, so repos under the workspace get both repo-local and shared workspace instructions. Codex repos receive workspace instructions through a generated `AGENTS.override.md`, which is added to each repo's `.git/info/exclude`. Claude Code receives workspace instructions through generated `CLAUDE.local.md` files, never by editing committed `CLAUDE.md`.

Cursor documents `AGENTS.md` support in project roots and subdirectories. `code-agnostic` does not copy or link the shared workspace `AGENTS.md` into child repos; Cursor will load `AGENTS.md` files that already exist in the opened project. Codex documents nested `AGENTS.md` discovery, but not a native config include for an extra workspace file.

## Features

### Sync engine

Plan-then-apply workflow. Preview every change before it touches disk.

```bash
code-agnostic validate              # check canonical source files
code-agnostic plan -a cursor        # dry-run for one editor
code-agnostic plan                   # dry-run for all
code-agnostic apply                  # apply changes for all enabled editors
code-agnostic status                 # check drift and disabled app states
code-agnostic explain-lossiness      # show fields omitted or rejected per editor
```

Bare `plan` and `apply` target every enabled editor; bare `status` also shows
disabled app states. Use `-a codex`, `-a cursor`, `-a opencode`, or `-a claude`
when you want one editor at a time.

If managed outputs need repair after an apply, restore the active synced revision:

```bash
code-agnostic restore
code-agnostic restore -w myproject
```

### MCP management

Add, remove, and list MCP servers without editing JSON by hand.

```bash
code-agnostic mcp add github --command npx --args @modelcontextprotocol/server-github --env GITHUB_TOKEN
code-agnostic mcp add local-docs --command uvx --args docs-mcp --cwd ~/code/docs
code-agnostic mcp list
code-agnostic mcp remove github
```

Env vars without a value (`--env GITHUB_TOKEN`) are stored as `${GITHUB_TOKEN}` references.

### Rules with metadata

New rules should use bundle directories with schema-validated metadata and a
separate prompt body:

```text
rules/python-style/
├── meta.yaml
└── prompt.md
```

```yaml
# rules/python-style/meta.yaml
spec_version: v1
kind: rule
description: "Python coding standards"
globs: ["*.py"]
always_apply: false
```

```markdown
<!-- rules/python-style/prompt.md -->
Always use type hints. Prefer dataclasses over dicts.
```

Cross-compiled per editor: Cursor gets `.mdc` files with native frontmatter, OpenCode/Codex get `AGENTS.md` sections.
Legacy single-file rule markdown with YAML frontmatter remains supported for migration.

```bash
code-agnostic rules list
code-agnostic rules remove --name python-style
```

### Skills and agents

Use bundle directories for new skills and agents, then let `code-agnostic`
cross-compile them per editor. Install or edit skills in the `code-agnostic`
source of truth, then run `plan` / `apply`; do not hand-copy generated skills
into `.codex`, `.cursor`, `.agents`, or OpenCode directories.

```bash
code-agnostic skills list
code-agnostic agents list
```

Install copies a skill into managed source first for the chosen scope. Run
`plan` / `apply` afterward to generate target app files.

```bash
code-agnostic skills install ./my-skill --global
code-agnostic skills install ./my-skill --workspace myworkspace
code-agnostic projects add --name myproject --path .
code-agnostic skills install ./my-skill --project myproject
code-agnostic plan
code-agnostic apply
```

Remote GitHub-style sources are also supported:

```bash
code-agnostic skills install owner/repo --global
code-agnostic skills install https://github.com/owner/repo --workspace myworkspace
code-agnostic skills install https://github.com/owner/repo/tree/main/path/to/skills --skill reviewer --skill triage --project myproject
```

Remote sources may be an `owner/repo` shorthand, a GitHub repository URL, or a
GitHub tree URL. When a remote source contains multiple skill candidates,
repeat `--skill` to select the intended skills; otherwise install fails instead
of guessing. Remote installs still copy the selected skill into the
`code-agnostic` source of truth before any generated target outputs are written.

Global skills live under `~/.config/code-agnostic/skills`. Workspace-local
skills live under `~/.config/code-agnostic/workspaces/<name>/skills` and can be
inspected with `code-agnostic skills list -w <name>`. Project-local skills live
under `~/.config/code-agnostic/projects/<name>/skills` and are generated into
the registered project directory by `plan` / `apply`. Codex generated skill
outputs are written to `~/.agents/skills`, while Codex agents and config remain
under `CODEX_HOME` when set, defaulting to `~/.codex`. Claude Code generated
skills and agents are written under `~/.claude/skills` and `~/.claude/agents`,
with workspace/project copies under repo-local `.claude/skills` and
`.claude/agents`.

If a target app discovers user-created repo-local skill folders such as `.agents/skills`, `.opencode/skills`, or `.claude/skills`, treat those as unmanaged app inputs unless they were generated from `code-agnostic` project source. Workspace and project sync write only the exact generated paths recorded in their `.sync-state.json` files.

Planned convenience command:

```bash
code-agnostic skills install ./my-skill --apply
```

That command should copy the skill into the source of truth and then run the normal compiler/apply flow.
See [docs/project-scoped-skills.md](docs/project-scoped-skills.md) for the
first implementation slice.

### Workspaces

Register workspace directories. Workspace rules are compiled into a canonical `AGENTS.md` at the workspace root. Repos keep their own repo-specific `AGENTS.md`; Codex receives the workspace rules through generated, git-excluded `AGENTS.override.md` files, while OpenCode workspace configs write project-root `opencode.json` files that reference the shared workspace file through `instructions`. Claude receives generated `CLAUDE.local.md` files and project MCP entries in `~/.claude.json["projects"][absolute_repo_path]["mcpServers"]`. Workspace source config, skills, and agents are propagated into repo-local generated paths for OpenCode, Cursor, Codex, and Claude; user-created target app skill folders remain unmanaged unless they were generated from managed source.

Cursor propagation intentionally stays to repo-local MCP, skills, and agents; it does not copy the shared workspace `AGENTS.md` into child repos.

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
code-agnostic import plan -a claude
code-agnostic import apply -a cursor --include mcp --on-conflict overwrite
code-agnostic import plan -a codex -i    # interactive TUI picker
```

`import plan` previews what will be copied into the hub; `import apply` writes
only the selected sections. Conflicts are skipped by default, so rerun with
`--on-conflict overwrite` only after reviewing the preview. Use `--include`,
`--exclude`, `--source-root`, and `--follow-symlinks` to narrow what gets
imported. `--source-root` means the source app config root to read from, not the
`code-agnostic` hub root.

### CLI conventions

All commands use named flags (`-a`, `-w`, `-v`). Singular aliases work too: `app` = `apps`, `workspace` = `workspaces`.

## Compiler docs

The compiler migration is documented in:

- [docs/compiler/overview.md](docs/compiler/overview.md)
- [docs/compiler/skills.md](docs/compiler/skills.md)
- [docs/compiler/agents.md](docs/compiler/agents.md)
- [docs/compiler/rules.md](docs/compiler/rules.md)
- [docs/compiler/mcp.md](docs/compiler/mcp.md)
- [docs/compiler/lossiness.md](docs/compiler/lossiness.md)

## Roadmap

- [x] Plan/apply/status sync engine
- [x] MCP server sync across editors
- [x] Skills and agents sync across editors
- [x] Workspace propagation into git repos
- [x] Import from existing editor configs
- [x] Consistent CLI with named flags and aliases
- [x] MCP add/remove/list commands
- [x] Rules system with YAML frontmatter and per-editor compilation
- [x] Cross-compilation for skills and agents
- [x] Planner integration for cross-compiled skills and agents
- [x] Per-workspace git-exclude customization
- [x] Interactive TUI for import selection
- [x] Claude Code support
- [x] Project-scoped skill installs and sync
- [ ] `rules add` / `skills add` / `agents add` commands (open `$EDITOR` with template)
- [ ] Shell auto-complete
- [ ] Full TUI mode (command palette + menus)

## Testing

```bash
uv sync --dev
uv run pytest
```

Before pushing release-prep work, run the supported Python matrix locally. Tox
delegates each environment to `uv run --python`, so `uv` can provide the
requested interpreter when it is not already installed:

```bash
uvx tox run -p auto
uvx tox run -e uv310 -- tests/test_version.py -q
```

For a hermetic Linux matrix that does not depend on locally installed Python
versions, run the Docker matrix:

```bash
./scripts/run-docker-matrix.sh
./scripts/run-docker-matrix.sh tests/test_version.py -q
```

Limit the Docker matrix while iterating:

```bash
PYTHON_VERSIONS="3.10 3.14" ./scripts/run-docker-matrix.sh tests/test_version.py -q
```

The release gate still requires GitHub Actions to pass because the published
workflow is the source of truth for OS coverage across Ubuntu, macOS, and
Windows on every supported Python version.

Real app-ingestion E2E is gated because it requires installed target CLIs and
uses each tool's own introspection surface:

```bash
CODE_AGNOSTIC_REAL_APP_E2E=1 uv run pytest tests/e2e/test_real_app_ingestion_e2e.py -q
CODE_AGNOSTIC_REAL_APP_E2E=1 CODE_AGNOSTIC_REAL_APP_TARGETS=codex,opencode,claude uv run pytest tests/e2e/test_real_app_ingestion_e2e.py -q
```
