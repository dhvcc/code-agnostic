from pathlib import Path
import json

from code_agnostic.errors import InvalidJsonFormatError
from code_agnostic.constants import AGENTS_FILENAME
from code_agnostic.executor import SyncExecutor
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
from code_agnostic.models import ActionKind, ActionStatus
from code_agnostic.planner import SyncPlanner
from code_agnostic.core.repository import CoreRepository


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


def test_build_plan_and_apply_create_opencode_and_workspace_links(
    tmp_path: Path,
    core_root: Path,
    opencode_root: Path,
    write_json,
) -> None:
    workspace_root = tmp_path / "example-workspace"

    workspace_root.mkdir()
    (workspace_root / "shop-api" / ".git").mkdir(parents=True)
    (workspace_root / "shop-web" / ".git").mkdir(parents=True)

    write_json(
        core_root / "config" / "mcp.base.json",
        {
            "mcpServers": {
                "context7": {"url": "https://mcp.context7.com/mcp"},
                "sentry": {"command": "npx", "args": ["@sentry/mcp-server@latest"]},
            }
        },
    )
    write_json(
        core_root / "config" / "opencode.base.json",
        {
            "$schema": "https://opencode.ai/config.json",
            "instructions": ["/tmp/AGENTS.md"],
        },
    )

    (core_root / "skills" / "frontend-design").mkdir(parents=True)
    (core_root / "skills" / "frontend-design" / "SKILL.md").write_text(
        "skill", encoding="utf-8"
    )
    (core_root / "agents").mkdir(parents=True)
    (core_root / "agents" / "planner.md").write_text("agent", encoding="utf-8")

    core = CoreRepository(core_root)
    core.add_workspace("workspace-example", workspace_root)

    # Create workspace config with rules in workspace config dir
    ws_config_dir = core.workspace_config_dir("workspace-example")
    (ws_config_dir / "AGENTS.md").write_text("workspace rules", encoding="utf-8")

    opencode_config_path = opencode_root / "opencode.json"

    plan = SyncPlanner(
        core=core, app_services=[_opencode_service(core, opencode_root)]
    ).build()

    assert plan.errors == []
    assert any(
        action.kind == ActionKind.WRITE_JSON and action.path == opencode_config_path
        for action in plan.actions
    )
    workspace_targets = {
        str(workspace_root / "shop-api" / AGENTS_FILENAME),
        str(workspace_root / "shop-web" / AGENTS_FILENAME),
    }
    planned_workspace_targets = {
        str(action.path)
        for action in plan.actions
        if action.kind == ActionKind.SYMLINK
        and action.path.name == AGENTS_FILENAME
        and "example-workspace" in str(action.path)
    }
    assert workspace_targets.issubset(planned_workspace_targets)

    applied, failed, failures = SyncExecutor(core=core).execute(plan)

    assert failed == 0
    assert failures == []
    assert applied > 0

    opencode_config = json.loads(opencode_config_path.read_text(encoding="utf-8"))
    assert opencode_config["mcp"]["context7"] == {
        "type": "remote",
        "url": "https://mcp.context7.com/mcp",
    }
    assert opencode_config["mcp"]["sentry"] == {
        "type": "local",
        "command": ["npx", "@sentry/mcp-server@latest"],
    }

    for repo_name in ["shop-api", "shop-web"]:
        link_path = workspace_root / repo_name / AGENTS_FILENAME
        assert link_path.is_symlink()
        assert link_path.resolve() == (ws_config_dir / "AGENTS.md").resolve()

    # Workspace state is persisted in workspace state file
    from code_agnostic.core.workspace_repository import WorkspaceConfigRepository

    ws_repo = WorkspaceConfigRepository(root=ws_config_dir)
    ws_state = ws_repo.load_state()
    assert len(ws_state["managed_links"]["rules"]) == 2


def test_plan_marks_config_create_when_missing(
    minimal_shared_config: Path,
    core_root: Path,
    opencode_root: Path,
) -> None:
    core = CoreRepository(core_root)
    plan = SyncPlanner(
        core=core,
        app_services=[_opencode_service(core, opencode_root)],
    ).build()

    config_actions = [
        action for action in plan.actions if action.kind == ActionKind.WRITE_JSON
    ]
    assert len(config_actions) == 1
    assert config_actions[0].status == ActionStatus.CREATE


def test_plan_marks_config_update_when_existing_but_different(
    minimal_shared_config: Path,
    core_root: Path,
    opencode_root: Path,
) -> None:
    config_path = opencode_root / "opencode.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}\n", encoding="utf-8")

    core = CoreRepository(core_root)
    plan = SyncPlanner(
        core=core,
        app_services=[_opencode_service(core, opencode_root)],
    ).build()

    config_actions = [
        action for action in plan.actions if action.kind == ActionKind.WRITE_JSON
    ]
    assert len(config_actions) == 1
    assert config_actions[0].status == ActionStatus.UPDATE


def test_plan_marks_config_noop_when_already_synced(
    minimal_shared_config: Path,
    core_root: Path,
    opencode_root: Path,
) -> None:
    core = CoreRepository(core_root)
    first_plan = SyncPlanner(
        core=core,
        app_services=[_opencode_service(core, opencode_root)],
    ).build()
    payload = next(
        action.payload
        for action in first_plan.actions
        if action.kind == ActionKind.WRITE_JSON
    )

    config_path = opencode_root / "opencode.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    second_plan = SyncPlanner(
        core=core,
        app_services=[_opencode_service(core, opencode_root)],
    ).build()
    config_actions = [
        action for action in second_plan.actions if action.kind == ActionKind.WRITE_JSON
    ]
    assert len(config_actions) == 1
    assert config_actions[0].status == ActionStatus.NOOP


def test_plan_collects_invalid_opencode_json_as_error(
    minimal_shared_config: Path,
    core_root: Path,
    opencode_root: Path,
) -> None:
    config_path = opencode_root / "opencode.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{not-json", encoding="utf-8")

    core = CoreRepository(core_root)
    plan = SyncPlanner(
        core=core,
        app_services=[_opencode_service(core, opencode_root)],
    ).build()

    assert len(plan.errors) == 1
    assert isinstance(plan.errors[0], InvalidJsonFormatError)
    assert str(config_path) in str(plan.errors[0])


def test_plan_treats_empty_opencode_config_as_update(
    minimal_shared_config: Path,
    core_root: Path,
    opencode_root: Path,
) -> None:
    config_path = opencode_root / "opencode.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("", encoding="utf-8")

    core = CoreRepository(core_root)
    plan = SyncPlanner(
        core=core,
        app_services=[_opencode_service(core, opencode_root)],
    ).build()

    config_actions = [
        action for action in plan.actions if action.kind == ActionKind.WRITE_JSON
    ]
    assert len(config_actions) == 1
    assert config_actions[0].status == ActionStatus.UPDATE


def test_cursor_build_plan_includes_skill_symlinks(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    (core_root / "skills" / "my-skill").mkdir(parents=True)
    (core_root / "skills" / "my-skill" / "SKILL.md").write_text(
        "skill", encoding="utf-8"
    )

    core = CoreRepository(core_root)
    cursor_root = tmp_path / ".cursor"
    plan = SyncPlanner(core=core, app_services=[_cursor_service(cursor_root)]).build()

    skill_actions = [
        a
        for a in plan.actions
        if a.kind == ActionKind.SYMLINK and a.scope == "app:cursor:skills"
    ]
    assert len(skill_actions) == 1
    assert skill_actions[0].path == cursor_root / "skills" / "my-skill"
    assert skill_actions[0].status == ActionStatus.CREATE


def test_cursor_build_plan_includes_agent_symlinks(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    (core_root / "agents").mkdir(parents=True)
    (core_root / "agents" / "planner.md").write_text("agent", encoding="utf-8")

    core = CoreRepository(core_root)
    cursor_root = tmp_path / ".cursor"
    plan = SyncPlanner(core=core, app_services=[_cursor_service(cursor_root)]).build()

    agent_actions = [
        a
        for a in plan.actions
        if a.kind == ActionKind.SYMLINK and a.scope == "app:cursor:agents"
    ]
    assert len(agent_actions) == 1
    assert agent_actions[0].path == cursor_root / "agents" / "planner.md"
    assert agent_actions[0].status == ActionStatus.CREATE


def test_codex_build_plan_includes_skill_symlinks(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    (core_root / "skills" / "my-skill").mkdir(parents=True)
    (core_root / "skills" / "my-skill" / "SKILL.md").write_text(
        "skill", encoding="utf-8"
    )

    core = CoreRepository(core_root)
    codex_root = tmp_path / ".codex"
    plan = SyncPlanner(core=core, app_services=[_codex_service(codex_root)]).build()

    skill_actions = [
        a
        for a in plan.actions
        if a.kind == ActionKind.SYMLINK and a.scope == "app:codex:skills"
    ]
    assert len(skill_actions) == 1
    assert skill_actions[0].path == codex_root / "skills" / "my-skill"
    assert skill_actions[0].status == ActionStatus.CREATE


def test_codex_build_plan_has_no_agent_actions(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    (core_root / "agents").mkdir(parents=True)
    (core_root / "agents" / "planner.md").write_text("agent", encoding="utf-8")

    core = CoreRepository(core_root)
    codex_root = tmp_path / ".codex"
    plan = SyncPlanner(core=core, app_services=[_codex_service(codex_root)]).build()

    agent_actions = [
        a for a in plan.actions if a.scope and "agents" in a.scope and a.app == "codex"
    ]
    assert agent_actions == []
