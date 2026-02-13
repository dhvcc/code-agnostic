import os
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from code_agnostic.apps.app_id import AppId
from code_agnostic.apps.common.models import MCPServerDTO
from code_agnostic.apps.core.repository import CoreRepository
from code_agnostic.apps.common.framework import RegisteredAppConfigService
from code_agnostic.apps.common.interfaces.mapper import IAppMCPMapper
from code_agnostic.apps.common.interfaces.repositories import (
    IAppConfigRepository,
    ISourceRepository,
)
from code_agnostic.apps.opencode.config_repository import OpenCodeConfigRepository
from code_agnostic.apps.opencode.mapper import OpenCodeMCPMapper
from code_agnostic.apps.opencode.schema_repository import OpenCodeSchemaRepository
from code_agnostic.errors import InvalidConfigSchemaError
from code_agnostic.models import Action, ActionKind, ActionStatus, SyncPlan


def _schema_error_message(error: Any) -> str:
    path = ".".join([str(part) for part in error.path])
    return f"{error.message} at {path}" if path else str(error.message)


def validate_opencode_config(
    payload: Any, config_path: Path, validator: Draft202012Validator
) -> None:
    if not isinstance(payload, dict):
        raise InvalidConfigSchemaError(config_path, "must be a JSON object")
    error = next(iter(validator.iter_errors(payload)), None)
    if error is not None:
        raise InvalidConfigSchemaError(config_path, _schema_error_message(error))


class OpenCodeConfigService(RegisteredAppConfigService):
    APP_ID = AppId.OPENCODE

    def __init__(
        self,
        repository: OpenCodeConfigRepository,
        mapper: IAppMCPMapper,
        schema_repository: OpenCodeSchemaRepository,
        core_repository: CoreRepository,
    ) -> None:
        self._repository = repository
        self._mapper = mapper
        self._schema_repository = schema_repository
        self._core_repository = core_repository
        self._validator = Draft202012Validator(self._schema_repository.load_schema())

    @classmethod
    def create_default(cls) -> "OpenCodeConfigService":
        return cls(
            repository=OpenCodeConfigRepository(),
            mapper=OpenCodeMCPMapper(),
            schema_repository=OpenCodeSchemaRepository(),
            core_repository=CoreRepository(),
        )

    @property
    def app_id(self) -> AppId:
        return AppId.OPENCODE

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
        validate_opencode_config(
            payload=payload,
            config_path=self.repository.config_path,
            validator=self._validator,
        )

    def build_action_payload(self, payload: dict[str, Any]) -> Any:
        return payload

    def build_action(self, common_servers: dict[str, MCPServerDTO]):
        if not isinstance(self.repository, OpenCodeConfigRepository):
            raise InvalidConfigSchemaError(
                self.repository.config_path, "invalid opencode repository"
            )

        existing = self.repository.load_config()
        if existing or self.repository.config_path.exists():
            self.validate_config(existing)

        opencode_base = self._core_repository.load_opencode_base()
        desired_mcp = self.mapper.from_common(common_servers)
        merged = self.repository.merge_config(existing, opencode_base, desired_mcp)
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

        desired_skill_links: list[Path] = []
        for source in source_repository.list_skill_sources():
            target = self.repository.skills_dir / source.name
            desired_skill_links.append(target)
            action = self._plan_symlink(target, source, scope="app:opencode:skills")
            actions.append(action)
            if action.status == ActionStatus.CONFLICT:
                skipped.append(f"Skill link skipped (conflict): {action.path}")

        desired_agent_links: list[Path] = []
        for source in source_repository.list_agent_sources():
            target = self.repository.agents_dir / source.name
            desired_agent_links.append(target)
            action = self._plan_symlink(target, source, scope="app:opencode:agents")
            actions.append(action)
            if action.status == ActionStatus.CONFLICT:
                skipped.append(f"Agent link skipped (conflict): {action.path}")

        state = source_repository.load_state()
        managed_links = state.get("managed_links", {})
        if not isinstance(managed_links, dict):
            managed_links = {}

        actions.extend(
            self._plan_stale_group(
                old_links=self._state_links(managed_links, "app:opencode:skills"),
                desired_links=desired_skill_links,
                remove_detail="remove stale managed skill symlink",
                conflict_detail="stale managed path is not a symlink",
                noop_detail="stale symlink already absent",
                scope="app:opencode:skills",
                skipped=skipped,
                skipped_message="Stale link cleanup skipped (not symlink): {path}",
            )
        )
        actions.extend(
            self._plan_stale_group(
                old_links=self._state_links(managed_links, "app:opencode:agents"),
                desired_links=desired_agent_links,
                remove_detail="remove stale managed agent symlink",
                conflict_detail="stale managed path is not a symlink",
                noop_detail="stale symlink already absent",
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

    @staticmethod
    def _plan_symlink(target: Path, source: Path, scope: str) -> Action:
        desired = str(source.resolve())
        if target.exists() or target.is_symlink():
            if target.is_symlink():
                current = os.path.realpath(target)
                if current == desired:
                    return Action(
                        ActionKind.SYMLINK,
                        target,
                        ActionStatus.NOOP,
                        "already linked",
                        source=source,
                        app=AppId.OPENCODE.value,
                        scope=scope,
                    )
                return Action(
                    ActionKind.SYMLINK,
                    target,
                    ActionStatus.FIX,
                    "symlink points elsewhere",
                    source=source,
                    app=AppId.OPENCODE.value,
                    scope=scope,
                )
            return Action(
                ActionKind.SYMLINK,
                target,
                ActionStatus.CONFLICT,
                "non-symlink path exists",
                source=source,
                app=AppId.OPENCODE.value,
                scope=scope,
            )
        return Action(
            ActionKind.SYMLINK,
            target,
            ActionStatus.CREATE,
            "create symlink",
            source=source,
            app=AppId.OPENCODE.value,
            scope=scope,
        )

    @staticmethod
    def _state_links(managed_links: dict[str, Any], scope: str) -> list[Path]:
        raw = managed_links.get(scope, [])
        if not isinstance(raw, list):
            return []
        return [Path(item) for item in raw if isinstance(item, str)]

    @staticmethod
    def _plan_stale_group(
        old_links: list[Path],
        desired_links: list[Path],
        remove_detail: str,
        conflict_detail: str,
        noop_detail: str,
        scope: str,
        skipped: list[str],
        skipped_message: str,
    ) -> list[Action]:
        desired = {str(path) for path in desired_links}
        actions: list[Action] = []
        for old in old_links:
            if str(old) in desired:
                continue
            if old.is_symlink():
                actions.append(
                    Action(
                        ActionKind.REMOVE_SYMLINK,
                        old,
                        ActionStatus.REMOVE,
                        remove_detail,
                        app=AppId.OPENCODE.value,
                        scope=scope,
                    )
                )
            elif old.exists():
                actions.append(
                    Action(
                        ActionKind.REMOVE_SYMLINK,
                        old,
                        ActionStatus.CONFLICT,
                        conflict_detail,
                        app=AppId.OPENCODE.value,
                        scope=scope,
                    )
                )
                skipped.append(skipped_message.format(path=old))
            else:
                actions.append(
                    Action(
                        ActionKind.REMOVE_SYMLINK,
                        old,
                        ActionStatus.NOOP,
                        noop_detail,
                        app=AppId.OPENCODE.value,
                        scope=scope,
                    )
                )
        return actions
