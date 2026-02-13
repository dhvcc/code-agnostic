from typing import Any

from code_agnostic.apps.sync.base import IAppConfigRepository, IAppMCPMapper
from code_agnostic.apps.sync.framework import RegisteredAppConfigService
from code_agnostic.apps.sync.apps.opencode.mapper import OpenCodeMCPMapper
from code_agnostic.apps.sync.apps.opencode.repository import OpenCodeRepository
from code_agnostic.models import ActionKind, ActionStatus, AppId


class OpenCodeConfigService(RegisteredAppConfigService):
    APP_ID = AppId.OPENCODE

    def __init__(self, repository: IAppConfigRepository, mapper: IAppMCPMapper) -> None:
        self._repository = repository
        self._mapper = mapper

    @classmethod
    def create_default(cls) -> "OpenCodeConfigService":
        return cls(repository=OpenCodeRepository(), mapper=OpenCodeMCPMapper())

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
        if not isinstance(payload, dict):
            raise ValueError("OpenCode config must be an object")

    def build_action_payload(self, payload: dict[str, Any]) -> Any:
        return payload

    def set_mcp_payload(
        self, merged: dict[str, Any], desired_mcp: dict[str, Any]
    ) -> None:
        merged["mcp"] = desired_mcp

    def derive_status(
        self, existing: dict[str, Any], merged: dict[str, Any]
    ) -> ActionStatus:
        existing_mcp = (
            existing.get("mcp") if isinstance(existing.get("mcp"), dict) else {}
        )
        desired_mcp = merged.get("mcp") if isinstance(merged.get("mcp"), dict) else {}
        if not self.repository.config_path.exists():
            return ActionStatus.CREATE
        if existing_mcp == desired_mcp:
            return ActionStatus.NOOP
        return ActionStatus.UPDATE
