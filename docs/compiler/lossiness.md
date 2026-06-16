# Lossiness policy

The compiler must make cross-app lossiness explicit.

## Rules

- unknown properties are validation errors
- supported-but-unrepresentable properties are target diagnostics
- required semantics that cannot be preserved are target errors
- optional semantics that cannot be preserved may be ignored only with an explicit warning

## Examples

- Rule `globs` compiling to `AGENTS.md` is lossy because Codex and OpenCode do not model that field in the same way as Cursor.
- Agent `sandbox_mode` is Codex-oriented today; other targets should not silently invent an equivalent.
- MCP `timeout` is no longer speculative: it is part of the canonical contract and maps to app-native timeout fields.
- MCP `env` is rejected for OpenCode remote MCP servers because current
  OpenCode schema only supports `environment` on local MCP servers.
- MCP `envFile` is compiled only for Cursor local MCP servers. It is lossy for
  Codex, OpenCode, and Claude Code because current target configs do not model
  a native environment-file field.
- Codex MCP `env_vars` entries with `source = "remote"` are rejected on import
  because preserving the remote-executor source would require a Codex-specific
  canonical extension that does not exist in v1.
- Skill `tools.*` is lossy for Cursor, Codex, OpenCode, and Claude Code skills because
  current target `SKILL.md` frontmatter does not represent per-skill tool
  permissions.
- Agent `tools.read`, `tools.mcp`, and `reasoning_effort` are lossy for Cursor
  agents because current Cursor subagent frontmatter supports `readonly`, but not
  those controls. Agent `tools.write: false` maps to Cursor `readonly: true`.
- Agent `tools.*` is lossy for Codex agents because current Codex subagent TOML
  does not expose generic per-agent read, write, or MCP tool permissions.
- Agent `description` is rejected for OpenCode agents when absent because
  OpenCode requires that field for agent config.

## CLI follow-up

This doc is the contract for `code-agnostic explain-lossiness`. That command reports:

- resource path
- target app
- property name
- status: `ignored` or `rejected`
- short reason
