# Changelog

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
