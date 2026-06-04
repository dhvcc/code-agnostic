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

Legacy single-file markdown agents can express the same override with flat aliases such as `opencode-model: opencode/big-pickle` or `claude-model: claude-sonnet-4-20250514`.

## Capability matrix

| Property | Compiler | Cursor | Codex | OpenCode | Claude Code |
| --- | --- | --- | --- | --- | --- |
| `name` | supported | compiled | compiled | compiled | compiled |
| `description` | supported | compiled | compiled | compiled | compiled |
| `model` | supported | compiled | native | native | native |
| `reasoning_effort` | supported | ignored or compiled | native | native | compiled to `effort` |
| `sandbox_mode` | supported | ignored | native | ignored | ignored |
| `nickname_candidates` | supported | ignored | native | ignored | ignored |
| `tools.read` | supported | compiled | ignored | compiled to `permission.read` | ignored |
| `tools.write` | supported | compiled | ignored | compiled to `permission.edit` | ignored |
| `tools.mcp` | supported | compiled | ignored | compiled to MCP tool permissions | ignored |
| `codex.mcp_servers` | supported | ignored | native | ignored | ignored |
| `codex.skills.config` | supported | ignored | native | ignored | ignored |
| `prompt.md` body | supported | compiled | compiled | compiled | compiled |
| `x-cursor.*` | supported | native or compiled | ignored | ignored | ignored |
| `x-codex.*` | supported | ignored | native or compiled | ignored | ignored |
| `x-opencode.*` | supported | ignored | ignored | native or compiled | ignored |
| `x-claude.*` | supported | ignored | ignored | ignored | native or compiled |

## Notes

- Current Codex subagent TOML does not expose generic agent tool permissions;
  `tools.*` is omitted from generated Codex agent files and reported by
  `explain-lossiness`.
- If a target cannot represent a field without changing behavior, the compiler should reject instead of silently dropping it.
