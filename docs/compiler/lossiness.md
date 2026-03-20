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
- Future MCP properties like `timeout` must not appear in canonical config until target mappings are documented.

## CLI follow-up

This doc is the contract for a future `code-agnostic explain-lossiness` command. That command should report:

- resource path
- target app
- property name
- status: `ignored` or `rejected`
- short reason
