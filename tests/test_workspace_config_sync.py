"""Tests for workspace-level config sync (MCP, skills, agents, rules)."""

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from code_agnostic.apps.codex.config_repository import CodexConfigRepository
from code_agnostic.apps.codex.mapper import CodexMCPMapper
from code_agnostic.apps.codex.schema_repository import CodexSchemaRepository
from code_agnostic.apps.codex.service import CodexConfigService
from code_agnostic.apps.claude.config_repository import ClaudeConfigRepository
from code_agnostic.apps.claude.mapper import ClaudeMCPMapper
from code_agnostic.apps.claude.service import ClaudeConfigService
from code_agnostic.apps.cursor.config_repository import CursorConfigRepository
from code_agnostic.apps.cursor.mapper import CursorMCPMapper
from code_agnostic.apps.cursor.schema_repository import CursorSchemaRepository
from code_agnostic.apps.cursor.service import CursorConfigService
from code_agnostic.apps.copilot.config_repository import CopilotConfigRepository
from code_agnostic.apps.copilot.mapper import CopilotMCPMapper
from code_agnostic.apps.copilot.service import CopilotConfigService
from code_agnostic.apps.opencode.config_repository import OpenCodeConfigRepository
from code_agnostic.apps.opencode.mapper import OpenCodeMCPMapper
from code_agnostic.apps.opencode.schema_repository import OpenCodeSchemaRepository
from code_agnostic.apps.opencode.service import OpenCodeConfigService
from code_agnostic.constants import (
    AGENTS_FILENAME,
    CLAUDE_LOCAL_FILENAME,
    CODEX_AGENTS_OVERRIDE_FILENAME,
)
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


def _claude_service(claude_root: Path) -> ClaudeConfigService:
    return ClaudeConfigService(
        repository=ClaudeConfigRepository(
            root=claude_root,
            config_path=claude_root.parent / ".claude.json",
        ),
        mapper=ClaudeMCPMapper(),
    )


def _copilot_service(copilot_root: Path) -> CopilotConfigService:
    return CopilotConfigService(
        repository=CopilotConfigRepository(root=copilot_root),
        mapper=CopilotMCPMapper(),
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


def test_workspace_config_repository_has_bundle_rules(tmp_path: Path) -> None:
    ws_root = tmp_path / "ws-config"
    bundle_dir = ws_root / "rules" / "python-style"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "meta.yaml").write_text(
        "spec_version: v1\nkind: rule\ndescription: Python style\n",
        encoding="utf-8",
    )
    (bundle_dir / "prompt.md").write_text("Use type hints.\n", encoding="utf-8")
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


# --- Workspace rules files ---


def test_workspace_rules_file_planned_for_workspace_root_only(
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
    (ws_config / "rules").mkdir(parents=True, exist_ok=True)
    (ws_config / "rules" / "shared.md").write_text("rules", encoding="utf-8")

    plan = SyncPlanner(
        core=core, app_services=[_opencode_service(core, opencode_root)]
    ).build()

    rules_actions = [
        a
        for a in plan.actions
        if a.kind == ActionKind.WRITE_TEXT and a.scope == "rules"
    ]
    assert len(rules_actions) == 1
    assert all(a.workspace == "myws" for a in rules_actions)
    assert all(a.app == "workspace" for a in rules_actions)
    assert rules_actions[0].path == workspace_root / AGENTS_FILENAME


def test_workspace_rules_file_planned_for_cursor(
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
    (ws_config / "rules").mkdir(parents=True, exist_ok=True)
    (ws_config / "rules" / "shared.md").write_text("rules", encoding="utf-8")

    cursor_root = tmp_path / ".cursor"
    plan = SyncPlanner(core=core, app_services=[_cursor_service(cursor_root)]).build()

    rules_actions = [
        a
        for a in plan.actions
        if a.kind == ActionKind.WRITE_TEXT and a.scope == "rules"
    ]
    assert len(rules_actions) == 1
    assert rules_actions[0].path == workspace_root / AGENTS_FILENAME
    assert not any(
        a.scope is not None and a.scope.startswith("ws:cursor:") for a in plan.actions
    )


# --- Workspace MCP config sync ---


def test_workspace_mcp_sync_writes_cursor_workspace_outputs(
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

    actions = {
        action.scope: action
        for action in plan.actions
        if action.kind == ActionKind.WRITE_JSON
    }
    assert actions["ws:cursor:workspace_root_mcp"].path == (
        workspace_root / ".cursor" / "mcp.json"
    )
    assert actions["ws:cursor:repo_mcp"].path == (
        workspace_root / "repo-a" / ".cursor" / "mcp.json"
    )
    assert (
        actions["ws:cursor:workspace_root_mcp"].payload["mcpServers"]["test-server"][
            "url"
        ]
        == "https://test.example.com/mcp"
    )
    assert not any(ws_config in action.path.parents for action in plan.actions)


def test_workspace_plan_never_writes_generated_app_dirs_to_source_of_truth(
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
    (ws_config / "skills" / "my-skill").mkdir(parents=True)
    (ws_config / "skills" / "my-skill" / "SKILL.md").write_text("s", encoding="utf-8")
    (ws_config / "agents").mkdir(parents=True)
    (ws_config / "agents" / "planner.md").write_text(
        "---\ndescription: Plan repository changes\n---\n\na",
        encoding="utf-8",
    )

    plan = SyncPlanner(
        core=core,
        app_services=[
            _codex_service(tmp_path / ".codex"),
            _cursor_service(tmp_path / ".cursor"),
            _opencode_service(core, tmp_path / ".config" / "opencode"),
        ],
    ).build()

    generated_source_paths = [
        action.path
        for action in plan.actions
        if action.path == ws_config or ws_config in action.path.parents
    ]
    assert generated_source_paths == []

    result = SyncExecutor(core=core).execute(plan)
    assert result[1] == 0
    assert not (ws_config / ".codex").exists()
    assert not (ws_config / ".cursor").exists()
    assert not (ws_config / ".opencode").exists()


def test_workspace_opencode_config_includes_workspace_agents_file(
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
    (ws_config / "rules").mkdir(parents=True, exist_ok=True)
    (ws_config / "rules" / "shared.md").write_text("rules", encoding="utf-8")

    opencode_root = tmp_path / ".config" / "opencode"
    plan = SyncPlanner(
        core=core, app_services=[_opencode_service(core, opencode_root)]
    ).build()

    config_actions = [
        a
        for a in plan.actions
        if a.app == "workspace"
        and a.kind == ActionKind.WRITE_JSON
        and a.scope in {"ws:opencode:workspace_root_mcp", "ws:opencode:repo_mcp"}
    ]
    assert len(config_actions) == 2
    assert {action.path for action in config_actions} == {
        workspace_root / "opencode.json",
        workspace_root / "repo-a" / "opencode.json",
    }
    assert all(
        isinstance(action.payload, dict)
        and action.payload["instructions"] == [str(workspace_root / AGENTS_FILENAME)]
        for action in config_actions
    )


def test_workspace_opencode_config_migrates_legacy_project_config(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    write_json,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    repo = workspace_root / "repo-a"
    (repo / ".git").mkdir(parents=True)

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    (ws_config / "rules").mkdir(parents=True, exist_ok=True)
    (ws_config / "rules" / "shared.md").write_text("rules", encoding="utf-8")

    write_json(
        workspace_root / ".opencode" / "opencode.json",
        {"username": "workspace-user"},
    )
    write_json(repo / ".opencode" / "opencode.json", {"share": "manual"})

    opencode_root = tmp_path / ".config" / "opencode"
    plan = SyncPlanner(
        core=core, app_services=[_opencode_service(core, opencode_root)]
    ).build()

    payloads = {
        action.path: action.payload
        for action in plan.actions
        if action.app == "workspace"
        and action.kind == ActionKind.WRITE_JSON
        and action.scope in {"ws:opencode:workspace_root_mcp", "ws:opencode:repo_mcp"}
    }

    assert payloads[workspace_root / "opencode.json"]["username"] == "workspace-user"
    assert payloads[repo / "opencode.json"]["share"] == "manual"
    assert payloads[workspace_root / "opencode.json"]["instructions"] == [
        str(workspace_root / AGENTS_FILENAME)
    ]
    assert payloads[repo / "opencode.json"]["instructions"] == [
        str(workspace_root / AGENTS_FILENAME)
    ]


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

    mcp_actions = sorted(
        [
            a
            for a in plan.actions
            if a.app == "workspace"
            and a.kind == ActionKind.WRITE_TEXT
            and a.scope in {"ws:codex:workspace_root_mcp", "ws:codex:repo_mcp"}
        ],
        key=lambda action: str(action.path),
    )
    assert [action.path for action in mcp_actions] == [
        workspace_root / ".codex" / "config.toml",
        workspace_root / "repo-a" / ".codex" / "config.toml",
    ]


def test_workspace_mcp_sync_respects_targeted_server_keys(
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
        {
            "mcpServers": {
                "@opencode-playwright": {"command": "npx", "args": ["playwright"]},
                "!codex-shared": {"url": "https://example.com/mcp"},
                "all-apps": {"command": "uvx", "args": ["demo"]},
            }
        },
    )

    plan = SyncPlanner(
        core=core,
        app_services=[
            _codex_service(tmp_path / ".codex"),
            _cursor_service(tmp_path / ".cursor"),
            _opencode_service(core, tmp_path / ".config" / "opencode"),
        ],
    ).build()

    root_mcp = {
        action.scope: action
        for action in plan.actions
        if action.scope
        in {
            "ws:codex:workspace_root_mcp",
            "ws:opencode:workspace_root_mcp",
        }
    }

    opencode_payload = root_mcp["ws:opencode:workspace_root_mcp"].payload
    codex_payload = tomllib.loads(root_mcp["ws:codex:workspace_root_mcp"].payload)
    cursor_payload = next(
        action.payload
        for action in plan.actions
        if action.scope == "ws:cursor:workspace_root_mcp"
    )
    assert set(opencode_payload["mcp"]) == {"playwright", "shared", "all-apps"}
    assert set(codex_payload["mcp_servers"]) == {"all-apps"}
    assert set(cursor_payload["mcpServers"]) == {"shared", "all-apps"}


def test_workspace_rules_sync_to_codex_repo_override_and_git_exclude(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    repo = workspace_root / "repo-a"
    (repo / ".git" / "info").mkdir(parents=True)
    (repo / AGENTS_FILENAME).write_text("repo rules\n", encoding="utf-8")

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    (ws_config / AGENTS_FILENAME).write_text("workspace rules\n", encoding="utf-8")

    codex_root = tmp_path / ".codex"
    plan = SyncPlanner(core=core, app_services=[_codex_service(codex_root)]).build()

    override_actions = [
        a
        for a in plan.actions
        if a.kind == ActionKind.WRITE_TEXT
        and a.scope == "ws:codex:repo_agents_override"
    ]
    assert len(override_actions) == 1
    assert override_actions[0].path == repo / CODEX_AGENTS_OVERRIDE_FILENAME
    assert override_actions[0].payload == "workspace rules\n"

    applied, failed, failures = SyncExecutor(core=core).execute(plan)

    assert failed == 0
    assert failures == []
    assert applied > 0
    assert (repo / AGENTS_FILENAME).read_text(encoding="utf-8") == "repo rules\n"
    assert (repo / CODEX_AGENTS_OVERRIDE_FILENAME).read_text(
        encoding="utf-8"
    ) == "workspace rules\n"
    exclude = repo / ".git" / "info" / "exclude"
    assert CODEX_AGENTS_OVERRIDE_FILENAME in exclude.read_text(encoding="utf-8")


def test_workspace_rules_sync_to_claude_local_memory_preserves_committed_claude(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    repo = workspace_root / "repo-a"
    (repo / ".git" / "info").mkdir(parents=True)
    (repo / "CLAUDE.md").write_text("tracked claude memory\n", encoding="utf-8")

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    (ws_config / AGENTS_FILENAME).write_text("workspace rules\n", encoding="utf-8")

    plan = SyncPlanner(
        core=core,
        app_services=[_claude_service(tmp_path / ".claude")],
    ).build()

    memory_actions = {
        a.scope: a
        for a in plan.actions
        if a.kind == ActionKind.WRITE_TEXT
        and a.scope
        in {
            "ws:claude:workspace_memory",
            "ws:claude:repo_memory",
        }
    }
    assert memory_actions["ws:claude:workspace_memory"].path == (
        workspace_root / CLAUDE_LOCAL_FILENAME
    )
    assert memory_actions["ws:claude:repo_memory"].path == (
        repo / CLAUDE_LOCAL_FILENAME
    )

    applied, failed, failures = SyncExecutor(core=core).execute(plan)

    assert failed == 0
    assert failures == []
    assert applied > 0
    assert (repo / "CLAUDE.md").read_text(encoding="utf-8") == (
        "tracked claude memory\n"
    )
    assert (repo / CLAUDE_LOCAL_FILENAME).read_text(encoding="utf-8") == (
        "workspace rules\n"
    )


def test_claude_owned_workspace_memory_conflict_fails_apply(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    repo = workspace_root / "repo-a"
    (repo / ".git").mkdir(parents=True)
    (repo / CLAUDE_LOCAL_FILENAME).write_text("user local memory\n", encoding="utf-8")

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    (ws_config / AGENTS_FILENAME).write_text("workspace rules\n", encoding="utf-8")

    plan = SyncPlanner(
        core=core,
        app_services=[_claude_service(tmp_path / ".claude")],
    ).build()

    repo_memory = next(a for a in plan.actions if a.scope == "ws:claude:repo_memory")
    assert repo_memory.status == ActionStatus.CONFLICT

    applied, failed, failures = SyncExecutor(core=core).execute(plan)

    assert applied == 0
    assert failed == 1
    assert failures == [
        f"Conflict (not overwritten): {repo / CLAUDE_LOCAL_FILENAME} "
        "(non-managed path exists)"
    ]
    assert (repo / CLAUDE_LOCAL_FILENAME).read_text(encoding="utf-8") == (
        "user local memory\n"
    )


def test_codex_owned_workspace_override_conflicts_with_unmanaged_file(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    repo = workspace_root / "repo-a"
    (repo / ".git").mkdir(parents=True)
    override = repo / CODEX_AGENTS_OVERRIDE_FILENAME
    override.write_text("user override\n", encoding="utf-8")

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    (ws_config / AGENTS_FILENAME).write_text("workspace rules\n", encoding="utf-8")

    plan = SyncPlanner(
        core=core, app_services=[_codex_service(tmp_path / ".codex")]
    ).build()

    override_action = next(action for action in plan.actions if action.path == override)
    assert override_action.status == ActionStatus.CONFLICT

    applied, failed, failures = SyncExecutor(core=core).execute(plan)

    assert applied == 0
    assert failed == 1
    assert failures == [
        f"Conflict (not overwritten): {override} (non-managed path exists)"
    ]
    assert override.read_text(encoding="utf-8") == "user override\n"


def test_codex_owned_workspace_override_updates_managed_file(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    repo = workspace_root / "repo-a"
    (repo / ".git").mkdir(parents=True)
    override = repo / CODEX_AGENTS_OVERRIDE_FILENAME
    override.write_text("old generated override\n", encoding="utf-8")

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    (ws_config / AGENTS_FILENAME).write_text("workspace rules\n", encoding="utf-8")
    WorkspaceConfigRepository(root=ws_config).save_state(
        {"managed_paths": {"ws:codex:repo_agents_override": [str(override)]}}
    )

    plan = SyncPlanner(
        core=core, app_services=[_codex_service(tmp_path / ".codex")]
    ).build()

    override_action = next(action for action in plan.actions if action.path == override)
    assert override_action.status == ActionStatus.UPDATE

    _applied, failed, failures = SyncExecutor(core=core).execute(plan)

    assert failed == 0
    assert failures == []
    assert override.read_text(encoding="utf-8") == "workspace rules\n"


def test_workspace_claude_mcp_merges_project_entries_into_home_config(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    write_json,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    repo = workspace_root / "repo-a"
    (repo / ".git").mkdir(parents=True)

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    write_json(
        ws_config / "mcp.base.json",
        {"mcpServers": {"ws-server": {"url": "https://example.com/mcp"}}},
    )

    plan = SyncPlanner(
        core=core,
        app_services=[_claude_service(tmp_path / ".claude")],
    ).build()

    config_actions = [
        a
        for a in plan.actions
        if a.app == "claude" and a.path == tmp_path / ".claude.json"
    ]
    assert len(config_actions) == 1
    payload = config_actions[0].payload
    assert payload["projects"][str(workspace_root.resolve())]["mcpServers"] == {
        "ws-server": {"type": "http", "url": "https://example.com/mcp"}
    }
    assert payload["projects"][str(repo.resolve())]["mcpServers"] == {
        "ws-server": {"type": "http", "url": "https://example.com/mcp"}
    }


def test_workspace_targeted_plan_does_not_cleanup_other_app_scopes(
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

    stale_codex_link = workspace_root / "repo-a" / ".codex" / "config.toml"
    stale_codex_link.parent.mkdir(parents=True, exist_ok=True)
    codex_source = ws_config / ".codex" / "config.toml"
    codex_source.parent.mkdir(parents=True, exist_ok=True)
    codex_source.write_text("codex", encoding="utf-8")
    stale_codex_link.symlink_to(codex_source)

    WorkspaceConfigRepository(root=ws_config).save_state(
        {"managed_links": {"ws:codex:repo_mcp": [str(stale_codex_link)]}}
    )

    opencode_root = tmp_path / ".config" / "opencode"
    plan = SyncPlanner(
        core=core, app_services=[_opencode_service(core, opencode_root)]
    ).build()

    stale_cleanup_paths = {
        action.path
        for action in plan.actions
        if action.kind == ActionKind.REMOVE_SYMLINK
    }
    assert stale_codex_link not in stale_cleanup_paths


def test_workspace_targeted_plan_cleans_stale_cursor_workspace_outputs(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    repo = workspace_root / "repo-a"
    (repo / ".git").mkdir(parents=True)

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    stale_mcp = repo / ".cursor" / "mcp.json"
    stale_mcp.parent.mkdir(parents=True, exist_ok=True)
    stale_mcp.write_text('{"mcpServers": {}}\n', encoding="utf-8")

    stale_agent = repo / ".cursor" / "agents" / "old.md"
    stale_agent.parent.mkdir(parents=True, exist_ok=True)
    stale_agent_source = ws_config / "old-agent.md"
    stale_agent_source.write_text("old", encoding="utf-8")
    stale_agent.symlink_to(stale_agent_source)

    ws_repo = WorkspaceConfigRepository(root=ws_config)
    ws_repo.save_state(
        {
            "managed_paths": {"ws:cursor:repo_mcp": [str(stale_mcp)]},
            "managed_links": {"ws:cursor:repo_agents_dir": [str(stale_agent)]},
        }
    )

    cursor_root = tmp_path / ".cursor"
    plan = SyncPlanner(core=core, app_services=[_cursor_service(cursor_root)]).build()

    remove_file_paths = {
        action.path for action in plan.actions if action.kind == ActionKind.REMOVE_FILE
    }
    remove_link_paths = {
        action.path
        for action in plan.actions
        if action.kind == ActionKind.REMOVE_SYMLINK
    }
    assert stale_mcp in remove_file_paths
    assert stale_agent in remove_link_paths

    applied, failed, failures = SyncExecutor(core=core).execute(plan)
    assert failed == 0
    assert failures == []
    assert applied > 0
    assert not stale_mcp.exists()
    assert not stale_agent.exists()
    state = ws_repo.load_state()
    assert "ws:cursor:repo_mcp" not in state["managed_paths"]
    assert "ws:cursor:repo_agents_dir" not in state["managed_links"]


def test_workspace_plan_skips_legacy_link_cleanup_when_same_path_is_now_generated(
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

    stale_codex_file = workspace_root / "repo-a" / ".codex" / "config.toml"
    stale_codex_file.parent.mkdir(parents=True, exist_ok=True)
    stale_codex_file.write_text('model = "gpt-5"\n', encoding="utf-8")

    WorkspaceConfigRepository(root=ws_config).save_state(
        {"managed_links": {"ws:codex:repo_mcp": [str(stale_codex_file)]}}
    )

    codex_root = tmp_path / ".codex"
    plan = SyncPlanner(core=core, app_services=[_codex_service(codex_root)]).build()

    stale_cleanup_paths = {
        action.path
        for action in plan.actions
        if action.kind == ActionKind.REMOVE_SYMLINK
    }
    assert stale_codex_file not in stale_cleanup_paths

    repo_actions = [
        action
        for action in plan.actions
        if action.kind == ActionKind.WRITE_TEXT and action.scope == "ws:codex:repo_mcp"
    ]
    assert len(repo_actions) == 1
    assert repo_actions[0].path == stale_codex_file
    assert repo_actions[0].status in {ActionStatus.UPDATE, ActionStatus.NOOP}


# --- Workspace skill symlinks ---


def test_workspace_skills_sync_writes_cursor_workspace_outputs(
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

    skill_actions = [
        action
        for action in plan.actions
        if action.kind == ActionKind.WRITE_TEXT
        and action.scope
        in {"ws:cursor:workspace_root_skills_dir", "ws:cursor:repo_skills_dir"}
    ]
    assert {action.path for action in skill_actions} == {
        workspace_root / ".cursor" / "skills" / "my-skill" / "SKILL.md",
        workspace_root / "repo-a" / ".cursor" / "skills" / "my-skill" / "SKILL.md",
    }


def test_workspace_skills_sync_codex_to_agents_skills(
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

    codex_root = tmp_path / ".codex-global"
    plan = SyncPlanner(core=core, app_services=[_codex_service(codex_root)]).build()

    workspace_skills = [
        a for a in plan.actions if a.scope == "ws:codex:workspace_root_skills_dir"
    ]
    repo_skills = [a for a in plan.actions if a.scope == "ws:codex:repo_skills_dir"]

    assert len(workspace_skills) == 1
    assert (
        workspace_skills[0].path
        == workspace_root / ".agents" / "skills" / "my-skill" / "SKILL.md"
    )
    assert len(repo_skills) == 1
    assert (
        repo_skills[0].path
        == workspace_root / "repo-a" / ".agents" / "skills" / "my-skill" / "SKILL.md"
    )


def test_workspace_skills_and_agents_sync_claude_owned_paths(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    repo = workspace_root / "repo-a"
    (repo / ".git").mkdir(parents=True)

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    (ws_config / "skills" / "my-skill").mkdir(parents=True)
    (ws_config / "skills" / "my-skill" / "SKILL.md").write_text("s", encoding="utf-8")
    (ws_config / "agents").mkdir(parents=True)
    (ws_config / "agents" / "planner.md").write_text("a", encoding="utf-8")

    plan = SyncPlanner(
        core=core,
        app_services=[_claude_service(tmp_path / ".claude")],
    ).build()

    workspace_skills = [
        a for a in plan.actions if a.scope == "ws:claude:workspace_root_skills_dir"
    ]
    repo_skills = [a for a in plan.actions if a.scope == "ws:claude:repo_skills_dir"]
    workspace_agents = [
        a for a in plan.actions if a.scope == "ws:claude:workspace_root_agents_dir"
    ]
    repo_agents = [a for a in plan.actions if a.scope == "ws:claude:repo_agents_dir"]

    assert workspace_skills[0].path == (
        workspace_root / ".claude" / "skills" / "my-skill" / "SKILL.md"
    )
    assert repo_skills[0].path == (
        repo / ".claude" / "skills" / "my-skill" / "SKILL.md"
    )
    assert workspace_agents[0].path == (
        workspace_root / ".claude" / "agents" / "planner.md"
    )
    assert repo_agents[0].path == repo / ".claude" / "agents" / "planner.md"


def test_workspace_claude_unmanaged_existing_asset_conflict_fails_apply(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    repo = workspace_root / "repo-a"
    (repo / ".git").mkdir(parents=True)
    unmanaged = repo / ".claude" / "skills" / "my-skill" / "SKILL.md"
    unmanaged.parent.mkdir(parents=True)
    unmanaged.write_text("user skill\n", encoding="utf-8")

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    (ws_config / "skills" / "my-skill").mkdir(parents=True)
    (ws_config / "skills" / "my-skill" / "SKILL.md").write_text("s", encoding="utf-8")

    plan = SyncPlanner(
        core=core,
        app_services=[_claude_service(tmp_path / ".claude")],
    ).build()

    repo_skill = next(a for a in plan.actions if a.path == unmanaged)
    assert repo_skill.status == ActionStatus.CONFLICT

    applied, failed, failures = SyncExecutor(core=core).execute(plan)

    assert applied == 0
    assert failed == 1
    assert failures == [
        f"Conflict (not overwritten): {unmanaged} (non-managed path exists)"
    ]
    assert unmanaged.read_text(encoding="utf-8") == "user skill\n"


def test_workspace_copilot_unmanaged_existing_asset_conflict_fails_apply(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    repo = workspace_root / "repo-a"
    (repo / ".git").mkdir(parents=True)
    unmanaged = repo / ".github" / "skills" / "my-skill" / "SKILL.md"
    unmanaged.parent.mkdir(parents=True)
    unmanaged.write_text("user skill\n", encoding="utf-8")

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    (ws_config / "skills" / "my-skill").mkdir(parents=True)
    (ws_config / "skills" / "my-skill" / "SKILL.md").write_text(
        "---\nname: my-skill\ndescription: Workspace skill\n---\n\ns\n",
        encoding="utf-8",
    )

    plan = SyncPlanner(
        core=core,
        app_services=[_copilot_service(tmp_path / ".copilot")],
    ).build()

    repo_skill = next(a for a in plan.actions if a.path == unmanaged)
    assert repo_skill.status == ActionStatus.CONFLICT

    applied, failed, failures = SyncExecutor(core=core).execute(plan)

    assert applied == 0
    assert failed == 1
    assert failures == [
        f"Conflict (not overwritten): {unmanaged} (non-managed path exists)"
    ]
    assert unmanaged.read_text(encoding="utf-8") == "user skill\n"


def test_workspace_compiled_sync_replaces_legacy_skill_symlink(
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

    legacy_target = tmp_path / "legacy-skills"
    legacy_target.mkdir()
    legacy_link = workspace_root / ".agents" / "skills"
    legacy_link.parent.mkdir(parents=True, exist_ok=True)
    legacy_link.symlink_to(legacy_target)
    WorkspaceConfigRepository(root=ws_config).save_state(
        {"managed_links": {"ws:codex:workspace_root_skills_dir": [str(legacy_link)]}}
    )

    codex_root = tmp_path / ".codex-global"
    plan = SyncPlanner(core=core, app_services=[_codex_service(codex_root)]).build()

    remove_actions = [
        action
        for action in plan.actions
        if action.kind == ActionKind.REMOVE_SYMLINK and action.path == legacy_link
    ]
    assert len(remove_actions) == 1
    assert remove_actions[0].status == ActionStatus.REMOVE

    skill_actions = [
        action
        for action in plan.actions
        if action.scope == "ws:codex:workspace_root_skills_dir"
        and action.kind == ActionKind.WRITE_TEXT
    ]
    assert len(skill_actions) == 1
    assert skill_actions[0].status == ActionStatus.CREATE

    applied, failed, failures = SyncExecutor(core=core).execute(plan)

    assert failed == 0
    assert failures == []
    assert applied > 0
    assert legacy_link.is_dir()
    assert not legacy_link.is_symlink()
    assert (legacy_link / "my-skill" / "SKILL.md").is_file()


# --- Workspace agent symlinks ---


def test_workspace_agents_sync_writes_cursor_workspace_outputs(
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

    agent_actions = [
        action
        for action in plan.actions
        if action.kind == ActionKind.WRITE_TEXT
        and action.scope
        in {"ws:cursor:workspace_root_agents_dir", "ws:cursor:repo_agents_dir"}
    ]
    assert {action.path for action in agent_actions} == {
        workspace_root / ".cursor" / "agents" / "planner.md",
        workspace_root / "repo-a" / ".cursor" / "agents" / "planner.md",
    }


def test_workspace_cursor_does_not_render_global_mcp_when_workspace_has_no_mcp_file(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    write_json,
) -> None:
    """Workspace Cursor config should not mirror global MCP into project config."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "repo-a" / ".git").mkdir(parents=True)

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    write_json(
        core_root / "config" / "mcp.base.json",
        {
            "mcpServers": {
                "global": {"command": "npx", "args": ["-y", "global-server"]},
            }
        },
    )

    cursor_root = tmp_path / ".cursor"
    plan = SyncPlanner(core=core, app_services=[_cursor_service(cursor_root)]).build()

    root_mcp = [a for a in plan.actions if a.scope == "ws:cursor:workspace_root_mcp"]
    repo_mcp = [a for a in plan.actions if a.scope == "ws:cursor:repo_mcp"]
    assert root_mcp == []
    assert repo_mcp == []


def test_workspace_cursor_subrepo_propagation_enabled_for_mcp(
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
    assert any(
        action.scope == "ws:cursor:workspace_root_mcp" for action in plan.actions
    )
    assert any(action.scope == "ws:cursor:repo_mcp" for action in plan.actions)


def test_workspace_agents_synced_to_codex(
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

    source_render_actions = [
        a
        for a in plan.actions
        if a.kind == ActionKind.WRITE_TEXT and a.scope == "ws:codex:agents_entries"
    ]
    assert source_render_actions == []

    repo_actions = [
        a
        for a in plan.actions
        if a.kind == ActionKind.WRITE_TEXT and a.scope == "ws:codex:repo_agents_dir"
    ]
    assert len(repo_actions) == 1
    assert (
        repo_actions[0].path
        == workspace_root / "repo-a" / ".codex" / "agents" / "planner.toml"
    )

    workspace_config_actions = [
        a
        for a in plan.actions
        if a.kind == ActionKind.WRITE_TEXT and a.scope == "ws:codex:workspace_root_mcp"
    ]
    assert len(workspace_config_actions) == 1
    workspace_config_payload = tomllib.loads(workspace_config_actions[0].payload)
    assert workspace_config_actions[0].path == workspace_root / ".codex" / "config.toml"
    assert workspace_config_payload["agents"]["planner"] == {
        "description": "planner",
        "config_file": "agents/planner.toml",
    }

    repo_config_actions = [
        a
        for a in plan.actions
        if a.kind == ActionKind.WRITE_TEXT and a.scope == "ws:codex:repo_mcp"
    ]
    assert len(repo_config_actions) == 1
    repo_config_payload = tomllib.loads(repo_config_actions[0].payload)
    assert (
        repo_config_actions[0].path
        == workspace_root / "repo-a" / ".codex" / "config.toml"
    )
    assert repo_config_payload["agents"]["planner"] == {
        "description": "planner",
        "config_file": "agents/planner.toml",
    }


def test_workspace_agents_synced_to_opencode(
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
    (ws_config / "agents" / "planner.md").write_text(
        "---\n"
        "description: Plan repository changes\n"
        "model: openai/gpt-5\n"
        "model_reasoning_effort: high\n"
        "---\n"
        "\n"
        "Review carefully.\n",
        encoding="utf-8",
    )

    opencode_root = tmp_path / ".config" / "opencode"
    plan = SyncPlanner(
        core=core, app_services=[_opencode_service(core, opencode_root)]
    ).build()

    source_render_actions = [
        a
        for a in plan.actions
        if a.kind == ActionKind.WRITE_TEXT and a.scope == "ws:opencode:agents_entries"
    ]
    assert source_render_actions == []

    repo_actions = [
        a
        for a in plan.actions
        if a.kind == ActionKind.WRITE_TEXT and a.scope == "ws:opencode:repo_agents_dir"
    ]
    assert len(repo_actions) == 1
    assert (
        repo_actions[0].path
        == workspace_root / "repo-a" / ".opencode" / "agents" / "planner.md"
    )
    assert "reasoningEffort: high" in repo_actions[0].payload


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
    (ws_config / "rules").mkdir(parents=True, exist_ok=True)
    (ws_config / "rules" / "shared.md").write_text("rules", encoding="utf-8")

    codex_root = tmp_path / ".codex"
    plan = SyncPlanner(core=core, app_services=[_codex_service(codex_root)]).build()

    applied, failed, failures = SyncExecutor(core=core).execute(plan)
    assert failed == 0

    # Workspace state persisted to workspace state file.
    ws_repo = WorkspaceConfigRepository(root=ws_config)
    ws_state = ws_repo.load_state()
    managed = ws_state["managed_paths"]
    assert "rules" in managed
    assert len(managed["rules"]) == 1

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
    (ws_config / "rules").mkdir(parents=True, exist_ok=True)
    (ws_config / "rules" / "shared.md").write_text("workspace rules", encoding="utf-8")
    write_json(
        ws_config / "mcp.base.json",
        {"mcpServers": {"ws-server": {"url": "https://ws.example.com/mcp"}}},
    )
    (ws_config / "skills" / "ws-skill").mkdir(parents=True)
    (ws_config / "skills" / "ws-skill" / "SKILL.md").write_text("s", encoding="utf-8")
    (ws_config / "agents").mkdir(parents=True)
    (ws_config / "agents" / "ws-agent.md").write_text(
        "---\ndescription: Run workspace automation\n---\n\na",
        encoding="utf-8",
    )

    plan = SyncPlanner(
        core=core,
        app_services=[
            _opencode_service(core, opencode_root),
        ],
    ).build()

    assert plan.errors == []

    applied, failed, failures = SyncExecutor(core=core).execute(plan)
    assert failed == 0
    assert failures == []
    assert applied > 0

    workspace_link = workspace_root / AGENTS_FILENAME
    assert workspace_link.is_file()
    assert not workspace_link.is_symlink()
    assert (
        workspace_link.read_text(encoding="utf-8") == "## shared\n\nworkspace rules\n"
    )

    for repo_name in ["repo-a", "repo-b"]:
        link = workspace_root / repo_name / AGENTS_FILENAME
        assert not link.exists()

    # This plan omits Cursor; no workspace .cursor outputs.
    assert not (ws_config / ".cursor").exists()
    assert not (workspace_root / ".cursor").exists()
    for repo_name in ["repo-a", "repo-b"]:
        assert not (workspace_root / repo_name / ".cursor").exists()


# --- Stale workspace link cleanup ---


def test_workspace_rules_not_linked_for_cursor(
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
    (ws_config / "rules").mkdir(parents=True, exist_ok=True)
    (ws_config / "rules" / "shared.md").write_text("rules", encoding="utf-8")

    cursor_root = tmp_path / ".cursor"
    plan = SyncPlanner(core=core, app_services=[_cursor_service(cursor_root)]).build()

    SyncExecutor(core=core).execute(plan)
    assert not (workspace_root / "repo-a" / ".cursor" / "rules").exists()


def test_workspace_stale_skills_cleanup_when_skills_removed_for_codex(
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

    codex_root = tmp_path / ".codex"
    plan = SyncPlanner(core=core, app_services=[_codex_service(codex_root)]).build()

    SyncExecutor(core=core).execute(plan)
    skill_file = (
        workspace_root / "repo-a" / ".agents" / "skills" / "my-skill" / "SKILL.md"
    )
    assert skill_file.is_file()

    # Verify state was persisted with workspace scopes
    ws_repo = WorkspaceConfigRepository(root=ws_config)
    state = ws_repo.load_state()
    assert "ws:codex:repo_skills_dir" in state["managed_paths"]

    # Remove all skills from workspace config
    import shutil

    shutil.rmtree(ws_config / "skills")

    plan2 = SyncPlanner(core=core, app_services=[_codex_service(codex_root)]).build()

    # Should have remove actions for stale generated repo skill files
    remove_actions = [
        a
        for a in plan2.actions
        if a.kind == ActionKind.REMOVE_FILE and a.scope == "ws:codex:repo_skills_dir"
    ]
    assert len(remove_actions) == 1

    SyncExecutor(core=core).execute(plan2)
    assert not skill_file.exists()


def test_workspace_stale_skills_cleanup_when_skills_removed_for_claude(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    repo = workspace_root / "repo-a"
    (repo / ".git").mkdir(parents=True)

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    (ws_config / "skills" / "my-skill").mkdir(parents=True)
    (ws_config / "skills" / "my-skill" / "SKILL.md").write_text("s", encoding="utf-8")

    plan = SyncPlanner(
        core=core,
        app_services=[_claude_service(tmp_path / ".claude")],
    ).build()

    SyncExecutor(core=core).execute(plan)
    skill_file = repo / ".claude" / "skills" / "my-skill" / "SKILL.md"
    assert skill_file.is_file()

    ws_repo = WorkspaceConfigRepository(root=ws_config)
    state = ws_repo.load_state()
    assert "ws:claude:repo_skills_dir" in state["managed_paths"]

    import shutil

    shutil.rmtree(ws_config / "skills")

    plan2 = SyncPlanner(
        core=core,
        app_services=[_claude_service(tmp_path / ".claude")],
    ).build()

    remove_actions = [
        a
        for a in plan2.actions
        if a.kind == ActionKind.REMOVE_FILE and a.scope == "ws:claude:repo_skills_dir"
    ]
    assert len(remove_actions) == 1

    SyncExecutor(core=core).execute(plan2)
    assert not skill_file.exists()


def test_workspace_stale_skills_cleanup_when_skills_removed_for_copilot(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    repo = workspace_root / "repo-a"
    (repo / ".git").mkdir(parents=True)

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)

    ws_config = core.workspace_config_dir("myws")
    (ws_config / "skills" / "my-skill").mkdir(parents=True)
    (ws_config / "skills" / "my-skill" / "SKILL.md").write_text(
        "---\nname: my-skill\ndescription: Workspace skill\n---\n\ns\n",
        encoding="utf-8",
    )

    plan = SyncPlanner(
        core=core,
        app_services=[_copilot_service(tmp_path / ".copilot")],
    ).build()

    SyncExecutor(core=core).execute(plan)
    skill_file = repo / ".github" / "skills" / "my-skill" / "SKILL.md"
    assert skill_file.is_file()

    ws_repo = WorkspaceConfigRepository(root=ws_config)
    state = ws_repo.load_state()
    assert "ws:copilot:repo_skills_dir" in state["managed_paths"]

    import shutil

    shutil.rmtree(ws_config / "skills")

    plan2 = SyncPlanner(
        core=core,
        app_services=[_copilot_service(tmp_path / ".copilot")],
    ).build()

    remove_actions = [
        a
        for a in plan2.actions
        if a.kind == ActionKind.REMOVE_FILE and a.scope == "ws:copilot:repo_skills_dir"
    ]
    assert len(remove_actions) == 1

    SyncExecutor(core=core).execute(plan2)
    assert not skill_file.exists()


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
