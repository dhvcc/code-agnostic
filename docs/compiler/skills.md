# Skills compiler contract

Canonical skill source:

```text
skills/<name>/
  meta.yaml
  prompt.md
```

`meta.yaml` fields for v1:

- `spec_version`
- `kind`
- `name`
- `description`
- `tools.read`
- `tools.write`
- `tools.mcp`
- `x-cursor.*`
- `x-codex.*`
- `x-opencode.*`

Unknown keys fail validation.

## Capability matrix

| Property | Compiler | Cursor | Codex | OpenCode |
| --- | --- | --- | --- | --- |
| `name` | supported | compiled | compiled | compiled |
| `description` | supported | compiled | compiled | compiled |
| `tools.read` | supported | compiled | compiled | compiled |
| `tools.write` | supported | compiled | compiled | compiled |
| `tools.mcp` | supported | compiled | compiled | compiled |
| `prompt.md` body | supported | compiled | compiled | compiled |
| `x-cursor.*` | supported | native or compiled | ignored | ignored |
| `x-codex.*` | supported | ignored | native or compiled | ignored |
| `x-opencode.*` | supported | ignored | ignored | native or compiled |

## Notes

- The v1 skill contract stays intentionally small.
- New fields should not be added until at least one target mapping and one test exist.
