# MCP compiler contract

Canonical MCP source is moving toward `config/mcp.base.yaml`. Today the CLI
also supports legacy/common `config/mcp.base.json`, and import/MCP management
commands still write that JSON source.

Published schemas:

- canonical YAML bundle: `https://raw.githubusercontent.com/dhvcc/code-agnostic/main/code_agnostic/spec/schemas/mcp.v1.schema.json`
- legacy/common JSON source: `https://raw.githubusercontent.com/dhvcc/code-agnostic/main/code_agnostic/spec/schemas/mcp.base.schema.json`

Both formats support an optional top-level `$schema` property for editor validation.

Top-level fields for v1:

- `spec_version`
- `mcp_servers`

Per-server fields for v1:

- `type`
- `command`
- `args`
- `cwd`
- `url`
- `timeout`
- `headers`
- `env`
- `auth.client_id`
- `auth.client_secret`
- `auth.scopes`
- `auth.token_endpoint`

Unknown keys fail validation.

Legacy/common `mcp.base.json` server keys can target app compilation:

- `@opencode-playwright` compiles only for OpenCode as `playwright`
- `!codex-playwright` compiles for every target except Codex as `playwright`
- `@claude-playwright` compiles only for Claude Code as `playwright`
- unprefixed server keys compile for every target

Target markers are recognized only for known targetable app ids.

## Capability matrix

| Property | Compiler | Cursor | Codex | OpenCode | Claude Code |
| --- | --- | --- | --- | --- | --- |
| `type` | supported | compiled | compiled | compiled | compiled |
| `command` | supported | native | native | native | native |
| `args` | supported | native | native | native | native |
| `cwd` | supported for local servers | ignored | native | native for local servers | native |
| `url` | supported | native | native | native | native |
| `headers` | supported | native | compiled | native | native |
| `env` | supported | native | compiled | native for local servers; rejected for remote servers | native |
| `auth.client_id` | supported | compiled | compiled | compiled | ignored |
| `auth.client_secret` | supported | compiled | compiled | compiled | ignored |
| `auth.scopes` | supported | compiled | compiled | compiled | ignored |
| `auth.token_endpoint` | supported | compiled | compiled | compiled | ignored |
| `timeout` | supported | native | compiled to `tool_timeout_sec` | native | native |

## Notes

- If a property is not in this table, it is not part of the compiler contract.
- Target-specific MCP extensions belong under `x-*` only after a concrete use case and test exist.
- Canonical `timeout` is expressed in milliseconds.
- Canonical `cwd` is expressed as a string and applies only to local/stdio MCP
  servers. It is currently omitted for Cursor because the official Cursor MCP
  docs checked in this run document `envFile` but did not establish `cwd`.
- OpenCode's current schema allows `environment` only on local MCP servers.
  Remote OpenCode MCP servers can carry `headers` and OAuth config, but not
  per-server environment variables.
- OpenCode project/workspace MCP config is generated as project-root
  `opencode.json`. OpenCode skills and agents remain under `.opencode/`.
- Claude workspace MCP is written into `~/.claude.json` under
  `projects[absolute_repo_path].mcpServers`; v1 does not generate committed
  `.mcp.json`.
