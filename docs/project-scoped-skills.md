# Project-Scoped Skill Installs

This documents the first implementation slice for managed project-local skills.

## Goal

Let a user run `code-agnostic` from inside one project and install a skill for
that project without bypassing the hub source of truth. The generated app files
should still be produced by the normal `plan` / `apply` flow.

## Source Model

Projects are registered under `~/.config/code-agnostic/config/projects.json`.
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

Project-aware `plan`, `apply`, and `status` support project-local skills.

`skills install` supports local skill directories:

```bash
code-agnostic skills install ./my-skill --project <name>
```

Explicit flags choose the install scope:

```bash
code-agnostic skills install ./my-skill --global
code-agnostic skills install ./my-skill --workspace <name>
code-agnostic skills install ./my-skill --project <name>
```

Without an explicit scope, install chooses the containing registered project
when there is exactly one match, otherwise the containing workspace when there
is exactly one match. When there is no unique scope, pass `--global`,
`--project`, or `--workspace`.

## Safety

`skills install` should write only to code-agnostic source first. It must not let
third-party installers write directly into `.agents`, `.cursor`, `.opencode`, or
`.claude` target directories as the managed source of truth.

`plan` should preview the generated repo-local outputs before any target files
are written. `apply` should keep using managed path ownership and conflict
detection for generated files.

## Out of Scope

- MCP install/add flows.
- Remote skills.sh/GitHub package references.
- Interactive scope prompts.
- A general plugin marketplace.
- Replacing workspaces. Workspaces remain the multi-repo propagation model.
