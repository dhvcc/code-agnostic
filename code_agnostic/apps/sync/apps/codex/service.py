from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

from code_agnostic.apps.sync.base import IAppConfigRepository, IAppMCPMapper
from code_agnostic.apps.sync.framework import (
    IAppConfigService,
    format_schema_error,
    load_json_schema,
)
from code_agnostic.apps.sync.apps.codex.repository import CodexRepository
from code_agnostic.errors import InvalidConfigSchemaError
from code_agnostic.models import ActionKind, ActionStatus, AppId


class CodexConfigService(IAppConfigService):
    def __init__(self, repository: CodexRepository, mapper: IAppMCPMapper) -> None:
        self._repository = repository
        self._mapper = mapper
        schema_path = Path(__file__).resolve().parent / "schema.json"
        self._validator = Draft7Validator(load_json_schema(schema_path))

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
        if not isinstance(self.repository, CodexRepository):
            raise InvalidConfigSchemaError(
                self.repository.config_path, "invalid codex repository"
            )
        return self.repository.serialize_config(payload)

    def set_mcp_payload(
        self, merged: dict[str, Any], desired_mcp: dict[str, Any]
    ) -> None:
        merged["mcp_servers"] = desired_mcp

    def derive_status(
        self, existing: dict[str, Any], merged: dict[str, Any]
    ) -> ActionStatus:
        if not isinstance(self.repository, CodexRepository):
            return ActionStatus.UPDATE
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
