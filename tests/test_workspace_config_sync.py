"""Tests for workspace-level config sync (MCP, skills, agents, rules)."""

import json
from pathlib import Path

from code_agnostic.apps.codex.config_repository import CodexConfigRepository
from code_agnostic.apps.codex.mapper import CodexMCPMapper
from code_agnostic.apps.codex.schema_repository import CodexSchemaRepository
from code_agnostic.apps.codex.service import CodexConfigService
from code_agnostic.apps.cursor.config_repository import CursorConfigRepository
from code_agnostic.apps.cursor.mapper import CursorMCPMapper
from code_agnostic.apps.cursor.schema_repository import CursorSchemaRepository
from code_agnostic.apps.cursor.service import CursorConfigService
from code_agnostic.apps.opencode.config_repository import OpenCodeConfigRepository
from code_agnostic.apps.opencode.mapper import OpenCodeMCPMapper
from code_agnostic.apps.opencode.schema_repository import OpenCodeSchemaRepository
from code_agnostic.apps.opencode.service import OpenCodeConfigService
from code_agnostic.constants import AGENTS_FILENAME
from code_agnostic.core.repository import CoreRepository
from code_agnostic.core.workspace_repository import WorkspaceConfigRepository
from code_agnostic.executor import SyncExecutor
from code_agnostic.models import ActionKind, ActionStatus
from code_agnostic.planner import SyncPlanner


def _opencode_service(
    core: CoreRepository, opencode_root: Path
) -> OpenCodeConfigService:
    return OpenCodeConfigService(
        repository=OpenCodeConfigRepository(root=opencode_root),
        mapper=OpenCodeMCPMapper(),
        schema_repository=OpenCodeSchemaRepository(),
        base_config_path=core.opencode_base_path,
    )


def _cursor_service(cursor_root: Path) -> CursorConfigService:
    return CursorConfigService(
        repository=CursorConfigRepository(root=cursor_root),
        mapper=CursorMCPMapper(),
        schema_repository=CursorSchemaRepository(),
    )


def _codex_service(codex_root: Path) -> CodexConfigService:
    return CodexConfigService(
        repository=CodexConfigRepository(root=codex_root),
        mapper=CodexMCPMapper(),
        schema_repository=CodexSchemaRepository(),
    )


# --- WorkspaceConfigRepository ---


def test_workspace_config_repository_has_any_config_empty(tmp_path: Path) -> None:
    ws_root = tmp_path / "ws-config"
    ws_root.mkdir(parents=True)
    repo = WorkspaceConfigRepository(root=ws_root)

    assert not repo.has_any_config()
    assert not repo.has_mcp()
    assert not repo.has_rules()
    assert not repo.has_skills()
    assert not repo.has_agents()


def test_workspace_config_repository_has_rules(tmp_path: Path) -> None:
    ws_root = tmp_path / "ws-config"
    ws_root.mkdir(parents=True)
    (ws_root / "AGENTS.md").write_text("rules", encoding="utf-8")
    repo = WorkspaceConfigRepository(root=ws_root)

    assert repo.has_rules()
    assert repo.has_any_config()


def test_workspace_config_repository_has_mcp(tmp_path: Path, write_json) -> None:
    ws_root = tmp_path / "ws-config"
    ws_root.mkdir(parents=True)
    write_json(ws_root / "mcp.base.json", {"mcpServers": {"test": {"url": "http://x"}}})
    repo = WorkspaceConfigRepository(root=ws_root)

    assert repo.has_mcp()
    assert repo.has_any_config()
    mcp = repo.load_mcp_base()
    assert "test" in mcp["mcpServers"]


def test_workspace_config_repository_has_skills(tmp_path: Path) -> None:
    ws_root = tmp_path / "ws-config"
    (ws_root / "skills" / "my-skill").mkdir(parents=True)
    (ws_root / "skills" / "my-skill" / "SKILL.md").write_text("s", encoding="utf-8")
    repo = WorkspaceConfigRepository(root=ws_root)

    assert repo.has_skills()
    assert repo.has_any_config()
    assert len(repo.list_skill_sources()) == 1


def test_workspace_config_repository_has_agents(tmp_path: Path) -> None:
    ws_root = tmp_path / "ws-config"
    (ws_root / "agents").mkdir(parents=True)
    (ws_root / "agents" / "planner.md").write_text("a", encoding="utf-8")
    repo = WorkspaceConfigRepository(root=ws_root)

    assert repo.has_agents()
    assert repo.has_any_config()
    assert len(repo.list_agent_sources()) == 1


def test_workspace_config_repository_state_roundtrip(tmp_path: Path) -> None:
    ws_root = tmp_path / "ws-config"
    ws_root.mkdir(parents=True)
    repo = WorkspaceConfigRepository(root=ws_root)

    state = repo.load_state()
    assert isinstance(state, dict)

    repo.save_state({"managed_links": {"rules": ["/path/to/link"]}})
    loaded = repo.load_state()
    assert loaded["managed_links"]["rules"] == ["/path/to/link"]


# --- Workspace rules symlinks ---


def test_workspace_rules_symlinks_planned_for_each_repo(
    minimal_shared_config: Path,
    core_root: Path,
    opencode_root: Path,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "repo-a" / ".git").mkdir(parents=True)
    (workspace_root / "repo-b" / ".git").mkdir(parents=True)

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    (ws_config / AGENTS_FILENAME).write_text("rules", encoding="utf-8")

    plan = SyncPlanner(
        core=core, app_services=[_opencode_service(core, opencode_root)]
    ).build()

    rules_actions = [
        a for a in plan.actions if a.kind == ActionKind.SYMLINK and a.scope == "rules"
    ]
    assert len(rules_actions) == 2
    assert all(a.workspace == "myws" for a in rules_actions)
    assert all(a.app == "workspace" for a in rules_actions)


# --- Workspace MCP config sync ---


def test_workspace_mcp_sync_to_cursor_project_dirs(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    write_json,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "repo-a" / ".git").mkdir(parents=True)

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    write_json(
        ws_config / "mcp.base.json",
        {"mcpServers": {"test-server": {"url": "https://test.example.com/mcp"}}},
    )

    cursor_root = tmp_path / ".cursor"
    plan = SyncPlanner(core=core, app_services=[_cursor_service(cursor_root)]).build()

    mcp_actions = [
        a
        for a in plan.actions
        if a.app == "workspace"
        and a.kind in (ActionKind.WRITE_JSON, ActionKind.WRITE_TEXT)
    ]
    assert len(mcp_actions) == 1
    assert mcp_actions[0].workspace == "myws"

    # The MCP config should be rendered once into workspace config dir
    expected_path = ws_config / ".cursor" / "mcp.json"
    assert mcp_actions[0].path == expected_path

    # And then symlinked into each repo
    link_actions = [
        a
        for a in plan.actions
        if a.kind == ActionKind.SYMLINK and a.scope == "ws:cursor:repo_mcp"
    ]
    assert len(link_actions) == 1
    assert link_actions[0].path == workspace_root / "repo-a" / ".cursor" / "mcp.json"
    assert link_actions[0].source == expected_path


def test_workspace_mcp_sync_to_codex_project_dirs(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    write_json,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "repo-a" / ".git").mkdir(parents=True)

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    write_json(
        ws_config / "mcp.base.json",
        {"mcpServers": {"test-server": {"command": "npx", "args": ["test"]}}},
    )

    codex_root = tmp_path / ".codex"
    plan = SyncPlanner(core=core, app_services=[_codex_service(codex_root)]).build()

    mcp_actions = [
        a
        for a in plan.actions
        if a.app == "workspace" and a.kind == ActionKind.WRITE_TEXT
    ]
    assert len(mcp_actions) == 1
    expected_path = ws_config / ".codex" / "config.toml"
    assert mcp_actions[0].path == expected_path

    link_actions = [
        a
        for a in plan.actions
        if a.kind == ActionKind.SYMLINK and a.scope == "ws:codex:repo_mcp"
    ]
    assert len(link_actions) == 1
    assert link_actions[0].path == workspace_root / "repo-a" / ".codex" / "config.toml"
    assert link_actions[0].source == expected_path


# --- Workspace skill symlinks ---


def test_workspace_skills_symlinked_to_repo_project_dirs(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "repo-a" / ".git").mkdir(parents=True)

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    (ws_config / "skills" / "my-skill").mkdir(parents=True)
    (ws_config / "skills" / "my-skill" / "SKILL.md").write_text("s", encoding="utf-8")

    cursor_root = tmp_path / ".cursor"
    plan = SyncPlanner(core=core, app_services=[_cursor_service(cursor_root)]).build()

    # Workspace skill entry symlinked into workspace project dir
    ws_entry_actions = [
        a
        for a in plan.actions
        if a.kind == ActionKind.SYMLINK and a.scope == "ws:cursor:skills_entries"
    ]
    assert len(ws_entry_actions) == 1
    assert ws_entry_actions[0].workspace == "myws"
    assert ws_entry_actions[0].path == ws_config / ".cursor" / "skills" / "my-skill"
    assert ws_entry_actions[0].source == ws_config / "skills" / "my-skill"

    # Repo links its skills dir to workspace skills dir
    repo_dir_actions = [
        a
        for a in plan.actions
        if a.kind == ActionKind.SYMLINK and a.scope == "ws:cursor:repo_skills_dir"
    ]
    assert len(repo_dir_actions) == 1
    assert repo_dir_actions[0].workspace == "myws"
    assert repo_dir_actions[0].path == workspace_root / "repo-a" / ".cursor" / "skills"
    assert repo_dir_actions[0].source == ws_config / ".cursor" / "skills"


# --- Workspace agent symlinks ---


def test_workspace_agents_symlinked_to_repo_project_dirs(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "repo-a" / ".git").mkdir(parents=True)

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    (ws_config / "agents").mkdir(parents=True)
    (ws_config / "agents" / "planner.md").write_text("a", encoding="utf-8")

    cursor_root = tmp_path / ".cursor"
    plan = SyncPlanner(core=core, app_services=[_cursor_service(cursor_root)]).build()

    ws_entry_actions = [
        a
        for a in plan.actions
        if a.kind == ActionKind.SYMLINK and a.scope == "ws:cursor:agents_entries"
    ]
    assert len(ws_entry_actions) == 1
    assert ws_entry_actions[0].workspace == "myws"
    assert ws_entry_actions[0].path == ws_config / ".cursor" / "agents" / "planner.md"
    assert ws_entry_actions[0].source == ws_config / "agents" / "planner.md"

    repo_dir_actions = [
        a
        for a in plan.actions
        if a.kind == ActionKind.SYMLINK and a.scope == "ws:cursor:repo_agents_dir"
    ]
    assert len(repo_dir_actions) == 1
    assert repo_dir_actions[0].workspace == "myws"
    assert repo_dir_actions[0].path == workspace_root / "repo-a" / ".cursor" / "agents"
    assert repo_dir_actions[0].source == ws_config / ".cursor" / "agents"


def test_workspace_agents_not_synced_to_codex(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "repo-a" / ".git").mkdir(parents=True)

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    (ws_config / "agents").mkdir(parents=True)
    (ws_config / "agents" / "planner.md").write_text("a", encoding="utf-8")

    codex_root = tmp_path / ".codex"
    plan = SyncPlanner(core=core, app_services=[_codex_service(codex_root)]).build()

    agent_actions = [
        a
        for a in plan.actions
        if a.scope and "agents" in a.scope and a.app == "workspace"
    ]
    assert agent_actions == []


# --- Executor workspace state persistence ---


def test_executor_persists_workspace_state_separately(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "repo-a" / ".git").mkdir(parents=True)

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    (ws_config / AGENTS_FILENAME).write_text("rules", encoding="utf-8")

    cursor_root = tmp_path / ".cursor"
    plan = SyncPlanner(core=core, app_services=[_cursor_service(cursor_root)]).build()

    applied, failed, failures = SyncExecutor(core=core).execute(plan)
    assert failed == 0

    # Workspace state persisted to workspace state file
    ws_repo = WorkspaceConfigRepository(root=ws_config)
    ws_state = ws_repo.load_state()
    assert "rules" in ws_state["managed_links"]
    assert len(ws_state["managed_links"]["rules"]) == 1

    # Global state should not contain workspace links
    global_state = core.load_state()
    assert "rules" not in global_state.get("managed_links", {})


# --- Full roundtrip with apply ---


def test_full_workspace_config_roundtrip(
    minimal_shared_config: Path,
    core_root: Path,
    opencode_root: Path,
    tmp_path: Path,
    write_json,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "repo-a" / ".git").mkdir(parents=True)
    (workspace_root / "repo-b" / ".git").mkdir(parents=True)

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    (ws_config / AGENTS_FILENAME).write_text("workspace rules", encoding="utf-8")
    write_json(
        ws_config / "mcp.base.json",
        {"mcpServers": {"ws-server": {"url": "https://ws.example.com/mcp"}}},
    )
    (ws_config / "skills" / "ws-skill").mkdir(parents=True)
    (ws_config / "skills" / "ws-skill" / "SKILL.md").write_text("s", encoding="utf-8")
    (ws_config / "agents").mkdir(parents=True)
    (ws_config / "agents" / "ws-agent.md").write_text("a", encoding="utf-8")

    cursor_root = tmp_path / ".cursor"
    plan = SyncPlanner(
        core=core,
        app_services=[
            _opencode_service(core, opencode_root),
            _cursor_service(cursor_root),
        ],
    ).build()

    assert plan.errors == []

    applied, failed, failures = SyncExecutor(core=core).execute(plan)
    assert failed == 0
    assert failures == []
    assert applied > 0

    # Check rules symlinks
    for repo_name in ["repo-a", "repo-b"]:
        link = workspace_root / repo_name / AGENTS_FILENAME
        assert link.is_symlink()
        assert link.resolve() == (ws_config / AGENTS_FILENAME).resolve()

    # Check MCP config rendered into workspace, then linked into repos
    ws_cursor_mcp = ws_config / ".cursor" / "mcp.json"
    assert ws_cursor_mcp.exists()
    payload = json.loads(ws_cursor_mcp.read_text(encoding="utf-8"))
    assert "ws-server" in payload.get("mcpServers", {})

    # Workspace root also gets the shared links (for multi-root workspace sessions)
    ws_root_cursor_mcp = workspace_root / ".cursor" / "mcp.json"
    assert ws_root_cursor_mcp.is_symlink()
    assert ws_root_cursor_mcp.resolve() == ws_cursor_mcp.resolve()

    for repo_name in ["repo-a", "repo-b"]:
        cursor_mcp = workspace_root / repo_name / ".cursor" / "mcp.json"
        assert cursor_mcp.is_symlink()
        assert cursor_mcp.resolve() == ws_cursor_mcp.resolve()

    # Check skill links in workspace project dir and repo linkage
    ws_skill_link = ws_config / ".cursor" / "skills" / "ws-skill"
    assert ws_skill_link.is_symlink()

    ws_root_skill_dir = workspace_root / ".cursor" / "skills"
    assert ws_root_skill_dir.is_symlink()

    for repo_name in ["repo-a", "repo-b"]:
        skill_dir = workspace_root / repo_name / ".cursor" / "skills"
        assert skill_dir.is_symlink()
        skill_link = skill_dir / "ws-skill"
        assert skill_link.is_symlink()

    # Check agent links in workspace project dir and repo linkage
    ws_agent_link = ws_config / ".cursor" / "agents" / "ws-agent.md"
    assert ws_agent_link.is_symlink()

    ws_root_agent_dir = workspace_root / ".cursor" / "agents"
    assert ws_root_agent_dir.is_symlink()

    for repo_name in ["repo-a", "repo-b"]:
        agent_dir = workspace_root / repo_name / ".cursor" / "agents"
        assert agent_dir.is_symlink()
        agent_link = agent_dir / "ws-agent.md"
        assert agent_link.is_symlink()


# --- Stale workspace link cleanup ---


def test_workspace_stale_rules_cleanup_on_config_removal(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "repo-a" / ".git").mkdir(parents=True)

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    (ws_config / AGENTS_FILENAME).write_text("rules", encoding="utf-8")

    cursor_root = tmp_path / ".cursor"
    plan = SyncPlanner(core=core, app_services=[_cursor_service(cursor_root)]).build()

    SyncExecutor(core=core).execute(plan)
    link = workspace_root / "repo-a" / AGENTS_FILENAME
    assert link.is_symlink()

    # Remove rules file
    (ws_config / AGENTS_FILENAME).unlink()

    plan2 = SyncPlanner(core=core, app_services=[_cursor_service(cursor_root)]).build()

    SyncExecutor(core=core).execute(plan2)
    assert not link.is_symlink()


def test_workspace_stale_skills_cleanup_when_skills_removed(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    """Skills removed from workspace config should have their symlinks cleaned up."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "repo-a" / ".git").mkdir(parents=True)

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    (ws_config / "skills" / "my-skill").mkdir(parents=True)
    (ws_config / "skills" / "my-skill" / "SKILL.md").write_text("s", encoding="utf-8")

    cursor_root = tmp_path / ".cursor"
    plan = SyncPlanner(core=core, app_services=[_cursor_service(cursor_root)]).build()

    SyncExecutor(core=core).execute(plan)
    skill_dir_link = workspace_root / "repo-a" / ".cursor" / "skills"
    assert skill_dir_link.is_symlink()

    # Verify state was persisted with workspace scopes
    ws_repo = WorkspaceConfigRepository(root=ws_config)
    state = ws_repo.load_state()
    assert "ws:cursor:skills_entries" in state["managed_links"]
    assert "ws:cursor:repo_skills_dir" in state["managed_links"]

    # Remove all skills from workspace config
    import shutil

    shutil.rmtree(ws_config / "skills")

    plan2 = SyncPlanner(core=core, app_services=[_cursor_service(cursor_root)]).build()

    # Should have remove actions for stale workspace entry and repo dir link
    remove_actions = [
        a
        for a in plan2.actions
        if a.kind == ActionKind.REMOVE_SYMLINK
        and a.scope in ("ws:cursor:skills_entries", "ws:cursor:repo_skills_dir")
    ]
    assert len(remove_actions) == 2

    SyncExecutor(core=core).execute(plan2)
    assert not skill_dir_link.is_symlink()


# --- plan_resource_symlinks utility ---


def test_plan_resource_symlinks_creates_actions(tmp_path: Path) -> None:
    from code_agnostic.apps.common.symlink_planning import plan_resource_symlinks

    source = tmp_path / "source"
    source.mkdir()
    target_dir = tmp_path / "target"
    target_dir.mkdir()

    actions, desired, skipped = plan_resource_symlinks(
        [source], target_dir, scope="test", app="test-app"
    )

    assert len(actions) == 1
    assert actions[0].status == ActionStatus.CREATE
    assert desired == [target_dir / source.name]
    assert skipped == []


def test_plan_resource_symlinks_conflict(tmp_path: Path) -> None:
    from code_agnostic.apps.common.symlink_planning import plan_resource_symlinks

    source = tmp_path / "source"
    source.mkdir()
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    conflict = target_dir / source.name
    conflict.write_text("conflict", encoding="utf-8")

    actions, desired, skipped = plan_resource_symlinks(
        [source], target_dir, scope="test", app="test-app"
    )

    assert len(actions) == 1
    assert actions[0].status == ActionStatus.CONFLICT
    assert len(skipped) == 1


# --- load_state_links utility ---


def test_load_state_links_returns_paths() -> None:
    from code_agnostic.apps.common.symlink_planning import load_state_links

    managed = {"scope1": ["/path/a", "/path/b"]}
    result = load_state_links(managed, "scope1")

    assert result == [Path("/path/a"), Path("/path/b")]


def test_load_state_links_missing_scope() -> None:
    from code_agnostic.apps.common.symlink_planning import load_state_links

    result = load_state_links({}, "missing")
    assert result == []


def test_load_state_links_non_list() -> None:
    from code_agnostic.apps.common.symlink_planning import load_state_links

    result = load_state_links({"bad": "not-a-list"}, "bad")
    assert result == []


# --- CoreRepository workspace config dir ---


def test_core_repository_workspace_config_dir(core_root: Path) -> None:
    core = CoreRepository(core_root)

    ws_dir = core.workspace_config_dir("myws")
    assert ws_dir == core_root / "workspaces" / "myws"


def test_add_workspace_creates_config_dir(core_root: Path, tmp_path: Path) -> None:
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    assert core.workspace_config_dir("myws").exists()
    assert core.workspace_config_dir("myws").is_dir()
