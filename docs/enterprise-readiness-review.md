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

### 0.7.0 (shipped)
- Claude per-project MCP prune. Project paths we write are tracked under
  `app:claude:projects` (via the same `managed_entries` mechanism);
  `build_project_mcp_action` takes `previously_managed_projects` and drops the
  `mcpServers` sub-key of any previously-managed path no longer synced, leaving
  the rest of the entry and user-added projects intact. `apps disable` prunes
  them too. All merge-without-prune orphan classes from P0-1/P1 are now closed.

### 0.8.0 (shipped)
- Typed `SyncState` replaces the `dict[str, Any]` state. `load_state()` returns
  a `SyncState`; `SyncState.from_payload` centralizes normalization once,
  removing ~11 defensive `isinstance` read sites and the `_normalize_group` /
  `_normalize_managed_group` helpers. On-disk layout unchanged.

### Follow-up (tracked)
- P1: adopt `WorkspaceConfig` (still unused) for `load_workspaces()`/
  `load_projects()` return types across the planner/status/CLI/TUI boundaries;
  planner de-duplication (compiled-text emit ×5, stale-cleanup);
  README/`.mdc` reconciliation.
- P2: remove dead legacy state keys (`managed_skill_links`/…), remaining
  mapper/service/repository de-duplication, concurrency lock.

---

## Handoff notes for the next session

State of the world: 0.4.0–0.7.0 shipped to PyPI + ghcr (tags `v*` trigger
`.github/workflows/publish_to_pypi.yml` + `publish-docker.yml`). `main` is the
release branch, mypy `strict` is green, full suite green (~760 tests). Every
merge-without-prune orphan class flagged in P0-1/P1 is now closed.

**The ownership pattern to reuse** (this is the backbone of all cleanup work):
- `apply_mcp_servers(existing, desired, previously_managed, replace=False)` in
  `apps/common/utils.py` — preserve user entries, prune ones we previously wrote
  that are now gone, upsert desired.
- Ownership is recorded on `Action.managed_entries: dict[scope, list[str]]` and
  persisted by `executor._persist_state` into `sync_state.json` under
  `managed_mcp` (a generic `scope → names` map despite the name). Scopes so far:
  `app:<app>:mcp`, `app:codex:agents_registry`, `app:claude:projects` (the names
  there are resolved project *paths*, not server names).
- `build_plan` reads previous names from state and threads them into
  `build_action(..., previously_managed=..., previously_managed_agents=...)`.
  The claude project variant reads previous paths in
  `planner._merge_claude_project_mcp` and threads them into
  `build_project_mcp_action(..., previously_managed_projects=...)`, then merges
  the projects scope into the global action's `managed_entries`.
- Generated/owned files (workspace/project) pass `replace_mcp=True` (full
  replace); user-shared global configs use ownership-aware (default).

**Next: adopt `WorkspaceConfig`.** `SyncState` is done (0.8.0). The remaining
typed-boundary work is the still-unused `WorkspaceConfig` dataclass
(`models.py`): `CoreRepository.load_workspaces()` / `load_projects()` return
`list[dict[str, str]]` (`{"name","path"}`) and ~15 sites consume
`workspace["name"]`/`["path"]` (planner `_plan_single_workspace`/
`_plan_single_project`, `status.py`, `apps_service.py`, `mcp_service.py`,
`git_exclude_service.py`, `cli/helpers.py`, `cli/commands/{workspaces,projects,
skills}.py`, `tui/tables.py`). Convert the return types to `list[WorkspaceConfig]`
(projects can reuse it or get a sibling), thread it through, and update
`save_workspaces`/`add`/`remove` + the tests that assert on the entry dicts.
Then planner de-duplication (compiled-text emit block ×5, stale-cleanup logic)
and README/`.mdc` reconciliation, then the P2 debt.

**Release mechanics gotcha:** the pre-commit `ruff-format` hook can reformat a
file and *reject* the commit; always `git add -A` again and re-commit. Bump
`__version__` (`code_agnostic/__init__.py`) and `version` (`pyproject.toml`)
together (test_version enforces match) — bump *after* the last full test run to
avoid a version-race failure. Tag only after `git push origin main` succeeds.
