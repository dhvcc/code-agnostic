from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from code_agnostic.apps.app_id import AppId, app_label
from code_agnostic.apps.common.framework import (
    RegisteredAppConfigService,
    format_schema_error,
)
from code_agnostic.apps.common.interfaces.mapper import IAppMCPMapper
from code_agnostic.apps.common.interfaces.repositories import (
    IAppConfigRepository,
    ISchemaRepository,
    ISourceRepository,
)
from code_agnostic.apps.common.models import MCPServerDTO
from code_agnostic.apps.common.symlink_planning import plan_stale_group, plan_symlink
from code_agnostic.apps.cursor.config_repository import CursorConfigRepository
from code_agnostic.apps.cursor.mapper import CursorMCPMapper
from code_agnostic.apps.cursor.schema_repository import CursorSchemaRepository
from code_agnostic.errors import InvalidConfigSchemaError
from code_agnostic.models import Action, ActionKind, ActionStatus, SyncPlan


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
    def create_default(cls) -> "CursorConfigService":
        return cls(
            repository=CursorConfigRepository(),
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

        desired_skill_links: list[Path] = []
        for source in source_repository.list_skill_sources():
            target = self._cursor_repo.skills_dir / source.name
            desired_skill_links.append(target)
            action = plan_symlink(
                target, source, scope="app:cursor:skills", app=AppId.CURSOR.value
            )
            actions.append(action)
            if action.status == ActionStatus.CONFLICT:
                skipped.append(f"Skill link skipped (conflict): {action.path}")

        desired_agent_links: list[Path] = []
        for source in source_repository.list_agent_sources():
            target = self._cursor_repo.agents_dir / source.name
            desired_agent_links.append(target)
            action = plan_symlink(
                target, source, scope="app:cursor:agents", app=AppId.CURSOR.value
            )
            actions.append(action)
            if action.status == ActionStatus.CONFLICT:
                skipped.append(f"Agent link skipped (conflict): {action.path}")

        state = source_repository.load_state()
        managed_links = state.get("managed_links", {})
        if not isinstance(managed_links, dict):
            managed_links = {}

        actions.extend(
            plan_stale_group(
                old_links=self._state_links(managed_links, "app:cursor:skills"),
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
            plan_stale_group(
                old_links=self._state_links(managed_links, "app:cursor:agents"),
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

        return SyncPlan(actions=actions, errors=[], skipped=skipped)

    @staticmethod
    def _state_links(managed_links: dict[str, Any], scope: str) -> list[Path]:
        raw = managed_links.get(scope, [])
        if not isinstance(raw, list):
            return []
        return [Path(item) for item in raw if isinstance(item, str)]
