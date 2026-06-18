# Agents compiler contract

Canonical agent source:

```text
agents/<name>/
  meta.yaml
  prompt.md
```

`meta.yaml` can declare `$schema` and point at:

- `https://raw.githubusercontent.com/dhvcc/code-agnostic/main/code_agnostic/spec/schemas/agent.v1.schema.json`

`meta.yaml` fields for v1:

- `spec_version`
- `kind`
- `name`
- `description`
- `model`
- `reasoning_effort`
- `sandbox_mode`
- `nickname_candidates`
- `tools.read`
- `tools.write`
- `tools.mcp`
- `codex.mcp_servers`
- `codex.skills.config`
- `x-cursor.*`
- `x-codex.*`
- `x-opencode.*`
- `x-claude.*`
- `x-copilot.*`

Tool permission fields are intentionally coarse in v1:

```yaml
tools:
  read: true
  write: true
  mcp:
    - server: filesystem
```

`tools.read` and `tools.write` are booleans. `tools.mcp` is a list of
string-keyed tool references.

Unknown keys fail validation outside app vendor blocks.

App vendor blocks are the supported place for per-app overrides and passthrough settings. Shared fields remain the default layer, and a matching `x-*` block can override them for one app only.

Example:

```yaml
spec_version: v1
kind: agent
name: reviewer
model: gpt-5.4-mini

x-opencode:
  model: opencode/big-pickle
  temperature: 0.2
```

This means Codex still receives `model: gpt-5.4-mini`, while OpenCode receives `model: opencode/big-pickle` plus `temperature: 0.2`.
Current OpenCode agent-native fields such as `variant` can be preserved through
`x-opencode`.

Legacy single-file markdown agents can express the same override with flat aliases such as `opencode-model: opencode/big-pickle` or `claude-model: claude-sonnet-4-20250514`.

## Capability matrix

| Property | Compiler | Cursor | Codex | OpenCode | Claude Code | GitHub Copilot |
| --- | --- | --- | --- | --- | --- | --- |
| `name` | supported | compiled | compiled | compiled | compiled | compiled |
| `description` | supported | compiled | compiled | required | compiled | required |
| `model` | supported | compiled | native | native | native | native |
| `reasoning_effort` | supported | ignored | native | native | compiled to `effort` | ignored |
| `sandbox_mode` | supported | ignored | native | ignored | ignored | ignored |
| `nickname_candidates` | supported | ignored | native | ignored | ignored | ignored |
| `tools.read` | supported | ignored | ignored | compiled to `permission.read` | ignored | compiled to `tools: ["read"]` |
| `tools.write` | supported | compiled to `readonly` when false | ignored | compiled to `permission.edit` | ignored | compiled to `tools: ["edit"]` |
| `tools.mcp` | supported | ignored | ignored | compiled to MCP tool permissions | ignored | compiled to `server/tool` strings when server is present |
| `codex.mcp_servers` | supported | ignored | native | ignored | ignored | ignored |
| `codex.skills.config` | supported | ignored | native | ignored | ignored | ignored |
| `prompt.md` body | supported | compiled | compiled | compiled | compiled | compiled |
| `x-cursor.*` | supported | native or compiled | ignored | ignored | ignored | ignored |
| `x-codex.*` | supported | ignored | native or compiled | ignored | ignored | ignored |
| `x-opencode.*` | supported | ignored | ignored | native or compiled | ignored | ignored |
| `x-claude.*` | supported | ignored | ignored | ignored | native or compiled | ignored |
| `x-copilot.*` | supported | ignored | ignored | ignored | ignored | native or compiled |

## Notes

- Cursor subagent frontmatter currently supports `name`, `description`, `model`,
  `readonly`, and `is_background`. Canonical `tools.write: false` maps to
  `readonly: true`; canonical `tools.read`, `tools.mcp`, and
  `reasoning_effort` are omitted and reported by `explain-lossiness`.
- Current Codex subagent TOML does not expose generic agent tool permissions;
  `tools.*` is omitted from generated Codex agent files and reported by
  `explain-lossiness`.
- OpenCode requires agent `description`; OpenCode compilation rejects agents
  without one instead of emitting an invalid target agent.
- GitHub Copilot custom agents are emitted as `<name>.agent.md`. The compiler
  writes `name`, required `description`, optional canonical `model`, and a
  native `tools` list only from canonical `tools.read`, `tools.write`, and MCP
  references that include a `server`.
- If a target cannot represent a field without changing behavior, the compiler should reject instead of silently dropping it.
