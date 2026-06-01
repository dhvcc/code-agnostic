# Changelog

## 0.3.5 - 2026-06-01

### Highlights

- Hardened `plan`, `apply`, `status`, and `restore` around invalid source config,
  workspace-only sync, symlinked paths, and rollback recovery.
- Added real app-ingestion E2E coverage that checks Codex, Cursor, and OpenCode
  through their own CLI/debug/introspection surfaces instead of filesystem-only
  assertions.
- Aligned Codex user skill output with current Codex discovery: global generated
  skills now go to `~/.agents/skills`; Codex config and agents remain under
  `~/.codex`.

### Added

- `restore` regression coverage for missing revision artifacts and symlink target
  rollback.
- Real app-ingestion smoke tests for MCP, skills, agents, and workspace
  instructions across supported tools.
- `skills list` now shows scope, source format, and source directory.
- Version contract test ensuring package metadata and `code_agnostic.__version__`
  stay in sync.

### Changed

- Codex skill import/discovery now reads from `.agents/skills`.
- Previously managed Codex skill outputs under `.codex/skills` are planned as
  stale generated files and cleaned up during apply.
- README and compiler docs now prefer bundle source directories with
  `meta.yaml` and `prompt.md`, while preserving legacy single-file formats.
- OpenCode schema snapshots and compatibility docs were refreshed.

### Fixed

- `plan` and `status` now fail closed on invalid source config instead of
  returning success or reporting misleading synced states.
- App-scoped `status -a <app>` no longer inherits unrelated app config errors.
- Workspace status rows that report errors now produce a nonzero exit code.
- Workspace-only Codex apply/status no longer requires a global MCP source file.
- Symlinked ancestor paths such as macOS `/tmp -> /private/tmp` no longer create
  false target conflicts for generated files.
- Restore no longer removes an existing target before confirming the active
  revision artifact exists.
- Restore rollback now captures and repairs symlink target file contents.
- OpenCode remote MCP servers now reject unsupported `env` explicitly.
- OpenCode skill frontmatter rejects unsupported native overrides instead of
  silently emitting ignored no-op keys.

### Migration Notes

- Codex generated skills moved from `~/.codex/skills` to `~/.agents/skills`.
  Run `code-agnostic plan -a codex` before applying to review cleanup of any
  previously managed generated `.codex/skills` outputs.
- Remote OpenCode MCP entries with environment variables are now invalid; use
  local MCP servers for env-backed commands.
