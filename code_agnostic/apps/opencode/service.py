from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from code_agnostic.apps.app_id import AppId, app_label
from code_agnostic.apps.common.models import MCPServerDTO
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
from code_agnostic.apps.common.symlink_planning import (
    load_state_links,
    plan_resource_symlinks,
    plan_stale_group,
)
from code_agnostic.core.repository import CoreRepository
from code_agnostic.apps.opencode.config_repository import OpenCodeConfigRepository
from code_agnostic.apps.opencode.mapper import OpenCodeMCPMapper
from code_agnostic.apps.opencode.schema_repository import OpenCodeSchemaRepository
from code_agnostic.errors import InvalidConfigSchemaError
from code_agnostic.models import Action, ActionKind, ActionStatus, SyncPlan


class OpenCodeConfigService(RegisteredAppConfigService):
    APP_ID = AppId.OPENCODE
    APP_LABEL = app_label(APP_ID)

    def __init__(
        self,
        repository: OpenCodeConfigRepository,
        mapper: IAppMCPMapper,
        schema_repository: ISchemaRepository,
        base_config_path: Path | None = None,
    ) -> None:
        self._repository = repository
        self._opencode_repo = repository
        self._mapper = mapper
        self._schema_repository = schema_repository
        self._base_config_path = base_config_path
        self._validator = Draft202012Validator(self._schema_repository.load_schema())

    @classmethod
    def create_default(cls, root: Path | None = None) -> "OpenCodeConfigService":
        if root is not None:
            return cls(
                repository=OpenCodeConfigRepository(root=root),
                mapper=OpenCodeMCPMapper(),
                schema_repository=OpenCodeSchemaRepository(),
                base_config_path=None,
            )
        core = CoreRepository()
        return cls(
            repository=OpenCodeConfigRepository(),
            mapper=OpenCodeMCPMapper(),
            schema_repository=OpenCodeSchemaRepository(),
            base_config_path=core.opencode_base_path,
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
        if not isinstance(payload, dict):
            raise InvalidConfigSchemaError(
                self.repository.config_path, "must be a JSON object"
            )
        error = next(iter(self._validator.iter_errors(payload)), None)
        if error is not None:
            raise InvalidConfigSchemaError(
                self.repository.config_path, format_schema_error(error)
            )

    def build_action_payload(self, payload: dict[str, Any]) -> Any:
        return payload

    def _load_base_config(self) -> dict[str, Any]:
        from code_agnostic.errors import MissingConfigFileError, InvalidJsonFormatError
        from code_agnostic.utils import read_json_safe

        if not self._base_config_path.exists():
            raise MissingConfigFileError(self._base_config_path)
        payload, error = read_json_safe(self._base_config_path)
        if error is not None:
            raise InvalidJsonFormatError(self._base_config_path, error)
        if not isinstance(payload, dict):
            raise InvalidConfigSchemaError(
                self._base_config_path, "must be a JSON object"
            )
        return payload

    def build_action(self, common_servers: dict[str, MCPServerDTO]) -> Action:
        existing = self._opencode_repo.load_config()
        if existing or self._opencode_repo.config_path.exists():
            self.validate_config(existing)

        desired_mcp = self.mapper.from_common(common_servers)

        if self._base_config_path is not None:
            opencode_base = self._load_base_config()
            merged = self._opencode_repo.merge_config(
                existing, opencode_base, desired_mcp
            )
        else:
            merged = dict(existing)
            self.set_mcp_payload(merged, desired_mcp)

        self.validate_config(merged)

        return Action(
            kind=self.action_kind,
            path=self.repository.config_path,
            status=self.derive_status(existing, merged),
            detail=f"sync {self.app_id.value} config from common mcp base",
            payload=self.build_action_payload(merged),
            app=self.app_id.value,
        )

    def build_plan(
        self,
        common_servers: dict[str, MCPServerDTO],
        source_repository: ISourceRepository,
    ) -> SyncPlan:
        config_action = self.build_action(common_servers)
        actions: list[Action] = [config_action]
        skipped: list[str] = []

        skill_actions, desired_skill_links, skill_skipped = plan_resource_symlinks(
            source_repository.list_skill_sources(),
            self._opencode_repo.skills_dir,
            scope="app:opencode:skills",
            app=AppId.OPENCODE.value,
        )
        actions.extend(skill_actions)
        skipped.extend(skill_skipped)

        agent_actions, desired_agent_links, agent_skipped = plan_resource_symlinks(
            source_repository.list_agent_sources(),
            self._opencode_repo.agents_dir,
            scope="app:opencode:agents",
            app=AppId.OPENCODE.value,
        )
        actions.extend(agent_actions)
        skipped.extend(agent_skipped)

        state = source_repository.load_state()
        managed_links = state.get("managed_links", {})
        if not isinstance(managed_links, dict):
            managed_links = {}

        actions.extend(
            plan_stale_group(
                old_links=load_state_links(managed_links, "app:opencode:skills"),
                desired_links=desired_skill_links,
                remove_detail="remove stale managed skill symlink",
                conflict_detail="stale managed path is not a symlink",
                noop_detail="stale symlink already absent",
                app=AppId.OPENCODE.value,
                scope="app:opencode:skills",
                skipped=skipped,
                skipped_message="Stale link cleanup skipped (not symlink): {path}",
            )
        )
        actions.extend(
            plan_stale_group(
                old_links=load_state_links(managed_links, "app:opencode:agents"),
                desired_links=desired_agent_links,
                remove_detail="remove stale managed agent symlink",
                conflict_detail="stale managed path is not a symlink",
                noop_detail="stale symlink already absent",
                app=AppId.OPENCODE.value,
                scope="app:opencode:agents",
                skipped=skipped,
                skipped_message="Stale link cleanup skipped (not symlink): {path}",
            )
        )

        return SyncPlan(actions=actions, errors=[], skipped=skipped)

    def set_mcp_payload(
        self, merged: dict[str, Any], desired_mcp: dict[str, Any]
    ) -> None:
        merged["mcp"] = desired_mcp

    def derive_status(
        self, existing: dict[str, Any], merged: dict[str, Any]
    ) -> ActionStatus:
        if not self.repository.config_path.exists():
            return ActionStatus.CREATE
        if existing == merged:
            return ActionStatus.NOOP
        return ActionStatus.UPDATE
