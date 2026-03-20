from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from code_agnostic.apps.app_id import AppId, app_label
from code_agnostic.apps.common.framework import (
    RegisteredAppConfigService,
    format_schema_error,
)
from code_agnostic.apps.common.compiled_planning import plan_compiled_text_action
from code_agnostic.apps.common.interfaces.mapper import IAppMCPMapper
from code_agnostic.apps.common.interfaces.repositories import (
    IAppConfigRepository,
    ISchemaRepository,
    ISourceRepository,
)
from code_agnostic.apps.common.models import MCPServerDTO
from code_agnostic.apps.common.symlink_planning import (
    load_state_links,
    load_state_paths,
    plan_resource_symlinks,
    plan_stale_files_group,
    plan_stale_group,
)
from code_agnostic.agents.compilers import CursorAgentCompiler
from code_agnostic.agents.parser import parse_agent
from code_agnostic.apps.cursor.config_repository import CursorConfigRepository
from code_agnostic.apps.cursor.mapper import CursorMCPMapper
from code_agnostic.apps.cursor.schema_repository import CursorSchemaRepository
from code_agnostic.errors import InvalidConfigSchemaError
from code_agnostic.models import Action, ActionKind, ActionStatus, SyncPlan
from code_agnostic.skills.compilers import CursorSkillCompiler
from code_agnostic.skills.parser import parse_skill


class CursorConfigService(RegisteredAppConfigService):
    APP_ID = AppId.CURSOR
    APP_LABEL = app_label(APP_ID)

    def __init__(
        self,
        repository: CursorConfigRepository,
        mapper: IAppMCPMapper,
        schema_repository: ISchemaRepository,
    ) -> None:
        self._repository = repository
        self._cursor_repo = repository
        self._mapper = mapper
        self._schema_repository = schema_repository
        self._validator = Draft202012Validator(self._schema_repository.load_schema())

    @classmethod
    def create_default(cls, root: Path | None = None) -> "CursorConfigService":
        return cls(
            repository=CursorConfigRepository(root=root),
            mapper=CursorMCPMapper(),
            schema_repository=CursorSchemaRepository(),
        )

    @property
    def app_id(self) -> AppId:
        return self.APP_ID

    @property
    def action_kind(self) -> ActionKind:
        return ActionKind.WRITE_JSON

    @property
    def repository(self) -> IAppConfigRepository:
        return self._repository

    @property
    def mapper(self) -> IAppMCPMapper:
        return self._mapper

    def validate_config(self, payload: Any) -> None:
        if payload == {}:
            return
        error = next(iter(self._validator.iter_errors(payload)), None)
        if error is not None:
            raise InvalidConfigSchemaError(
                self.repository.config_path, format_schema_error(error)
            )

    def build_action_payload(self, payload: dict[str, Any]) -> Any:
        return payload

    def set_mcp_payload(
        self, merged: dict[str, Any], desired_mcp: dict[str, Any]
    ) -> None:
        merged["mcpServers"] = desired_mcp

    def derive_status(
        self, existing: dict[str, Any], merged: dict[str, Any]
    ) -> ActionStatus:
        existing_mcp = (
            existing.get("mcpServers")
            if isinstance(existing.get("mcpServers"), dict)
            else {}
        )
        desired_mcp = (
            merged.get("mcpServers")
            if isinstance(merged.get("mcpServers"), dict)
            else {}
        )
        if not self.repository.config_path.exists():
            return ActionStatus.CREATE
        if existing_mcp == desired_mcp:
            return ActionStatus.NOOP
        return ActionStatus.UPDATE

    def build_plan(
        self,
        common_servers: dict[str, MCPServerDTO],
        source_repository: ISourceRepository,
    ) -> SyncPlan:
        config_action = self.build_action(common_servers)
        actions: list[Action] = [config_action]
        skipped: list[str] = []
        state = source_repository.load_state()
        managed_links = state.get("managed_links", {})
        if not isinstance(managed_links, dict):
            managed_links = {}
        managed_paths = state.get("managed_paths", {})
        if not isinstance(managed_paths, dict):
            managed_paths = {}

        skill_sources = source_repository.list_skill_sources()
        legacy_skills = [
            source for source in skill_sources if (source / "SKILL.md").exists()
        ]
        bundle_skills = [
            source for source in skill_sources if (source / "meta.yaml").exists()
        ]

        skill_actions, desired_skill_links, skill_skipped = plan_resource_symlinks(
            legacy_skills,
            self._cursor_repo.skills_dir,
            scope="app:cursor:skills",
            app=AppId.CURSOR.value,
        )
        actions.extend(skill_actions)
        skipped.extend(skill_skipped)

        compiled_skill_actions, desired_skill_paths, compiled_skill_skipped = (
            self.plan_skill_actions(
                bundle_skills,
                self._cursor_repo.skills_dir,
                scope="app:cursor:skills",
                app=AppId.CURSOR.value,
                managed_paths=load_state_paths(managed_paths, "app:cursor:skills"),
            )
        )
        actions.extend(compiled_skill_actions)
        skipped.extend(compiled_skill_skipped)

        agent_sources = source_repository.list_agent_sources()
        legacy_agents = [source for source in agent_sources if source.is_file()]
        bundle_agents = [source for source in agent_sources if source.is_dir()]

        agent_actions, desired_agent_links, agent_skipped = plan_resource_symlinks(
            legacy_agents,
            self._cursor_repo.agents_dir,
            scope="app:cursor:agents",
            app=AppId.CURSOR.value,
        )
        actions.extend(agent_actions)
        skipped.extend(agent_skipped)

        compiled_agent_actions, desired_agent_paths, compiled_agent_skipped = (
            self.plan_agent_actions(
                bundle_agents,
                self._cursor_repo.agents_dir,
                scope="app:cursor:agents",
                app=AppId.CURSOR.value,
                managed_paths=load_state_paths(managed_paths, "app:cursor:agents"),
            )
        )
        actions.extend(compiled_agent_actions)
        skipped.extend(compiled_agent_skipped)

        actions.extend(
            plan_stale_group(
                old_links=load_state_links(managed_links, "app:cursor:skills"),
                desired_links=desired_skill_links,
                remove_detail="remove stale managed skill symlink",
                conflict_detail="stale managed path is not a symlink",
                noop_detail="stale symlink already absent",
                app=AppId.CURSOR.value,
                scope="app:cursor:skills",
                skipped=skipped,
                skipped_message="Stale link cleanup skipped (not symlink): {path}",
            )
        )
        actions.extend(
            plan_stale_files_group(
                old_paths=load_state_paths(managed_paths, "app:cursor:skills"),
                desired_paths=desired_skill_paths,
                remove_detail="remove stale managed skill file",
                conflict_detail="stale managed path is not a file",
                noop_detail="stale managed file already absent",
                app=AppId.CURSOR.value,
                scope="app:cursor:skills",
                skipped=skipped,
                skipped_message="Stale file cleanup skipped (not file): {path}",
            )
        )
        actions.extend(
            plan_stale_group(
                old_links=load_state_links(managed_links, "app:cursor:agents"),
                desired_links=desired_agent_links,
                remove_detail="remove stale managed agent symlink",
                conflict_detail="stale managed path is not a symlink",
                noop_detail="stale symlink already absent",
                app=AppId.CURSOR.value,
                scope="app:cursor:agents",
                skipped=skipped,
                skipped_message="Stale link cleanup skipped (not symlink): {path}",
            )
        )
        actions.extend(
            plan_stale_files_group(
                old_paths=load_state_paths(managed_paths, "app:cursor:agents"),
                desired_paths=desired_agent_paths,
                remove_detail="remove stale managed agent file",
                conflict_detail="stale managed path is not a file",
                noop_detail="stale managed file already absent",
                app=AppId.CURSOR.value,
                scope="app:cursor:agents",
                skipped=skipped,
                skipped_message="Stale file cleanup skipped (not file): {path}",
            )
        )

        return SyncPlan(actions=actions, errors=[], skipped=skipped)

    def plan_skill_actions(
        self,
        sources: list[Path],
        target_dir: Path,
        scope: str,
        app: str,
        managed_paths: list[Path],
    ) -> tuple[list[Action], list[Path], list[str]]:
        compiler = CursorSkillCompiler()
        managed_path_set = {path.resolve(strict=False) for path in managed_paths}
        actions: list[Action] = []
        desired_paths: list[Path] = []
        skipped: list[str] = []

        for source in sources:
            skill = parse_skill(source)
            target = target_dir / source.name / "SKILL.md"
            desired_paths.append(target)
            payload = compiler.compile(skill)
            action = plan_compiled_text_action(
                target=target,
                payload=payload,
                managed_paths=managed_path_set,
                scope=scope,
                app=app,
                create_detail="create compiled cursor skill",
                noop_detail="compiled cursor skill already up to date",
                update_detail="update compiled cursor skill",
            )
            actions.append(action)
            if action.status == ActionStatus.CONFLICT:
                skipped.append(f"Cursor skill sync skipped (conflict): {target}")

        return actions, desired_paths, skipped

    def plan_agent_actions(
        self,
        sources: list[Path],
        target_dir: Path,
        scope: str,
        app: str,
        managed_paths: list[Path],
    ) -> tuple[list[Action], list[Path], list[str]]:
        compiler = CursorAgentCompiler()
        managed_path_set = {path.resolve(strict=False) for path in managed_paths}
        actions: list[Action] = []
        desired_paths: list[Path] = []
        skipped: list[str] = []

        for source in sources:
            agent = parse_agent(source)
            target = target_dir / f"{source.name}.md"
            desired_paths.append(target)
            payload = compiler.compile(agent)
            action = plan_compiled_text_action(
                target=target,
                payload=payload,
                managed_paths=managed_path_set,
                scope=scope,
                app=app,
                create_detail="create compiled cursor agent",
                noop_detail="compiled cursor agent already up to date",
                update_detail="update compiled cursor agent",
            )
            actions.append(action)
            if action.status == ActionStatus.CONFLICT:
                skipped.append(f"Cursor agent sync skipped (conflict): {target}")

        return actions, desired_paths, skipped
