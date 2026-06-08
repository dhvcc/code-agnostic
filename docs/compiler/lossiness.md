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
- Skill `tools.*` is lossy for Cursor, Codex, OpenCode, and Claude Code skills because
  current target `SKILL.md` frontmatter does not represent per-skill tool
  permissions.
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
