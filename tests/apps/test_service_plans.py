from collections.abc import Callable
from pathlib import Path

import pytest

from code_agnostic.apps.app_id import AppId, app_scope
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
from code_agnostic.models import ActionStatus


ServiceFactory = Callable[[CoreRepository, Path], object]


def _build_opencode_service(core: CoreRepository, root: Path) -> OpenCodeConfigService:
    return OpenCodeConfigService(
        repository=OpenCodeConfigRepository(root=root),
        mapper=OpenCodeMCPMapper(),
        schema_repository=OpenCodeSchemaRepository(),
        base_config_path=core.opencode_base_path,
    )


def _build_cursor_service(core: CoreRepository, root: Path) -> CursorConfigService:
    return CursorConfigService(
        repository=CursorConfigRepository(root=root),
        mapper=CursorMCPMapper(),
        schema_repository=CursorSchemaRepository(),
    )


def _build_codex_service(core: CoreRepository, root: Path) -> CodexConfigService:
    return CodexConfigService(
        repository=CodexConfigRepository(root=root),
        mapper=CodexMCPMapper(),
        schema_repository=CodexSchemaRepository(),
    )


@pytest.mark.parametrize(
    ("app_id", "service_factory", "target_root_name"),
    [
        (AppId.OPENCODE, _build_opencode_service, "opencode"),
        (AppId.CURSOR, _build_cursor_service, ".cursor"),
        (AppId.CODEX, _build_codex_service, ".codex"),
    ],
)
def test_app_services_build_skill_and_agent_scopes(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    app_id: AppId,
    service_factory: ServiceFactory,
    target_root_name: str,
) -> None:
    core = CoreRepository(core_root)
    (core.skills_dir / "review").mkdir(parents=True)
    (core.skills_dir / "review" / "SKILL.md").write_text(
        "Review code.\n", encoding="utf-8"
    )
    core.agents_dir.mkdir(parents=True)
    (core.agents_dir / "planner.md").write_text(
        "You are a planner.\n", encoding="utf-8"
    )

    service = service_factory(core, tmp_path / target_root_name)
    plan = service.build_plan({}, core)

    assert plan.errors == []
    assert any(action.scope == app_scope(app_id, "skills") for action in plan.actions)
    assert any(action.scope == app_scope(app_id, "agents") for action in plan.actions)


@pytest.mark.parametrize(
    ("app_id", "service_factory", "target_root_name", "expected_status"),
    [
        (AppId.OPENCODE, _build_opencode_service, "opencode", ActionStatus.CONFLICT),
        (AppId.CURSOR, _build_cursor_service, ".cursor", ActionStatus.CREATE),
        (AppId.CODEX, _build_codex_service, ".codex", ActionStatus.CONFLICT),
    ],
)
def test_agent_planning_only_uses_managed_symlink_ancestors_where_supported(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    app_id: AppId,
    service_factory: ServiceFactory,
    target_root_name: str,
    expected_status: ActionStatus,
) -> None:
    core = CoreRepository(core_root)
    core.agents_dir.mkdir(parents=True)
    (core.agents_dir / "planner.md").write_text(
        "You are a planner.\n", encoding="utf-8"
    )

    service = service_factory(core, tmp_path / target_root_name)
    legacy_agents_dir = tmp_path / f"legacy-{app_id.value}-agents"
    legacy_agents_dir.mkdir(parents=True)
    service.repository.root.mkdir(parents=True, exist_ok=True)
    service.repository.agents_dir.symlink_to(legacy_agents_dir)

    core.save_state(
        {
            "managed_links": {
                app_scope(app_id, "agents"): [str(service.repository.agents_dir)]
            },
            "managed_paths": {},
        }
    )

    plan = service.build_plan({}, core)
    agent_actions = [
        action for action in plan.actions if action.scope == app_scope(app_id, "agents")
    ]

    assert len(agent_actions) == 1
    assert agent_actions[0].status == expected_status
