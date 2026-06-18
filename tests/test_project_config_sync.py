"""Tests for project-level config sync."""

import shutil
from pathlib import Path

from code_agnostic.__main__ import cli
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
from code_agnostic.core.repository import CoreRepository
from code_agnostic.executor import SyncExecutor
from code_agnostic.models import ActionKind, ActionStatus, ProjectSyncStatus
from code_agnostic.planner import SyncPlanner
from code_agnostic.status import StatusService


def _codex_service(codex_root: Path) -> CodexConfigService:
    return CodexConfigService(
        repository=CodexConfigRepository(root=codex_root),
        mapper=CodexMCPMapper(),
        schema_repository=CodexSchemaRepository(),
    )


def _cursor_service(cursor_root: Path) -> CursorConfigService:
    return CursorConfigService(
        repository=CursorConfigRepository(root=cursor_root),
        mapper=CursorMCPMapper(),
        schema_repository=CursorSchemaRepository(),
    )


def _opencode_service(
    core: CoreRepository, opencode_root: Path
) -> OpenCodeConfigService:
    return OpenCodeConfigService(
        repository=OpenCodeConfigRepository(root=opencode_root),
        mapper=OpenCodeMCPMapper(),
        schema_repository=OpenCodeSchemaRepository(),
        base_config_path=core.opencode_base_path,
    )


def _register_project(
    core: CoreRepository,
    project_root: Path,
    write_json,
    *,
    name: str = "service-api",
) -> None:
    write_json(
        core.root / "config" / "projects.json",
        [{"name": name, "path": str(project_root)}],
    )


def _write_project_skill(core: CoreRepository, *, name: str = "service-api") -> None:
    skill = core.root / "projects" / name / "skills" / "project-tool" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: project-tool\ndescription: Project tool\n---\n\nUse project context.\n",
        encoding="utf-8",
    )


def test_project_skill_plan_targets_enabled_app_project_dirs(
    minimal_shared_config: Path,
    core_root: Path,
    opencode_root: Path,
    tmp_path: Path,
    write_json,
) -> None:
    project_root = tmp_path / "service-api"
    project_root.mkdir()
    core = CoreRepository(core_root)
    _register_project(core, project_root, write_json)
    _write_project_skill(core)

    plan = SyncPlanner(
        core=core,
        app_services=[
            _codex_service(tmp_path / ".codex"),
            _cursor_service(tmp_path / ".cursor"),
            _opencode_service(core, opencode_root),
        ],
    ).build()

    skill_actions = sorted(
        [
            action
            for action in plan.actions
            if action.kind == ActionKind.WRITE_TEXT
            and action.scope is not None
            and action.scope.startswith("project:")
        ],
        key=lambda action: str(action.path),
    )

    assert [action.path for action in skill_actions] == [
        project_root / ".agents" / "skills" / "project-tool" / "SKILL.md",
        project_root / ".cursor" / "skills" / "project-tool" / "SKILL.md",
        project_root / ".opencode" / "skills" / "project-tool" / "SKILL.md",
    ]
    assert {action.status for action in skill_actions} == {ActionStatus.CREATE}
    assert {action.app for action in skill_actions} == {"codex", "cursor", "opencode"}


def test_project_skill_apply_writes_project_local_outputs(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    write_json,
) -> None:
    project_root = tmp_path / "service-api"
    project_root.mkdir()
    core = CoreRepository(core_root)
    _register_project(core, project_root, write_json)
    _write_project_skill(core)

    plan = SyncPlanner(
        core=core,
        app_services=[
            _codex_service(tmp_path / ".codex"),
            _cursor_service(tmp_path / ".cursor"),
        ],
    ).build()

    applied, failed, failures = SyncExecutor(core=core).execute(plan)

    assert failed == 0
    assert failures == []
    assert applied > 0
    assert (project_root / ".agents" / "skills" / "project-tool" / "SKILL.md").exists()
    assert (project_root / ".cursor" / "skills" / "project-tool" / "SKILL.md").exists()
    assert (core.root / "projects" / "service-api" / ".sync-state.json").exists()
    assert not (core.root / ".sync-state.json").exists()


def test_project_status_reports_drift_and_synced_after_apply(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    write_json,
) -> None:
    project_root = tmp_path / "service-api"
    project_root.mkdir()
    core = CoreRepository(core_root)
    services = [_codex_service(tmp_path / ".codex")]
    _register_project(core, project_root, write_json)
    _write_project_skill(core)

    before = StatusService().build_project_status(core, services)
    assert before[0].status == ProjectSyncStatus.DRIFT
    assert "missing .agents/skills/project-tool/SKILL.md" in before[0].detail

    plan = SyncPlanner(core=core, app_services=services).build()
    applied, failed, failures = SyncExecutor(core=core).execute(plan)
    assert applied > 0
    assert failed == 0
    assert failures == []

    after = StatusService().build_project_status(core, services)
    assert after[0].status == ProjectSyncStatus.SYNCED
    assert after[0].detail == "project skills synced"

    target = project_root / ".agents" / "skills" / "project-tool" / "SKILL.md"
    target.write_text("manual edit\n", encoding="utf-8")
    drift = StatusService().build_project_status(core, services)
    assert drift[0].status == ProjectSyncStatus.DRIFT
    assert "mismatched .agents/skills/project-tool/SKILL.md" in drift[0].detail


def test_project_skill_removed_from_source_cleans_stale_outputs(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    write_json,
) -> None:
    project_root = tmp_path / "service-api"
    project_root.mkdir()
    core = CoreRepository(core_root)
    services = [_codex_service(tmp_path / ".codex")]
    _register_project(core, project_root, write_json)
    _write_project_skill(core)

    create_plan = SyncPlanner(core=core, app_services=services).build()
    applied, failed, failures = SyncExecutor(core=core).execute(create_plan)
    assert applied > 0
    assert failed == 0
    assert failures == []

    target = project_root / ".agents" / "skills" / "project-tool" / "SKILL.md"
    assert target.exists()

    shutil.rmtree(core.root / "projects" / "service-api" / "skills" / "project-tool")
    stale = StatusService().build_project_status(core, services)
    assert stale[0].status == ProjectSyncStatus.DRIFT
    assert "stale .agents/skills/project-tool/SKILL.md" in stale[0].detail

    cleanup_plan = SyncPlanner(core=core, app_services=services).build()
    assert any(action.path == target for action in cleanup_plan.actions)
    applied, failed, failures = SyncExecutor(core=core).execute(cleanup_plan)
    assert applied > 0
    assert failed == 0
    assert failures == []
    assert not target.exists()


def test_project_status_cli_renders_project_section(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    write_json,
    cli_runner,
    enable_app,
) -> None:
    project_root = tmp_path / "service-api"
    project_root.mkdir()
    core = CoreRepository(core_root)
    _register_project(core, project_root, write_json)
    _write_project_skill(core)
    enable_app("codex")

    rows = StatusService().build_project_status(
        core, [_codex_service(tmp_path / ".codex")]
    )
    assert rows[0].detail == "missing .agents/skills/project-tool/SKILL.md"

    result = cli_runner.invoke(cli, ["status"])

    assert result.exit_code == 0
    assert "project sync" in result.output
    assert "service-api" in result.output


def test_project_status_drift_suggests_project_recovery(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    write_json,
    cli_runner,
    enable_app,
) -> None:
    project_root = tmp_path / "service-api"
    project_root.mkdir()
    core = CoreRepository(core_root)
    _register_project(core, project_root, write_json)
    _write_project_skill(core)
    enable_app("codex")

    apply_result = cli_runner.invoke(cli, ["apply", "-a", "codex"])
    assert apply_result.exit_code == 0

    target = project_root / ".agents" / "skills" / "project-tool" / "SKILL.md"
    target.write_text("manual edit\n", encoding="utf-8")

    result = cli_runner.invoke(cli, ["status", "-a", "codex"])

    assert result.exit_code == 0
    assert "project sync" in result.output
    assert "drift" in result.output
    assert "code-agnostic plan -a codex" in result.output
    assert "code-agnostic apply -a codex" in result.output
    assert "code-agnostic restore --project service-api" in result.output
