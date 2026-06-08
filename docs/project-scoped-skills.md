# Project-Scoped Skill Installs

This is the first implementation slice for managed project-local skills. It is a
proposal, not current CLI behavior.

## Goal

Let a user run `code-agnostic` from inside one project and install a skill for
that project without bypassing the hub source of truth. The generated app files
should still be produced by the normal `plan` / `apply` flow.

## Source Model

Add a project registry under `~/.config/code-agnostic/config/projects.json`.
Each project entry should have:

- `name`
- `path`

Project source lives under `~/.config/code-agnostic/projects/<name>/`. The first
slice only needs `skills/`, plus provenance stored outside strict skill metadata
so existing schema validation remains deterministic.

Scopes should be explicit:

- global: `~/.config/code-agnostic/`
- workspace: `~/.config/code-agnostic/workspaces/<name>/`
- project: `~/.config/code-agnostic/projects/<name>/`

## CLI Flow

Add project-aware `plan`, `apply`, and `status` for project-local skills.

Add `skills install` for local directories first:

```bash
code-agnostic skills install ./my-skill --project <name>
```

When the scope is ambiguous, prompt for global, current project, or containing
workspace. Explicit flags should skip prompts:

```bash
code-agnostic skills install ./my-skill --global
code-agnostic skills install ./my-skill --workspace <name>
code-agnostic skills install ./my-skill --project <name>
```

If the current directory is not registered and no explicit scope was provided,
offer to register it as a project before installing.

## Safety

`skills install` should write only to code-agnostic source first. It must not let
third-party installers write directly into `.agents`, `.cursor`, `.opencode`, or
`.claude` target directories as the managed source of truth.

`plan` should preview the generated repo-local outputs before any target files
are written. `apply` should keep using managed path ownership and conflict
detection for generated files.

## Out of Scope

- MCP install/add flows.
- A general plugin marketplace.
- Replacing workspaces. Workspaces remain the multi-repo propagation model.
