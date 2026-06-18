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
- `envFile`
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
- `@copilot-playwright` compiles only for GitHub Copilot as `playwright`
- unprefixed server keys compile for every target

Target markers are recognized only for known targetable app ids.

## Capability matrix

| Property | Compiler | Cursor | Codex | OpenCode | Claude Code | GitHub Copilot |
| --- | --- | --- | --- | --- | --- | --- |
| `type` | supported | compiled | compiled | compiled | compiled | compiled to `local`/`http` |
| `command` | supported | native | native | native | native | native |
| `args` | supported | native | native | native | native | native |
| `cwd` | supported for local servers | ignored | native | native for local servers | native | ignored |
| `envFile` | supported for local servers | native | ignored | ignored | ignored | ignored |
| `url` | supported | native | native | native | native | native |
| `headers` | supported | native | compiled | native | native | native |
| `env` | supported | native | compiled | native for local servers; rejected for remote servers | native | native |
| `auth.client_id` | supported | compiled | compiled | compiled | ignored | rejected |
| `auth.client_secret` | supported | compiled | compiled | compiled | ignored | rejected |
| `auth.scopes` | supported | compiled | compiled | compiled | ignored | rejected |
| `auth.token_endpoint` | supported | compiled | compiled | compiled | ignored | rejected |
| `timeout` | supported | native | compiled to `tool_timeout_sec` | native | native | native |

## Notes

- If a property is not in this table, it is not part of the compiler contract.
- Target-specific MCP extensions belong under `x-*` only after a concrete use case and test exist.
- Canonical `timeout` is expressed in milliseconds.
- Canonical `cwd` is expressed as a string and applies only to local/stdio MCP
  servers. It is currently omitted for Cursor because the official Cursor MCP
  docs checked in this run document `envFile` but did not establish `cwd`.
- Canonical `envFile` is expressed as a string and applies only to local/stdio
  MCP servers. It is emitted only for Cursor, whose official MCP docs document
  `envFile` for STDIO servers and explicitly exclude it for remote servers.
- Codex `env_vars` string entries and object entries with `source = "local"`
  import as canonical environment references. Codex `env_vars` entries with
  `source = "remote"` are rejected during import because the canonical MCP
  contract does not represent Codex remote-executor environment sourcing.
- OpenCode's current schema allows `environment` only on local MCP servers.
  Remote OpenCode MCP servers can carry `headers` and OAuth config, but not
  per-server environment variables.
- OpenCode project/workspace MCP config is generated as project-root
  `opencode.json`. OpenCode skills and agents remain under `.opencode/`.
- Claude workspace MCP is written into `~/.claude.json` under
  `projects[absolute_repo_path].mcpServers`; v1 does not generate committed
  `.mcp.json`.
- GitHub Copilot user MCP is written to `~/.copilot/mcp-config.json` (or
  `$COPILOT_HOME/mcp-config.json`). Workspace/project MCP is written to
  repo-shared `.github/mcp.json`. v1 does not generate `.mcp.json`.
- GitHub Copilot output always emits `tools: ["*"]` for compiled MCP servers.
  Canonical OAuth servers are rejected because current Copilot repository MCP
  docs do not support OAuth remote servers.
