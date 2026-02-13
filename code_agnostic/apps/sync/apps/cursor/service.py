from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from code_agnostic.apps.sync.base import IAppConfigRepository, IAppMCPMapper
from code_agnostic.apps.sync.framework import (
    RegisteredAppConfigService,
    format_schema_error,
    load_json_schema,
)
from code_agnostic.apps.sync.apps.cursor.mapper import CursorMCPMapper
from code_agnostic.apps.sync.apps.cursor.repository import CursorRepository
from code_agnostic.errors import InvalidConfigSchemaError
from code_agnostic.models import ActionKind, ActionStatus, AppId


class CursorConfigService(RegisteredAppConfigService):
    APP_ID = AppId.CURSOR

    def __init__(self, repository: CursorRepository, mapper: IAppMCPMapper) -> None:
        self._repository = repository
        self._mapper = mapper
        schema_path = Path(__file__).resolve().parent / "schema.json"
        self._validator = Draft202012Validator(load_json_schema(schema_path))

    @classmethod
    def create_default(cls) -> "CursorConfigService":
        return cls(repository=CursorRepository(), mapper=CursorMCPMapper())

    @property
    def app_id(self) -> AppId:
        return AppId.CURSOR

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
