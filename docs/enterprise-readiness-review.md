# Enterprise-Readiness & Code-Quality Review

Scope: `code_agnostic` as a cross-harness config backbone. Focus areas: contract
adherence, DRY, and cleanup/state (orphan removal). Severity: P0 (release
blocker) / P1 (should fix before 1.0.0) / P2 (debt).

Findings triangulated across a direct read of the core, two subsystem audits
(apps/DRY and cleanup-trace), and a `codex` cross-review. Line references are as
of version 0.3.18.

---

## P0 — release blockers

### P0-1. `set_mcp_payload` has two incompatible semantics across editors
`set_mcp_payload` is overridden in all 5 app services with divergent behavior:

| App | Code | On server deletion from `mcp.base.json` |
|---|---|---|
| cursor `service.py:82`, opencode `:239`, copilot `:71` | `merged[key] = desired_mcp` | full-replace → prunes orphan **but wipes servers the user added by hand** |
| codex `service.py:97-107` | merge-overlay | orphan **stays in `~/.codex` forever** |
| claude `service.py:65-73` | merge-overlay (no empty-`pop`) | orphan **stays in `~/.claude.json` forever** |

One `apply` yields three different results. Silent, hits every user.

### P0-2. No per-server ownership for MCP (root cause of P0-1)
Skills/agents/rules are tracked in `sync_state.json` (`managed_links` /
`managed_paths` by scope) and persisted atomically by
`executor._persist_state` — stale cleanup works. **MCP is tracked nowhere**: the
global MCP action is built with `scope=None`
(`interfaces/service.py:249-256`) and `_persist_state` skips unscoped actions
(`executor.py:768`). The tool cannot distinguish "a server we wrote" from "a
server the user added", so it cannot safely prune. (codex confirmed: even
workspace/project MCP is tracked at file granularity, not per server.)

**Fix:** track `managed_mcp` (server names we wrote) in state; unify
`set_mcp_payload` in the base class to `existing − (previously_managed −
desired) ∪ desired`. Removes our orphans, keeps the user's servers, identical
across all 5 editors.

### P0-3. `apps disable` cleans up nothing and orphans become unrecoverable
`AppsService.disable` (`apps_service.py:65`) only flips a bool in `apps.json`. On
the next `apply all`, the disabled app is excluded from selection and stale
sweeps only consider selected apps' scopes (`planner.py:928-966`, `430-437`), so
every artifact that app ever synced (MCP config, skills, agents, workspace
`AGENTS.md`/`CLAUDE.local.md`, codex overrides) is left on disk with no recovery
via the normal flow.

**Fix:** `disable` builds and applies a cleanup plan for the disabled app from
tracked state, then clears its state entries.

---

## P1 — before 1.0.0

- **Contract bypassed via `getattr`/`hasattr`** in `planner.py:377,398,682,707,146`
  for methods already declared `@abstractmethod` on `IAppConfigService`.
- **`validate_config` — 5 different contracts** under one name; claude
  (`service.py:56-60`) does no schema validation at all → invalid config can be
  written.
- **Typing not enforced**: no `[tool.mypy]` in `pyproject.toml`; mypy runs on
  defaults, so `Any`/untyped defs pass. Enable strict.
- **State is stringly-typed `dict[str, Any]`** re-validated defensively in ~5
  places. Introduce a typed `SyncState` and use the existing but unused
  `WorkspaceConfig` (`models.py:148`) across boundaries (`planner.py:457` takes a
  raw `dict`).
- **`planner.py` (988 lines)** repeats the compiled-text emit block 5×
  (`:498,528,559,588,742`) and duplicates stale-cleanup logic across
  `_plan_single_workspace`, `_plan_single_project`, and
  `service._build_compiled_group`.
- **README vs reality**: README promises Cursor rules compile to `.mdc`, but
  `CursorRuleCompiler` (`rules/compilers.py:18`) is never invoked; only
  `OpenCodeRuleCompiler` runs.
- **codex agent-registry orphans** (`codex/service.py:150-171`) and **claude
  project-entry orphans** (`claude/service.py:93-112`): same merge-without-prune
  class as P0-1, for agents and per-project MCP respectively.

## P2 — debt

- Dead state keys `managed_skill_links`/`managed_agent_links`/
  `managed_workspace_links` (`core/repository.py:117-133`) — written, never read.
- Duplicated mapper helpers (timeout coercion ×4, `_as_list`, str-dict).
- Duplicated `_load_base_config` (opencode/codex), `build_action_payload` (4/5),
  `plan_skill_actions` bodies (5×), repo `load_config`/`load_mcp_payload`
  (differ only by key), schema repos (differ only by URL).
- Dead/lazy code: `cursor.agent_action_removable_links` (`:103`) equals base
  default; `codex.derive_status` (`:112-117`) reads files before the `exists()`
  check.
- Duplicated workspace/project CRUD in `core/repository.py:213-381`.
- Concurrency: `datetime.now()` revision ids + no file lock → parallel `apply`
  races on `sync_state.json`.

---

## Release plan

### 0.4.0 (shipped)
- **P0-1 + P0-2**: ownership-aware, unified `set_mcp_payload` in the base class
  (`apply_mcp_servers`) + `managed_mcp` in `sync_state.json` + executor
  persistence. Removing a server from the source now prunes it from every editor
  (incl. Codex and global Claude), while servers the user added by hand are
  preserved. Covered by `tests/test_cli_apply_mcp_cleanup.py`.
- **P0-3**: `apps disable` runs a cleanup plan from tracked global/workspace/
  project state (removes compiled skills/agents, prunes our MCP servers) and
  clears the state. Covered by `tests/test_cli_disable_cleanup.py`.

### 0.5.0 (shipped) — contract & type hardening
- Removed the `getattr`/`hasattr` contract bypass in the planner; typed `core`
  as `CoreRepository`; **enabled mypy `strict`** (0 errors) and fixed a latent
  narrowing bug in `restore_active_revision`.

### 0.5.1 (shipped)
- Unified `validate_config` into one base contract (empty-ok, object-required,
  `_validate_schema` hook); Claude/Copilot no longer skip validation.

### 0.6.0 (shipped)
- Codex agent-registry prune via a generalized ownership mechanism
  (`Action.managed_entries`, scope→names); `apps disable` prunes it too.

### Follow-up (tracked)
- P1: claude project-entry prune (bespoke `build_project_mcp_action` flow) —
  next.
- P1: typed `SyncState`/`WorkspaceConfig` model, planner de-duplication,
  README/`.mdc` reconciliation.
- P2: remove dead legacy state keys (`managed_skill_links`/…), remaining
  mapper/service/repository de-duplication, concurrency lock.

---

## Handoff notes for the next session

State of the world: 0.4.0–0.6.0 shipped to PyPI + ghcr (tags `v*` trigger
`.github/workflows/publish_to_pypi.yml` + `publish-docker.yml`). `main` is the
release branch, mypy `strict` is green, full suite green (~757 tests).

**The ownership pattern to reuse** (this is the backbone of all cleanup work):
- `apply_mcp_servers(existing, desired, previously_managed, replace=False)` in
  `apps/common/utils.py` — preserve user entries, prune ones we previously wrote
  that are now gone, upsert desired.
- Ownership is recorded on `Action.managed_entries: dict[scope, list[str]]` and
  persisted by `executor._persist_state` into `sync_state.json` under
  `managed_mcp` (a generic `scope → names` map despite the name). Scopes so far:
  `app:<app>:mcp`, `app:codex:agents_registry`.
- `build_plan` reads previous names from state and threads them into
  `build_action(..., previously_managed=..., previously_managed_agents=...)`.
- Generated/owned files (workspace/project) pass `replace_mcp=True` (full
  replace); user-shared global configs use ownership-aware (default).

**Next: claude project-entry prune.** `ClaudeConfigService.build_project_mcp_action`
(`apps/claude/service.py`) copies `projects` and only updates currently-desired
paths, never removing the `mcpServers` sub-key of project paths we previously
wrote but no longer sync (e.g. a repo removed from a workspace). Plan:
1. Track managed project paths under a new scope, e.g. `app:claude:projects`, on
   the merged Claude action's `managed_entries` (the action is assembled in
   `planner._merge_claude_project_mcp`, which already carries `managed_entries`
   from the global action — extend it there).
2. Read previous project paths from state in the planner (it has `self.core`)
   and pass them into `build_project_mcp_action`.
3. For each previously-managed path NOT in the current desired set, delete only
   its `mcpServers` sub-key (leave the rest of the Claude project entry — history
   etc. — untouched). Never remove non-managed project entries.
4. TDD: mirror `tests/test_cli_apply_mcp_cleanup.py` — sync two workspace repos,
   then remove one, assert its `projects.<path>.mcpServers` is gone and the
   other + any user project entry survive.

**Release mechanics gotcha:** the pre-commit `ruff-format` hook can reformat a
file and *reject* the commit; always `git add -A` again and re-commit. Bump
`__version__` (`code_agnostic/__init__.py`) and `version` (`pyproject.toml`)
together (test_version enforces match) — bump *after* the last full test run to
avoid a version-race failure. Tag only after `git push origin main` succeeds.
