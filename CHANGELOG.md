# Changelog

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
