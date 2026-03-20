# MCP compiler contract

Canonical MCP source should move to `config/mcp.base.yaml`.

Top-level fields for v1:

- `spec_version`
- `mcp_servers`

Per-server fields for v1:

- `type`
- `command`
- `args`
- `url`
- `headers`
- `env`
- `auth.client_id`
- `auth.client_secret`
- `auth.scopes`
- `auth.token_endpoint`

Unknown keys fail validation.

## Capability matrix

| Property | Compiler | Cursor | Codex | OpenCode |
| --- | --- | --- | --- | --- |
| `type` | supported | compiled | compiled | compiled |
| `command` | supported | native | native | native |
| `args` | supported | native | native | native |
| `url` | supported | native | native | native |
| `headers` | supported | native | compiled | native |
| `env` | supported | native | compiled | native |
| `auth.client_id` | supported | compiled | compiled | compiled |
| `auth.client_secret` | supported | compiled | compiled | compiled |
| `auth.scopes` | supported | compiled | compiled | compiled |
| `auth.token_endpoint` | supported | compiled | compiled | compiled |
| `timeout` | planned | document per app | document per app | document per app |

## Notes

- If a property is not in this table, it is not part of the compiler contract.
- Target-specific MCP extensions belong under `x-*` only after a concrete use case and test exist.
