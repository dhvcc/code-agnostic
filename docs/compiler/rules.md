# Rules compiler contract

Canonical rule source:

```text
rules/<name>/
  meta.yaml
  prompt.md
```

`meta.yaml` fields for v1:

- `spec_version`
- `kind`
- `description`
- `globs`
- `always_apply`
- `x-cursor.*`
- `x-codex.*`
- `x-opencode.*`
- `x-claude.*`
- `x-copilot.*`

Unknown keys fail validation.

## Capability matrix

| Property | Compiler | Cursor | Codex | OpenCode | Claude Code | GitHub Copilot |
| --- | --- | --- | --- | --- | --- | --- |
| `description` | supported | native | compiled | compiled | compiled | compiled |
| `globs` | supported | native | ignored | ignored | ignored | ignored |
| `always_apply` | supported | native | ignored | ignored | ignored | ignored |
| `prompt.md` body | supported | native | compiled | compiled | compiled | compiled |
| `x-cursor.*` | supported | native | ignored | ignored | ignored | ignored |
| `x-codex.*` | supported | ignored | native or compiled | ignored | ignored | ignored |
| `x-opencode.*` | supported | ignored | ignored | native or compiled | ignored | ignored |
| `x-claude.*` | supported | ignored | ignored | ignored | native or compiled | ignored |
| `x-copilot.*` | supported | ignored | ignored | ignored | ignored | ignored |

## Notes

- `globs` and `always_apply` are Cursor-oriented semantics today.
- If another app gains an equivalent, update the matrix and add tests before exposing the field more broadly.
