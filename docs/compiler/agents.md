# Agents compiler contract

Canonical agent source:

```text
agents/<name>/
  meta.yaml
  prompt.md
```

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

Unknown keys fail validation.

## Capability matrix

| Property | Compiler | Cursor | Codex | OpenCode |
| --- | --- | --- | --- | --- |
| `name` | supported | compiled | compiled | compiled |
| `description` | supported | compiled | compiled | compiled |
| `model` | supported | compiled | native | native |
| `reasoning_effort` | supported | ignored or compiled | native | native |
| `sandbox_mode` | supported | ignored | native | ignored |
| `nickname_candidates` | supported | ignored | native | ignored |
| `tools.read` | supported | compiled | pin to actual target behavior | compiled |
| `tools.write` | supported | compiled | pin to actual target behavior | compiled |
| `tools.mcp` | supported | compiled | pin to actual target behavior | compiled |
| `codex.mcp_servers` | supported | ignored | native | ignored |
| `codex.skills.config` | supported | ignored | native | ignored |
| `prompt.md` body | supported | compiled | compiled | compiled |
| `x-cursor.*` | supported | native or compiled | ignored | ignored |
| `x-codex.*` | supported | ignored | native or compiled | ignored |
| `x-opencode.*` | supported | ignored | ignored | native or compiled |

## Notes

- Codex-specific cells must be documented from real target behavior, not inference.
- If a target cannot represent a field without changing behavior, the compiler should reject instead of silently dropping it.
