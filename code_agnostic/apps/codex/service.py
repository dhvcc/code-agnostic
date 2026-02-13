from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

from code_agnostic.apps.app_id import AppId
from code_agnostic.apps.common.framework import (
    RegisteredAppConfigService,
    format_schema_error,
)
from code_agnostic.apps.codex.config_repository import CodexConfigRepository
from code_agnostic.apps.codex.mapper import CodexMCPMapper
from code_agnostic.apps.codex.schema_repository import CodexSchemaRepository
from code_agnostic.apps.common.interfaces.mapper import IAppMCPMapper
from code_agnostic.apps.common.interfaces.repositories import (
    IAppConfigRepository,
    ISchemaRepository,
    ISourceRepository,
)
from code_agnostic.apps.common.models import MCPServerDTO
from code_agnostic.apps.common.symlink_planning import plan_stale_group, plan_symlink
from code_agnostic.errors import InvalidConfigSchemaError
from code_agnostic.models import Action, ActionKind, ActionStatus, SyncPlan


class CodexConfigService(RegisteredAppConfigService):
    APP_ID = AppId.CODEX

    def __init__(
        self,
        repository: CodexConfigRepository,
        mapper: IAppMCPMapper,
        schema_repository: ISchemaRepository,
    ) -> None:
        self._repository = repository
        self._codex_repo = repository
        self._mapper = mapper
        self._schema_repository = schema_repository
        self._validator = Draft7Validator(self._schema_repository.load_schema())

    @classmethod
    def create_default(cls) -> "CodexConfigService":
        return cls(
            repository=CodexConfigRepository(),
            mapper=CodexMCPMapper(),
            schema_repository=CodexSchemaRepository(),
        )

    @property
    def app_id(self) -> AppId:
        return AppId.CODEX

    @property
    def action_kind(self) -> ActionKind:
        return ActionKind.WRITE_TEXT

    @property
    def repository(self) -> IAppConfigRepository:
        return self._repository

    @property
    def mapper(self) -> IAppMCPMapper:
        return self._mapper

    def validate_config(self, payload: Any) -> None:
        error = next(iter(self._validator.iter_errors(payload)), None)
        if error is not None:
            raise InvalidConfigSchemaError(
                self.repository.config_path, format_schema_error(error)
            )

    def build_action_payload(self, payload: dict[str, Any]) -> Any:
        return self.repository.serialize_config(payload)

    def set_mcp_payload(
        self, merged: dict[str, Any], desired_mcp: dict[str, Any]
    ) -> None:
        merged["mcp_servers"] = desired_mcp

    def derive_status(
        self, existing: dict[str, Any], merged: dict[str, Any]
    ) -> ActionStatus:
        rendered = self.repository.serialize_config(merged)
        existing_text = (
            self.repository.config_path.read_text(encoding="utf-8")
            if self.repository.config_path.exists()
            else ""
        )
        if not self.repository.config_path.exists():
            return ActionStatus.CREATE
        if existing_text == rendered:
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
            target = self._codex_repo.skills_dir / source.name
            desired_skill_links.append(target)
            action = plan_symlink(
                target, source, scope="app:codex:skills", app=AppId.CODEX.value
            )
            actions.append(action)
            if action.status == ActionStatus.CONFLICT:
                skipped.append(f"Skill link skipped (conflict): {action.path}")

        state = source_repository.load_state()
        managed_links = state.get("managed_links", {})
        if not isinstance(managed_links, dict):
            managed_links = {}

        actions.extend(
            plan_stale_group(
                old_links=self._state_links(managed_links, "app:codex:skills"),
                desired_links=desired_skill_links,
                remove_detail="remove stale managed skill symlink",
                conflict_detail="stale managed path is not a symlink",
                noop_detail="stale symlink already absent",
                app=AppId.CODEX.value,
                scope="app:codex:skills",
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
