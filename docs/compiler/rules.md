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

Unknown keys fail validation.

## Capability matrix

| Property | Compiler | Cursor | Codex | OpenCode |
| --- | --- | --- | --- | --- |
| `description` | supported | native | compiled | compiled |
| `globs` | supported | native | ignored | ignored |
| `always_apply` | supported | native | ignored | ignored |
| `prompt.md` body | supported | native | compiled | compiled |
| `x-cursor.*` | supported | native | ignored | ignored |
| `x-codex.*` | supported | ignored | native or compiled | ignored |
| `x-opencode.*` | supported | ignored | ignored | native or compiled |

## Notes

- `globs` and `always_apply` are Cursor-oriented semantics today.
- If another app gains an equivalent, update the matrix and add tests before exposing the field more broadly.
