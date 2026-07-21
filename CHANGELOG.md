# Changelog

## 0.9.1

### Fixed
- `test_file_lock` no longer asserts the lock file exists — on non-POSIX the
  lock degrades to a no-op and never creates the file (Windows CI green).

## 0.9.0

Enterprise-readiness cleanup — closes the remaining P1/P2 debt. No change to
on-disk config/state layout.

### Changed
- **Rules standardized on `AGENTS.md`.** Rules compile to a single `AGENTS.md`
  section format consumed natively by Cursor/OpenCode/Codex/Copilot (mirrored to
  `CLAUDE.local.md` for Claude). The never-wired `.mdc` Cursor compiler and the
  duplicate Codex compiler are removed; the README (which promised `.mdc` for
  Cursor) is corrected to match. This documents reality — no output that was
  actually produced before has changed.

### Internal
- Typed `WorkspaceConfig` for workspace/project entries (was `dict[str, str]`).
- Removed vestigial `managed_*_links` state keys (no reader).
- De-duplicated the planner's compiled-text emit (×5) and stale-cleanup blocks,
  shared MCP mapper coercions, and the identity `build_action_payload`.
- Removed dead code (`cursor.agent_action_removable_links`) and reordered
  `codex.derive_status` to skip work before an early `CREATE`.
- Advisory file lock around the executor's state write so parallel `apply` runs
  can't race on `sync_state.json`.

## 0.8.0

Contract & type-safety hardening (pre-1.0). No user-facing behavior change.

### Changed
- **Typed `SyncState` replaces the stringly-typed state dict.**
  `Repository.load_state()` now returns a `SyncState` dataclass; all defensive
  normalization (missing keys, wrong JSON types, stray non-string entries) is
  centralized once in `SyncState.from_payload` instead of being re-implemented
  with `isinstance` guards at ~11 read sites (planner, executor, status,
  `AppsService`, and the app-service `build_plan`). The on-disk
  `.sync-state.json` layout is unchanged; `save_state` still accepts a dict.

### Internal
- Removed the duplicated `_normalize_group` / `_normalize_managed_group`
  state-shape helpers now that `SyncState` guarantees the field types.

## 0.7.0

### Fixed
- **Claude per-project MCP is now pruned when a repo leaves a workspace.**
  Previously the `mcpServers` block under `projects.<path>` in `~/.claude.json`
  lingered forever once a repo was removed from a synced workspace (the top-level
  `mcpServers` was ownership-tracked, but per-project entries were merge-only).
  Project paths we write are now tracked per-path (`app:claude:projects`), so a
  removed repo has only its `mcpServers` sub-key pruned — the rest of the project
  entry (history etc.) and any project the user added by hand are left untouched.
  `apps disable` prunes the project entries it owns too.

## 0.6.0

### Fixed
- **Codex agent-registry entries are now pruned when the agent is removed from
  the source.** Previously an agent deleted from the hub left a stale
  `[agents.<name>]` entry in `~/.codex/config.toml` (its generated `.toml` file
  was removed, but the registry pointer lingered). Ownership is tracked
  per-name, so base-config agent settings and user-added entries are preserved.
  `apps disable` also prunes the registry entries it owns.

### Internal
- Generalized MCP ownership tracking (`Action.mcp_managed` → `managed_entries`,
  a scope→names map) so the same preserve-user / prune-ours cleanup now backs
  both MCP servers and the Codex agent registry. State layout
  (`managed_mcp` scope→names) is unchanged.

## 0.5.1

### Changed
- **Single `validate_config` contract for every editor.** Validation now lives
  in the base service: empty/absent config is valid, any present config must be
  a JSON object, and schema-backed editors (OpenCode/Cursor/Codex) plus
  Copilot's `mcpServers` check run via a `_validate_schema` hook. Previously
  Claude did no validation and each editor handled empty/non-object payloads
  differently.

## 0.5.0

Contract & type-safety hardening (pre-1.0). No user-facing behavior change.

### Changed
- **Killed `getattr`/`hasattr` contract bypass in the planner.** Methods that are
  already declared abstract on `IAppConfigService` / `IAppConfigRepository`
  (`plan_skill_actions`, `plan_agent_actions`, `validate_config`,
  `derive_status`, `agents_dir`) are now called through the typed interface
  instead of stringly-typed duck-typing.
- **`core` is typed as `CoreRepository`** across the planner, executor,
  `AppsService`, and `StatusService` — the honest contract (they operate on the
  global source root), which also removed the untyped attribute access.
- **mypy `strict` is now enforced** (`[tool.mypy]` in `pyproject.toml`); the
  package type-checks clean (0 errors, 109 files). Enabling it surfaced and
  fixed a latent type-narrowing bug in `SyncExecutor.restore_active_revision`.

## 0.4.0

Enterprise-readiness release focused on cleanup correctness and a single MCP
sync contract. See `docs/enterprise-readiness-review.md` for the full review.

### Fixed / Changed
- **MCP sync is now ownership-aware and consistent across all editors.**
  Previously Codex and Claude (global) merged MCP servers and never removed a
  server deleted from the source, while Cursor/OpenCode/Copilot fully replaced
  the map (wiping servers the user had added by hand). `set_mcp_payload` is now
  a single base-class implementation (`apply_mcp_servers`): removing a server
  from `config/mcp.base.json` prunes it from every target, and servers the user
  added directly are preserved.
- **Per-server MCP ownership is tracked** in `sync_state.json` under
  `managed_mcp`, so orphan pruning is safe (we only remove servers we wrote).
- **`apps disable` now cleans up.** Disabling an editor removes the compiled
  skills/agents it synced and prunes the MCP servers we own from its config,
  across global, workspace, and project scopes, and clears the tracked state —
  instead of stranding orphaned files with no way to reclaim them.

### Notes
- Workspace/project generated configs keep full-replace semantics (they are
  fully owned outputs); only user-shared global configs use the preserve-user /
  prune-ours model.
